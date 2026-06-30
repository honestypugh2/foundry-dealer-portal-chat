using '../main.bicep'

// ============================================================================
// Production Environment Parameters
// Follows Azure Well-Architected Framework (WAF):
//   - Reliability: Multi-replica search, GRS storage
//   - Security: Identity/policy-based isolation (APIM Consumption, no VNet), purge protection
//   - Operational Excellence: Extended log retention, monitoring
//   - Performance: Standard-tier services with appropriate capacity
// ============================================================================

param environment = 'prod'
param location = 'swedencentral'
param baseName = 'mydealer'

// Deployment toggles
param deployAppService = true
param deployApim = true
param deployDocumentIntelligence = true

// APIM JWT validation — audience (Entra app / API GUID). Leave '' to deploy
// without enforcement until the dealer-portal app registration exists, then set
// to the API's application (client) ID to enforce validate-jwt at the gateway.
param apimJwtAudience = ''

// AI Models - Higher capacity for production traffic
param openAiModelDeployment = 'gpt-5'
param embeddingModelDeployment = 'text-embedding-3-large'
param openAiModelCapacity = 80
param embeddingModelCapacity = 80

// App Service - Standard tier for production (auto-scale capable)
param appServiceSkuName = 'P1v3'
param appServiceSkuTier = 'PremiumV3'

// Azure AI Search - Standard with 2 replicas for HA (99.95% SLA)
param searchSkuName = 'standard'
param searchReplicaCount = 2
param searchPartitionCount = 1
param searchIndexName = 'dealer-portal-docs'

// Storage - GRS for production geo-redundancy
param storageSkuName = 'Standard_GRS'

// Networking - APIM Consumption tier (D9 / PLATFORM-STANDARDS §3 + ADR-001):
// public gateway, no VNet/private endpoints. Backend protection is delivered by
// APIM policy (JWT validation, rate limiting), Managed Identity, and Key Vault
// credential injection rather than network isolation.
param useNetworkIsolation = false
param publicNetworkAccess = 'Enabled'

// Key Vault - Strict for production
param enablePurgeProtection = true
param softDeleteRetentionInDays = 90

// Monitoring - Extended retention for compliance
param logRetentionDays = 90

// Document Intelligence - Standard tier for production
param documentIntelligenceSkuName = 'S0'

// App configuration
param corsOrigins = 'https://dealer-portal.company.com'
param simulatedMode = false

// RBAC - Set via CI/CD pipeline service principal
param principalId = ''
param principalType = 'ServicePrincipal'
