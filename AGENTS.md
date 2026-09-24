# AGENTS.md — reglas para agentes de desarrollo

## Contexto mínimo obligatorio

Antes de modificar código, leer solo:

1. `docs/00_SOURCE_OF_TRUTH.md`;
2. la spec activa (`spec.md`, `plan.md`, `tasks.md`);
3. ADR directamente relacionado;
4. contratos que toque la tarea;
5. archivos de código que realmente se modificarán.

No recorrer todo el repositorio por defecto.

## Reglas duras

- No agregar servicios cloud sin ADR.
- No mover responsabilidades entre AWS/on-prem/Azure sin ADR.
- No incorporar PII real, PAN, CVV, PIN, secretos o credenciales.
- No convertir Azure ML/GenAI en autorizador financiero.
- No usar `fraud_label`, `fraud_scenario`, `score_riesgo` o `alerta_sistema` como input online.
- No crear un case para MEDIUM salvo cambio explícito de policy/ADR.
- No duplicar contratos en varios lugares: usar `contracts/`.
- No hardcodear thresholds, connection strings o secretos.
- No usar recursos premium/always-on si una opción LITE satisface el acceptance test.
- No desplegar antes de validar IaC/dry-run.

## Regla de eficiencia

Implementar el **cambio mínimo completo**:

- una tarea;
- un conjunto pequeño de archivos;
- tests dirigidos;
- diff resumido;
- no refactorizar áreas no relacionadas.

## Salida obligatoria de cada cambio

1. archivos tocados;
2. decisión aplicada;
3. tests ejecutados;
4. resultado;
5. riesgos/pendientes;
6. recursos cloud creados/modificados/eliminados, si aplica.
