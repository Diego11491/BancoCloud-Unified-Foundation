# Servicios LOCAL FIRST y ejecución en tu PC

Fuente de verdad: `../00_SOURCE_OF_TRUTH.md`. Esta fase prepara los servicios y scripts; la ejecución Docker y cualquier conexión externa quedan en tus manos. No ejecutar `git init`, `git remote`, `az deployment` ni `sam deploy` para seguir este manual.

## To-Do exacto de esta fase

| Servicio | Archivo principal | Estado de código | Gate en tu PC |
|---|---|---|---|
| PostgreSQL OLTP | `infra/local/schema.sql`, `infra/local/migrations/002_cards_loans.sql`, `docker-compose.yml` | Preparado | Healthy, migración automática y 5960 cuentas sembradas |
| Core API modular + outbox ACID | `bancocloud/api/core.py` (`app`) | Preparado | Cuentas, tarjetas, préstamos, transferencia e idempotencia |
| Publicador con reintentos | `bancocloud/publisher.py`, `bancocloud/adapters.py` | Preparado | Outbox retenido cuando fraud se detiene; entregado al reanudar |
| Clasificador local | `bancocloud/service.py` (`fraud_app`), `bancocloud/engine.py`, `config/policy.v1.json` | Preparado | 10 000 scores para 10 000 eventos sintéticos |
| Casos HIGH y decisión | `bancocloud/service.py`, `contracts/` | Preparado para emulación local | Solo HIGH crea caso, replay no lo duplica |
| Reproductor de eventos | `bancocloud/replay.py` | Preparado | Primera pasada: 10 000 aceptados; segunda: 10 000 replays |
| Verificador de gates | `bancocloud/gates.py` | Preparado | `pass:true` y exit code 0 |
| Cold path local | `bancocloud/cold.py`, `bancocloud/bi.py` | Ya preparado | Bronze=10k, Silver=10k, cuarentena=0 y Gold BI conciliado |
| AWS/Azure | `bancocloud/adapters.py` | Interfaces bloqueadas intencionalmente | Invocarlas lanza `CloudAdapterDisabled`, sin red cloud |

## Empaquetado y configuración

Hay **un Dockerfile** compartido por `core`, `fraud`, `publisher`, `replay` y `gate`: misma versión de contratos y dependencias, distinto comando por servicio. `docker-compose.yml` arranca cuatro contenedores persistentes (`db`, `core`, `fraud`, `publisher`) y ejecuta `migrate` como tarea efímera antes del Core. En un volumen nuevo PostgreSQL también aplica `001.sql` y `002_cards_loans.sql` en orden; en uno existente `migrate` vuelve a ejecutar la migración idempotente. `replay`, `gate` y `genai` se inician solo a pedido. Solo el core publica el puerto local `127.0.0.1:8080`; `fraud` y PostgreSQL no tienen puertos del host.

`.env.example` enumera variables; `python scripts/init_env.py` crea `.env` privado con claves nuevas. **No copies las claves del ejemplo ni subas `.env`**. `POSTGRES_PASSWORD` y `DATABASE_URL` se generan de manera coherente. `EVENT_SINK=local-http` impide escoger un adaptador cloud por error. No se incluyen credenciales AWS/Azure.

## Secuencia exacta en Windows PowerShell

Desde la carpeta que contiene el ZIP, extráelo y entra a la raíz del proyecto. Si ya lo extrajiste, empieza en `Set-Location`:

```powershell
Expand-Archive -Path .\BancoCloud_LOCAL_SERVICES_READY.zip -DestinationPath .
Set-Location .\BancoCloud_Unified_Foundation
py -3.12 scripts\init_env.py
docker compose config --quiet
docker compose up --build -d db core fraud publisher
docker compose ps
docker compose ps -a migrate
docker compose run --rm core python -m bancocloud.seed_db data/synthetic/customer_seed.jsonl
docker compose run --rm core python -m bancocloud.seed_products data/synthetic/customer_seed.jsonl
docker compose exec -T db psql -U bancocloud -d bancocloud -tAc "SELECT count(*) FROM accounts;"
docker compose run --rm replay
docker compose run --rm replay
py -3.12 scripts\smoke_local.py
docker compose run --rm gate
```

Resultados esperados: `migrate` aparece como `Exited (0)`, `accounts=5960`, productos sintéticos disponibles; primera pasada de `replay`: `accepted=10000`, `replayed=0`; segunda: `accepted=0`, `replayed=10000`. `smoke_local.py` debe mostrar tres PASS e imprimir solo IDs técnicos. `gate` exige `fixture_events=10000`, `fixture_scores=10000`, casos HIGH iguales a scores HIGH, casos MEDIUM=0, correlación válida y outbox drenado. Si un gate falla, el comando devuelve exit code 1; revisar logs y el JSON de conteos antes de avanzar.

Si ya existe `.env`, `init_env.py` se detiene sin cambiarlo. Si ya sembraste cuentas, `seed_db.py` no restaura saldos: las repeticiones del seed respetan las cuentas existentes. El replay de eventos usa IDs fijos, así que puede repetirse sin duplicar scores/casos.

## Comprobar outbox ante una caída local

Después del gate anterior, detener `fraud` y enviar una transferencia sintética. El publicador seguirá reintentando y no marcará el evento como publicado. Luego reiniciar el consumidor:

```powershell
docker compose stop fraud
py -3.12 scripts\smoke_local.py --transfer-only
docker compose exec -T db psql -U bancocloud -d bancocloud -tAc "SELECT count(*) FROM outbox_events WHERE published_at IS NULL;"
docker compose start fraud
for ($i=0; $i -lt 30; $i++) { $n = docker compose exec -T db psql -U bancocloud -d bancocloud -tAc "SELECT count(*) FROM outbox_events WHERE published_at IS NULL;"; if ([int]$n -eq 0) { break }; Start-Sleep -Seconds 2 }
docker compose run --rm gate
```

Se espera al menos un outbox pendiente durante la caída y cero al recuperarse. El `gate` confirma integridad de transacciones y correlaciones. Revisar `docker compose logs --tail=100 publisher fraud core` si falla.

## Cold path y cierre

Opcional, sin Docker, desde la raíz con Python: `py -3.12 -m bancocloud.cold data/synthetic/transaction_events.jsonl data/quality/lake`. Para generar el Gold dimensional reproducible para Power BI: `py -3.12 -m bancocloud.bi --expected-events 10000`. Para detener servicios conservando el volumen: `docker compose down`. No usar `down -v` salvo cuando decidas borrar de forma deliberada el entorno demo.

## Lo que aún no autoriza este gate

No representa un Event Hubs o un Service Bus reales, ni Azure SQL, Cognito, Lambda, Power BI o ML entrenado. La plantilla Bicep parcial existente no debe ejecutarse como parte de esta secuencia. El adaptador AWS carece de ruta AWS→core aprobada. La siguiente fase requerirá ADR de conectividad, implementación de transporte real, identidades, `what-if`/`sam validate` y presupuesto.
