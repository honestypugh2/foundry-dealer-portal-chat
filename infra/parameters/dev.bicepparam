using '../main.bicep'

// ============================================================================
// Development Environment Parameters
// Optimized for cost and developer productivity.
// No network isolation, lower SKUs, simulated mode enabled.
// ============================================================================

param environment = 'dev'
param location = 'swedencentral'
param baseName = 'mydealer'

// Deployment toggles
param deployAppService = false
param deployApim = false
param deployDocumentIntelligence = true

// AI Models
param openAiModelDeployment = 'gpt-5'
param embeddingModelDeployment = 'text-embedding-3-large'
param openAiModelCapacity = 30
param embeddingModelCapacity = 30

// App Service - Basic tier for dev
param appServiceSkuName = 'B1'
param appServiceSkuTier = 'Basic'

// Azure AI Search - Basic with single replica
param searchSkuName = 'basic'
param searchReplicaCount = 1
param searchPartitionCount = 1
param searchIndexName = 'dealer-portal-docs'

// Storage - LRS for dev (no geo-redundancy needed)
param storageSkuName = 'Standard_LRS'

// Networking - Open for dev (no VNet/private endpoints)
param useNetworkIsolation = false
param publicNetworkAccess = 'Enabled'

// Key Vault - Relaxed for dev
param enablePurgeProtection = false
param softDeleteRetentionInDays = 7

// Monitoring - Short retention for cost
param logRetentionDays = 30

// Document Intelligence - Free tier for dev
param documentIntelligenceSkuName = 'F0'

// App configuration
param corsOrigins = 'http://localhost:5173,http://localhost:3000'
param simulatedMode = true

// RBAC - Set via CLI: az deployment group create --parameters principalId=$(az ad signed-in-user show --query id -o tsv)
param principalId = ''
param principalType = 'User'
