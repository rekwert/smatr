#!/bin/bash
echo "=== sample active signals ==="
docker exec smas-postgres psql -U smas -d smas -c "
SELECT exchange, symbol, direction, score, timeframe,
       reason->>'lifecycle_status' AS life,
       reason->>'setup_score' AS setup,
       reason->>'execution_score' AS exec,
       reason->>'edge_score' AS edge,
       reason->>'universe_v2' AS univ
FROM signals
WHERE status='active'
ORDER BY score DESC
LIMIT 15;
"
echo "=== majors in active? ==="
docker exec smas-postgres psql -U smas -d smas -c "
SELECT symbol, exchange, score
FROM signals
WHERE status='active'
  AND symbol IN ('BTCUSDT','ETHUSDT','SOLUSDT','XRPUSDT','BNBUSDT','DOGEUSDT','ADAUSDT')
ORDER BY score DESC;
"
echo "=== exchange mix ==="
docker exec smas-postgres psql -U smas -d smas -c "
SELECT exchange, count(*) FROM signals WHERE status='active' GROUP BY 1 ORDER BY 2 DESC;
"
