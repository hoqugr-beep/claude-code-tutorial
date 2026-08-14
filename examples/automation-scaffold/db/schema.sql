-- Postgres schema for the usage ledger.
--
-- The scaffold runs on SQLite out of the box (src/ledger.py creates the same
-- table automatically). Use this when you move to Postgres — typically once you
-- have more than one worker, since SQLite does not like concurrent writers.
--
-- To switch: apply this file, then replace the sqlite3 connection in
-- src/ledger.py with psycopg. The queries carry over unchanged apart from
-- placeholder style (%s instead of ?) and using date_trunc instead of substr.

CREATE TABLE IF NOT EXISTS api_usage (
    id                  BIGSERIAL PRIMARY KEY,
    client_id           TEXT        NOT NULL,
    job_id              TEXT        NOT NULL,
    model               TEXT        NOT NULL,
    input_tokens        INTEGER     NOT NULL DEFAULT 0,
    output_tokens       INTEGER     NOT NULL DEFAULT 0,
    cache_read_tokens   INTEGER     NOT NULL DEFAULT 0,
    cache_write_tokens  INTEGER     NOT NULL DEFAULT 0,
    -- NUMERIC, never a float. Money in binary floating point accumulates
    -- rounding error, and this table decides when to stop spending.
    cost_usd            NUMERIC(12, 6) NOT NULL,
    occurred_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- The cap check filters by client and month on every single API call, so this
-- index is load-bearing rather than an optimisation.
CREATE INDEX IF NOT EXISTS idx_usage_client_time
    ON api_usage (client_id, occurred_at);

-- Current-month spend per client. This is your invoicing input and your
-- profitability answer.
CREATE OR REPLACE VIEW monthly_spend AS
SELECT
    client_id,
    date_trunc('month', occurred_at) AS month,
    COUNT(*)                         AS calls,
    SUM(input_tokens)                AS input_tokens,
    SUM(output_tokens)               AS output_tokens,
    SUM(cost_usd)                    AS spend_usd
FROM api_usage
GROUP BY client_id, date_trunc('month', occurred_at);
