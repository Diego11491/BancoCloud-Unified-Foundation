// Student LITE messaging and governed lake zones. Preview before any deployment.
// Each cost-bearing capability can be disabled independently by the composition root.
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

@description('Principal ID of the user-assigned identity used by the Azure fraud worker')
param workloadIdentityPrincipalId string

@description('Optional Entra service principal object ID for the temporary local publisher and worker')
param localIntegrationPrincipalId string = ''

@description('Days to retain rejected records in the quarantine container')
@minValue(1)
@maxValue(90)
param quarantineRetentionDays int = 30

@description('Deploy Event Hubs, the transaction hub and fraud consumer group')
param deployEventStreaming bool = true

@description('Deploy the governed ADLS account, Medallion zones and checkpoint container')
param deployDataLake bool = true

@description('Deploy Service Bus and the HIGH fraud queue')
param deployServiceBus bool = false

var tags = {
  project: 'bancocloud'
  environment: 'student-lite'
  owner: owner
  expiry: expiry
}

var eventHubsDataReceiverRoleDefinitionId = 'a638d3c7-ab3a-418d-83e6-5f17a39d4fde'
var eventHubsDataSenderRoleDefinitionId = '2b629674-e913-4c01-ae53-ef4638d8f975'
var storageBlobDataContributorRoleDefinitionId = 'ba92f5b4-2d11-453d-a403-e96b0029c9fe'

