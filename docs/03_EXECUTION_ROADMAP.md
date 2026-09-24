# 03 — Roadmap de ejecución

## Fase 0 — Congelar arquitectura

**Entregables**
- Source of Truth aprobada.
- ADR inicial.
- contratos base.
- estructura de repositorio.

**Gate:** ningún miembro/agente mantiene una arquitectura alternativa en paralelo.

## Fase 1 — Datos y contratos

1. auditar dataset fuente;
2. producir `customer_seed`;
3. cerrar `transaction.v1`;
4. generar 10k transacciones;
5. generar labels en tabla/archivo separado;
6. validar duplicados, timestamps, dominios, distribución y ausencia de leakage.

**Gate:** 0 errores críticos y reproducibilidad por seed.

## Fase 2 — Core Simulator + Outbox

- Customer/Account/Card/Loan/Transaction mínimos;
- operación de transferencia demo;
- reglas inline;
- outbox en mismo commit;
- publisher retryable;
- correlation ID.

**Gate:** fallo del publisher no pierde la transacción ni el evento pendiente.

## Fase 3 — Azure hot path LITE

- Event Hubs;
- `fraud-engine` Container App;
- profiles en Azure SQL;
- scoring rules+ML;
- LOW/MEDIUM/HIGH;
- HIGH → Service Bus → case service.

**Gate:** replay no duplica casos.

## Fase 4 — Azure cold path

- Bronze/Silver/Gold;
- calidad/quarantine;
- Gold para fraude;
- Synapse/Power BI bajo demanda.

**Gate:** Power BI consume Gold y existe reconciliación event→bronze→silver→gold.

## Fase 5 — AWS digital layer

- web estática;
- Cognito;
- API Gateway;
- Lambda BFF;
- integración con Core Simulator mediante el mecanismo de demo aprobado.

**Gate:** usuario autenticado puede ejecutar el escenario de transferencia de prueba de punta a punta.

## Fase 6 — GenAI + Analyst Portal

- portal de casos;
- resumen de evidencia;
- human-in-the-loop;
- analyst decision event.

**Gate:** caída del LLM no detiene scoring ni case management.

## Fase 7 — DevSecOps e IaC

- Bicep Azure;
- SAM/CloudFormation AWS;
- GitHub Actions;
- lint/test/schema/SAST/secret scan/IaC validation/container scan;
- OIDC cuando sea viable.

**Gate:** entorno recreable sin secretos embebidos.

## Fase 8 — Resiliencia y performance

- duplicados;
- eventos late/out-of-order;
- Event Hubs temporalmente no disponible;
- fraud engine caído;
- rules-only fallback;
- load test 5→20→100 eps según capacidad del laboratorio.

**Gate:** evidencia con latencias y recuperación.

## Fase 9 — Demo Full y cierre

- WAF/controles visuales necesarios;
- Power BI;
- GenAI si disponible;
- trazas end-to-end;
- evidencia y teardown posterior.
