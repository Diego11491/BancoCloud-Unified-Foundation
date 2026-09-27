# ADR-0004 — Asistencia GenAI evidence-only fuera del camino crítico

**Estado:** adoptado para validación local; proveedor cloud pendiente.

## Contexto

La arquitectura permite GenAI únicamente después de crear un caso HIGH. Su
indisponibilidad no puede detener scoring, creación/consulta de casos ni decisiones
humanas. Tampoco debe recibir dumps de base de datos ni información financiera
sensible. En esta fase no existe cuota aprobada de Azure OpenAI.

## Decisión

- Exponer una API local independiente para resumir un `CreateFraudCase.v1` ya
  existente; el cliente envía `case_id` y evidencia contractual mínima.
- Versionar el prompt como `fraud-case-summary-v1` y la salida como
  `GenAICaseSummary.v1`, conservando hash del input, modelo y timestamp.
- Usar un proveedor HTTP OpenAI-compatible solo cuando las variables de entorno
  estén configuradas. Sin proveedor se usa una explicación determinista explícita.
- Ante timeout, error o respuesta que invente reason codes, incluya datos sensibles
  o intente decidir, descartar la respuesta y devolver el fallback local.
- Mantener la API fuera de `core`, `fraud-engine`, outbox y case management. GenAI
  nunca escribe la decisión ni modifica score, caso o transacción.

## Consecuencias

La capa puede demostrarse y probarse sin credenciales ni recursos cloud. El
fallback preserva disponibilidad, pero no sustituye una evaluación de calidad del
modelo real. Antes de Azure se requieren cuota aprobada, secreto en Key Vault,
Managed Identity donde aplique, evaluación de prompts, telemetría sin contenido
sensible, costo/teardown y pruebas con el deployment seleccionado.
