// BancoCloud STUDENT LITE data layer.
// Static validation only. Deployment requires cost and network gates.
targetScope = 'resourceGroup'

@description('Unique lowercase project suffix; use letters and digits only')
@minLength(6)
@maxLength(12)
param suffix string

@description('Azure region confirmed for the subscription')
param location string = resourceGroup().location

@description('Named human owner; do not use a personal email address')
@minLength(2)
@maxLength(64)
param owner string

@description('Resource expiry date in YYYY-MM-DD format')
@minLength(10)
@maxLength(10)
param expiry string

@description('SQL administrator login name')
@minLength(1)
@maxLength(128)
param sqlAdministratorLogin string

@secure()
@description('SQL administrator password supplied only during deployment')
param sqlAdministratorPassword string

var tags = {
  project: 'bancocloud'
  environment: 'student-lite'
  owner: owner
  expiry: expiry
}

resource sqlServer 'Microsoft.Sql/servers@2023-08-01' = {
  name: 'bc-sql-${suffix}'
  location: location
  tags: tags
  properties: {
    administratorLogin: sqlAdministratorLogin
    administratorLoginPassword: sqlAdministratorPassword
    minimalTlsVersion: '1.2'
    publicNetworkAccess: 'Enabled'
    restrictOutboundNetworkAccess: 'Disabled'
    version: '12.0'
  }
}

resource operationalDatabase 'Microsoft.Sql/servers/databases@2023-08-01' = {
  name: 'bancoclouddb'
  parent: sqlServer
  location: location
  tags: tags
  sku: {
    name: 'Basic'
    tier: 'Basic'
    capacity: 5
  }
  properties: {
    collation: 'SQL_Latin1_General_CP1_CI_AS'
    createMode: 'Default'
    maxSizeBytes: 2147483648
    requestedBackupStorageRedundancy: 'Local'
    zoneRedundant: false
  }
}

output sqlServerId string = sqlServer.id
output sqlServerName string = sqlServer.name
output sqlServerFqdn string = sqlServer.properties.fullyQualifiedDomainName

output databaseId string = operationalDatabase.id
output databaseName string = operationalDatabase.name
output databaseSku string = operationalDatabase.sku.name