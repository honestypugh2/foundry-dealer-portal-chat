// ============================================================================
// Azure AI Foundry (AIServices) + Project + Model Deployments + Connections
// Reference: https://github.com/microsoft-foundry/foundry-samples/tree/main/infrastructure/infrastructure-setup-bicep
// ============================================================================

param location string
param baseName string
param modelDeploymentName string = 'gpt-5'
param embeddingDeploymentName string = 'text-embedding-3-large'

@description('Model deployment capacity (TPM in thousands)')
param modelCapacity int = 30

@description('Embedding deployment capacity (TPM in thousands)')
param embeddingCapacity int = 30

@description('Public network access setting')
@allowed(['Enabled', 'Disabled'])
param publicNetworkAccess string = 'Enabled'

@description('Foundry project display name')
param projectDisplayName string = 'Dealer Portal AI Project'

@description('Application Insights resource ID for Foundry connection')
param appInsightsId string = ''

@description('Application Insights connection string')
param appInsightsConnectionString string = ''

@description('Storage account resource ID for Foundry connection')
param storageAccountId string = ''

@description('Storage account blob endpoint for Foundry connection')
param storageAccountBlobEndpoint string = ''

@description('AI Search endpoint for Foundry connection')
param searchEndpoint string = ''

@description('AI Search resource ID for Foundry connection')
param searchId string = ''

// ============================================================================
// 1. Azure AI Foundry Account (AIServices)
// ============================================================================
resource aiServices 'Microsoft.CognitiveServices/accounts@2025-06-01' = {
  name: 'ai-${baseName}'
  location: location
  kind: 'AIServices'
  identity: {
    type: 'SystemAssigned'
  }
  sku: {
    name: 'S0'
  }
  properties: {
    customSubDomainName: 'ai-${baseName}'
    publicNetworkAccess: publicNetworkAccess
    allowProjectManagement: true
    disableLocalAuth: false
  }
}

// ============================================================================
// 2. AI Foundry Project (child of AIServices)
// ============================================================================
resource aiProject 'Microsoft.CognitiveServices/accounts/projects@2025-06-01' = {
  parent: aiServices
  name: 'proj-${baseName}'
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    description: projectDisplayName
    displayName: projectDisplayName
  }
}

// ============================================================================
// 3. Foundry Connections
// ============================================================================

// Azure OpenAI connection (self-referencing — models deployed on the same account)
resource aoaiConnection 'Microsoft.CognitiveServices/accounts/connections@2025-06-01' = {
  name: 'aoai-connection'
  parent: aiServices
  properties: {
    category: 'AzureOpenAI'
    authType: 'AAD'
    isSharedToAll: true
    target: aiServices.properties.endpoints['OpenAI Language Model Instance API']
    metadata: {
      ApiType: 'azure'
      ResourceId: aiServices.id
    }
  }
}

// Application Insights connection
resource appInsightsConnection 'Microsoft.CognitiveServices/accounts/connections@2025-06-01' = if (!empty(appInsightsId)) {
  name: 'appinsights-connection'
  parent: aiServices
  properties: {
    category: 'AppInsights'
    target: appInsightsId
    authType: 'ApiKey'
    isSharedToAll: true
    credentials: {
      #disable-next-line use-secure-value-for-secure-inputs
      key: appInsightsConnectionString
    }
    metadata: {
      ApiType: 'Azure'
      ResourceId: appInsightsId
    }
  }
}

// Azure Storage connection (AAD auth — allowSharedKeyAccess is disabled)
resource storageConnection 'Microsoft.CognitiveServices/accounts/connections@2025-06-01' = if (!empty(storageAccountId)) {
  name: 'storage-connection'
  parent: aiServices
  properties: {
    category: 'AzureStorageAccount'
    target: storageAccountBlobEndpoint
    authType: 'AAD'
    isSharedToAll: true
    metadata: {
      ApiType: 'Azure'
      ResourceId: storageAccountId
    }
  }
}

// Azure AI Search connection
resource searchConnection 'Microsoft.CognitiveServices/accounts/connections@2025-06-01' = if (!empty(searchId)) {
  name: 'aisearch-connection'
  parent: aiServices
  properties: {
    category: 'CognitiveSearch'
    target: searchEndpoint
    authType: 'AAD'
    isSharedToAll: true
    metadata: {
      ApiType: 'Azure'
      ResourceId: searchId
    }
  }
}

// ============================================================================
// 4. GPT-5 Deployment
// ============================================================================
resource gpt5Deployment 'Microsoft.CognitiveServices/accounts/deployments@2025-06-01' = {
  parent: aiServices
  name: modelDeploymentName
  sku: {
    name: 'GlobalStandard'
    capacity: modelCapacity
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: 'gpt-5'
      version: '2025-08-07'
    }
  }
}

// ============================================================================
// 5. Text Embedding 3 Large Deployment
// ============================================================================
resource embeddingDeployment 'Microsoft.CognitiveServices/accounts/deployments@2025-06-01' = {
  parent: aiServices
  name: embeddingDeploymentName
  sku: {
    name: 'Standard'
    capacity: embeddingCapacity
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: 'text-embedding-3-large'
      version: '1'
    }
  }
  dependsOn: [gpt5Deployment]
}

// ============================================================================
// Outputs
// ============================================================================
output endpoint string = aiServices.properties.endpoint
output openAiId string = aiServices.id
output openAiName string = aiServices.name
output accountPrincipalId string = aiServices.identity.principalId
output projectName string = aiProject.name
output projectResourceId string = aiProject.id
output projectEndpoint string = aiProject.properties.endpoints['AI Foundry API']
output projectPrincipalId string = aiProject.identity.principalId
