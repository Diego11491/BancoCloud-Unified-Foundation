# Estado ejecutable y gates de despliegue

## Autoridad

`../00_SOURCE_OF_TRUTH.md` decide la arquitectura. Este documento registra implementación y evidencia; no redefine servicios ni responsabilidades. Los prompts en `prompts/work/` son guías de ejecución.

## Validación del baseline — 21/09/2026

| Comprobación | Estado | Evidencia |
|---|---|---|
| Pruebas unitarias y contratos | PASS | `python -m unittest discover -s tests -v`: 8 pruebas, 0 fallos |
| Excel fuente | PASS | SHA-256 del adjunto idéntico a `data/quality/source_audit.json`; 5960 filas útiles |
| Artefactos sintéticos | PASS | 5960 perfiles, 10 000 eventos y 10 000 labels separados; 323 positivos sintéticos |
| Cold path local | PASS | Reproyección temporal: Bronze=10 000, Silver=10 000, quarantine=0, duplicate=0 |
| Integración Docker | PASS | Windows, Python 3.12.10, Docker Engine 27.4.0 y Compose v2.31.0; cuatro servicios activos, PostgreSQL healthy y 5960 cuentas |
| Replay real, casos y outbox | PASS | Primera pasada: 10 000 aceptados; segunda: 10 000 replays; 93 HIGH, 93 casos, 0 duplicados y gate `pass:true` |
| Smoke transaccional | PASS | Cuatro transferencias, idempotencia y creación de caso HIGH con `correlation_id` preservado |
| Caída/recuperación del consumidor | PASS | Con `fraud` detenido: outbox pendiente=1; después de reiniciarlo: 1→1→0; gate final `pass:true` |
| AWS/Azure | NOT RUN | Cero recursos cloud creados, modificados o eliminados |

## Validación T4 — 24/09/2026 UTC

| Comprobación | Estado | Evidencia |
|---|---|---|
| Enrichment `student-features-v2` | PASS LOCAL UNIT | 5 pruebas dirigidas: ventanas, monedas, ausencias, antigüedad observada, cronología y ventana configurable |
| Regresión contratos y servicios | PASS LOCAL UNIT | `python -m unittest discover -s tests -v`: 13 pruebas, 0 fallos |
| Reproducción en memoria de fixture | PASS LOCAL OFFLINE | 10 000 eventos; 93 HIGH, `rules-only-v1` con `student-rules-v2` y `student-features-v2` |
| Replay/score/casos v2 en Docker | PASS | Proyecto aislado `bancocloud_t4`: 5960 cuentas; 10 000 aceptados y luego 10 000 replays; 93 HIGH, 93 casos, 0 MEDIUM con caso y 0 duplicados; gate `pass:true` |
| Versiones de scoring | PASS | 10 000 scores con `rules-only-v1`, `student-features-v2` y `student-rules-v2` |
| Recursos cloud | NOT RUN | Cero recursos creados, modificados o eliminados |

La consulta local de historial ahora abarca eventos previos del mismo cliente; ADR-0003
registra el cambio de semántica cuando faltan referencias. El catálogo
`06_FEATURE_CATALOG_LOCAL.md` documenta linaje, valores desconocidos y fuentes pendientes.

El PASS local no equivale a despliegue cloud ni autoriza a exponer el Core a Internet.
`tasks.md` mantiene separadas las capacidades locales verificadas de las tareas Azure/AWS.