resource eventHubNamespace 'Microsoft.EventHub/namespaces@2024-01-01' = if (deployEventStreaming) {
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
resource transactions 'Microsoft.EventHub/namespaces/eventhubs@2024-01-01' = if (deployEventStreaming) {
  name: 'transaction-posted-v1'
  parent: eventHubNamespace
  properties: {
    partitionCount: 2
    messageRetentionInDays: 1
  }
}
resource fraudConsumerGroup 'Microsoft.EventHub/namespaces/eventhubs/consumergroups@2024-01-01' = if (deployEventStreaming) {
  name: 'fraud-engine'
  parent: transactions
  properties: {}
}
resource lakeConsumerGroup 'Microsoft.EventHub/namespaces/eventhubs/consumergroups@2024-01-01' = if (deployEventStreaming) {
  name: 'lake-writer'
  parent: transactions
  properties: {}
}
resource bus 'Microsoft.ServiceBus/namespaces@2024-01-01' = if (deployServiceBus) {
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
resource highQueue 'Microsoft.ServiceBus/namespaces/queues@2024-01-01' = if (deployServiceBus) {
  name: 'high-fraud-cases'
  parent: bus
  properties: {
    requiresDuplicateDetection: true
    duplicateDetectionHistoryTimeWindow: 'P1D'
  }
}
resource lake 'Microsoft.Storage/storageAccounts@2023-05-01' = if (deployDataLake) {
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
resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = if (deployDataLake) {
  name: 'default'
  parent: lake
}
resource bronze 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = if (deployDataLake) {
  name: 'bronze'
  parent: blobService
  properties: { publicAccess: 'None' }
}
resource silver 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = if (deployDataLake) {
  name: 'silver'
  parent: blobService
  properties: { publicAccess: 'None' }
}
resource gold 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = if (deployDataLake) {
  name: 'gold'
  parent: blobService
  properties: { publicAccess: 'None' }
}

resource eventHubCheckpoints 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = if (deployDataLake) {
  name: 'eventhub-checkpoints'
  parent: blobService
  properties: { publicAccess: 'None' }
}
// Each independent consumer group has its own checkpoint container.
resource bronzeCheckpoints 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = if (deployDataLake && deployEventStreaming) {
  name: 'bronze-checkpoints'
  parent: blobService
  properties: { publicAccess: 'None' }
}

// Quarantine is a side zone for invalid records, not a fourth Medallion layer.
resource quarantine 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = if (deployDataLake) {
  name: 'quarantine'
  parent: blobService
  properties: { publicAccess: 'None' }
}

resource lakeLifecycle 'Microsoft.Storage/storageAccounts/managementPolicies@2023-05-01' = if (deployDataLake) {
  name: 'default'
  parent: lake
  properties: {
    policy: {
      rules: [
        {
          enabled: true
          name: 'delete-expired-quarantine'
          type: 'Lifecycle'
          definition: {
            actions: {
              baseBlob: {
                delete: {
                  daysAfterModificationGreaterThan: quarantineRetentionDays
                }
              }
            }
            filters: {
              blobTypes: [
                'blockBlob'
              ]
              prefixMatch: [
                'quarantine/'
              ]
            }
          }
        }
      ]
    }
  }
}

resource fraudReceiverRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (deployEventStreaming) {
  name: guid(transactions.id, workloadIdentityPrincipalId, eventHubsDataReceiverRoleDefinitionId)
  scope: transactions
  properties: {
    principalId: workloadIdentityPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', eventHubsDataReceiverRoleDefinitionId)
  }
}

resource checkpointWriterRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (deployDataLake) {
  name: guid(eventHubCheckpoints.id, workloadIdentityPrincipalId, storageBlobDataContributorRoleDefinitionId)
  scope: eventHubCheckpoints
  properties: {
    principalId: workloadIdentityPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', storageBlobDataContributorRoleDefinitionId)
  }
}

resource bronzeCheckpointWriterRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (deployDataLake && deployEventStreaming) {
  name: guid(bronzeCheckpoints.id, workloadIdentityPrincipalId, storageBlobDataContributorRoleDefinitionId)
  scope: bronzeCheckpoints
  properties: {
    principalId: workloadIdentityPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', storageBlobDataContributorRoleDefinitionId)
  }
}

// The future managed workload reads Bronze, writes Silver/Gold/Quarantine and
// uses the same receiver assignment scoped to the transaction Event Hub.
resource bronzeWriterRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (deployDataLake && deployEventStreaming) {
  name: guid(bronze.id, workloadIdentityPrincipalId, storageBlobDataContributorRoleDefinitionId)
  scope: bronze
  properties: {
    principalId: workloadIdentityPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', storageBlobDataContributorRoleDefinitionId)
  }
}

resource silverWriterRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (deployDataLake && deployEventStreaming) {
  name: guid(silver.id, workloadIdentityPrincipalId, storageBlobDataContributorRoleDefinitionId)
  scope: silver
  properties: {
    principalId: workloadIdentityPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', storageBlobDataContributorRoleDefinitionId)
  }
}

resource goldWriterRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (deployDataLake && deployEventStreaming) {
  name: guid(gold.id, workloadIdentityPrincipalId, storageBlobDataContributorRoleDefinitionId)
  scope: gold
  properties: {
    principalId: workloadIdentityPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', storageBlobDataContributorRoleDefinitionId)
  }
}

resource quarantineWriterRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (deployDataLake && deployEventStreaming) {
  name: guid(quarantine.id, workloadIdentityPrincipalId, storageBlobDataContributorRoleDefinitionId)
  scope: quarantine
  properties: {
    principalId: workloadIdentityPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', storageBlobDataContributorRoleDefinitionId)
  }
}

resource localIntegrationSenderRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (deployEventStreaming && !empty(localIntegrationPrincipalId)) {
  name: guid(transactions.id, localIntegrationPrincipalId, eventHubsDataSenderRoleDefinitionId)
  scope: transactions
  properties: {
    principalId: localIntegrationPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', eventHubsDataSenderRoleDefinitionId)
  }
}

resource localIntegrationReceiverRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (deployEventStreaming && !empty(localIntegrationPrincipalId)) {
  name: guid(transactions.id, localIntegrationPrincipalId, eventHubsDataReceiverRoleDefinitionId)
  scope: transactions
  properties: {
    principalId: localIntegrationPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', eventHubsDataReceiverRoleDefinitionId)
  }
}

resource localIntegrationCheckpointRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (deployDataLake && !empty(localIntegrationPrincipalId)) {
  name: guid(eventHubCheckpoints.id, localIntegrationPrincipalId, storageBlobDataContributorRoleDefinitionId)
  scope: eventHubCheckpoints
  properties: {
    principalId: localIntegrationPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', storageBlobDataContributorRoleDefinitionId)
  }
}

var deployedEventHubNamespaceName = eventHubNamespace.?name ?? ''
var deployedStorageAccountName = lake.?name ?? ''

output eventHubNamespaceName string = deployedEventHubNamespaceName
output eventHubFullyQualifiedNamespace string = empty(deployedEventHubNamespaceName)
  ? ''
  : '${deployedEventHubNamespaceName}.servicebus.windows.net'
output eventHubName string = transactions.?name ?? ''
output eventHubConsumerGroupName string = fraudConsumerGroup.?name ?? ''
output lakeConsumerGroupName string = lakeConsumerGroup.?name ?? ''
output serviceBusNamespaceName string = bus.?name ?? ''
output queueName string = highQueue.?name ?? ''
output storageAccountName string = deployedStorageAccountName
output blobAccountUrl string = empty(deployedStorageAccountName)
  ? ''
  : 'https://${deployedStorageAccountName}.blob.${environment().suffixes.storage}'
output checkpointContainerName string = eventHubCheckpoints.?name ?? ''
output bronzeCheckpointContainerName string = bronzeCheckpoints.?name ?? ''
output quarantineContainerName string = quarantine.?name ?? ''
output quarantineRetentionDaysApplied int = deployDataLake ? quarantineRetentionDays : 0
