# Gold local para Power BI

`bancocloud.bi` amplía el cold path validado sin participar en autorización ni
scoring online. Usa únicamente referencias sintéticas/pseudónimas y produce CSV
UTF-8 con BOM, compatibles con Power BI Desktop en Windows.

## Ejecución

```powershell
python -m bancocloud.bi --expected-events 10000
```

El comando reproyecta Bronze/Silver/Quarantine mediante `bancocloud.cold` y
publica en `data/quality/lake/gold/`:

| Archivo | Grano |
|---|---|
| `dim_customer.csv` | un perfil/cuenta sintético |
| `dim_date.csv` | un día del fixture |
| `fact_transactions.csv` | una transacción validada |
| `fact_fraud_evaluations.csv` | una evaluación rules-only y su etiqueta separada |
| `fact_fraud_cases.csv` | un caso derivado exclusivamente de HIGH |
| `agg_transactions_by_day_channel.csv` | día, canal y moneda |

`bi_reconciliation.json` conserva conteos, distribución de riesgo, matriz HIGH
versus etiqueta sintética, controles de integridad y limitaciones. Los outputs
se regeneran y permanecen ignorados por Git; el código, pruebas y documentación
son los artefactos versionados.

## Modelo en Power BI

- `dim_customer[customer_ref]` 1→* `fact_transactions[customer_ref]`.
- `dim_customer[customer_ref]` 1→* `fact_fraud_evaluations[customer_ref]`.
- `dim_date[date_key]` 1→* cada tabla de hechos por `date_key`.
- `fact_transactions[transaction_id]` 1→1
  `fact_fraud_evaluations[transaction_id]`.
- `fact_fraud_evaluations[transaction_id]` 1→0..1
  `fact_fraud_cases[transaction_id]`.

Los 323 positivos de `is_fraud` son ground truth sintético. Los 93 HIGH son
alertas de la policy reproducida offline; no deben presentarse como conceptos
equivalentes ni como desempeño productivo.

## Gate

La carga base aprueba solamente si existen 10 000 eventos, cada transacción
tiene cliente, etiqueta y evaluación, cada HIGH produce un caso y ningún
registro rechazado es promovido a Gold. Quarantine permanece fuera de Power BI
y ML hasta corrección y reproceso.
