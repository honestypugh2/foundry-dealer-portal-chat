// ============================================================================
// Azure Document Intelligence (Form Recognizer)
// Used for PDF extraction with prebuilt-layout model
// ============================================================================

param location string
param baseName string

@description('Document Intelligence SKU')
@allowed(['F0', 'S0'])
param skuName string = 'S0'

@description('Public network access setting')
@allowed(['Enabled', 'Disabled'])
param publicNetworkAccess string = 'Enabled'

resource documentIntelligence 'Microsoft.CognitiveServices/accounts@2024-10-01' = {
  name: 'di-${baseName}'
  location: location
  kind: 'FormRecognizer'
  identity: {
    type: 'SystemAssigned'
  }
  sku: {
    name: skuName
  }
  properties: {
    customSubDomainName: 'di-${baseName}'
    publicNetworkAccess: publicNetworkAccess
    disableLocalAuth: false
    networkAcls: {
      defaultAction: publicNetworkAccess == 'Enabled' ? 'Allow' : 'Deny'
    }
  }
}

output endpoint string = documentIntelligence.properties.endpoint
output documentIntelligenceId string = documentIntelligence.id
output documentIntelligenceName string = documentIntelligence.name
