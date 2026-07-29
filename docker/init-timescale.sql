-- Part 14: TimescaleDB + SaaS foundation
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Seed exchanges (idempotent)
INSERT INTO exchanges (name, type, api_status)
SELECT v.name, v.type, 'unknown'
FROM (VALUES
  ('bybit', 'futures'),
  ('okx', 'futures'),
  ('bitget', 'futures'),
  ('mexc', 'futures'),
  ('bingx', 'futures'),
  ('kucoin', 'futures')
) AS v(name, type)
WHERE NOT EXISTS (SELECT 1 FROM exchanges e WHERE e.name = v.name);

-- Convert market_candles to hypertable if plain table exists
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_name = 'market_candles'
  ) AND NOT EXISTS (
    SELECT 1 FROM timescaledb_information.hypertables
    WHERE hypertable_name = 'market_candles'
  ) THEN
    PERFORM create_hypertable(
      'market_candles',
      'time',
      if_not_exists => TRUE,
      migrate_data => TRUE
    );
  END IF;
EXCEPTION
  WHEN OTHERS THEN
    RAISE NOTICE 'hypertable setup skipped: %', SQLERRM;
END $$;

-- Helpful indexes for multi-exchange scans
CREATE INDEX IF NOT EXISTS idx_market_candles_symbol_tf_time
  ON market_candles (exchange, symbol, timeframe, time DESC);

CREATE INDEX IF NOT EXISTS idx_market_trades_symbol_ts
  ON market_trades (exchange, symbol, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_orderbook_symbol_ts
  ON orderbook_snapshots (exchange, symbol, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_derivatives_symbol_ts
  ON derivatives_data (exchange, symbol, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_smart_money_events_symbol_ts
  ON smart_money_events (symbol, event_type, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_candidates_status_score
  ON candidates (status, pump_score DESC);

CREATE INDEX IF NOT EXISTS idx_training_samples_label
  ON training_samples (label, created_at DESC);

-- Retention policies (Timescale) — safe if hypertable ready
DO $$
BEGIN
  PERFORM add_retention_policy('market_candles', INTERVAL '10 years', if_not_exists => TRUE);
EXCEPTION
  WHEN OTHERS THEN
    RAISE NOTICE 'retention policy skipped: %', SQLERRM;
END $$;
