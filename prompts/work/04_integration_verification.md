# Prompt — Verificación end-to-end

Verifica la integración `<FASE>` sin cambiar arquitectura salvo que encuentres un defecto real.

Debes seguir una transacción sintética mediante:
AWS request → Core → OLTP/outbox → Event Hubs → Fraud Engine → Policy → Service Bus (si HIGH) → Case → Analyst/BI.

Comprueba:
- mismo `correlation_id`;
- contrato válido;
- no PII prohibida;
- retry/replay;
- no duplicate case;
- versiones de model/features/policy;
- GenAI fuera del critical path;
- evidencia en logs sin payload sensible.

Ejecuta pruebas en orden barato→caro:
1. unit/contract;
2. local integration;
3. cloud smoke;
4. load/resilience solo si lo anterior pasa.

No hagas load testing mientras existan fallos funcionales básicos.

Entrega una tabla PASS/FAIL, evidencia y un máximo de 5 acciones correctivas priorizadas.
