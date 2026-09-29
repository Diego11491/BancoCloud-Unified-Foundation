# Fase 2 — Vertical slice de Azure Event Hubs

## Alcance autorizado

Esta fase prepara y prueba el recorrido `Outbox Publisher → Event Hubs → worker →
FraudService` usando exclusivamente eventos sintéticos. El modo predeterminado sigue
siendo `EVENT_SINK=local-http`; ningún test unitario contacta Azure.

El primer E2E híbrido ejecutará Core, PostgreSQL y el worker en la PC, usando Event
Hubs y Blob checkpoint como servicios Azure reales. Esto permite validar contrato,
identidad, at-least-once y checkpoint antes de sumar Azure SQL y Container Apps.

## Configuración sin secretos embebidos

Instalar las dependencias opcionales:

```powershell
python -m pip install -r .\requirements-azure.txt
```

El productor y worker locales utilizan `DefaultAzureCredential` con
`AZURE_TENANT_ID`, `AZURE_CLIENT_ID` y `AZURE_CLIENT_SECRET` suministrados fuera de
Git. Para esta prueba corta el principal recibe Sender/Receiver sobre el Event Hub y
Blob Data Contributor solo sobre el container de checkpoint. Se revoca al finalizar;
el target bancario separa identidades.

El worker necesita:

```text
AZURE_EVENTHUB_FULLY_QUALIFIED_NAMESPACE=<namespace>.servicebus.windows.net
AZURE_EVENTHUB_NAME=transaction-posted-v1
AZURE_EVENTHUB_CONSUMER_GROUP=fraud-engine
AZURE_BLOB_ACCOUNT_URL=https://<storage>.blob.core.windows.net
AZURE_BLOB_CHECKPOINT_CONTAINER=eventhub-checkpoints
```

## Orden de ejecución del E2E híbrido

1. Validar Bicep y revisar `what-if`.
2. Aprobar región, presupuesto, RBAC y teardown.
3. Crear la plataforma solo durante la ventana acordada.
4. Cambiar temporalmente `.env` a `EVENT_SINK=azure-event-hubs` y completar las
   variables Azure.
5. Recrear el publisher e iniciar el worker con
   `docker compose --profile azure up -d --build publisher azure-worker`.
6. Ejecutar una transferencia sintética y verificar score, correlation ID y Blob
   checkpoint.
7. Detener publisher/worker, revocar la credencial local y eliminar el grupo dedicado.

## Gate y limitación explícita

El checkpoint nunca se adelanta a la persistencia: si `FraudService` falla, Event
Hubs puede volver a entregar el evento. La idempotencia del store evita duplicar el
score. Esta fase no autoriza desplegar el worker en Container Apps porque todavía usa
el adaptador PostgreSQL; antes se requiere implementar y migrar el store Azure SQL.
