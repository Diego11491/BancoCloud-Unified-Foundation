# Azure cost-controlled slice

## Objetivo

El primer corte desplegable reduce costo y superficie operativa. Por defecto,
`main-lite.bicep` incluye únicamente:

- una User Assigned Managed Identity;
- Event Hubs Standard, `transaction-posted-v1` y el consumer group
  `fraud-engine`;
- una cuenta ADLS Gen2 con Bronze, Silver, Gold, Quarantine y el contenedor
  privado `eventhub-checkpoints`;
- RBAC del worker limitado a Receiver sobre el Event Hub y Blob Data
  Contributor sobre el contenedor de checkpoint.

Azure SQL, Service Bus, Log Analytics, Application Insights, Container Registry
y Key Vault permanecen deshabilitados. Container Apps no forma parte de
`main-lite.bicep` y continúa bloqueado hasta contar con persistencia Azure
compatible.

## Feature flags

| Parámetro | Predeterminado | Alcance |
| --- | --- | --- |
| `deployEventStreaming` | `true` | Event Hubs, hub y consumer group |
| `deployDataLake` | `true` | ADLS, zonas, checkpoint y lifecycle |
| `deploySql` | `false` | Azure SQL y base operacional |
| `deployServiceBus` | `false` | Namespace y cola HIGH |
| `deployObservability` | `false` | Log Analytics y Application Insights |
| `deployContainerRegistry` | `false` | ACR y AcrPull de la identidad |
| `deployKeyVault` | `false` | Key Vault y acceso de la identidad |

Event streaming activa siempre Data Lake porque el consumidor necesita checkpoint
durable, incluso si se intenta pasar `deployDataLake=false`. Las credenciales SQL
solo se validan por el módulo de datos cuando `deploySql=true`.

## Preflight sin despliegue

Usar exclusivamente un Resource Group dedicado y vacío. El script no contiene
`az deployment group create`; ejecuta lint, build, validación ARM y what-if.

```powershell
.\scripts\azure_cost_slice_preflight.ps1 `
    -ResourceGroup "rg-bancocloud-student-lite" `
    -Location "brazilsouth" `
    -Suffix "dv260929" `
    -Owner "diego-ventura" `
    -Expiry "2026-10-06"
```

No pasar `LocalIntegrationPrincipalId` hasta disponer de una identidad de
integración temporal aprobada. Si se proporciona, el what-if también declarará
Sender/Receiver de Event Hubs y acceso al checkpoint para ese principal.

El gate exige:

- validación ARM `Succeeded`;
- al menos Managed Identity, Event Hubs y Storage en el preview;
- cero SQL, Service Bus, ACR, observabilidad y Key Vault;
- cero cambios `Delete` y `Modify`;
- elementos `Unsupported` limitados a asignaciones RBAC dependientes del
  `principalId` creado durante el despliegue;
- cero recursos reales antes y después del what-if.

## Evidencia observada

El 29/09/2026 el preflight terminó en PASS sobre la suscripción con rol Owner y
región `brazilsouth`: validación ARM `Succeeded`, 12 cambios `Create`, 2 cambios
`Unsupported` limitados a RBAC, 0 `Modify`, 0 `Delete` y 0 recursos realmente
desplegados. El resumen sanitizado está en
`evidence/azure-cost-controlled-slice-summary.json`.

## Decisión posterior

Un preflight exitoso no autoriza el despliegue. Antes de ejecutar `create` se
deben registrar precio estimado, responsable, hora de teardown y evidencia del
Resource Group. El primer despliegue real será una acción manual separada; nunca
se activa automáticamente por `push`.
