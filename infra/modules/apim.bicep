// ============================================================================
// Azure API Management (Future Architecture)
// Public entry point (Consumption tier per D9 / PLATFORM-STANDARDS §3 + ADR-001)
// with Entra JWT validation, dealer-context header propagation, throttling,
// request logging, and AI Gateway policies. Backend protection is delivered by
// APIM policy + Managed Identity + Key Vault credential injection, not VNet.
// ============================================================================

param location string
param baseName string
param backendUrl string
param appInsightsInstrumentationKey string
param logAnalyticsWorkspaceId string

@description('OpenID configuration URL used by validate-jwt. Empty disables JWT enforcement.')
param jwtOpenIdConfigUrl string = ''

@description('Expected audience (Entra app / API GUID) for validate-jwt. Empty disables JWT enforcement.')
param jwtAudience string = ''

@description('Allowed CORS origins for the dealer API. Empty falls back to localhost dev origin.')
param allowedCorsOrigins array = []

resource apim 'Microsoft.ApiManagement/service@2023-09-01-preview' = {
  name: 'apim-${baseName}'
  location: location
  sku: {
    name: 'Consumption'
    capacity: 0
  }
  properties: {
    publisherEmail: 'admin@company-dealer-portal.com'
    publisherName: 'COMPANY Dealer Portal'
  }
}

resource apimLogger 'Microsoft.ApiManagement/service/loggers@2023-09-01-preview' = {
  parent: apim
  name: 'appinsights-logger'
  properties: {
    loggerType: 'applicationInsights'
    credentials: {
      instrumentationKey: appInsightsInstrumentationKey
    }
  }
}

resource diagnosticSettings 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
  name: 'apim-diagnostics'
  scope: apim
  properties: {
    workspaceId: logAnalyticsWorkspaceId
    logs: [
      {
        categoryGroup: 'allLogs'
        enabled: true
      }
    ]
    metrics: [
      {
        category: 'AllMetrics'
        enabled: true
      }
    ]
  }
}

// Backend pointing to FastAPI App Service
resource backend 'Microsoft.ApiManagement/service/backends@2023-09-01-preview' = {
  parent: apim
  name: 'fastapi-backend'
  properties: {
    url: backendUrl
    protocol: 'http'
    tls: {
      validateCertificateChain: true
      validateCertificateName: true
    }
  }
}

// API definition for Dealer Portal
resource dealerApi 'Microsoft.ApiManagement/service/apis@2023-09-01-preview' = {
  parent: apim
  name: 'company-dealer-api'
  properties: {
    displayName: 'COMPANY Dealer Portal API'
    path: 'dealer'
    protocols: ['https']
    subscriptionRequired: true
    serviceUrl: backendUrl
  }
}

// Chat operation
resource chatOperation 'Microsoft.ApiManagement/service/apis/operations@2023-09-01-preview' = {
  parent: dealerApi
  name: 'chat'
  properties: {
    displayName: 'Chat'
    method: 'POST'
    urlTemplate: '/api/chat'
  }
}

// Search operation
resource searchOperation 'Microsoft.ApiManagement/service/apis/operations@2023-09-01-preview' = {
  parent: dealerApi
  name: 'search'
  properties: {
    displayName: 'Search Documents'
    method: 'POST'
    urlTemplate: '/api/search'
  }
}

// Documents operation
resource documentsOperation 'Microsoft.ApiManagement/service/apis/operations@2023-09-01-preview' = {
  parent: dealerApi
  name: 'documents'
  properties: {
    displayName: 'List Documents'
    method: 'GET'
    urlTemplate: '/api/documents'
  }
}

// Rate limiting + identity policy at API level
//   - cors: scoped to allowedCorsOrigins (no wildcard with credentials)
//   - validate-jwt: Entra JWT validation (enabled when jwtAudience is set)
//   - dealer-context headers: X-Dealer-Code / X-User-Id / X-User-Roles from JWT
//     claims, propagated to the FastAPI backend for Tier-2 data scoping (07 §2/§7)
var corsOriginsXml = empty(allowedCorsOrigins)
  ? '<origin>http://localhost:5173</origin>'
  : join(map(allowedCorsOrigins, origin => '<origin>${trim(origin)}</origin>'), '\n        ')

var validateJwtXml = empty(jwtAudience)
  ? '<!-- validate-jwt disabled: set apimJwtAudience to enable enforcement -->'
  : '<validate-jwt header-name="Authorization" failed-validation-httpcode="401" failed-validation-error-message="Unauthorized">\n      <openid-config url="${jwtOpenIdConfigUrl}" />\n      <audiences>\n        <audience>${jwtAudience}</audience>\n      </audiences>\n    </validate-jwt>'

var dealerApiPolicyTemplate = '''
<policies>
  <inbound>
    <base />
    <cors allow-credentials="true">
      <allowed-origins>
        __CORS_ORIGINS__
      </allowed-origins>
      <allowed-methods>
        <method>GET</method>
        <method>POST</method>
        <method>OPTIONS</method>
      </allowed-methods>
      <allowed-headers>
        <header>*</header>
      </allowed-headers>
    </cors>
    __VALIDATE_JWT__
    <rate-limit-by-key calls="100" renewal-period="60" counter-key="@(context.Subscription?.Id ?? context.Request.IpAddress)" />
    <set-backend-service backend-id="fastapi-backend" />
    <set-header name="X-Caller-Identity" exists-action="override">
      <value>@(context.Request.Headers.GetValueOrDefault("Authorization","").Replace("Bearer ","").AsJwt()?.Subject)</value>
    </set-header>
    <set-header name="X-Dealer-Code" exists-action="override">
      <value>@{
        var jwt = context.Request.Headers.GetValueOrDefault("Authorization","").Replace("Bearer ","").AsJwt();
        return jwt?.Claims.GetValueOrDefault("dealer_code", new string[0]).FirstOrDefault() ?? "";
      }</value>
    </set-header>
    <set-header name="X-User-Id" exists-action="override">
      <value>@{
        var jwt = context.Request.Headers.GetValueOrDefault("Authorization","").Replace("Bearer ","").AsJwt();
        return jwt?.Claims.GetValueOrDefault("sub", new string[0]).FirstOrDefault() ?? "";
      }</value>
    </set-header>
    <set-header name="X-User-Roles" exists-action="override">
      <value>@{
        var jwt = context.Request.Headers.GetValueOrDefault("Authorization","").Replace("Bearer ","").AsJwt();
        return jwt == null ? "" : string.Join(",", jwt.Claims.GetValueOrDefault("roles", new string[0]));
      }</value>
    </set-header>
  </inbound>
  <backend>
    <base />
  </backend>
  <outbound>
    <base />
  </outbound>
  <on-error>
    <base />
  </on-error>
</policies>
'''

var dealerApiPolicyXml = replace(replace(dealerApiPolicyTemplate, '__CORS_ORIGINS__', corsOriginsXml), '__VALIDATE_JWT__', validateJwtXml)

resource apiPolicy 'Microsoft.ApiManagement/service/apis/policies@2023-09-01-preview' = {
  parent: dealerApi
  name: 'policy'
  properties: {
    format: 'xml'
    value: dealerApiPolicyXml
  }
}

output gatewayUrl string = apim.properties.gatewayUrl
output apimName string = apim.name
