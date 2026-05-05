// ============================================================================
// Azure AI Foundry (AIServices) + Project + GPT-5 + Text Embedding 3 Large
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

@description('Foundry project description')
param projectDescription string = 'Dealer Portal AI Project'

// ============================================================================
// 1. Azure AI Foundry Account (AIServices) — unified cognitive services account
// ============================================================================
resource aiServices 'Microsoft.CognitiveServices/accounts@2025-04-01-preview' = {
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
resource aiProject 'Microsoft.CognitiveServices/accounts/projects@2025-04-01-preview' = {
  parent: aiServices
  name: 'proj-${baseName}'
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    description: projectDescription
  }
}

// ============================================================================
// 3. GPT-5 Deployment
// ============================================================================
resource gpt5Deployment 'Microsoft.CognitiveServices/accounts/deployments@2025-04-01-preview' = {
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
// 4. Text Embedding 3 Large Deployment
// ============================================================================
resource embeddingDeployment 'Microsoft.CognitiveServices/accounts/deployments@2025-04-01-preview' = {
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
output projectName string = aiProject.name
output projectEndpoint string = '${aiServices.properties.endpoint}/api/projects/${aiProject.name}'
output projectPrincipalId string = aiProject.identity.principalId
