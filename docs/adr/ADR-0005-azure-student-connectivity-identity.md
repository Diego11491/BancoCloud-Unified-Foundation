# ADR-0005 — Conectividad e identidad para Azure Student

**Estado:** Proposed; requiere ratificación del equipo antes de crear recursos.
**Fecha:** 2026-09-29

## Contexto

El Core simulado permanece fuera de Azure y debe publicar hechos desde su outbox
hacia Event Hubs. Los workloads Azure deben consumir eventos, persistir perfiles y
casos, escribir el lake y publicar comandos HIGH sin incorporar secretos al código.
El modo Student no despliega ExpressRoute, VPN Gateway ni Private Endpoints.

## Decisión propuesta

- Mantener PostgreSQL como sistema autoritativo del Core; Azure SQL conserva solo
  perfiles antifraude, evaluaciones, casos y decisiones del analista.
- Core local → Event Hubs usa TLS 1.2+ y una identidad de aplicación de Entra con
  `Azure Event Hubs Data Sender` limitada al Event Hub. Su credencial temporal vive
  únicamente fuera del repositorio y se revoca al cerrar la demostración.
- Los workloads en Container Apps usan una identidad administrada asignada por el
  usuario. No reciben connection strings de Event Hubs, Service Bus o Storage.
- La identidad obtiene únicamente los roles requeridos: Event Hubs Data Receiver,
  Service Bus Data Sender/Receiver y Storage Blob Data Contributor en los scopes
  mínimos correspondientes.
- Azure SQL usa autenticación Entra para el workload. La credencial administrativa
  de bootstrap no se entrega a la aplicación y las migraciones se ejecutan como un
  paso controlado y auditable.
- El checkpoint de Event Hubs se conserva en un container dedicado de Blob Storage.
- En Student se aceptan endpoints públicos con autenticación fuerte, TLS y datos
  sintéticos durante una ventana corta. Esto no se describe como red privada ni
  sustituye el TARGET con ExpressRoute/Private Endpoints.
- El despliegue se divide en dos etapas: plataforma (identidad, ACR, mensajería,
  storage, SQL y observabilidad), luego imagen inmutable y workloads.
- Todo recurso lleva `owner` y `expiry`; la ejecución termina con inventario, costo
  observado y eliminación del resource group dedicado.

## Consecuencias

- Se requieren adaptadores Azure reales y un worker, no el endpoint HTTP local.
- El sender local necesita una credencial temporal porque no dispone de Managed
  Identity. Nunca se almacena en GitHub, imagen Docker, Bicep ni archivos versionados.
- El primer despliegue demuestra un vertical slice antes de incorporar Synapse,
  Power BI Service o Azure OpenAI.

## Gate de aprobación

Antes de `az deployment group create`, el equipo debe aprobar región, scopes RBAC,
método de bootstrap SQL, presupuesto, horario de teardown y salida del `what-if`.
