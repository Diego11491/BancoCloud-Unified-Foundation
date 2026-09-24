"""Create local-only credentials; do not commit .env."""
from pathlib import Path
from secrets import token_urlsafe
from urllib.parse import quote

root = Path(__file__).resolve().parents[1]
dest = root / ".env"
if dest.exists():
    raise SystemExit(".env already exists; no changes made")
password, key = token_urlsafe(36), token_urlsafe(36)
dest.write_text(f"POSTGRES_PASSWORD={password}\nDEMO_API_KEY={key}\nDATABASE_URL=postgresql://bancocloud:{quote(password,safe='')}@db:5432/bancocloud\nFRAUD_URL=http://fraud:8000/ingest\nPOLICY_PATH=/app/config/policy.v1.json\nEVENT_SINK=local-http\n")
dest.chmod(0o600)
print("Local .env created. Keep it private and outside version control.")
