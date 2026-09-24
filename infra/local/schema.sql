CREATE TABLE IF NOT EXISTS customers (
  customer_ref uuid PRIMARY KEY,
  region text NOT NULL
);
CREATE TABLE IF NOT EXISTS accounts (
  account_ref uuid PRIMARY KEY,
  customer_ref uuid NOT NULL REFERENCES customers(customer_ref),
  balance numeric(18,2) NOT NULL CHECK (balance >= 0),
  status text NOT NULL CHECK (status IN ('ACTIVE','FROZEN'))
);
CREATE TABLE IF NOT EXISTS transactions (
  transaction_id uuid PRIMARY KEY,
  idempotency_key uuid NOT NULL UNIQUE,
  request_hash text NOT NULL,
  customer_ref uuid NOT NULL REFERENCES customers(customer_ref),
  source_account uuid NOT NULL REFERENCES accounts(account_ref),
  destination_account uuid NOT NULL REFERENCES accounts(account_ref),
  amount numeric(18,2) NOT NULL CHECK (amount > 0),
  correlation_id uuid NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  CHECK (source_account <> destination_account)
);
CREATE TABLE IF NOT EXISTS outbox_events (
  event_id uuid PRIMARY KEY,
  transaction_id uuid NOT NULL UNIQUE REFERENCES transactions(transaction_id),
  payload jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  published_at timestamptz,
  attempts integer NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS outbox_pending ON outbox_events(created_at) WHERE published_at IS NULL;
CREATE TABLE IF NOT EXISTS processed_events (
  event_id uuid PRIMARY KEY,
  transaction_id uuid NOT NULL UNIQUE,
  event_time timestamptz NOT NULL,
  customer_ref uuid NOT NULL,
  device_ref text,
  beneficiary_ref text,
  event_payload jsonb NOT NULL
);
CREATE INDEX IF NOT EXISTS history_customer_time ON processed_events(customer_ref,event_time);
CREATE TABLE IF NOT EXISTS fraud_scores (
  event_id uuid PRIMARY KEY REFERENCES processed_events(event_id),
  transaction_id uuid NOT NULL UNIQUE,
  score_payload jsonb NOT NULL
);
CREATE TABLE IF NOT EXISTS fraud_cases (
  case_id uuid PRIMARY KEY,
  command_id uuid NOT NULL UNIQUE,
  transaction_id uuid NOT NULL,
  policy_version text NOT NULL,
  correlation_id uuid NOT NULL,
  command_payload jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(transaction_id,policy_version)
);
CREATE TABLE IF NOT EXISTS analyst_decisions (
  case_id uuid PRIMARY KEY REFERENCES fraud_cases(case_id),
  decision_payload jsonb NOT NULL
);
