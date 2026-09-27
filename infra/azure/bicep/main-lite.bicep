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

@description('SQL administrator login name')
@minLength(1)
@maxLength(128)
param sqlAdministratorLogin string

@secure()
@description('SQL administrator password supplied only during deployment')
param sqlAdministratorPassword string

module messaging './messaging-lite.bicep' = {
  name: 'messaging-${uniqueString(resourceGroup().id, suffix)}'
  params: {
    suffix: suffix
    location: location
    owner: owner
    expiry: expiry
    quarantineRetentionDays: quarantineRetentionDays
  }
}

module foundation './foundation-lite.bicep' = {
  name: 'foundation-${uniqueString(resourceGroup().id, suffix)}'
  params: {
    suffix: suffix
    location: location
    owner: owner
    expiry: expiry
    logDailyQuotaGb: logDailyQuotaGb
    enablePurgeProtection: enablePurgeProtection
  }
}

module data './data-lite.bicep' = {
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

output deploymentMode string = 'STUDENT_LITE_STATIC_PREFLIGHT'

output eventHubNamespaceName string = messaging.outputs.eventHubNamespaceName
output eventHubName string = messaging.outputs.eventHubName
output serviceBusNamespaceName string = messaging.outputs.serviceBusNamespaceName
output highFraudQueueName string = messaging.outputs.queueName
output storageAccountName string = messaging.outputs.storageAccountName
output quarantineContainerName string = messaging.outputs.quarantineContainerName
output quarantineRetentionDaysApplied int = messaging.outputs.quarantineRetentionDaysApplied

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

output sqlServerId string = data.outputs.sqlServerId
output sqlServerName string = data.outputs.sqlServerName
output sqlServerFqdn string = data.outputs.sqlServerFqdn
output databaseId string = data.outputs.databaseId
output databaseName string = data.outputs.databaseName
output databaseSku string = data.outputs.databaseSku
