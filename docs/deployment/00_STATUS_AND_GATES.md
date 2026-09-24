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
| 2 Core/outbox | Gate Docker completado: transferencia, idempotencia, outbox ACID, publisher, replay y recuperación ante caída | PASS local; conservar evidencia y no reutilizar autenticación demo fuera del laboratorio |
| 3 Azure hot path | Enrichment v2 probado a nivel unitario y Docker; rules/policy locales con 10 000 scores versionados y 93 casos idempotentes; adaptadores cloud deshabilitados | Baseline ML local y fuentes gobernadas pendientes, además de Event Hubs, Container Apps, Azure SQL y Service Bus; Bicep de messaging parcial; `what-if` pendiente |
| 4 Cold path | Bronze/Silver/Gold local, cuarentena y reconciliación | ADLS ingestion, vistas Synapse y Power BI pendientes; BI de morosidad/rentabilidad exige fuentes de préstamos/costos aún no modeladas |
| 5 AWS | Contrato core disponible para BFF; interfaz AWS→core deshabilitada | Cognito, API Gateway, Lambda, S3/CloudFront y método seguro AWS→core pendientes; no exponer el core local por Internet sin diseño aprobado |
| 6 Analistas/GenAI | Registro de decisión humana por contrato | Staff IAM, portal y resumen asistido pendientes; GenAI no bloquea casos |
| 7 IaC/CI | Bicep de messaging como base revisable | Validación `az bicep build`, `what-if`, SAM, OIDC y scans pendientes |
| 8/9 Resiliencia/demo | Unitarios, reconciliación, replay real, smoke y recuperación del consumidor ejecutados | Métricas bajo carga, nube y teardown cloud pendientes |

**Regla de liberación:** el código local no equivale a despliegue bancario ni a entorno cloud operativo. Ningún recurso cloud se crea sin pasar validación local, preview de IaC, decisión de región/cuota y estrategia de apagado.

| Baseline ML temporal | PASS LOCAL OFFLINE | 10 000 filas; split temporal 7000/1500/1500; 323 positivos; 0 variables prohibidas; test PR-AUC=1.0, precision=1.0, recall=0.979167, FPR=0.0 y Brier=0.000311. Candidato no autorizado; `rules-only-v1` permanece activo |

## Próximo gate autorizado

La siguiente unidad de trabajo es **T4-ML-BASELINE-LOCAL**: preparar features
ordenadas temporalmente, unir la etiqueta separada únicamente como variable objetivo,
probar ausencia de leakage y evaluar un baseline interpretable con split temporal,
PR-AUC, recall, precision, FPR y calibración. `rules-only-v1` permanece como fallback.

## Riesgos conocidos

1. El Excel no tiene ID bancario ni secuencias de operaciones. Los UUID y las fechas generadas son simulados. No se infiere fraude real de sus columnas.
2. `rules-only-v1` es una línea base explícita, no un modelo ML entrenado. El entrenamiento requiere datos longitudinales válidos y evaluación temporal.
3. La autenticación `X-Demo-Key` y el core local son exclusivos de demostración. Una ruta pública AWS→on-prem necesita control de identidad y conectividad propios antes de habilitarse.
4. La política `config/policy.v1.json` es provisional y versionada; los umbrales requieren calibración con costos, capacidad de analistas y datos etiquetados defendibles.
5. La persistencia del consumidor LOCAL FIRST usa PostgreSQL compartido como emulación. En Azure, profile/cases pertenecen a Azure SQL y la entrega de HIGH a Service Bus debe ser durable e idempotente.
6. Consultar todo el historial anterior por cliente sirve para el fixture actual; antes de escalar hay que medir latencia y diseñar agregados/perfiles online. La edad del dispositivo observada no equivale a su fecha real de alta.