#!/bin/bash
# Gera tráfego contra a api-python pra povoar a telemetria.
# Uso: ./load/generate.sh           (loop infinito)
#      ./load/generate.sh 30        (roda por 30 segundos)

DURATION=${1:-0}
END=$(( $(date +%s) + DURATION ))
URL="http://localhost:8001"

i=0
while true; do
  curl -s "$URL/" > /dev/null
  curl -s "$URL/products" > /dev/null
  curl -s "$URL/products/$((RANDOM % 4 + 1))" > /dev/null
  curl -s "$URL/checkout/$((RANDOM % 4 + 1))" > /dev/null
  [ $((RANDOM % 3)) -eq 0 ] && curl -s "$URL/slow" > /dev/null
  [ $((RANDOM % 5)) -eq 0 ] && curl -s "$URL/broken" > /dev/null
  i=$((i + 1))
  printf "\r  %d ciclos enviados" "$i"
  [ "$DURATION" -gt 0 ] && [ "$(date +%s)" -ge "$END" ] && break
  sleep 0.5
done
echo ""
