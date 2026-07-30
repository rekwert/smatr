#!/bin/bash
curl -fsS http://127.0.0.1:8010/api/v1/data/history/stats
echo
docker exec smas-postgres psql -U smas -d smas -c "SELECT timeframe, count(*) AS c, min(time) AS oldest, max(time) AS newest FROM market_candles GROUP BY 1 ORDER BY 1;"
echo "--- worker recent ---"
docker logs smas-worker --since 20m 2>&1 | grep -E 'ingest_market_history candles|universe_scan L1|scan_market created|different loop' | tail -12
