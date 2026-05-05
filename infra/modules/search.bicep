// ============================================================================
// Azure AI Search - Hybrid retrieval (keyword + semantic/vector)
// ============================================================================

param location string
param baseName string

@description('Azure AI Search SKU')
@allowed(['basic', 'standard', 'standard2', 'standard3'])
param skuName string = 'basic'

@description('Number of replicas (2+ for production HA)')
param replicaCount int = 1

@description('Number of partitions')
param partitionCount int = 1

@description('Public network access setting')
@allowed(['Enabled', 'Disabled'])
param publicNetworkAccess string = 'Enabled'

resource searchService 'Microsoft.Search/searchServices@2024-06-01-preview' = {
  name: 'srch-${baseName}'
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  sku: {
    name: skuName
  }
  properties: {
    replicaCount: replicaCount
    partitionCount: partitionCount
    hostingMode: 'default'
    semanticSearch: 'standard'
    publicNetworkAccess: publicNetworkAccess == 'Enabled' ? 'enabled' : 'disabled'
    disableLocalAuth: false
    authOptions: {
      aadOrApiKey: {
        aadAuthFailureMode: 'http401WithBearerChallenge'
      }
    }
  }
}

output endpoint string = 'https://${searchService.name}.search.windows.net'
output searchServiceId string = searchService.id
output searchServiceName string = searchService.name
