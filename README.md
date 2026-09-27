# BancoCloud Multicloud Fraud Platform

Base unificada para el proyecto académico de **banca digital híbrida multicloud**.

## Objetivo

Implementar una banca digital demostrable en la que:

- **AWS** aloja la experiencia digital del cliente.
- **On-premise simulado** conserva el core transaccional y la verdad operativa.
- **Azure** aloja streaming, fraude, datos, BI, casos, GenAI, observabilidad y gobierno.
- El caso conductor es **monitoreo de fraude transaccional casi en tiempo real**, sin convertir el prototipo en autorizador financiero ni en un sistema AML completo.

## Regla principal de documentación

La única fuente de verdad arquitectónica es:

> [`docs/00_SOURCE_OF_TRUTH.md`](docs/00_SOURCE_OF_TRUTH.md)

Los ADR explican decisiones; las specs traducen esas decisiones a trabajo; los contratos fijan interfaces; el IaC y el código implementan. **Ningún documento subordinado puede redefinir la arquitectura por su cuenta.**

## Orden de autoridad

1. `docs/00_SOURCE_OF_TRUTH.md`
2. `docs/adr/ADR-*.md` aprobados
3. `specs/**/spec.md`, `plan.md`, `tasks.md`
4. `contracts/*.schema.json`
5. `infra/**`
6. `src/**` y `tests/**`

Si dos niveles entran en conflicto, se corrige el nivel inferior o se propone un ADR que modifique explícitamente la fuente de verdad.

## Flujo spec-driven

```text
Source of Truth
      ↓
   spec.md      qué debe ocurrir
      ↓
   plan.md      cómo se implementará
      ↓
  tasks.md      unidades pequeñas y verificables
      ↓
  código/IaC
      ↓
  pruebas + evidencia
      ↓
  revisión arquitectónica
```

## Documentos clave

- `docs/01_REVIEW_AND_RESOLUTIONS.md`: inconsistencias detectadas en los avances y decisión final adoptada.
- `docs/02_IMPLEMENTATION_MODES_COST.md`: modos LITE/FULL/TARGET y guardrails de costo.
- `docs/03_EXECUTION_ROADMAP.md`: secuencia por fases y gates.
- `docs/04_SECURITY_DATA_GOVERNANCE.md`: identidad, secretos, PII, contratos y gobierno.
- `docs/05_TEST_STRATEGY.md`: pruebas funcionales, datos, streaming, ML, seguridad y resiliencia.
- `AGENTS.md`: reglas obligatorias para agentes de programación.
- `prompts/work/`: prompts preparados para ChatGPT Work con consumo de contexto y recursos controlado.

## Estado inicial

La arquitectura está **congelada a nivel lógico**. La implementación LOCAL FIRST incorpora generador de datos, Core Simulator con outbox PostgreSQL, publicador con reintentos, clasificación por reglas, casos HIGH y cold path local. La verificación de integración en contenedores y los despliegues cloud siguen condicionados a sus gates.

## Iniciar el entorno

1. Leer [estado y gates](docs/deployment/00_STATUS_AND_GATES.md) para identificar qué está implementado y qué requiere integración.
2. Ejecutar el [manual de servicios y gates LOCAL FIRST](docs/deployment/05_SERVICES_AND_RUNBOOK.md). El ZIP incluye perfiles y 10 000 eventos sintéticos derivados del Excel; también permite regenerarlos desde el original.
3. Consultar los manuales [Azure](docs/deployment/02_AZURE_STUDENT_LITE.md), [AWS](docs/deployment/03_AWS_STUDENT_LITE.md) y [evidencia/operación](docs/deployment/04_OPERATIONS_AND_EVIDENCE.md) antes de crear recursos.

El código Python vive en `bancocloud/`; `data/generator/` genera los datos. Los JSON Schema solo viven en `contracts/`. `config/policy.v1.json` controla los umbrales de demo. `docker-compose.yml` inicia PostgreSQL, core, consumidor y publicador, sin servicios externos. Los perfiles `replay` y `gate` se ejecutan solo a pedido. GitHub Actions valida pruebas y Bicep, pero no despliega recursos cloud.

El Core de Docker usa la API modular `bancocloud.api.core:app`. Compose aplica
automáticamente la migración idempotente de tarjetas/préstamos mediante el servicio
efímero `migrate` antes de iniciar el Core, tanto sobre volúmenes nuevos como existentes.

## Probar la asistencia GenAI local

GenAI es un servicio opcional y aislado. No requiere un modelo ni credenciales en
modo local y nunca interviene en scoring, creación de casos o autorización.

```powershell
docker compose --profile tools up -d --build genai
Invoke-RestMethod -Method Get -Uri http://127.0.0.1:8082/health
```

Para `POST /explain-case`, enviar el header `x-demo-key` y un JSON con `case_id`
más `evidence`, donde `evidence` cumple `CreateFraudCase.v1`. La respuesta se
valida contra `GenAICaseSummary.v1` y queda marcada como asistencia con revisión
humana obligatoria. Las variables `GENAI_*` de `.env.example` permiten conectar
más adelante un endpoint HTTPS OpenAI-compatible; si se dejan vacías se usa el
fallback determinista local.

## Integración continua

`.github/workflows/ci.yml` ejecuta las pruebas Python y la validación estática de
los cinco módulos Bicep en cada `push` o pull request a `main`. Este workflow es
CI únicamente: no inicia sesión en Azure, no usa secretos cloud y no despliega
recursos. El CD se añadirá en un workflow separado después de aprobar OIDC,
`what-if`, environment protegido, costo y teardown.
