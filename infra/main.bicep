// ============================================================================
// COMPANY Dealer Portal - Main Infrastructure Template (WAF-aligned)
// Deploys: Azure OpenAI, AI Search, Storage, App Service, APIM, Key Vault,
//          Document Intelligence, Application Insights, Log Analytics,
//          VNet + Private Endpoints (prod), RBAC Role Assignments
// ============================================================================

targetScope = 'resourceGroup'

// ============================================================================
// Parameters
// ============================================================================

@description('Environment name (dev, staging, prod)')
@allowed(['dev', 'staging', 'prod'])
param environment string = 'dev'

@description('Azure region for all resources')
param location string = resourceGroup().location

@description('Base name for all resources')
param baseName string = 'mydealer'

@description('Deploy App Service (production hosting). Set false for dev where developers run locally.')
param deployAppService bool = false

@description('Deploy APIM (production API gateway). Requires deployAppService = true.')
param deployApim bool = false

@description('Audience (Entra app / API GUID) for APIM validate-jwt. Empty disables JWT enforcement.')
param apimJwtAudience string = ''

@description('Azure OpenAI model deployment name')
param openAiModelDeployment string = 'gpt-5'

@description('Azure OpenAI embedding model deployment name')
param embeddingModelDeployment string = 'text-embedding-3-large'

@description('Azure OpenAI model capacity (tokens-per-minute in thousands)')
param openAiModelCapacity int = 30

@description('Azure OpenAI embedding model capacity')
param embeddingModelCapacity int = 30

@description('App Service Plan SKU name')
param appServiceSkuName string = 'B1'

@description('App Service Plan SKU tier')
param appServiceSkuTier string = 'Basic'

@description('Azure AI Search SKU')
@allowed(['basic', 'standard', 'standard2', 'standard3'])
param searchSkuName string = 'basic'

@description('Azure AI Search replica count')
param searchReplicaCount int = 1

@description('Azure AI Search partition count')
param searchPartitionCount int = 1

@description('Storage account redundancy SKU')
@allowed(['Standard_LRS', 'Standard_GRS', 'Standard_ZRS', 'Standard_RAGRS'])
param storageSkuName string = 'Standard_LRS'

@description('Enable network isolation with VNet and private endpoints')
param useNetworkIsolation bool = false

@description('Public network access for AI services')
@allowed(['Enabled', 'Disabled'])
param publicNetworkAccess string = 'Enabled'

@description('Enable Key Vault purge protection (required for production)')
param enablePurgeProtection bool = false

@description('Key Vault soft delete retention in days')
param softDeleteRetentionInDays int = 7

@description('Log Analytics retention in days')
param logRetentionDays int = 30

@description('Id of the deploying user or service principal for RBAC assignments')
param principalId string = ''

@description('Type of the deploying principal')
@allowed(['User', 'ServicePrincipal'])
param principalType string = 'User'

@description('Deploy Document Intelligence for PDF extraction')
param deployDocumentIntelligence bool = true

@description('Document Intelligence SKU')
@allowed(['F0', 'S0'])
param documentIntelligenceSkuName string = 'S0'

@description('Search index name')
param searchIndexName string = 'dealer-portal-docs'

@description('CORS allowed origins (comma-separated)')
param corsOrigins string = 'http://localhost:5173'

@description('Enable simulated mode for demo')
param simulatedMode bool = true

// ============================================================================
// Variables
// ============================================================================

var resourceSuffix = '${baseName}-${environment}'
var uniqueSuffix = uniqueString(resourceGroup().id, baseName)

// ============================================================================
// Modules - Core Infrastructure
// ============================================================================

module monitoring 'modules/monitoring.bicep' = {
  name: 'monitoring-${resourceSuffix}'
  params: {
    location: location
    baseName: resourceSuffix
    retentionDays: logRetentionDays
  }
}

module storage 'modules/storage.bicep' = {
  name: 'storage-${resourceSuffix}'
  params: {
    location: location
    baseName: baseName
    uniqueSuffix: uniqueSuffix
    skuName: storageSkuName
    publicNetworkAccess: publicNetworkAccess
  }
}

module keyvault 'modules/keyvault.bicep' = if (deployAppService) {
  name: 'keyvault-${resourceSuffix}'
  params: {
    location: location
    baseName: resourceSuffix
    logAnalyticsWorkspaceId: monitoring.outputs.logAnalyticsWorkspaceId
    enablePurgeProtection: enablePurgeProtection
    softDeleteRetentionInDays: softDeleteRetentionInDays
  }
}

module foundry 'modules/foundry.bicep' = {
  name: 'foundry-${resourceSuffix}'
  params: {
    location: location
    baseName: resourceSuffix
    modelDeploymentName: openAiModelDeployment
    embeddingDeploymentName: embeddingModelDeployment
    modelCapacity: openAiModelCapacity
    embeddingCapacity: embeddingModelCapacity
    publicNetworkAccess: publicNetworkAccess
    appInsightsId: monitoring.outputs.appInsightsId
    appInsightsConnectionString: monitoring.outputs.appInsightsConnectionString
    storageAccountId: storage.outputs.storageAccountId
    storageAccountBlobEndpoint: storage.outputs.blobEndpoint
    searchEndpoint: search.outputs.endpoint
    searchId: search.outputs.searchServiceId
  }
}

