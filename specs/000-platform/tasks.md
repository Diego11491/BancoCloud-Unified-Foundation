# Platform Foundation — tasks

## Convención de estado

- `[x] LOCAL VERIFIED`: existe evidencia reproducible mediante pruebas o auditoría de artefactos.
- `[ ] LOCAL READY / DOCKER BLOCKED`: el código está preparado, pero falta la integración real en contenedores.
- `[ ] CLOUD PENDING`: no existe evidencia de despliegue o integración cloud.
- `[ ] ADR BLOCKED`: falta una decisión arquitectónica explícita antes de implementar o desplegar.
- `[ ] TEAM DECISION`: depende de aprobación del equipo, no de evidencia técnica.

La existencia de código por sí sola no completa una tarea. La validación del baseline del
21/09/2026 ejecutó 8 pruebas unitarias/contratos, verificó el hash del Excel y reproyectó
10 000 eventos en un directorio temporal. El gate posterior en Windows con Docker Desktop
verificó 5960 cuentas, dos replays completos, smoke transaccional, idempotencia, casos HIGH,
correlación y recuperación del outbox ante la caída del consumidor.

## T0 — Gobernanza

- [x] Crear ADR-0001 y declarar `docs/00_SOURCE_OF_TRUTH.md` como documento canónico en el repositorio. **LOCAL VERIFIED**
- [ ] Ratificar la adopción del baseline con el equipo. **TEAM DECISION**
- [ ] Configurar CODEOWNERS/PR template cuando exista repo remoto. **CLOUD PENDING**

## T1 — Contratos

- [x] Validar los cuatro JSON Schema contra ejemplos sintéticos y negativos en `tests/test_foundation.py`. **LOCAL VERIFIED**
- [x] Crear ejemplos válidos/negativos mediante generación determinista y tests. **LOCAL VERIFIED**
- [ ] Añadir tests de compatibilidad de evolución de contratos v2 cuando existan cambios. **CLOUD PENDING: no existe v2**

## T2 — Datos

- [x] Confirmar que el SHA-256 del Excel adjunto coincide con `data/quality/source_audit.json`. **LOCAL VERIFIED**
- [x] Convertir el dataset original en 5960 perfiles anónimos de `customer_seed`. **LOCAL VERIFIED**
- [x] Implementar generator determinista por seed. **LOCAL VERIFIED**
- [x] Generar 10 000 eventos transaccionales sintéticos. **LOCAL VERIFIED**
- [x] Separar 10 000 fraud labels del evento operativo. **LOCAL VERIFIED**
- [x] Verificar ausencia de leakage contractual y reconciliación local. **LOCAL VERIFIED**

## T3 — Core/outbox

- [x] Crear schema OLTP PostgreSQL. **LOCAL VERIFIED por inspección y tests de límites**
- [x] Ejecutar `POST /transfers` con idempotencia sobre PostgreSQL en Docker. **LOCAL VERIFIED**
- [x] Demostrar `Transaction + OutboxEvent` en el mismo commit y ausencia de transacciones sin outbox. **LOCAL VERIFIED**
- [x] Detener el consumidor, comprobar un outbox pendiente y verificar drenado a cero al recuperarlo. **LOCAL VERIFIED**
- [x] Ejecutar publisher y replay dos veces sin duplicar scores ni casos. **LOCAL VERIFIED**
- [ ] Arrancar el Core modular desde Docker y ejecutar automáticamente la migración idempotente 002 antes del servicio. **LOCAL READY / DOCKER VALIDATION PENDING**

## T4 — Fraud engine local

- [x] Implementar las features derivables del evento y del historial anterior; verificar ventanas, moneda, comportamiento ante valores desconocidos y ausencia de leakage con cinco pruebas dirigidas. **LOCAL VERIFIED**
- [x] Integrar `student-features-v2` y `student-rules-v2` mediante replay Docker con volumen aislado: 5960 cuentas, 10 000 aceptados, 10 000 replays, 93 HIGH, 93 casos, 0 duplicados y 10 000 scores v2. **LOCAL VERIFIED**
- [ ] Obtener fuente gobernada para fallas de autenticación, alta real del dispositivo y relaciones externas de beneficiario. **DATA SOURCE PENDING**
- [x] Implementar features iniciales de monto, dispositivo, beneficiario y actividad reciente. **LOCAL VERIFIED**
- [x] Implementar rules baseline configurable y versionado. **LOCAL VERIFIED**
- [x] Implementar y evaluar baseline ML interpretable con split temporal 70/15/15, controles de leakage y métricas PR-AUC, precision, recall, FPR y calibración. **LOCAL VERIFIED — OFFLINE CANDIDATE; NOT AUTHORIZED**
- [x] Implementar policy engine LOCAL FIRST con LOW/MEDIUM/HIGH. **LOCAL VERIFIED**
- [x] Emitir `reason_codes`, `model_version`, `feature_version` y `policy_version` conforme al contrato. **LOCAL VERIFIED**
- [x] Extraer la orquestación antifraude de `service.py` mediante puertos para evaluación y publicación de casos; conservar PostgreSQL como adaptador LOCAL FIRST. **LOCAL VERIFIED**

## T5 — Azure LITE

