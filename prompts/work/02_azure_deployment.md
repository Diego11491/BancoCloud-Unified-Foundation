# Prompt — Azure Student LITE

Prepara/despliega únicamente los recursos Azure necesarios para `<OBJETIVO>` siguiendo `docs/00_SOURCE_OF_TRUTH.md` y `docs/02_IMPLEMENTATION_MODES_COST.md`.

Antes de desplegar:
1. inspecciona solo `infra/azure/bicep` y la spec relevante;
2. lista recursos a crear/modificar/eliminar;
3. marca los que generan costo continuo;
4. rechaza cualquier recurso fuera de STUDENT LITE salvo autorización explícita;
5. ejecuta lint/build/validate y `what-if`;
6. no imprimas secretos.

Preferencias:
- un `fraud-engine` Container App antes de múltiples microservicios;
- Azure SQL compartido por schemas antes de Cosmos/Redis en el MVP;
- serverless/scale-to-zero/bajo demanda;
- Synapse y OpenAI solo durante pruebas que los necesiten;
- logs/retención mínimos para evidencia;
- tags `project`, `environment`, `owner`, `expiry`.

Después del despliegue:
- ejecuta smoke test;
- captura nombres/IDs no sensibles necesarios para reproducibilidad;
- reporta recursos que deben detenerse/eliminarse al terminar;
- no dejes compute experimental encendido sin justificación.
