#!/usr/bin/env bash
# Deploy isolated SMAS stack on VPS. Never touches host postgres/redis containers.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

COMPOSE="docker compose -f docker-compose.vps.yml --env-file docker/.env.vps"

if [[ ! -f docker/.env.vps ]]; then
  echo "Missing docker/.env.vps — copy from docker/.env.vps.example and set SMAS_PG_PASSWORD"
  exit 1
fi

echo "==> Building & starting SMAS (isolated project name=smas)"
$COMPOSE up -d --build

echo "==> Waiting for API health..."
for i in $(seq 1 40); do
  if curl -fsS "http://127.0.0.1:8010/health" >/dev/null 2>&1; then
    echo "API OK"
    curl -fsS "http://127.0.0.1:8010/health"
    echo
    break
  fi
  sleep 3
  if [[ $i -eq 40 ]]; then
    echo "API health timeout"; $COMPOSE logs --tail=80 api; exit 1
  fi
done

echo "==> Existing host DB/Redis (untouched):"
docker ps --format 'table {{.Names}}\t{{.Ports}}\t{{.Status}}' | grep -E 'NAMES|postgres|redis|smas' || true

echo "==> SMAS URLs:"
echo "  API:  http://$(curl -4 -s --max-time 3 ifconfig.me || echo 108.174.78.39):8010/health"
echo "  Web:  http://$(curl -4 -s --max-time 3 ifconfig.me || echo 108.174.78.39):3010"
echo "Done."
