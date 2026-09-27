# Platform Foundation — spec

## Objetivo

Crear el esqueleto común que permitirá a equipos y agentes trabajar en AWS, core local y Azure sin reinterpretar la arquitectura.

## Requisitos funcionales

### RF-01 Contrato transaccional
El sistema debe publicar `TransactionPosted.v1` conforme al JSON Schema canónico.

### RF-02 Outbox
Una transacción confirmada debe tener un outbox event persistido atómicamente.

### RF-03 Fraude
Todo evento válido debe producir `FraudScore.v1` o un error auditable.

### RF-04 Política
El sistema debe clasificar LOW/MEDIUM/HIGH.

### RF-05 Casos
Solo HIGH crea `CreateFraudCase.v1` por defecto.

### RF-06 Analista
Una decisión de analista se registra como `AnalystDecision.v1`.

### RF-07 Cold path
Los eventos deben poder aterrizar en Bronze y continuar a Silver/Gold sin participar en el scoring síncrono.

### RF-08 Asistencia GenAI
Un caso HIGH ya creado puede producir un `GenAICaseSummary.v1` evidence-only. La
salida debe ser auditable, exigir revisión humana y degradar a fallback local sin
afectar scoring, case management ni la decisión del analista.

## Restricciones

- datos sintéticos únicamente;
- sin PAN/CVV/PIN/secretos;
- GenAI no scorea;
- Azure no es autorizador de la transacción en MVP;
- ningún servicio no listado en la Source of Truth puede añadirse sin ADR;
- despliegue cloud debe tener estrategia de teardown.

## Acceptance criteria

1. JSON Schemas validan ejemplos positivos y rechazan payloads inválidos.
2. Reintentar un evento no crea dos casos.
3. `correlation_id` aparece desde core hasta caso.
4. Deshabilitar GenAI no rompe el flujo.
5. Outbox sobrevive a fallo temporal de Event Hubs.
6. Un build limpio puede ejecutar tests sin credenciales cloud reales.
7. Una respuesta GenAI inválida o un timeout del proveedor activa fallback y no
   introduce reason codes ni acciones de decisión.
