# 01 — Revisión de avances y resolución de incongruencias

Este documento explica qué se corrigió para que la propuesta deje de existir como varios documentos parcialmente distintos y pase a una sola base.

| Tema | Estado previo | Resolución canónica |
|---|---|---|
| Nombre/identidad del proyecto | `BancoCloud_INTERBANK_Digital_Andino`, `itfb-hybrid-fraud-platform` y variantes | Nombre técnico común: `bancocloud-multicloud-fraud-platform`; el nombre académico puede conservar “BancoCloud INTERBANK Digital Andino” en exposición |
| Narrativa cloud | Algunos textos eran Azure-first | AWS = experiencia digital; on-prem = core; Azure = inteligencia/datos/fraude |
| Core | FastAPI/PostgreSQL y luego PostgreSQL/SQL Server indistinto | MVP: PostgreSQL + Core API en Docker. SQL Server solo mediante ADR si el curso lo exige |
| Stream processor | Azure Functions, Stream Analytics y Container Apps en distintos avances | Componente lógico único `Fraud Stream Processor`; MVP físico dentro del mismo Container App que scoring. Split futuro solo con evidencia |
| Scoring | Function que hacía features + score o servicio separado | Lógicamente separado: enrichment/features → rules+ML+policy; físicamente co-deploy en Student |
| Riesgo MEDIUM | A veces creaba caso; otras solo monitor | Canónico: MEDIUM = monitoreo/alerta; HIGH = case vía Service Bus. Policy configurable/versionada |
| Azure como autorizador | Algunos diagramas podían sugerirlo | Azure NRT no bloquea en MVP. Solo reglas críticas inline on-prem pueden condicionar operación |
| GenAI | Reclamos/Groq, Azure OpenAI y fraude mezclados | Arquitectura target usa GenAI para resumen de casos. Fallback de demo debe marcarse como fallback. Nunca scorea fraude |
| Profile store | Cosmos DB como decisión fija | Student reutiliza Azure SQL para profile snapshots; Target evalúa store especializado por benchmark |
| API Management Azure | Aparecía por herencia de una arquitectura Azure-first | No es pieza obligatoria del hot path event-driven. Solo se añade si existe API Azure que lo justifique |
| AWS backend | Lambda y ECS/Fargate como si ambos fueran obligatorios | Lambda es default MVP; Fargate es alternativa target para cargas sostenidas/larga duración |
| Identidad | Riesgo de mezclar Cognito y Entra | Cognito = clientes; Entra = staff/analistas/operación Azure |
| Pseudonimización | SHA-256 simple de IDs | Target: HMAC-SHA-256/tokenización; sintético: UUIDs no reales |
| Cold path | Capture siempre vs ADLS genérico | Capture se habilita en demo full; LITE puede usar writer controlado. Bronze sigue siendo requisito lógico |
| Infra as Code | Solo Bicep pese a ser multicloud | Bicep para Azure + SAM/CloudFormation para AWS; la fuente común son specs/contracts/ADRs |
| Costos | Arquitectura completa podía inducir despliegue excesivo | Modos LITE, DEMO FULL y TARGET; despliegue bajo demanda y teardown explícito |
| Dataset | Dataset recibido como si fuera transaccional | Se usa como `customer_seed`; transacciones y labels se generan separadamente |
| Leakage | `score_riesgo`/`alerta_sistema` podían contaminar ML | Prohibidos como features iniciales salvo linaje probado |
| División ML | Split 80/20 podía interpretarse como final | Split temporal obligatorio para evaluación final; random solo exploratorio |

## Regla para futuras discrepancias

No se resuelven creando otro documento paralelo. Se abre un ADR con:

- problema;
- opciones;
- decisión;
- consecuencias;
- archivos afectados.

Después se actualiza `00_SOURCE_OF_TRUTH.md`.
