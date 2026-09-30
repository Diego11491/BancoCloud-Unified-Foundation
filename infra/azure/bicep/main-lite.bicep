// BancoCloud STUDENT LITE composition root.
// Static validation is allowed; deployment requires cost and security gates.
targetScope = 'resourceGroup'

@description('Unique lowercase project suffix; use letters and digits only')
@minLength(6)
@maxLength(12)
param suffix string

@description('The Azure region confirmed for the subscription')
param location string = resourceGroup().location

@description('Named human owner; do not use a personal email address')
@minLength(2)
@maxLength(64)
param owner string

@description('Resource expiry date in YYYY-MM-DD format')
@minLength(10)
@maxLength(10)
param expiry string

@description('Maximum Log Analytics ingestion per day in GB')
@minValue(1)
@maxValue(1)
param logDailyQuotaGb int = 1

@description('Days to retain rejected records in the quarantine container')
@minValue(1)
@maxValue(90)
param quarantineRetentionDays int = 30

@description('Keep false in the disposable Student environment')
param enablePurgeProtection bool = false

@description('Deploy Event Hubs and its consumer group')
param deployEventStreaming bool = true

@description('Deploy ADLS Gen2, Medallion zones, Quarantine and checkpoint storage')
param deployDataLake bool = true

@description('Deploy Azure SQL. Disabled in the first cost-controlled slice')
param deploySql bool = false

@description('Deploy Service Bus. Disabled in the first cost-controlled slice')
param deployServiceBus bool = false

@description('Deploy Log Analytics and Application Insights')
param deployObservability bool = false

@description('Deploy Azure Container Registry')
param deployContainerRegistry bool = false

@description('Deploy Key Vault')
param deployKeyVault bool = false

@description('SQL administrator login; required only when deploySql is true')
@maxLength(128)
param sqlAdministratorLogin string = ''

@secure()
@description('SQL administrator password; required only when deploySql is true')
param sqlAdministratorPassword string = ''

@description('Optional Entra service principal object ID for the temporary local Event Hubs integration')
param localIntegrationPrincipalId string = ''

// Event consumers require durable checkpoint storage. Enabling streaming therefore
// always enables the lake/checkpoint account even if deployDataLake is passed false.
var effectiveDeployDataLake = deployDataLake || deployEventStreaming

module foundation './foundation-lite.bicep' = {
  name: 'foundation-${uniqueString(resourceGroup().id, suffix)}'
  params: {
    suffix: suffix
    location: location
    owner: owner
    expiry: expiry
    logDailyQuotaGb: logDailyQuotaGb
    enablePurgeProtection: enablePurgeProtection
    deployObservability: deployObservability
    deployContainerRegistry: deployContainerRegistry
    deployKeyVault: deployKeyVault
  }
}

module messaging './messaging-lite.bicep' = if (deployEventStreaming || effectiveDeployDataLake || deployServiceBus) {
  name: 'messaging-${uniqueString(resourceGroup().id, suffix)}'
  params: {
    suffix: suffix
    location: location
    owner: owner
    expiry: expiry
    quarantineRetentionDays: quarantineRetentionDays
    workloadIdentityPrincipalId: foundation.outputs.workloadIdentityPrincipalId
    localIntegrationPrincipalId: localIntegrationPrincipalId
    deployEventStreaming: deployEventStreaming
    deployDataLake: effectiveDeployDataLake
    deployServiceBus: deployServiceBus
  }
}

module data './data-lite.bicep' = if (deploySql) {
  name: 'data-${uniqueString(resourceGroup().id, suffix)}'
  params: {
    suffix: suffix
    location: location
    owner: owner
    expiry: expiry
    sqlAdministratorLogin: sqlAdministratorLogin
    sqlAdministratorPassword: sqlAdministratorPassword
  }
}

output deploymentMode string = 'STUDENT_LITE_COST_CONTROLLED'

output deploymentFeatures object = {
  managedIdentity: true
  eventStreaming: deployEventStreaming
  dataLake: effectiveDeployDataLake
  sql: deploySql
  serviceBus: deployServiceBus
  observability: deployObservability
  containerRegistry: deployContainerRegistry
  keyVault: deployKeyVault
}

output eventHubNamespaceName string = messaging.?outputs.?eventHubNamespaceName ?? ''
output eventHubFullyQualifiedNamespace string = messaging.?outputs.?eventHubFullyQualifiedNamespace ?? ''
output eventHubName string = messaging.?outputs.?eventHubName ?? ''
output eventHubConsumerGroupName string = messaging.?outputs.?eventHubConsumerGroupName ?? ''
output serviceBusNamespaceName string = messaging.?outputs.?serviceBusNamespaceName ?? ''
output highFraudQueueName string = messaging.?outputs.?queueName ?? ''
output storageAccountName string = messaging.?outputs.?storageAccountName ?? ''
output blobAccountUrl string = messaging.?outputs.?blobAccountUrl ?? ''
output checkpointContainerName string = messaging.?outputs.?checkpointContainerName ?? ''
output quarantineContainerName string = messaging.?outputs.?quarantineContainerName ?? ''
output quarantineRetentionDaysApplied int = messaging.?outputs.?quarantineRetentionDaysApplied ?? 0

output workloadIdentityId string = foundation.outputs.workloadIdentityId
output workloadIdentityClientId string = foundation.outputs.workloadIdentityClientId
output workloadIdentityPrincipalId string = foundation.outputs.workloadIdentityPrincipalId

output logAnalyticsWorkspaceId string = foundation.outputs.logAnalyticsWorkspaceId
output applicationInsightsName string = foundation.outputs.applicationInsightsName

output containerRegistryId string = foundation.outputs.containerRegistryId
output containerRegistryName string = foundation.outputs.containerRegistryName
output containerRegistryLoginServer string = foundation.outputs.containerRegistryLoginServer

output keyVaultId string = foundation.outputs.keyVaultId
output keyVaultName string = foundation.outputs.keyVaultName
output keyVaultUri string = foundation.outputs.keyVaultUri

output sqlServerId string = data.?outputs.?sqlServerId ?? ''
output sqlServerName string = data.?outputs.?sqlServerName ?? ''
output sqlServerFqdn string = data.?outputs.?sqlServerFqdn ?? ''
output databaseId string = data.?outputs.?databaseId ?? ''
output databaseName string = data.?outputs.?databaseName ?? ''
output databaseSku string = data.?outputs.?databaseSku ?? ''
