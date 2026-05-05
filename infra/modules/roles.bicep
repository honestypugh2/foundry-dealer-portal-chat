// ============================================================================
// RBAC Role Assignments
// Grants least-privilege access to App Service managed identity and
// the deploying user/service principal.
//
// Role Definition IDs:
//   Cognitive Services OpenAI User:        5e0bd9bd-7b93-4f28-af87-19fc36ad61bd
//   Cognitive Services User:               a97b65f3-24c7-4388-baec-2e87135dc908
//   Search Index Data Reader:              1407120a-92aa-4202-b7e9-c0e197c71c8f
//   Search Index Data Contributor:         8ebe5a00-799e-43f5-93ac-243d3dce84a7
//   Search Service Contributor:            7ca78c08-252a-4471-8644-bb5ff32d4ba0
//   Storage Blob Data Reader:              2a2b9908-6ea1-4ae2-8e65-a410df84e7d1
//   Storage Blob Data Contributor:         ba92f5b4-2d11-453d-a403-e96b0029c9fe
//   Key Vault Secrets User:                4633458b-17de-408a-b874-0445c86b69e6
//   Key Vault Crypto User:                 12338af0-0e69-4776-bea7-57ae8d297424
//   Monitoring Metrics Publisher:          3913510d-42f4-4e42-8a64-420c390055eb
// ============================================================================

@description('Principal ID of the App Service managed identity')
param appServicePrincipalId string

@description('Principal ID of the deploying user or service principal')
param principalId string = ''

@description('Type of the deploying principal')
@allowed(['User', 'ServicePrincipal'])
param principalType string = 'User'

@description('Azure OpenAI resource name')
param openAiName string

@description('Azure AI Search resource name')
param searchServiceName string

@description('Storage account name')
param storageAccountName string

@description('Key Vault name (empty if not deployed)')
param keyVaultName string = ''

@description('Document Intelligence resource name (empty if not deployed)')
param documentIntelligenceName string = ''

// ============================================================================
// Existing Resources (for scoped role assignments)
// ============================================================================

resource openAi 'Microsoft.CognitiveServices/accounts@2024-10-01' existing = {
  name: openAiName
}

resource searchService 'Microsoft.Search/searchServices@2024-06-01-preview' existing = {
  name: searchServiceName
}

resource storageAccount 'Microsoft.Storage/storageAccounts@2023-05-01' existing = {
  name: storageAccountName
}

resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' existing = if (!empty(keyVaultName)) {
  name: keyVaultName
}

resource documentIntelligence 'Microsoft.CognitiveServices/accounts@2024-10-01' existing = if (!empty(documentIntelligenceName)) {
  name: documentIntelligenceName
}

// ============================================================================
// App Service Managed Identity - Role Assignments
// ============================================================================

// App Service → Azure OpenAI (Cognitive Services OpenAI User)
resource appOpenAiRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(appServicePrincipalId)) {
  name: guid(openAi.id, appServicePrincipalId, '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd')
  scope: openAi
  properties: {
    principalId: appServicePrincipalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd')
    principalType: 'ServicePrincipal'
  }
}

// App Service → Azure AI Search (Search Index Data Reader)
resource appSearchReaderRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(appServicePrincipalId)) {
  name: guid(searchService.id, appServicePrincipalId, '1407120a-92aa-4202-b7e9-c0e197c71c8f')
  scope: searchService
  properties: {
    principalId: appServicePrincipalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '1407120a-92aa-4202-b7e9-c0e197c71c8f')
    principalType: 'ServicePrincipal'
  }
}

// App Service → Azure AI Search (Search Index Data Contributor - for indexing)
resource appSearchContribRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(appServicePrincipalId)) {
  name: guid(searchService.id, appServicePrincipalId, '8ebe5a00-799e-43f5-93ac-243d3dce84a7')
  scope: searchService
  properties: {
    principalId: appServicePrincipalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '8ebe5a00-799e-43f5-93ac-243d3dce84a7')
    principalType: 'ServicePrincipal'
  }
}

