# ADR-0003 — Enriquecimiento con historial observado en LOCAL FIRST

**Estado:** adoptado y verificado localmente, incluida integración Docker de v2.

## Contexto

El motor calculaba cuatro señales con hasta 100 eventos por cliente. Ese límite
podía ocultar un dispositivo antiguo y truncar ventanas históricas. El contrato
de eventos solo incluye hechos de transacciones confirmadas: no registra fallas
de autenticación, alta real de dispositivos ni vínculos externos de beneficiarios.

## Decisión

- Leer todos los eventos anteriores al evento actual del mismo cliente; excluir
  el propio evento, futuros, empates de timestamp y duplicados por `event_id`.
- Calcular ventanas y razones monetarias solo con eventos compatibles en moneda.
  La ausencia de base de comparación se representa como `None` en la feature.
- La novedad de dispositivo/beneficiario se evalúa respecto al historial observado;
  sin referencias anteriores conocidas se registra `None` y la regla no se activa.
- Preservar los cuatro pesos y umbrales de las reglas y el modelo
  `rules-only-v1`. Versionar las features como `student-features-v2` y la policy
  como `student-rules-v2`, dado el nuevo tratamiento de historial incompleto.
  El umbral `large_amount_pen` se aplica únicamente a eventos en PEN.
- Conservar scores previos ante replay: una transacción ya procesada no se puntúa
  de nuevo. Verificar v2 en un proyecto Docker aislado del volumen del gate T3.

## Consecuencias

La lectura completa por cliente es apta para esta carga sintética; antes de
operar a escala hacen falta un store de perfiles o agregados medidos, benchmarks
y un criterio explícito para eventos tardíos. No se infieren fallas de login ni
antigüedad real de dispositivo. Ningún recurso cloud ni contrato cambia.