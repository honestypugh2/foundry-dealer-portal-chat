// ============================================================================
// Azure App Service (Linux) - FastAPI Orchestrator
// ============================================================================

param location string
param baseName string
param openAiEndpoint string
param searchEndpoint string
param searchIndexName string
param storageAccountName string
param appInsightsConnectionString string
param keyVaultUri string

@description('Document Intelligence endpoint (empty if not deployed)')
param documentIntelligenceEndpoint string = ''

@description('App Service Plan SKU name')
param skuName string = 'B1'

@description('App Service Plan SKU tier')
param skuTier string = 'Basic'

@description('CORS allowed origins')
param corsOrigins string = 'http://localhost:5173'

@description('Enable simulated mode')
param simulatedMode bool = true

@description('VNet subnet ID for VNet integration (empty = no VNet)')
param subnetId string = ''

resource appServicePlan 'Microsoft.Web/serverfarms@2023-12-01' = {
  name: 'asp-${baseName}'
  location: location
  kind: 'linux'
  sku: {
    name: skuName
    tier: skuTier
  }
  properties: {
    reserved: true // Required for Linux
  }
}

resource appService 'Microsoft.Web/sites@2023-12-01' = {
  name: 'app-${baseName}'
  location: location
  kind: 'app,linux'
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    serverFarmId: appServicePlan.id
    httpsOnly: true
    virtualNetworkSubnetId: !empty(subnetId) ? subnetId : null
    siteConfig: {
      linuxFxVersion: 'PYTHON|3.12'
      appCommandLine: 'gunicorn -w 4 -k uvicorn.workers.UvicornWorker app.main:app'
      alwaysOn: true
      ftpsState: 'Disabled'
      http20Enabled: true
      minTlsVersion: '1.2'
      vnetRouteAllEnabled: !empty(subnetId)
      appSettings: [
        { name: 'AZURE_OPENAI_ENDPOINT', value: openAiEndpoint }
        { name: 'AZURE_SEARCH_ENDPOINT', value: searchEndpoint }
        { name: 'AZURE_SEARCH_INDEX_NAME', value: searchIndexName }
        { name: 'AZURE_STORAGE_ACCOUNT_NAME', value: storageAccountName }
        { name: 'AZURE_KEYVAULT_URI', value: keyVaultUri }
        { name: 'AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT', value: documentIntelligenceEndpoint }
        { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', value: appInsightsConnectionString }
        { name: 'SCM_DO_BUILD_DURING_DEPLOYMENT', value: 'true' }
        { name: 'SIMULATED_MODE', value: string(simulatedMode) }
        { name: 'CORS_ORIGINS', value: corsOrigins }
      ]
    }
  }
}

output appServiceUrl string = 'https://${appService.properties.defaultHostName}'
output appServiceName string = appService.name
output appServicePrincipalId string = appService.identity.principalId
