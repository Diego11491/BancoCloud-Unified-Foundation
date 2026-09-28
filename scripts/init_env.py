"""Create local-only credentials; do not commit .env."""
from pathlib import Path
from secrets import token_urlsafe
from urllib.parse import quote

root = Path(__file__).resolve().parents[1]
dest = root / ".env"
if dest.exists():
    raise SystemExit(".env already exists; no changes made")
password, key = token_urlsafe(36), token_urlsafe(36)
dest.write_text(
    f"POSTGRES_PASSWORD={password}\n"
    f"DEMO_API_KEY={key}\n"
    f"DATABASE_URL=postgresql://bancocloud:{quote(password,safe='')}@db:5432/bancocloud\n"
    "FRAUD_URL=http://fraud:8000/ingest\n"
    "POLICY_PATH=/app/config/policy.v1.json\n"
    "EVENT_SINK=local-http\n"
    "CORE_BIND_ADDRESS=127.0.0.1\n"
    "CORE_HOST_PORT=8080\n"
    "CORS_ALLOWED_ORIGINS=http://localhost:8081,http://127.0.0.1:8081\n"
)
dest.chmod(0o600)
print("Local .env created. Keep it private and outside version control.")