- [x] Ratificar ADR-0005 para identidad, conectividad, SQL y despliegue en dos etapas. **TEAM ACCEPTED / DEPLOYMENT GATED**
- [ ] Completar Bicep mínimo; mensajería incluye consumer group, checkpoint y RBAC mínimo. **CODE READY / STATIC AND CLOUD VALIDATION PENDING**
- [ ] Integrar Event Hubs con identidad y checkpoint duradero. **ADAPTERS READY / REAL AZURE E2E PENDING**
- [ ] Desplegar Container App `fraud-engine`. **CLOUD PENDING**
- [ ] Crear Azure SQL con schemas separados para profiles/cases. **CLOUD PENDING**
- [ ] Integrar HIGH con Service Bus. **CLOUD PENDING**
- [ ] Aterrizar Bronze en ADLS y promover Silver/Gold. **CLOUD PENDING**
- [ ] Configurar Key Vault, Managed Identity y telemetría mínima. **CLOUD PENDING**

## T6 — Cases

- [ ] Publicar HIGH en Service Bus y consumirlo en Case Service. **CLOUD PENDING**
- [x] Verificar creación idempotente de casos sobre PostgreSQL real: 93 HIGH, 93 casos y 0 duplicados. **LOCAL VERIFIED**
- [x] Validar `AnalystDecision.v1` y rechazar decisiones fuera del contrato. **LOCAL VERIFIED**
- [ ] Verificar persistencia de la decisión del analista mediante la API local. **LOCAL READY / DOCKER BLOCKED**

## T7 — AWS LITE

- [ ] Definir mediante ADR la conectividad segura AWS→core, identidad entre cargas, TLS, restricciones de origen y teardown. **ADR BLOCKED**
- [ ] Implementar S3/CloudFront. **CLOUD PENDING**
- [ ] Implementar Cognito. **CLOUD PENDING**
- [ ] Implementar API Gateway HTTP API. **CLOUD PENDING**
- [ ] Implementar Lambda BFF sin escribir directamente en el OLTP. **ADR BLOCKED**
- [x] Alinear el nombre del handler `transfers.py` con la referencia SAM y probar el rechazo sin idempotency key. **LOCAL VERIFIED**

## T8 — Cold path/BI

- [x] Proyectar 10 000 eventos en Bronze local. **LOCAL VERIFIED**
- [x] Validar y deduplicar 10 000 eventos en Silver con cuarentena local. **LOCAL VERIFIED**
- [x] Generar Gold local por día/canal y reconciliar conteos. **LOCAL VERIFIED**
- [x] Generar Gold dimensional reproducible para Power BI con 5960 perfiles, 10 000 transacciones/evaluaciones, etiquetas separadas y 93 casos HIGH. **LOCAL VERIFIED**
- [x] Declarar Quarantine privada en ADLS con output y lifecycle policy parametrizada. **LOCAL VERIFIED — BUILD/LINT PASS 27/09/2026**
- [ ] Implementar ADLS/Synapse Serverless para el cold path cloud. **CLOUD PENDING**
- [ ] Crear el archivo Power BI Desktop sobre Gold; morosidad/rentabilidad requieren fuentes todavía no modeladas. **LOCAL READY / DASHBOARD PENDING**

## T9 — GenAI

- [x] Implementar evidence-only prompt con versión, hash del input y contrato de salida. **LOCAL VERIFIED**
- [x] Implementar rechazo de PII/secrets, reason codes inventados y decisiones prohibidas. **LOCAL VERIFIED**
- [x] Demostrar por prueba aislada que el fallo del proveedor devuelve fallback y no muta el caso. **LOCAL VERIFIED**
- [x] Ejecutar la API con un caso HIGH real, comprobar autenticación/PII, health/readiness y continuidad del Core durante la caída de GenAI. **LOCAL VERIFIED — 28/09/2026**
- [ ] Evaluar un deployment real de Azure OpenAI, calidad, latencia, costo y telemetría. **CLOUD PENDING**

## T10 — End-to-end

- [x] Probar retry y deduplicación del replay con transporte simulado. **LOCAL VERIFIED**
- [x] Ejecutar replay real dos veces y verificar 10 000 aceptados + 10 000 replays. **LOCAL VERIFIED**
- [x] Probar caída y recuperación del consumidor con outbox retenido y drenado posterior. **LOCAL VERIFIED**
- [ ] Validar React Native/Expo contra el Core local usando CORS con allowlist, bind loopback por defecto y exposición LAN explícita solo para la demo en dispositivo físico. **LOCAL READY / MOBILE INTEGRATION PENDING**
- [ ] Ejecutar load test gradual 5→20→100 eps solo después de los gates funcionales. **LOCAL PENDING**
- [ ] Ejecutar smoke cloud y documentar costos/teardown. **CLOUD PENDING**

## T11 — CI/CD

- [x] Ejecutar en GitHub el workflow de pruebas Python y build/lint Bicep sin credenciales cloud. **CI VERIFIED — RUN #1 PASS 27/09/2026**
- [ ] Ejecutar en GitHub el workflow path-scoped de Data Quality para Medallion y Gold. **LOCAL VERIFIED / CI RUN PENDING**
- [ ] Proteger `main` y exigir el workflow CI antes de merge. **REPOSITORY CONFIG PENDING**
- [ ] Diseñar CD manual con OIDC, `what-if`, environment protegido, aprobación y teardown. **CLOUD PENDING**
- [ ] No habilitar despliegue automático por `push` mientras no estén cerrados los gates de seguridad y costo. **GUARDRAIL**

## Siguiente task exacta

**T5-AZURE-HOT-PATH-PREFLIGHT:** compilar/lint Bicep, revisar `what-if`, confirmar
región/costos/scopes y ejecutar Core→Event Hubs→worker local→FraudService con datos
sintéticos. No desplegar el worker en Container Apps hasta implementar Azure SQL.