| Fase | Resultado actual | Gate verificable / requisito pendiente |
|---|---|---|
| 0 Arquitectura | Fuente de verdad y ADR-0001/0002 preservados | Aceptación del equipo pendiente |
| 1 Datos/contratos | Excel revalidado por hash; 5960 perfiles; 10k eventos; etiquetas separadas; cuatro schemas usados; 0 rechazo en reproyección local | Verificar el escenario de datos con el equipo, calidad y representatividad; no interpretar etiquetas generadas como fraude real |
| 2 Core/outbox | Gate Docker legacy completado; entrypoint modular y migración automática declarados con regresión estática | Revalidar Docker modular: migrate=Exited(0), cuentas/productos, transferencia, casos, outbox y recuperación; no reutilizar autenticación demo fuera del laboratorio |
| 3 Azure hot path | FraudService desacoplado; sender/worker/checkpoint listos; Bicep lint/build, validación ARM y `what-if` completados; Resource Group vacío | Crear un corte de costo con Managed Identity + Event Hubs + checkpoint/Storage y ejecutar E2E híbrido real; Container Apps espera Azure SQL y Service Bus |
| 4 Cold path | Bronze/Silver/Gold local, cuarentena y reconciliación; Quarantine privada y lifecycle declaradas; build/lint PASS | ADLS ingestion, vistas Synapse y Power BI pendientes; BI de morosidad/rentabilidad exige fuentes de préstamos/costos aún no modeladas |
| 5 AWS | Contrato core disponible para BFF; interfaz AWS→core deshabilitada | Cognito, API Gateway, Lambda, S3/CloudFront y método seguro AWS→core pendientes; no exponer el core local por Internet sin diseño aprobado |
| 6 Analistas/GenAI | Registro de decisión humana por contrato; resumen evidence-only local, fallback, rechazo de PII/decisiones y smoke con caso HIGH real | Staff IAM, portal y evaluación con un deployment aprobado pendientes; GenAI no bloquea casos |
| 7 IaC/CI | Módulos Bicep, GitHub Actions Run #1 y preflight Azure PASS; `what-if`: 22 Create, 2 Unsupported conocidos, 0 Modify/Delete; ningún servicio desplegado | Corte Bicep por costo, SAM, OIDC y scans pendientes; CI no despliega recursos |
| 8/9 Resiliencia/demo | Unitarios, reconciliación, replay real, smoke y recuperación del consumidor ejecutados | Métricas bajo carga, nube y teardown cloud pendientes |

**Regla de liberación:** el código local no equivale a despliegue bancario ni a entorno cloud operativo. Ningún recurso cloud se crea sin pasar validación local, preview de IaC, decisión de región/cuota y estrategia de apagado.

| Baseline ML temporal | PASS LOCAL OFFLINE | 10 000 filas; split temporal 7000/1500/1500; 323 positivos; 0 variables prohibidas; test PR-AUC=1.0, precision=1.0, recall=0.979167, FPR=0.0 y Brier=0.000311. Candidato no autorizado; `rules-only-v1` permanece activo |

## Validación ML challenge v2 — 29/09/2026 UTC

| Comprobación | Estado | Evidencia |
|---|---|---|
| Dataset desafiante separado | PASS LOCAL OFFLINE | Configuración por defecto: 10 000 eventos, 500 clientes activos y 90 días; cuatro escenarios de fraude y tres negativos difíciles |
| Benchmark multi-modelo | PASS LOCAL OFFLINE | Dummy, Logistic Regression, Random Forest e HistGradientBoosting evaluados con el mismo split temporal y features allowlisted |
| Selección gobernada | PASS | Threshold y champion usan únicamente validation; test no participa en selección |
| Control negativo | PASS | El gate rechaza la corrida si Logistic Regression con labels de train mezclados supera el límite gobernado |
| Resultado | OFFLINE ONLY | El champion y las métricas quedan en el reporte reproducible local; no se serializa ni promueve; `rules-only-v1` permanece online |

## Próximo gate autorizado

La siguiente unidad Azure es **T5-AZURE-COST-CONTROLLED-SLICE**: separar el Bicep
para que el primer `create` incluya únicamente Managed Identity, Event Hubs,
Storage/checkpoint y RBAC mínimo. Un nuevo `what-if` debe demostrar que SQL, Service
Bus, ACR y observabilidad permanecen deshabilitados. Después se ejecutará
Core→Event Hubs→worker local con contrato, idempotencia, `correlation_id` y
recuperación ante reentrega. Container Apps continúa bloqueado hasta disponer de
persistencia Azure compatible.

## Riesgos conocidos

1. El Excel no tiene ID bancario ni secuencias de operaciones. Los UUID y las fechas generadas son simulados. No se infiere fraude real de sus columnas.
2. `rules-only-v1` continúa como fallback online. Los candidatos ML entrenados son
   evidencia offline sobre datos sintéticos; no representan calidad productiva ni están
   autorizados para participar en scoring hasta superar un gate de promoción separado.
3. La autenticación `X-Demo-Key` y el core local son exclusivos de demostración. Una ruta pública AWS→on-prem necesita control de identidad y conectividad propios antes de habilitarse.
4. La política `config/policy.v1.json` es provisional y versionada; los umbrales requieren calibración con costos, capacidad de analistas y datos etiquetados defendibles.
5. La persistencia del consumidor LOCAL FIRST usa PostgreSQL compartido como emulación. En Azure, profile/cases pertenecen a Azure SQL y la entrega de HIGH a Service Bus debe ser durable e idempotente.
6. Consultar todo el historial anterior por cliente sirve para el fixture actual; antes de escalar hay que medir latencia y diseñar agregados/perfiles online. La edad del dispositivo observada no equivale a su fecha real de alta.
