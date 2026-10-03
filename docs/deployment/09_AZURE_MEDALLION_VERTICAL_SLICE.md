# Corte Medallion en ADLS Gen2 — fase de ejecución

## Alcance y límites

El core y los procesos Python siguen locales. Un consumidor `lake-writer` lee el
mismo `transaction-posted-v1` desde **otro consumer group** y aterriza cada cuerpo
raw inmutable en `bronze/events/<sha256>.json`. Guarda su offset en el contenedor
privado `bronze-checkpoints`, separado de `eventhub-checkpoints` de `fraud-engine`.
Releer un cuerpo idéntico no crea otro blob ni adelanta el checkpoint antes de
confirmar la escritura. La promoción batch reutiliza `bancocloud.cold.project`:
valida el contrato, deduplica `event_id`, desvía inválidos a Quarantine y publica
Silver, Gold y conciliación bajo `runs/<run_id>/`. El manifiesto de Gold se escribe
al final y solo entonces el run está completo.

El core, el publicador y el consumidor Bronze continúan en la PC. La promoción
Silver/Gold se ejecutó también en Azure como un Container Apps Job manual con
identidad administrada; no hay un proceso Medallion permanentemente encendido.
Este MVP no contiene Synapse, un modelo ML online ni Azure OpenAI. Usa
exclusivamente eventos sintéticos.

## Antes del cambio de infraestructura

Desde la rama que contiene este cambio y en PowerShell, comprobar la suscripción
Owner y la región. El preflight inicial de fase 4 exigía un grupo **vacío** y
ya no se debe reutilizar sobre el grupo desplegado. El `what-if` detallado
de `main-lite.bicep` mostró ocho `Modify` en recursos existentes. Para este
incremento se despliega solo `medallion-additive.bicep`, que los referencia
como `existing` y no reenvía sus propiedades.

```powershell
$rg = "rg-bancocloud-student-lite"
$ownerId = (az account show --query id --output tsv).Trim()
$region = (az group show --name $rg --query location --output tsv).Trim()
if ($region -ne "brazilsouth") { throw "Región incorrecta" }
$objectId = (az ad signed-in-user show --query id --output tsv).Trim()
$roles = @(az role assignment list --assignee-object-id $objectId `
    --scope "/subscriptions/$ownerId" --include-inherited --include-groups `
    --query "[].roleDefinitionName" --output tsv)
if ($LASTEXITCODE -ne 0 -or $roles -notcontains "Owner") { throw "Falta Owner en esta suscripción" }

$template = ".\infra\azure\bicep\medallion-additive.bicep"
az bicep lint --file $template --no-restore
if ($LASTEXITCODE -ne 0) { throw "El Bicep aditivo no superó lint" }

$principalId = (az identity show --resource-group $rg `
    --name "bc-workload-dv260929" --query principalId --output tsv).Trim()
if ($LASTEXITCODE -ne 0 -or $principalId -notmatch '^[0-9a-fA-F-]{36}$') {
    throw "No se encontró la identidad ya desplegada"
}
$deployArgs = @("suffix=dv260929", "workloadIdentityPrincipalId=$principalId")
az deployment group validate --subscription $ownerId --resource-group $rg `
    --name bancocloud-medallion-validate `
    --template-file $template --parameters @deployArgs --output none
if ($LASTEXITCODE -ne 0) { throw "ARM validate falló" }

az deployment group what-if --subscription $ownerId --resource-group $rg `
    --name bancocloud-medallion-whatif `
    --template-file $template --parameters @deployArgs `
    --result-format FullResourcePayloads --exclude-change-types NoChange Ignore
if ($LASTEXITCODE -ne 0) { throw "What-if falló" }
```

Verificar exactamente dos nuevos recursos (`lake-writer`, `bronze-checkpoints`)
y cinco asignaciones `Storage Blob Data Contributor` para la identidad
administrada, una por contenedor. No ejecutar el siguiente bloque si aparece
`Delete`, `Modify`, `Unsupported`, otro recurso o un error de policy. Los roles
previos del fraude y su checkpoint no forman parte de esta plantilla.

```powershell
az deployment group create --subscription $ownerId --resource-group $rg `
    --name bancocloud-medallion-20261002 `
    --template-file $template --mode Incremental --parameters @deployArgs `
    --confirm-with-what-if --what-if-result-format FullResourcePayloads `
    --output none
if ($LASTEXITCODE -ne 0) { throw "El despliegue Medallion falló" }
```

## Identidad temporal de la PC

El tenant académico impidió crear un service principal de demostración. La
sesión `az login` de la PC ya dispone de Receiver sobre el Event Hub para el
fraude. Para este corte, dar al usuario `Storage Blob Data Contributor` solo
sobre los cinco contenedores necesarios. Estas asignaciones temporales se
revocan con el teardown. El Job manual alojado en Azure usa la Managed Identity
para leer/escribir ADLS y leer la imagen de ACR; Python local usa Azure CLI.

```powershell
$userObjectId = (az ad signed-in-user show --query id --output tsv).Trim()
$storageId = (az storage account show --resource-group $rg `
    --name bclakedv260929 --query id --output tsv).Trim()
if (-not $userObjectId -or -not $storageId) { throw "Identidad o Storage no encontrado" }