// App Service → Storage (Storage Blob Data Reader)
resource appStorageReaderRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(appServicePrincipalId)) {
  name: guid(storageAccount.id, appServicePrincipalId, '2a2b9908-6ea1-4ae2-8e65-a410df84e7d1')
  scope: storageAccount
  properties: {
    principalId: appServicePrincipalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '2a2b9908-6ea1-4ae2-8e65-a410df84e7d1')
    principalType: 'ServicePrincipal'
  }
}

// App Service → Key Vault (Key Vault Secrets User)
resource appKeyVaultRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(appServicePrincipalId) && !empty(keyVaultName)) {
  name: guid(keyVault.id, appServicePrincipalId, '4633458b-17de-408a-b874-0445c86b69e6')
  scope: keyVault
  properties: {
    principalId: appServicePrincipalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '4633458b-17de-408a-b874-0445c86b69e6')
    principalType: 'ServicePrincipal'
  }
}

// App Service → Document Intelligence (Cognitive Services User)
resource appDocIntelRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(appServicePrincipalId) && !empty(documentIntelligenceName)) {
  name: guid(documentIntelligence.id, appServicePrincipalId, 'a97b65f3-24c7-4388-baec-2e87135dc908')
  scope: documentIntelligence
  properties: {
    principalId: appServicePrincipalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'a97b65f3-24c7-4388-baec-2e87135dc908')
    principalType: 'ServicePrincipal'
  }
}

// ============================================================================
// Search Service → Storage (for Integrated Vectorization indexer)
// ============================================================================

// AI Search needs blob read access for integrated vectorization
resource searchStorageRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storageAccount.id, searchService.id, '2a2b9908-6ea1-4ae2-8e65-a410df84e7d1')
  scope: storageAccount
  properties: {
    principalId: searchService.identity.principalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '2a2b9908-6ea1-4ae2-8e65-a410df84e7d1')
    principalType: 'ServicePrincipal'
  }
}

// AI Search → OpenAI (for integrated vectorization embeddings)
resource searchOpenAiRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(openAi.id, searchService.id, '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd')
  scope: openAi
  properties: {
    principalId: searchService.identity.principalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd')
    principalType: 'ServicePrincipal'
  }
}

// ============================================================================
// Deploying User/Service Principal - Role Assignments (for CLI/development)
// ============================================================================

// User → Azure OpenAI (Cognitive Services OpenAI User)
resource userOpenAiRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(principalId)) {
  name: guid(openAi.id, principalId, '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd')
  scope: openAi
  properties: {
    principalId: principalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd')
    principalType: principalType
  }
}

// User → Azure AI Search (Search Index Data Contributor)
resource userSearchContribRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(principalId)) {
  name: guid(searchService.id, principalId, '8ebe5a00-799e-43f5-93ac-243d3dce84a7')
  scope: searchService
  properties: {
    principalId: principalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '8ebe5a00-799e-43f5-93ac-243d3dce84a7')
    principalType: principalType
  }
}

// User → Azure AI Search (Search Service Contributor - manage indexes)
resource userSearchSvcContribRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(principalId)) {
  name: guid(searchService.id, principalId, '7ca78c08-252a-4471-8644-bb5ff32d4ba0')
  scope: searchService
  properties: {
    principalId: principalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7ca78c08-252a-4471-8644-bb5ff32d4ba0')
    principalType: principalType
  }
}

// User → Storage (Storage Blob Data Contributor)
resource userStorageContribRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(principalId)) {
  name: guid(storageAccount.id, principalId, 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')
  scope: storageAccount
  properties: {
    principalId: principalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')
    principalType: principalType
  }
}

// User → Key Vault (Key Vault Secrets User)
resource userKeyVaultRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(principalId) && !empty(keyVaultName)) {
  name: guid(keyVault.id, principalId, '4633458b-17de-408a-b874-0445c86b69e6')
  scope: keyVault
  properties: {
    principalId: principalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '4633458b-17de-408a-b874-0445c86b69e6')
    principalType: principalType
  }
}

// User → Document Intelligence (Cognitive Services User)
resource userDocIntelRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(principalId) && !empty(documentIntelligenceName)) {
  name: guid(documentIntelligence.id, principalId, 'a97b65f3-24c7-4388-baec-2e87135dc908')
  scope: documentIntelligence
  properties: {
    principalId: principalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'a97b65f3-24c7-4388-baec-2e87135dc908')
    principalType: principalType
  }
}
