# Catálogo de features LOCAL FIRST (v2)

**Fuente:** campos permitidos de `TransactionPosted.v1` y eventos procesados del
mismo `customer_ref` con `event_time` estrictamente anterior; se ignoran eventos
duplicados por `event_id`. No se consulta `fraud_labels` ni `score_riesgo`.
Las features se calculan en memoria para cada scoring; el contrato `FraudScore.v1`
solo lleva nivel, score, reason codes y versiones, no la lista de features.

| Feature | Cálculo y ausencia de fuente |
|---|---|
| `tx_count_1m`, `tx_count_5m`, `tx_count_1h` | Número de transacciones anteriores en ventanas inclusivas de 60, 300 y 3600 segundos; cero si no hay. |
| `amount_sum_5m` | Suma previa de 5 min en moneda del evento actual; cero si no hay. |
| `amount_vs_avg_30d`, `amount_vs_median_30d` | Monto actual dividido por media/mediana histórica de 30 días en la misma moneda; `None` si no existe base. |
| `new_device`, `new_beneficiary` | Si la referencia actual apareció antes entre las referencias conocidas del cliente; `None` si falta referencia actual o historia comparable. |
| `device_age_days` | Días desde la primera transacción observada con la misma referencia; `None` sin aparición anterior. No representa la fecha de registro real. |
| `prior_beneficiary_tx_count` | Operaciones anteriores con el beneficiario actual; `None` cuando no hay referencia comparable. Es una aproximación de la relación observada. |
| `usual_channel`, `channel_changed` | Canal modal histórico con mínimo tres eventos y sin empate; `None` sin patrón. Cambio compara el canal actual con ese modo. |
| `hour_deviation` | Distancia circular de 0 a 12 horas al horario modal histórico en UTC, mínimo tres eventos y sin empate; `None` sin patrón. No representa la hora local del cliente. |
| `tx_count_rapid_window` | Conteo en ventana configurada de policy; alimenta `rapid_activity` junto con monto elevado, novedad observada de dispositivo y de beneficiario. |

El umbral `large_amount_pen` solo se evalúa en PEN. Otras monedas necesitan
umbrales versionados propios antes de activar esa señal.

**Pendiente por falta de fuente válida:** fallas de autenticación recientes,
fecha real de alta de dispositivo, relación de beneficiario fuera de transacciones
observadas y patrón horario en zona local. Los eventos `POSTED` no pueden probar
esas señales. Las nuevas métricas descriptivas aún no tienen pesos de riesgo
ni modelo ML calibrado; `rules-only-v1` se conserva.

**Gate de integración:** PASS en el proyecto Docker aislado `bancocloud_t4`:
5960 cuentas, 10 000 eventos aceptados, segundo replay con 10 000 duplicados
reconocidos, 93 HIGH, 93 casos, 0 MEDIUM con caso y 10 000 scores con
`student-features-v2`/`student-rules-v2`. Reproducir sobre el volumen T3 devolvería
los scores antiguos por idempotencia; eso es el comportamiento esperado.