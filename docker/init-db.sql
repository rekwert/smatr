-- Safe bootstrap for plain Postgres OR Timescale.
-- Failures on missing extension must not abort cluster init.
DO $$
BEGIN
  CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;
EXCEPTION WHEN OTHERS THEN
  RAISE NOTICE 'timescaledb extension skipped: %', SQLERRM;
END $$;
