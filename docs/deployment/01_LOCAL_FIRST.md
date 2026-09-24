# Instalación LOCAL FIRST

Para el empaquetado actualizado, la carga de los 10 000 eventos y los gates automáticos, seguir [05_SERVICES_AND_RUNBOOK.md](05_SERVICES_AND_RUNBOOK.md). Este archivo conserva la guía básica de una transferencia manual.

## Requisitos

Python 3.12, Docker Engine/Compose v2. Ejecutar en el directorio raíz de este proyecto. No se usan credenciales cloud.

## 1. Preparar datos

Los artefactos sintéticos derivados del Excel adjunto ya vienen incluidos. Para reproducirlos desde el archivo original, colocarlo fuera del repositorio y ejecutar:

```bash
python -m pip install openpyxl jsonschema
python -m data.generator.build --source "/ruta/DATOS OFICIALES.xlsx" --seed 42 --count 10000
python -m unittest discover -s tests -v
python -m bancocloud.cold data/synthetic/transaction_events.jsonl data/quality/lake
```

Windows PowerShell (desde la raíz):

```powershell
py -3.12 -m pip install openpyxl jsonschema
py -3.12 -m data.generator.build --source "C:\ruta\DATOS OFICIALES.xlsx" --seed 42 --count 10000
py -3.12 -m unittest discover -s tests -v
py -3.12 -m bancocloud.cold data/synthetic/transaction_events.jsonl data/quality/lake
```

`source_audit.json` guarda hash de origen, campos excluidos y conteos. `fraud_labels.jsonl` se almacena aparte; nunca se publica a `/ingest`.

## 2. Iniciar servicios

```bash
python scripts/init_env.py
docker compose config --quiet
docker compose up --build -d
docker compose run --rm core python -m bancocloud.seed_db data/synthetic/customer_seed.jsonl
curl http://127.0.0.1:8080/health
```

PowerShell: sustituir `python` por `py -3.12` si corresponde. La clave de demo y la contraseña se crean en `.env`; no imprimir ni publicar el archivo. Si cambia la contraseña después de crear el volumen PostgreSQL, deberá coordinar su rotación o recrear el volumen de demo de forma deliberada.

## 3. Hacer una transferencia sintética

Obtener dos `account_ref` con:

```bash
curl -H "X-Demo-Key: <valor_privado_de_DEMO_API_KEY>" http://127.0.0.1:8080/accounts
```

Enviar una transferencia de 25 PEN con UUID nuevo como `Idempotency-Key`:

```bash
curl -X POST http://127.0.0.1:8080/transfers \
  -H "Content-Type: application/json" \
  -H "X-Demo-Key: <valor_privado_de_DEMO_API_KEY>" \
  -H "Idempotency-Key: <uuid_unico>" \
  -d '{"source_account":"<account_ref_1>","destination_account":"<account_ref_2>","amount":"25.00","device_ref":"demo-device","beneficiary_ref":"demo-beneficiary"}'
```

Repetir la solicitud con la **misma** clave; la segunda respuesta lleva `replay:true` y los saldos no se modifican de nuevo. Consultar `GET /cases` para operaciones HIGH. `correlation_id` de la transferencia coincide con el score y el caso. Para prueba de fallo: `docker compose stop fraud`, enviar una transferencia y verificar que el outbox sigue pendiente; luego `docker compose start fraud` y esperar al publicador.

## 4. Inspección y apagado

```bash
docker compose logs --tail=50 core fraud publisher
docker compose exec db psql -U bancocloud -c "SELECT count(*) FROM outbox_events WHERE published_at IS NULL;"
docker compose exec db psql -U bancocloud -c "SELECT count(*) FROM fraud_cases;"
docker compose down
```

El volumen de datos persiste tras `down`. Solo en una demo descartable y **después** de conservar evidencias, `docker compose down -v` borra los datos locales. La API se liga a `127.0.0.1`; nunca se debe publicar este core como sistema bancario real.