foreach ($zone in @("bronze", "bronze-checkpoints", "silver", "gold", "quarantine")) {
    $scope = "$storageId/blobServices/default/containers/$zone"
    $existing = @(az role assignment list --assignee-object-id $userObjectId `
        --scope $scope --query "[?roleDefinitionName=='Storage Blob Data Contributor'].id" `
        --output tsv)
    if ($LASTEXITCODE -ne 0) { throw "No se pudo consultar RBAC de $zone" }
    if (-not @($existing | Where-Object { $_ }).Count) {
        az role assignment create --assignee-object-id $userObjectId `
            --assignee-principal-type User --scope $scope `
            --role "Storage Blob Data Contributor" --output none
        if ($LASTEXITCODE -ne 0) { throw "No se pudo asignar RBAC de $zone" }
    }
}
```

## Ejecutar y verificar

Instalar dependencias opcionales con `python -m pip install -r requirements-azure.txt`.
En una terminal **nueva** del repositorio, con Azure CLI apuntando a la suscripción
Owner, definir sin secretos:

```powershell
$env:AZURE_EVENTHUB_FULLY_QUALIFIED_NAMESPACE = "bcehdv260929.servicebus.windows.net"
$env:AZURE_EVENTHUB_NAME = "transaction-posted-v1"
$env:AZURE_BLOB_ACCOUNT_URL = "https://bclakedv260929.blob.core.windows.net"
Remove-Item Env:AZURE_CLIENT_ID,Env:AZURE_CLIENT_SECRET,Env:AZURE_MANAGED_IDENTITY_CLIENT_ID `
    -ErrorAction SilentlyContinue
python -m bancocloud.azure_bronze_worker
```

El consumidor empieza desde el inicio del periodo retenido si no hay checkpoint;
es posible que vuelva a leer las cuatro transferencias ya enviadas. Si expiraron,
emitir una **nueva transferencia sintética** mientras está ejecutándose. Cada
línea `checkpoint=updated` se imprime solo tras persistir Bronze. Detener con
Ctrl+C después de ver al menos una línea; no detener el worker de fraude.

En otra terminal definir `AZURE_BLOB_ACCOUNT_URL` y ejecutar:

```powershell
$env:AZURE_BLOB_ACCOUNT_URL = "https://bclakedv260929.blob.core.windows.net"
python -m bancocloud.azure_lake_promote
if ($LASTEXITCODE -ne 0) { throw "Promoción Medallion falló" }
```

El JSON reporta `run_id`, `bronze`, `silver`, `quarantine` y `duplicate`.
Verificar `bronze = silver + quarantine + duplicate`; el total no tiene por qué
ser exactamente 4 si existieron otras pruebas. Consultar el manifiesto con
`az storage blob list --account-name bclakedv260929 --container-name gold
--auth-mode login --prefix "runs/<run_id>/" --output table`.

## Gates posteriores

### Evidencia de promoción ejecutada en Azure (03/10/2026 UTC)

Una transferencia sintética pasó por core/outbox local y Event Hubs; el
consumidor `lake-writer` local confirmó el checkpoint después de escribir el
evento número 21 en Bronze. Se detuvieron los procesos locales con outbox=0.
Antes del Job, Gold no contenía el prefijo `runs/e3f5dd1180830b048619/`.

El Container Apps Job manual `bc-medallion-batch-dv260929`, en el entorno
`bc-aca-batch-dv260929` de tipo WorkloadProfiles/Consumption, ejecutó la imagen
versionada `bancocloud-medallion:crlf-20261003` mediante identidad administrada.
La ejecución `bc-medallion-batch-dv260929-lffjhes` terminó en `Succeeded`.
Silver y Gold publicaron el nuevo prefijo a las `2026-10-03T06:04:58Z`.
El manifiesto concilia Bronze=21, Silver=21, duplicate=0 y quarantine=0.
El archivo `quarantine/rejected.jsonl` existe, pero no contiene rechazados.

El reintento anterior sobre 20 eventos detectó que los archivos generados en
Windows tenían saltos CRLF y el Job Linux generaba LF. La comparación ahora
normaliza únicamente los saltos de línea de artefactos JSON/JSONL; conserva los
blobs inmutables y rechaza contenido distinto. Diez pruebas dirigidas pasaron.
Los logs efímeros de esta ejecución ya no estaban disponibles al consultar;
el estado del Job, los timestamps de creación y el manifiesto son la evidencia
persistente. Ver `evidence/azure-medallion-cloud-run.json`.

ACR Basic, Event Hubs Standard, Storage y los entornos creados requieren revisión
de costo y teardown explícito. La etiqueta `expiry` no elimina recursos.
La ejecución cloud de Medallion no autoriza ML online, casos en Azure ni GenAI.

- ML: el benchmark de cuatro candidatos sigue offline. Gold agregado por
  día/canal no es una matriz de features ni habilita scoring automático. Su
  promoción exige validación temporal, versionado y un store de serving.
- Azure OpenAI: comprobar cuota/modelo/región **en la suscripción concreta**;
  si Student no ofrece cuota, conservar el resumen GenAI local identificado
  como tal. Ninguna respuesta GenAI decide riesgo o bloquea transferencias.
- Registrar conteos, run_id, capturas sin identidades y hora de teardown.
  Detener procesos Python y retirar los cinco roles temporales al finalizar.
