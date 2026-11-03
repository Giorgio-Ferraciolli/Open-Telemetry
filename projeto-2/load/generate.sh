#!/usr/bin/env bash

set -u

DURATION=${1:-600}
URL=${URL:-http://localhost:8000}

if ! [[ "$DURATION" =~ ^[1-9][0-9]*$ ]]; then
  printf 'Uso: %s [duracao_em_segundos]\n' "$0" >&2
  exit 2
fi

END=$((SECONDS + DURATION))
RUN_ID=$(date +%Y%m%d%H%M%S)
REQUESTS=0
FAILURES=0

printf 'Gerando carga em %s/api/items por %s segundos (1 req/s, sequencial)\n' "$URL" "$DURATION"

while (( SECONDS < END )); do
  REQUESTS=$((REQUESTS + 1))

  if (( REQUESTS % 2 == 1 )); then
    STATUS=$(curl --silent --show-error --output /dev/null --write-out '%{http_code}' \
      --max-time 5 -X POST "$URL/api/items" \
      -H 'Content-Type: application/json' \
      --data-binary "{\"name\":\"load-${RUN_ID}-${REQUESTS}\"}")
    CURL_STATUS=$?
  else
    STATUS=$(curl --silent --show-error --output /dev/null --write-out '%{http_code}' \
      --max-time 5 "$URL/api/items")
    CURL_STATUS=$?
  fi

  if (( CURL_STATUS != 0 )) || [[ ! "$STATUS" =~ ^2[0-9][0-9]$ ]]; then
    FAILURES=$((FAILURES + 1))
    printf '\nFalha na requisicao %d (HTTP %s, curl %d)\n' "$REQUESTS" "${STATUS:-sem resposta}" "$CURL_STATUS" >&2
  fi

  if (( REQUESTS % 30 == 0 )); then
    printf '\r%d requisicoes enviadas; %d falhas' "$REQUESTS" "$FAILURES"
  fi

  sleep 1
done

printf '\nConcluido: %d requisicoes; %d falhas.\n' "$REQUESTS" "$FAILURES"