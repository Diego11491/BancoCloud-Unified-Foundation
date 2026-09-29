# Benchmark ML offline gobernado

## Propósito

El benchmark demuestra un proceso reproducible de comparación, no calidad bancaria
productiva. Ningún candidato participa en autorización, scoring online o creación de
casos. `rules-only-v1` permanece activo.

## Por qué existe un challenge separado

El fixture de regresión contiene 10 000 eventos, 5960 perfiles y un único escenario
fraudulento con señales muy separables. Es adecuado para contratos, replay y gates,
pero sus métricas casi perfectas no sirven para elegir un modelo.

`synthetic-ml-challenge-v2` conserva datos 100 % sintéticos y agrega:

- 90 días y 500 clientes activos por defecto;
- fraude por monto, account takeover, ráfaga/beneficiario y cambio de canal;
- operaciones legítimas de monto alto, dispositivo nuevo y beneficiario nuevo;
- solapamiento entre señales legítimas y fraudulentas;
- generación determinista por seed y labels separados del evento operativo.

## Candidatos

1. `DummyClassifier` como control mínimo.
2. Logistic Regression como baseline interpretable.
3. Random Forest como modelo no lineal.
4. HistGradientBoosting como challenger tabular.

No se usa SMOTE ni random split. El dataset se ordena por `event_time` y se divide
70/15/15. El threshold y el champion se eligen exclusivamente con validation; test
solo estima desempeño final. Se registran PR-AUC, precision, recall, FPR, Brier,
matriz de confusión, calibración, latencia y delta temporal.

El control negativo entrena regresión logística con labels de train mezclados. Si su
PR-AUC supera el límite gobernado, el benchmark falla por posible señal espuria.

## Ejecución

```powershell
python -m bancocloud.ml_benchmark

python -m unittest `
    tests.unit.ml.test_challenge_benchmark `
    tests.test_ml_baseline `
    -v
```

Artefactos locales ignorados por Git:

- `data/quality/ml_challenge_v2/`;
- `data/quality/ml_benchmark_matrix.csv`;
- `data/quality/ml_benchmark_report.json`.

## Gate de promoción

Un resultado `OFFLINE_CHAMPION_NOT_AUTHORIZED` no permite cargar el modelo en el
fraud engine. Una promoción futura requiere revisión humana, artefacto inmutable,
versionado, pruebas de latencia/replay, rollback y una decisión explícita sobre cómo
combinar ML con rules y policy.
