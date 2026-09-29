// Student LITE messaging and governed lake zones. Preview before any deployment.
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

var tags = {
  project: 'bancocloud'
  environment: 'student-lite'
  owner: owner
  expiry: expiry
}

var eventHubsDataReceiverRoleDefinitionId = 'a638d3c7-ab3a-418d-83e6-5f17a39d4fde'
var eventHubsDataSenderRoleDefinitionId = '2b629674-e913-4c01-ae53-ef4638d8f975'
var storageBlobDataContributorRoleDefinitionId = 'ba92f5b4-2d11-453d-a403-e96b0029c9fe'

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
resource fraudConsumerGroup 'Microsoft.EventHub/namespaces/eventhubs/consumergroups@2024-01-01' = {
  name: 'fraud-engine'
  parent: transactions
  properties: {}
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

resource eventHubCheckpoints 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  name: 'eventhub-checkpoints'
  parent: blobService
  properties: { publicAccess: 'None' }
}

// Quarantine is a side zone for invalid records, not a fourth Medallion layer.
resource quarantine 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  name: 'quarantine'
  parent: blobService
  properties: { publicAccess: 'None' }
}

resource lakeLifecycle 'Microsoft.Storage/storageAccounts/managementPolicies@2023-05-01' = {
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

resource fraudReceiverRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(transactions.id, workloadIdentityPrincipalId, eventHubsDataReceiverRoleDefinitionId)
  scope: transactions
  properties: {
    principalId: workloadIdentityPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', eventHubsDataReceiverRoleDefinitionId)
  }
}

resource checkpointWriterRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(eventHubCheckpoints.id, workloadIdentityPrincipalId, storageBlobDataContributorRoleDefinitionId)
  scope: eventHubCheckpoints
  properties: {
    principalId: workloadIdentityPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', storageBlobDataContributorRoleDefinitionId)
  }
}

resource localIntegrationSenderRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(localIntegrationPrincipalId)) {
  name: guid(transactions.id, localIntegrationPrincipalId, eventHubsDataSenderRoleDefinitionId)
  scope: transactions
  properties: {
    principalId: localIntegrationPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', eventHubsDataSenderRoleDefinitionId)
  }
}

resource localIntegrationReceiverRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(localIntegrationPrincipalId)) {
  name: guid(transactions.id, localIntegrationPrincipalId, eventHubsDataReceiverRoleDefinitionId)
  scope: transactions
  properties: {
    principalId: localIntegrationPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', eventHubsDataReceiverRoleDefinitionId)
  }
}

resource localIntegrationCheckpointRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(localIntegrationPrincipalId)) {
  name: guid(eventHubCheckpoints.id, localIntegrationPrincipalId, storageBlobDataContributorRoleDefinitionId)
  scope: eventHubCheckpoints
  properties: {
    principalId: localIntegrationPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', storageBlobDataContributorRoleDefinitionId)
  }
}

output eventHubNamespaceName string = eventHubNamespace.name
output eventHubFullyQualifiedNamespace string = '${eventHubNamespace.name}.servicebus.windows.net'
output eventHubName string = transactions.name
output eventHubConsumerGroupName string = fraudConsumerGroup.name
output serviceBusNamespaceName string = bus.name
output queueName string = highQueue.name
output storageAccountName string = lake.name
output blobAccountUrl string = 'https://${lake.name}.blob.${environment().suffixes.storage}'
output checkpointContainerName string = eventHubCheckpoints.name
output quarantineContainerName string = quarantine.name
output quarantineRetentionDaysApplied int = quarantineRetentionDays
