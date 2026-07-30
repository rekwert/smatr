#!/bin/bash
curl -fsS -X POST 'http://127.0.0.1:8010/api/v1/data/history/ingest?per_exchange=4&timeframes=15' --max-time 240
echo
docker exec smas-postgres psql -U smas -d smas -c "SELECT count(*) AS candles FROM market_candles; SELECT count(*) AS oi FROM derivatives_data; SELECT count(*) AS signals_active FROM signals WHERE status='active';"
echo "--- worker ---"
docker logs smas-worker --since 3m 2>&1 | grep -E 'different loop|ingest_market_history candles|scan_market created|scan_market failed|ready' | tail -20
