# Azure Bicep

Primeros módulos previstos:

- resource groups/tags;
- Event Hubs;
- Container Apps environment + fraud-engine;
- Azure SQL;
- Service Bus;
- ADLS Gen2 con Bronze, Silver, Gold y Quarantine privada;
- Key Vault;
- monitoring.

No crear Synapse/OpenAI/WAF/Purview/otros recursos hasta la fase que los necesite.

`messaging-lite.bicep` trata Quarantine como una zona lateral para registros
inválidos. Su retención se controla con `quarantineRetentionDays` (30 días por
defecto, rango 1–90) y una lifecycle policy; no es una cuarta capa Medallion.

El módulo también crea el consumer group `fraud-engine`, el container privado
`eventhub-checkpoints` y roles de mínimo privilegio: Receiver para la identidad del
worker y Blob Data Contributor limitado al checkpoint. El principal local opcional
recibe temporalmente Sender/Receiver y acceso al checkpoint para el E2E híbrido; se
revoca al cerrar la demo. No se crean connection strings ni secretos.
