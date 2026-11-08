// The real-Azure twin of docker-compose.yml.
// Deploy:   az group create -n rg-lab -l westeurope
//           az deployment group create -g rg-lab -f infra/main.bicep -p principalId=$(az ad signed-in-user show --query id -o tsv)
// Preview:  same command with `what-if` instead of `create`
// Tear down the same day: az group delete -n rg-lab --yes --no-wait
targetScope = 'resourceGroup'

@description('Short prefix for resource names (lowercase letters/digits).')
@maxLength(8)
param prefix string = 'lab'

param location string = resourceGroup().location

@description('Object id of the user or managed identity that gets data-plane access (az ad signed-in-user show --query id -o tsv).')
param principalId string

@description('Deploy Postgres Flexible Server (Burstable B1ms, ~13 USD/month while running).')
param deployPostgres bool = false

var suffix = uniqueString(resourceGroup().id)
var tags = { project: 'azure-local-lab', owner: 'mohammed-zakaria', ttl: 'delete-same-day' }

// ---------------------------------------------------------------- observability
resource logs 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: 'log-${prefix}-${suffix}'
  location: location
  tags: tags
  properties: { sku: { name: 'PerGB2018' }, retentionInDays: 30 }
}

resource appi 'Microsoft.Insights/components@2020-02-02' = {
  name: 'appi-${prefix}-${suffix}'
  location: location
  kind: 'web'
  tags: tags
  properties: { Application_Type: 'web', WorkspaceResourceId: logs.id }
}

// ---------------------------------------------------------------- storage (ADLS Gen2)
resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: take('st${prefix}${suffix}', 24)
  location: location
  tags: tags
  sku: { name: 'Standard_LRS' }
  kind: 'StorageV2'
  properties: {
    isHnsEnabled: true // hierarchical namespace = ADLS Gen2
    allowSharedKeyAccess: false // Entra ID only, same as cloudkit's azure mode
    minimumTlsVersion: 'TLS1_2'
    allowBlobPublicAccess: false
  }
}

resource blobSvc 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = {
  parent: storage
  name: 'default'
}

resource lakeContainers 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = [
  for c in ['bronze', 'silver', 'gold']: {
    parent: blobSvc
    name: c
  }
]

// ---------------------------------------------------------------- event hubs
resource ehns 'Microsoft.EventHub/namespaces@2024-01-01' = {
  name: 'evhns-${prefix}-${suffix}'
  location: location
  tags: tags
  sku: { name: 'Standard', tier: 'Standard', capacity: 1 } // Standard = Kafka endpoint
  properties: { disableLocalAuth: true, kafkaEnabled: true }
}

resource hubs 'Microsoft.EventHub/namespaces/eventhubs@2024-01-01' = [
  for h in ['transactions', 'telemetry']: {
    parent: ehns
    name: h
    properties: { partitionCount: 2, messageRetentionInDays: 1 }
  }
]

// ---------------------------------------------------------------- service bus
resource sbns 'Microsoft.ServiceBus/namespaces@2022-10-01-preview' = {
  name: 'sbns-${prefix}-${suffix}'
  location: location
  tags: tags
  sku: { name: 'Basic', tier: 'Basic' }
  properties: { disableLocalAuth: true }
}

resource alertsQueue 'Microsoft.ServiceBus/namespaces/queues@2022-10-01-preview' = {
  parent: sbns
  name: 'alerts'
  properties: { maxDeliveryCount: 5, defaultMessageTimeToLive: 'PT1H' }
}

// ---------------------------------------------------------------- key vault
resource kv 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: take('kv-${prefix}-${suffix}', 24)
  location: location
  tags: tags
  properties: {
    tenantId: subscription().tenantId
    sku: { family: 'A', name: 'standard' }
    enableRbacAuthorization: true
    enableSoftDelete: true
    softDeleteRetentionInDays: 7
  }
}

// ---------------------------------------------------------------- postgres (optional)
resource pg 'Microsoft.DBforPostgreSQL/flexibleServers@2024-08-01' = if (deployPostgres) {
  name: 'psql-${prefix}-${suffix}'
  location: location
  tags: tags
  sku: { name: 'Standard_B1ms', tier: 'Burstable' }
  properties: {
    version: '16'
    storage: { storageSizeGB: 32 }
    authConfig: { activeDirectoryAuth: 'Enabled', passwordAuth: 'Disabled', tenantId: subscription().tenantId }
  }
}

resource pgVector 'Microsoft.DBforPostgreSQL/flexibleServers/configurations@2024-08-01' = if (deployPostgres) {
  parent: pg
  name: 'azure.extensions'
  properties: { value: 'VECTOR', source: 'user-override' }
}

// ---------------------------------------------------------------- RBAC (least privilege, data plane)
var roles = {
  blobDataContributor: 'ba92f5b4-2d11-453d-a403-e96b0029c9fe'
  eventHubsDataOwner: 'f526a384-b230-433a-b45c-95f59c4a2dec'
  serviceBusDataOwner: '090c5cfd-751d-490a-894a-3ce6f1109419'
  keyVaultSecretsOfficer: 'b86a8fe4-44ce-4948-aee5-eccb2c155cd7'
}

resource raBlob 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: storage
  name: guid(storage.id, principalId, roles.blobDataContributor)
  properties: { principalId: principalId, roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.blobDataContributor) }
}

resource raEh 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: ehns
  name: guid(ehns.id, principalId, roles.eventHubsDataOwner)
  properties: { principalId: principalId, roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.eventHubsDataOwner) }
}

resource raSb 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: sbns
  name: guid(sbns.id, principalId, roles.serviceBusDataOwner)
  properties: { principalId: principalId, roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.serviceBusDataOwner) }
}

resource raKv 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: kv
  name: guid(kv.id, principalId, roles.keyVaultSecretsOfficer)
  properties: { principalId: principalId, roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.keyVaultSecretsOfficer) }
}

// ---------------------------------------------------------------- outputs = cloudkit env vars
output CLOUDKIT_MODE string = 'azure'
output AZURE_STORAGE_ACCOUNT string = storage.name
output AZURE_EVENTHUBS_NAMESPACE string = ehns.name
output AZURE_SERVICEBUS_NAMESPACE string = sbns.name
output AZURE_KEY_VAULT_NAME string = kv.name
output APPLICATIONINSIGHTS_CONNECTION_STRING string = appi.properties.ConnectionString
