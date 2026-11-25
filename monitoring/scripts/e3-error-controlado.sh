#!/usr/bin/env bash
# Escenario E3 - error controlado (Entrega 4, Juan David).
#
# Envia, durante un tiempo acotado, un POST /observability/error cada ERROR_INTERVAL
# segundos y, en paralelo, trafico normal autenticado (GET de un correo ficticio).
# Requiere que el servicio tenga OBS_LAB_ENABLED=true; si la ruta responde 404 se detiene.
#
# Uso (CloudShell, Git Bash o Linux):
#   export BASE_URL=http://<alb-propio>          # host explicito: solo infraestructura propia
#   export TOKEN='<jwt del ambiente>'             # no se imprime ni se escribe en disco
#   bash monitoring/scripts/e3-error-controlado.sh [DURACION_S] [DIRECTORIO_SALIDA]
#
# DURACION_S: 60-600 (por defecto 300). Salida: CSV con hora UTC, tipo y codigo HTTP,
# fuera del repositorio por defecto ($HOME/cb-e4-e3-<fecha>.csv).
set -euo pipefail

DURATION=${1:-300}
OUT_DIR=${2:-$HOME}
ERROR_INTERVAL=${ERROR_INTERVAL:-2}       # el endpoint acepta 1 error cada 2 s por proceso
NORMAL_INTERVAL=${NORMAL_INTERVAL:-1}
PROBE_EMAIL=${PROBE_EMAIL:-e3-probe@example.com}

: "${BASE_URL:?Definir BASE_URL con el host propio (sin barra final)}"
: "${TOKEN:?Definir TOKEN con el JWT del ambiente}"
command -v curl >/dev/null || { echo "Falta curl" >&2; exit 1; }

if ! [[ "$DURATION" =~ ^[0-9]+$ ]] || (( DURATION < 60 || DURATION > 600 )); then
  echo "DURACION_S debe estar entre 60 y 600" >&2; exit 1
fi
BASE_URL=${BASE_URL%/}
OUT="$OUT_DIR/cb-e4-e3-$(date -u +%Y%m%dT%H%M%SZ).csv"
AUTH="Authorization: Bearer $TOKEN"

code() { curl -s -o /dev/null -w '%{http_code}' --max-time 10 "$@" || true; }
log()  { printf '%s,%s,%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$1" "$2" >> "$OUT"; }

# Comprobaciones previas: servicio sano y ruta de laboratorio activa
health=$(code "$BASE_URL/health")
[[ "$health" == 200 ]] || { echo "/health respondio $health; no se inicia E3" >&2; exit 1; }
probe=$(code -X POST -H "$AUTH" "$BASE_URL/observability/error")
case "$probe" in
  500|429) echo "utc,tipo,http" > "$OUT"; log error "$probe" ;;
  404) echo "La ruta de laboratorio no existe (OBS_LAB_ENABLED=false)." >&2; exit 1 ;;
  401|422) echo "JWT rechazado ($probe)." >&2; exit 1 ;;
  *) echo "Respuesta inesperada de la ruta de laboratorio: $probe" >&2; exit 1 ;;
esac

START=$(date -u +%Y-%m-%dT%H:%M:%SZ)
END_AT=$(( $(date +%s) + DURATION ))
echo "E3 inicio $START UTC, duracion ${DURATION}s, salida $OUT"

normal_traffic() {
  while (( $(date +%s) < END_AT )); do
    log normal "$(code -H "$AUTH" "$BASE_URL/blacklists/$PROBE_EMAIL")"
    sleep "$NORMAL_INTERVAL"
  done
}
normal_traffic &
NORMAL_PID=$!
trap 'kill $NORMAL_PID 2>/dev/null || true' EXIT INT TERM

while (( $(date +%s) < END_AT )); do
  sleep "$ERROR_INTERVAL"
  log error "$(code -X POST -H "$AUTH" "$BASE_URL/observability/error")"
done
wait "$NORMAL_PID" 2>/dev/null || true

FIN=$(date -u +%Y-%m-%dT%H:%M:%SZ)
echo "E3 fin $FIN UTC. Iniciar E4: observar recuperacion y cierre del incidente."
echo "Resumen (tipo,http,cantidad):"
tail -n +2 "$OUT" | cut -d, -f2,3 | sort | uniq -c | awk '{print "  " $2 "," $1}'
echo "/health ahora: $(code "$BASE_URL/health")"
