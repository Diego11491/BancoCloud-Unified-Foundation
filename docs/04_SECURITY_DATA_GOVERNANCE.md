# 04 — Seguridad, datos y gobierno

## Clasificación

| Clase | Ejemplo | Política |
|---|---|---|
| Pública | documentación, diagramas | repositorio permitido |
| Interna | métricas técnicas, schemas | equipo |
| Confidencial demo | casos/eventos sintéticos | acceso restringido |
| Restringida | PII real, PAN, CVV, secretos | prohibida en el proyecto |

## Identidad y privilegio

- Customer IAM: Cognito.
- Staff Azure: Entra.
- Cloud workloads: roles/managed identities.
- CI/CD: OIDC federation cuando sea viable.
- App roles ≠ cloud RBAC.

## Tokenización/pseudonimización

En producción, un identificador pseudónimo estable debe impedir reversión trivial y no debe transportar el identificador bancario original. Se prefiere tokenización o HMAC con una clave protegida.

## Datos prohibidos en eventos

- PAN completo;
- CVV;
- PIN;
- contraseñas;
- access/refresh tokens;
- biometría cruda;
- secretos;
- PII directa que no sea necesaria.

## Data contract

Cada contrato define:

- owner;
- schema/version;
- required/optional;
- semántica;
- clasificación;
- compatibilidad;
- ejemplos sintéticos;
- reglas de evolución.

Cambios breaking requieren nueva versión mayor.

## Quality gates

- uniqueness;
- completeness;
- domain;
- integrity;
- timestamp validity;
- schema validity;
- freshness;
- duplicate rate;
- reconciliation;
- no labels in production event.

## ML governance

Cada modelo aprobado registra:

- dataset hash/version;
- feature schema/version;
- training window;
- métricas;
- threshold/policy;
- model artifact hash;
- image digest;
- approver;
- deployment timestamp.

## GenAI governance

Prompts de producción reciben evidencia estructurada mínima, no raw banking dumps. La salida se etiqueta como asistencia y permanece revisable por humano.
