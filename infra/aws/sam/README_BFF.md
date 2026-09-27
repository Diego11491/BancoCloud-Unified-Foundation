# AWS SAM BFF (additive)

This directory adds the AWS Digital Banking BFF without moving Core Banking SQL or financial rules into Lambda.

Do not deploy `demo.json` as-is. The AWS→Core connectivity/security gate in the existing source of truth must be resolved first.

Local Core modular entrypoint:

```bash
uvicorn bancocloud.api.core:app --host 127.0.0.1 --port 8080
```

Apply the additive database migration before using cards/loans:

```bash
psql "$DATABASE_URL" -f infra/local/migrations/002_cards_loans.sql
```

Validate SAM:

```bash
sam validate --lint -t infra/aws/sam/template.yaml
sam build -t infra/aws/sam/template.yaml
```
