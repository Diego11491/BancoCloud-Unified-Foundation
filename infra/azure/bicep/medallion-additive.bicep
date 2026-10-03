// Add the Medallion consumer and container to an already deployed Student slice.
// Existing resources are references: this template never redeploys their properties.
targetScope = 'resourceGroup'

@description('Suffix used by the existing Event Hubs, Storage and Managed Identity resources')
@minLength(6)
@maxLength(12)
param suffix string

@description('Object ID of the existing bc-workload user-assigned identity (not a secret)')
@minLength(36)
@maxLength(36)
param workloadIdentityPrincipalId string

var blobContributorRoleId = 'ba92f5b4-2d11-453d-a403-e96b0029c9fe'

resource eventHubNamespace 'Microsoft.EventHub/namespaces@2024-01-01' existing = {
  name: 'bceh${suffix}'
}

resource transactions 'Microsoft.EventHub/namespaces/eventhubs@2024-01-01' existing = {
  name: 'transaction-posted-v1'
  parent: eventHubNamespace
}

resource lakeConsumerGroup 'Microsoft.EventHub/namespaces/eventhubs/consumergroups@2024-01-01' = {
  name: 'lake-writer'
  parent: transactions
  properties: {}
}

resource lake 'Microsoft.Storage/storageAccounts@2023-05-01' existing = {
  name: 'bclake${suffix}'
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' existing = {
  name: 'default'
  parent: lake
}

resource bronze 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' existing = {
  name: 'bronze'
  parent: blobService
}

resource silver 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' existing = {
  name: 'silver'
  parent: blobService
}

resource gold 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' existing = {
  name: 'gold'
  parent: blobService
}

resource quarantine 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' existing = {
  name: 'quarantine'
  parent: blobService
}

resource bronzeCheckpoints 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  name: 'bronze-checkpoints'
  parent: blobService
  properties: {
    publicAccess: 'None'
  }
}

// The existing Event Hubs receiver role remains in the original deployment.
// Add only container-scoped Blob access for the future managed workload.
resource bronzeCheckpointWriterRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(bronzeCheckpoints.id, workloadIdentityPrincipalId, blobContributorRoleId)
  scope: bronzeCheckpoints
  properties: {
    principalId: workloadIdentityPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', blobContributorRoleId)
  }
}

resource bronzeWriterRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(bronze.id, workloadIdentityPrincipalId, blobContributorRoleId)
  scope: bronze
  properties: {
    principalId: workloadIdentityPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', blobContributorRoleId)
  }
}

resource silverWriterRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(silver.id, workloadIdentityPrincipalId, blobContributorRoleId)
  scope: silver
  properties: {
    principalId: workloadIdentityPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', blobContributorRoleId)
  }
}

resource goldWriterRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(gold.id, workloadIdentityPrincipalId, blobContributorRoleId)
  scope: gold
  properties: {
    principalId: workloadIdentityPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', blobContributorRoleId)
  }
}

resource quarantineWriterRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(quarantine.id, workloadIdentityPrincipalId, blobContributorRoleId)
  scope: quarantine
  properties: {
    principalId: workloadIdentityPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', blobContributorRoleId)
  }
}
