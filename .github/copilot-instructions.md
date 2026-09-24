# Copilot instructions — BancoCloud

La arquitectura oficial está en `docs/00_SOURCE_OF_TRUTH.md`.

Antes de generar código:

- conserva AWS como digital experience layer;
- conserva on-prem como sistema autoritativo;
- conserva Azure como intelligence/fraud/data platform;
- respeta contratos en `contracts/`;
- usa datos sintéticos;
- mantén GenAI fuera del scoring;
- preserva idempotencia, correlation IDs y outbox;
- evita servicios adicionales salvo ADR aprobado;
- para Student, favorece Lambda, Container Apps, Azure SQL compartido por schemas y recursos bajo demanda;
- genera tests junto con la implementación.

Cuando haya ambigüedad, no inventes una arquitectura alternativa: marca el punto como `DECISION_REQUIRED` y propone un ADR breve.
