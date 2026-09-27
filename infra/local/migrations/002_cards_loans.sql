-- Additive migration. Does not redefine existing source-of-truth tables.
CREATE TABLE IF NOT EXISTS cards (
  card_ref uuid PRIMARY KEY,
  account_ref uuid NOT NULL REFERENCES accounts(account_ref),
  customer_ref uuid NOT NULL REFERENCES customers(customer_ref),
  card_type text NOT NULL CHECK (card_type IN ('DEBIT','CREDIT')),
  last_four text NOT NULL CHECK (last_four ~ '^[0-9]{4}$'),
  credit_limit numeric(18,2) CHECK (credit_limit IS NULL OR credit_limit >= 0),
  used_balance numeric(18,2) NOT NULL DEFAULT 0 CHECK (used_balance >= 0),
  issued_at timestamptz NOT NULL DEFAULT now(),
  status text NOT NULL CHECK (status IN ('ACTIVE','BLOCKED','CANCELLED')),
  CHECK ((card_type='DEBIT' AND credit_limit IS NULL) OR (card_type='CREDIT' AND credit_limit IS NOT NULL)),
  CHECK (credit_limit IS NULL OR used_balance <= credit_limit)
);
CREATE INDEX IF NOT EXISTS cards_customer_idx ON cards(customer_ref);
CREATE INDEX IF NOT EXISTS cards_account_idx ON cards(account_ref);

CREATE TABLE IF NOT EXISTS loans (
  loan_ref uuid PRIMARY KEY,
  customer_ref uuid NOT NULL REFERENCES customers(customer_ref),
  account_ref uuid NOT NULL REFERENCES accounts(account_ref),
  principal numeric(18,2) NOT NULL CHECK (principal > 0),
  annual_rate numeric(8,6) NOT NULL CHECK (annual_rate > 0),
  term_months integer NOT NULL CHECK (term_months BETWEEN 1 AND 60),
  monthly_payment numeric(18,2) NOT NULL CHECK (monthly_payment > 0),
  outstanding_balance numeric(18,2) NOT NULL CHECK (outstanding_balance >= 0),
  days_past_due integer NOT NULL DEFAULT 0 CHECK (days_past_due >= 0),
  disbursed_at timestamptz NOT NULL DEFAULT now(),
  status text NOT NULL CHECK (status IN ('CURRENT','PAST_DUE','DEFAULTED','PAID_OFF'))
);
CREATE INDEX IF NOT EXISTS loans_customer_idx ON loans(customer_ref);
CREATE INDEX IF NOT EXISTS loans_account_idx ON loans(account_ref);
