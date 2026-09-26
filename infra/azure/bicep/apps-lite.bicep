// BancoCloud STUDENT LITE application layer.
// Deploy only after the fraud image exists in ACR.
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

@description('Resource ID of the user-assigned managed identity')
param workloadIdentityId string

@description('Azure Container Registry login server')
param containerRegistryLoginServer string

@description('Complete fraud image reference, including immutable tag')
param fraudContainerImage string

@description('Log Analytics workspace customer ID')
param logAnalyticsCustomerId string

@secure()
@description('Log Analytics workspace shared key')
param logAnalyticsSharedKey string

var tags = {
  project: 'bancocloud'
  environment: 'student-lite'
  owner: owner
  expiry: expiry
}

resource containerEnvironment 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: 'bc-cae-${suffix}'
  location: location
  tags: tags
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalyticsCustomerId
        sharedKey: logAnalyticsSharedKey
      }
    }
  }
}

resource fraudApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: 'bc-fraud-${suffix}'
  location: location
  tags: tags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${workloadIdentityId}': {}
    }
  }
  properties: {
    environmentId: containerEnvironment.id
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: false
        allowInsecure: false
        targetPort: 8000
        transport: 'auto'
      }
      registries: [
        {
          server: containerRegistryLoginServer
          identity: workloadIdentityId
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'fraud'
          image: fraudContainerImage
          env: [
            {
              name: 'SERVICE_NAME'
              value: 'bancocloud-fraud'
            }
            {
              name: 'DEPLOYMENT_MODE'
              value: 'STUDENT_LITE'
            }
          ]
          resources: {
            cpu: json('0.25')
            memory: '0.5Gi'
          }
        }
      ]
      scale: {
        minReplicas: 0
        maxReplicas: 1
      }
    }
  }
}

output containerEnvironmentId string = containerEnvironment.id
output containerEnvironmentName string = containerEnvironment.name
output fraudContainerAppId string = fraudApp.id
output fraudContainerAppName string = fraudApp.name
output fraudInternalFqdn string = fraudApp.properties.configuration.ingress.fqdn