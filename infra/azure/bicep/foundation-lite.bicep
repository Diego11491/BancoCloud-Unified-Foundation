// Identity plus optional registry, secrets boundary and observability for STUDENT LITE.
// The cost-controlled slice creates only the identity. No secret values are created.
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

@description('Keep false in the disposable Student environment so teardown can purge the vault')
param enablePurgeProtection bool = false

@description('Deploy Log Analytics and Application Insights')
param deployObservability bool = false

@description('Deploy Azure Container Registry and its AcrPull assignment')
param deployContainerRegistry bool = false

@description('Deploy Key Vault and its secrets-user assignment')
param deployKeyVault bool = false

var tags = {
  project: 'bancocloud'
  environment: 'student-lite'
  owner: owner
  expiry: expiry
}

var acrPullRoleDefinitionId = '7f951dda-4ed3-4680-a7ca-43fe172d538d'
var keyVaultSecretsUserRoleDefinitionId = '4633458b-17de-408a-b874-0445c86b69e6'

resource workloadIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: 'bc-workload-${suffix}'
  location: location
  tags: tags
}

resource logWorkspace 'Microsoft.OperationalInsights/workspaces@2023-09-01' = if (deployObservability) {
  name: 'bc-law-${suffix}'
  location: location
  tags: tags
  properties: {
    features: {
      disableLocalAuth: false
      enableLogAccessUsingOnlyResourcePermissions: true
    }
    publicNetworkAccessForIngestion: 'Enabled'
    publicNetworkAccessForQuery: 'Enabled'
    retentionInDays: 30
    sku: {
      name: 'PerGB2018'
    }
    workspaceCapping: {
      dailyQuotaGb: logDailyQuotaGb
    }
  }
}

resource appInsights 'Microsoft.Insights/components@2020-02-02' = if (deployObservability) {
  name: 'bc-appi-${suffix}'
  location: location
  kind: 'web'
  tags: tags
  properties: {
    Application_Type: 'web'
    DisableIpMasking: false
    DisableLocalAuth: false
    IngestionMode: 'LogAnalytics'
    Request_Source: 'rest'
    RetentionInDays: 30
    SamplingPercentage: 25
    WorkspaceResourceId: logWorkspace.id
    publicNetworkAccessForIngestion: 'Enabled'
    publicNetworkAccessForQuery: 'Enabled'
  }
}

resource registry 'Microsoft.ContainerRegistry/registries@2023-07-01' = if (deployContainerRegistry) {
  name: 'bcacr${suffix}'
  location: location
  tags: tags
  sku: {
    name: 'Basic'
  }
  properties: {
    adminUserEnabled: false
    dataEndpointEnabled: false
    publicNetworkAccess: 'Enabled'
  }
}

resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' = if (deployKeyVault) {
  name: 'bc-kv-${suffix}'
  location: location
  tags: tags
  properties: {
    enabledForDeployment: false
    enabledForDiskEncryption: false
    enabledForTemplateDeployment: false
    enablePurgeProtection: enablePurgeProtection
    enableRbacAuthorization: true
    enableSoftDelete: true
    publicNetworkAccess: 'Enabled'
    softDeleteRetentionInDays: 7
    tenantId: tenant().tenantId
    sku: {
      family: 'A'
      name: 'standard'
    }
    networkAcls: {
      bypass: 'AzureServices'
      defaultAction: 'Allow'
    }
  }
}

resource acrPullAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (deployContainerRegistry) {
  name: guid(registry.id, workloadIdentity.id, acrPullRoleDefinitionId)
  scope: registry
  properties: {
    principalId: workloadIdentity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', acrPullRoleDefinitionId)
  }
}

resource keyVaultSecretsUserAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (deployKeyVault) {
  name: guid(keyVault.id, workloadIdentity.id, keyVaultSecretsUserRoleDefinitionId)
  scope: keyVault
  properties: {
    principalId: workloadIdentity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', keyVaultSecretsUserRoleDefinitionId)
  }
}

output workloadIdentityId string = workloadIdentity.id
output workloadIdentityClientId string = workloadIdentity.properties.clientId
output workloadIdentityPrincipalId string = workloadIdentity.properties.principalId

output logAnalyticsWorkspaceId string = logWorkspace.?id ?? ''
output applicationInsightsName string = appInsights.?name ?? ''

output containerRegistryId string = registry.?id ?? ''
output containerRegistryName string = registry.?name ?? ''
output containerRegistryLoginServer string = registry.?properties.?loginServer ?? ''

output keyVaultId string = keyVault.?id ?? ''
output keyVaultName string = keyVault.?name ?? ''
output keyVaultUri string = keyVault.?properties.?vaultUri ?? ''
