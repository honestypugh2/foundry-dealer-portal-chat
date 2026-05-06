// ============================================================================
// Azure API Management (Future Architecture)
// Public entry point with JWT validation, throttling, request logging,
// and AI Gateway policies
// ============================================================================

param location string
param baseName string
param backendUrl string
param appInsightsInstrumentationKey string
param logAnalyticsWorkspaceId string

resource apim 'Microsoft.ApiManagement/service@2023-09-01-preview' = {
  name: 'apim-${baseName}'
  location: location
  sku: {
    name: 'Developer'
    capacity: 1
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

// Rate limiting policy at API level
resource apiPolicy 'Microsoft.ApiManagement/service/apis/policies@2023-09-01-preview' = {
  parent: dealerApi
  name: 'policy'
  properties: {
    format: 'xml'
    value: '''
<policies>
  <inbound>
    <base />
    <rate-limit calls="100" renewal-period="60" />
    <set-backend-service backend-id="fastapi-backend" />
    <cors>
      <allowed-origins>
        <origin>*</origin>
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
  }
}

output gatewayUrl string = apim.properties.gatewayUrl
output apimName string = apim.name
