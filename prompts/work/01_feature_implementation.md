# Prompt — Implementar una feature sin desperdiciar contexto

Implementa la task: `<TASK_ID / descripción>`.

Usa como autoridad `docs/00_SOURCE_OF_TRUTH.md` y la spec de la feature. Lee únicamente archivos relacionados con esta task.

Proceso obligatorio:
1. resume en 5 bullets los acceptance criteria que aplicarás;
2. localiza los archivos exactos a modificar;
3. propone el diff mínimo;
4. implementa;
5. ejecuta solo tests dirigidos primero;
6. si pasan, ejecuta el conjunto de regresión más pequeño que cubra el boundary afectado;
7. actualiza `tasks.md` solo si la evidencia demuestra completion.

Restricciones:
- no refactorizar fuera de alcance;
- no agregar dependencias/servicios sin justificar;
- no duplicar contratos;
- no usar datos reales;
- si cambias contrato, añade compatibilidad/tests y revisa consumers/producers;
- si el cambio altera arquitectura, no implementes: genera ADR.

Cierra con un resumen de máximo 12 líneas y el siguiente task sugerido.