module search 'modules/search.bicep' = {
  name: 'search-${resourceSuffix}'
  params: {
    location: location
    baseName: resourceSuffix
    skuName: searchSkuName
    replicaCount: searchReplicaCount
    partitionCount: searchPartitionCount
    publicNetworkAccess: publicNetworkAccess
  }
}

module documentIntelligence 'modules/documentintelligence.bicep' = if (deployDocumentIntelligence) {
  name: 'documentintelligence-${resourceSuffix}'
  params: {
    location: location
    baseName: resourceSuffix
    skuName: documentIntelligenceSkuName
    publicNetworkAccess: publicNetworkAccess
  }
}

module appservice 'modules/appservice.bicep' = if (deployAppService) {
  name: 'appservice-${resourceSuffix}'
  params: {
    location: location
    baseName: resourceSuffix
    skuName: appServiceSkuName
    skuTier: appServiceSkuTier
    openAiEndpoint: foundry.outputs.endpoint
    searchEndpoint: search.outputs.endpoint
    searchIndexName: searchIndexName
    storageAccountName: storage.outputs.storageAccountName
    appInsightsConnectionString: monitoring.outputs.appInsightsConnectionString
    keyVaultUri: deployAppService ? keyvault!.outputs.keyVaultUri : ''
    documentIntelligenceEndpoint: deployDocumentIntelligence ? documentIntelligence!.outputs.endpoint : ''
    corsOrigins: corsOrigins
    simulatedMode: simulatedMode
    subnetId: useNetworkIsolation ? networking!.outputs.appSubnetId : ''
  }
}

module apim 'modules/apim.bicep' = if (deployApim && deployAppService) {
  name: 'apim-${resourceSuffix}'
  params: {
    location: location
    baseName: resourceSuffix
    backendUrl: appservice!.outputs.appServiceUrl
    appInsightsInstrumentationKey: monitoring.outputs.appInsightsInstrumentationKey
    logAnalyticsWorkspaceId: monitoring.outputs.logAnalyticsWorkspaceId
    jwtOpenIdConfigUrl: empty(apimJwtAudience) ? '' : '${az.environment().authentication.loginEndpoint}${tenant().tenantId}/v2.0/.well-known/openid-configuration'
    jwtAudience: apimJwtAudience
    allowedCorsOrigins: split(corsOrigins, ',')
  }
}

// ============================================================================
// Networking - VNet + Private Endpoints (production)
// ============================================================================

module networking 'modules/networking.bicep' = if (useNetworkIsolation) {
  name: 'networking-${resourceSuffix}'
  params: {
    location: location
    baseName: resourceSuffix
    openAiId: foundry.outputs.openAiId
    searchServiceId: search.outputs.searchServiceId
    storageAccountId: storage.outputs.storageAccountId
    keyVaultId: deployAppService ? keyvault!.outputs.keyVaultId : ''
    documentIntelligenceId: deployDocumentIntelligence ? documentIntelligence!.outputs.documentIntelligenceId : ''
  }
}

// ============================================================================
// RBAC Role Assignments
// ============================================================================

module roles 'modules/roles.bicep' = {
  name: 'roles-${resourceSuffix}'
  params: {
    appServicePrincipalId: deployAppService ? appservice!.outputs.appServicePrincipalId : ''
    principalId: principalId
    principalType: principalType
    openAiName: foundry.outputs.openAiName
    searchServiceName: search.outputs.searchServiceName
    storageAccountName: storage.outputs.storageAccountName
    keyVaultName: deployAppService ? keyvault!.outputs.keyVaultName : ''
    documentIntelligenceName: deployDocumentIntelligence ? documentIntelligence!.outputs.documentIntelligenceName : ''
  }
}

// ============================================================================
// Outputs
// ============================================================================

output appServiceUrl string = deployAppService ? appservice!.outputs.appServiceUrl : ''
output appServiceName string = deployAppService ? appservice!.outputs.appServiceName : ''
#disable-next-line outputs-should-not-contain-secrets
output apimGatewayUrl string = (deployApim && deployAppService) ? apim!.outputs.gatewayUrl : ''
output storageAccountName string = storage.outputs.storageAccountName
output searchEndpoint string = search.outputs.endpoint
output searchServiceName string = search.outputs.searchServiceName
output openAiEndpoint string = foundry.outputs.endpoint
output openAiName string = foundry.outputs.openAiName
output aiProjectName string = foundry.outputs.projectName
output aiProjectEndpoint string = foundry.outputs.projectEndpoint
output aiProjectResourceId string = foundry.outputs.projectResourceId
output keyVaultUri string = deployAppService ? keyvault!.outputs.keyVaultUri : ''
output keyVaultName string = deployAppService ? keyvault!.outputs.keyVaultName : ''
output appInsightsName string = monitoring.outputs.appInsightsName
output documentIntelligenceEndpoint string = deployDocumentIntelligence ? documentIntelligence!.outputs.endpoint : ''
output environment string = environment
output resourceSuffix string = resourceSuffix
