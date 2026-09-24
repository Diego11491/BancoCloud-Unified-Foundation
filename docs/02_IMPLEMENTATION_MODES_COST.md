# 02 — Modos de implementación y control de recursos

El mismo diseño lógico tiene tres modos. Esto evita confundir “arquitectura bancaria” con “lo que debemos dejar encendido en una cuenta académica”.

## Modo A — LOCAL FIRST

Objetivo: desarrollar sin gasto cloud.

- core + PostgreSQL + outbox local;
- generador de eventos;
- contratos JSON;
- fraud engine local;
- tests de reglas/ML;
- emulación de Service Bus/Event Hubs mediante interfaces/adapters cuando sea útil;
- dataset sintético pequeño (10k inicialmente).

**Gate de salida:** contratos estables, outbox/idempotencia probados y scoring reproducible.

## Modo B — STUDENT LITE

Objetivo: integración real mínima AWS↔core↔Azure.

### AWS
- S3/CloudFront;
- API Gateway HTTP;
- Cognito;
- una Lambda BFF.

### Azure
- Event Hubs;
- un Container App `fraud-engine`;
- Azure SQL único con schemas separados;
- Service Bus;
- ADLS;
- Key Vault;
- App Insights/Monitor con retención mínima necesaria.

### Bajo demanda
- Synapse Serverless;
- Azure OpenAI;
- WAF;
- jobs de Data Factory;
- mayor telemetría.

## Modo C — DEMO FULL

Se activa alrededor de la presentación/validación:

- WAF;
- Bronze automático/Capture si se decidió;
- dashboards completos;
- Azure OpenAI si cuota disponible;
- consultas Synapse;
- alertas/monitoreo ampliados;
- prueba de carga controlada.

Tras la demo, volver a LITE.

## Modo D — TARGET BANK

Documento, no despliegue académico:

- conectividad privada resiliente;
- PaaS privados;
- HA/DR según BIA;
- separación de ambientes/subscriptions/accounts;
- profile store especializado si lo justifican pruebas;
- SIEM/SOC, lineage y gobierno empresarial;
- controles regulatorios formales.

## Guardrails obligatorios de costo

1. **No crear recursos antes del gate de datos/contratos.**
2. Toda tarea cloud debe declarar `purpose`, `environment`, `owner`, `expiry` y estrategia de teardown.
3. Preferir serverless/consumption/scale-to-zero cuando no comprometa la demo.
4. No crear AKS, Redis dedicado, Dedicated SQL Pool o appliances de red solo para completar un diagrama.
5. No mantener UAT permanente; desplegarlo de forma efímera.
6. ML compute se crea para entrenamiento y se detiene/elimina tras usarlo.
7. GenAI se usa solo cuando el caso de prueba lo requiera.
8. Log retention y volumen de telemetría se mantienen proporcionales al laboratorio.
9. Antes de `deploy`, ejecutar validación/preview (`what-if`, `sam validate`, equivalente).
10. Después de una sesión de integración, registrar qué recursos quedaron activos.

## Principio de optimización

> Primero optimizar **cantidad de servicios y tiempo encendido**; después optimizar microcostos internos.

Una arquitectura con 12 servicios mínimos bien gobernados es mejor que 25 servicios “enterprise” encendidos sin necesidad.
