#!/bin/bash
set -e
echo "=== API history/stats ==="
curl -fsS http://127.0.0.1:8010/api/v1/data/history/stats
echo
echo "=== API data/health ==="
curl -fsS http://127.0.0.1:8010/api/v1/data/health
echo
echo "=== PG totals ==="
docker exec smas-postgres psql -U smas -d smas -c "
SELECT
  (SELECT count(*) FROM market_candles) AS candles,
  (SELECT count(*) FROM derivatives_data) AS oi,
  (SELECT count(*) FROM signals) AS signals_all,
  (SELECT count(*) FROM signals WHERE status='active') AS signals_active,
  (SELECT count(DISTINCT exchange || ':' || symbol) FROM market_candles) AS pairs,
  (SELECT min(time) FROM market_candles) AS oldest,
  (SELECT max(time) FROM market_candles) AS newest;
"
echo "=== by exchange ==="
docker exec smas-postgres psql -U smas -d smas -c "
SELECT exchange, count(*) AS candles, count(DISTINCT symbol) AS symbols
FROM market_candles GROUP BY 1 ORDER BY 2 DESC;
"
echo "=== sample latest candles ==="
docker exec smas-postgres psql -U smas -d smas -c "
SELECT exchange, symbol, timeframe, time, close
FROM market_candles ORDER BY time DESC LIMIT 5;
"
echo "=== celery last 45m ==="
docker logs smas-worker --since 45m 2>&1 | grep -E 'ingest_market_history|scan_market|universe_scan|candles=|created signals|ERROR' | tail -25 || true
echo "=== containers ==="
docker ps --format '{{.Names}} {{.Status}}' | grep -E '^(postgres|redis|smas-)' || true
