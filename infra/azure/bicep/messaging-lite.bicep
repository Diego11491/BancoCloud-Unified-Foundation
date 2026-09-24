// Student LITE messaging and Bronze storage only. Preview before any deployment.
targetScope = 'resourceGroup'

@description('Unique lowercase project suffix; use letters and digits only')
@minLength(6)
@maxLength(12)
param suffix string
@description('The region confirmed for the subscription')
param location string = resourceGroup().location
@description('Named human owner, no personal email')
param owner string
@description('Resource expiry in YYYY-MM-DD')
param expiry string

var tags = {
  project: 'bancocloud'
  environment: 'student-lite'
  owner: owner
  expiry: expiry
}

resource eventHubNamespace 'Microsoft.EventHub/namespaces@2024-01-01' = {
  name: 'bceh${suffix}'
  location: location
  tags: tags
  sku: {
    name: 'Standard'
    tier: 'Standard'
    capacity: 1
  }
  properties: {
    minimumTlsVersion: '1.2'
    publicNetworkAccess: 'Enabled'
  }
}
resource transactions 'Microsoft.EventHub/namespaces/eventhubs@2024-01-01' = {
  name: 'transaction-posted-v1'
  parent: eventHubNamespace
  properties: {
    partitionCount: 2
    messageRetentionInDays: 1
  }
}
resource bus 'Microsoft.ServiceBus/namespaces@2024-01-01' = {
  name: 'bcsb${suffix}'
  location: location
  tags: tags
  sku: {
    name: 'Standard'
    tier: 'Standard'
  }
  properties: {
    minimumTlsVersion: '1.2'
    publicNetworkAccess: 'Enabled'
  }
}
resource highQueue 'Microsoft.ServiceBus/namespaces/queues@2024-01-01' = {
  name: 'high-fraud-cases'
  parent: bus
  properties: {
    requiresDuplicateDetection: true
    duplicateDetectionHistoryTimeWindow: 'P1D'
  }
}
resource lake 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: 'bclake${suffix}'
  location: location
  tags: tags
  sku: { name: 'Standard_LRS' }
  kind: 'StorageV2'
  properties: {
    isHnsEnabled: true
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
    allowBlobPublicAccess: false
  }
}
resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = {
  name: 'default'
  parent: lake
}
resource bronze 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  name: 'bronze'
  parent: blobService
  properties: { publicAccess: 'None' }
}
resource silver 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  name: 'silver'
  parent: blobService
  properties: { publicAccess: 'None' }
}
resource gold 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  name: 'gold'
  parent: blobService
  properties: { publicAccess: 'None' }
}

output eventHubNamespaceName string = eventHubNamespace.name
output eventHubName string = transactions.name
output serviceBusNamespaceName string = bus.name
output queueName string = highQueue.name
output storageAccountName string = lake.name
