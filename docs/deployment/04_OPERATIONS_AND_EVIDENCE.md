# Evidencia, pruebas y siguientes entregables

## Local reproducible

- `python -m unittest discover -s tests -v`: 17 pruebas de contratos, rechazo de leakage, enrichment v2, policy HIGH/MEDIUM, idempotencia, generador y conciliación.
- Docker T4: 5960 cuentas, 10 000 eventos aceptados, replay idempotente de 10 000,
  93 HIGH/casos, 0 duplicados y 10 000 scores con features/policy v2.
- `python -m data.generator.build --source <xlsx> --seed 42 --count 10000`: perfiles seguros y dataset sintético.
- `python -m bancocloud.cold data/synthetic/transaction_events.jsonl data/quality/lake`: Bronze/Silver/Gold local. Gold representa solamente volumen y monto por fecha/canal.
- `python -m bancocloud.bi --expected-events 10000`: reproyección cold path y Gold dimensional local para Power BI; genera conciliación separada, 5960 perfiles, 10 000 transacciones/evaluaciones, 323 etiquetas positivas y 93 casos HIGH esperados.
- `data/quality/source_audit.json` y `data/quality/lake/reconciliation.json`: reportes generados.
- `python -m bancocloud.ml_benchmark`: genera un challenge sintético temporal separado,
  ejecuta cuatro candidatos, selecciona threshold/champion solo con validation y aplica
  un control negativo con labels mezclados. No produce un modelo autorizado online.

## Registro de un despliegue futuro

Guardar fecha UTC, commit/hash del artefacto, policy/model/feature version, región, recursos/tags, what-if o change set, smoke test, latencia, volumen, costos medidos, responsables y evidencia de teardown. Nunca incluir credenciales o payloads bancarios completos en logs o capturas.

## Tareas restantes con aceptación clara

1. ML: ejecutar el benchmark challenge por commit relevante, revisar estabilidad y
   documentar cualquier futura promoción mediante un gate separado. Mientras tanto
   `model_version=rules-only-v1` permanece activo.
2. Azure: completar Bicep de Container App/SQL/Key Vault/ACR/Monitor, adapters reales e identidades; ejecutar preview antes de crear. Nunca poner casos MEDIUM en Service Bus con la política vigente.
3. AWS: cerrar ADR de conectividad segura, construir SAM/BFF/web y probar Cognito.
4. BI: importar el Gold dimensional validado en Power BI Desktop y construir las páginas transaccional, fraude/riesgo y calidad. Morosidad/rentabilidad siguen pendientes de fuentes acordadas de préstamos y costos.
5. Portal: IAM Entra para personal y decisión humana. Un resumen GenAI opcional recibe solo evidencia mínima y no determina score ni autorización.
