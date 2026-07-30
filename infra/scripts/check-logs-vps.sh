#!/bin/bash
echo "=== API last errors ==="
docker logs smas-api --since 30m 2>&1 | grep -Ei 'error|exception|traceback|critical' | grep -v 'CancelledError' | tail -30
echo "=== WORKER last errors ==="
docker logs smas-worker --since 30m 2>&1 | grep -Ei 'error|exception|traceback|critical|failed|different loop' | tail -40
echo "=== WEB last errors ==="
docker logs smas-web --since 30m 2>&1 | grep -Ei 'error|exception|traceback|critical' | tail -20
echo "=== WORKER successes ==="
docker logs smas-worker --since 30m 2>&1 | grep -E 'ingest_market_history candles|scan_market created|universe_scan L1|ready' | tail -20
echo "=== PG counts ==="
docker exec smas-postgres psql -U smas -d smas -c "SELECT (SELECT count(*) FROM market_candles) candles, (SELECT count(*) FROM derivatives_data) oi, (SELECT count(*) FROM signals WHERE status='active') signals;"
echo "=== restart count ==="
docker inspect smas-api smas-worker smas-web smas-postgres smas-redis --format '{{.Name}} restarts={{.RestartCount}} status={{.State.Status}}'
