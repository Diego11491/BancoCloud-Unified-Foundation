# 05 — Estrategia de pruebas

## Pirámide mínima

| Área | Pruebas |
|---|---|
| Core | transacciones ACID, reglas inline, saldos/estados |
| Outbox | mismo commit, retry, publish state, duplicate publish |
| Contract | JSON Schema válido/inválido y compatibilidad |
| Stream | orden relativo por entidad, duplicados, late/out-of-order |
| Fraud | features, rules, scoring, threshold/policy |
| Case | HIGH crea caso; replay no duplica |
| Data | Bronze/Silver/Gold, quarantine, reconciliation |
| ML | split temporal, PR-AUC, recall, FPR, calibration |
| Security | SAST, dependencies, secrets, authz, negative tests |
| Performance | API + event producer + end-to-end alert latency |
| Resilience | Event Hubs/engine/LLM unavailable |
| Observability | correlation ID y tracing completo |

## Escenario estrella

1. cliente sintético tiene patrón normal de montos bajos;
2. aparece dispositivo nuevo;
3. beneficiario nuevo;
4. varias transacciones rápidas;
5. monto elevado;
6. engine produce score alto y reason codes;
7. HIGH entra a Service Bus;
8. case service crea exactamente un caso;
9. GenAI resume evidencia;
10. analista decide;
11. decisión llega al dataset etiquetado;
12. Power BI refleja el caso sin consultar Bronze directamente.

## Resiliencia obligatoria

- Azure OpenAI down → scoring y casos continúan.
- ML model down/corrupto → `rules-only mode` con alerta operativa.
- Event Hubs down → outbox conserva evento.
- consumer down → replay posterior.
- duplicate delivery → no duplicate case.
