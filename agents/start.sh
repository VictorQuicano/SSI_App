#!/bin/bash
# ================================================
# Script para iniciar Aries Client con opciones
# Autor:
# ================================================

# ===== CONFIGURACIÓN =====
GENESIS_URL_DEFAULT="http://localhost:9000/genesis"
GENESIS_LOCAL_PATH="./genesis/genesis.txn"
COMPOSE_FILE_DEFAULT="docker-compose.yml"
ISSUER_ADMIN_URL="http://localhost:8031/status"
WAIT_TIMEOUT=60

ALL_AGENTS=(
  "http://localhost:8031/status"   # issuer
  "http://localhost:8051/status"   # evtol1
  "http://localhost:8061/status"   # vertiport1
  "http://localhost:8071/status"   # vertiport2
  "http://localhost:8081/status"   # holder (multitenant)
)
VON_REGISTER_URL="http://localhost:9000/register"
ISSUER_DID="Utwqp5cpEATQpGZL5WSQZJ"
ISSUER_VERKEY="GCqSzwWVsRumDY67zkBACHs92zQJpg71WKmFEHnTreUQ"
POLL_INTERVAL=2

# ===== PARSEAR ARGUMENTOS =====
GENESIS_URL="$GENESIS_URL_DEFAULT"
COMPOSE_FILE="$COMPOSE_FILE_DEFAULT"
REBUILD=false
DOWN=false

# ===== FUNCIONES =====
function show_help() {
  cat <<EOF
Uso: $0 [opciones]

Opciones:
  -u, --url <URL>            URL del archivo genesis (por defecto: $GENESIS_URL_DEFAULT)
  -f, --compose-file <FILE>  Archivo docker-compose-agents (por defecto: $COMPOSE_FILE_DEFAULT)
  -r, --rebuild              Reconstruir contenedores (docker compose build --no-cache)
  -d, --down                 Bajar contenedores del proyecto y volúmenes
  -h, --help                 Muestra esta ayuda
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -u|--url) GENESIS_URL="$2"; shift 2 ;;
    -f|--compose-file) COMPOSE_FILE="$2"; shift 2 ;;
    -r|--rebuild) REBUILD=true; shift ;;
    -d|--down) DOWN=true; shift ;;
    -h|--help) show_help; exit 0 ;;
    *) echo "Opción desconocida: $1"; show_help; exit 1 ;;
  esac
done

# ===== FUNCIONES AUX =====
function docker_compose_cmd() {
  # usa docker compose si existe, si no usa docker-compose
  # sin -p para que el project name sea el directorio (consistente con docker compose stop/start manual)
  if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    echo "docker compose -f \"$COMPOSE_FILE\""
  elif command -v docker-compose >/dev/null 2>&1; then
    echo "docker-compose -f \"$COMPOSE_FILE\""
  else
    echo "ERROR: ni 'docker compose' ni 'docker-compose' están disponibles en el PATH." >&2
    exit 1
  fi
}

function run_compose() {
  eval "$(docker_compose_cmd) up -d"
}

function build_compose() {
  eval "$(docker_compose_cmd) build --no-cache"
}

function down_compose() {
  eval "$(docker_compose_cmd) down -v"
}

function ensure_genesis() {
  mkdir -p "$(dirname "$GENESIS_LOCAL_PATH")"
  if [ -f "$GENESIS_LOCAL_PATH" ]; then
    echo "ℹ️  Usando genesis existente: $GENESIS_LOCAL_PATH"
    return 0
  fi
  echo "⬇️  Descargando genesis desde: $GENESIS_URL  ->  $GENESIS_LOCAL_PATH"
  if command -v curl >/dev/null 2>&1; then
    curl -sSf "$GENESIS_URL" -o "$GENESIS_LOCAL_PATH" || { echo "❌ Error descargando genesis"; return 1; }
  elif command -v wget >/dev/null 2>&1; then
    wget -q "$GENESIS_URL" -O "$GENESIS_LOCAL_PATH" || { echo "❌ Error descargando genesis"; return 1; }
  else
    echo "ERROR: ni curl ni wget instalados para descargar genesis." >&2
    return 1
  fi
  echo "✅ Genesis descargado."
  return 0
}

function stop_existing_multitenant() {
  # si existe un contenedor con nombre aca-py-agent, lo paramos para evitar conflictos
  if docker ps --format '{{.Names}}' | grep -q '^aca-py-agent$'; then
    echo "⚠️  Contenedor 'aca-py-agent' detectado en ejecución. Se detendrá para evitar conflictos..."
    docker stop aca-py-agent || true
    docker rm -f aca-py-agent || true
    echo "✅ 'aca-py-agent' detenido y removido."
  fi
}

function register_issuer_did() {
  echo "📝 Registrando DID del issuer en la VON Network (idempotente)..."
  local body
  body=$(curl -s -X POST "$VON_REGISTER_URL" \
    -H "Content-Type: application/json" \
    -d "{\"did\":\"${ISSUER_DID}\",\"verkey\":\"${ISSUER_VERKEY}\",\"alias\":\"issuer\",\"role\":\"TRUST_ANCHOR\"}")
  if echo "$body" | grep -q "\"did\""; then
    echo "✅ DID del issuer listo en el ledger."
  else
    echo "❌ Error registrando DID del issuer: $body" >&2
    return 1
  fi
}

function wait_for_status() {
  local url="$1"; local timeout="$2"
  local startt=$(date +%s)
  while true; do
    if curl -sS "$url" >/dev/null 2>&1; then
      echo "✅ $url responde correctamente."
      return 0
    fi
    now=$(date +%s)
    diff=$((now - startt))
    if [ "$diff" -ge "$timeout" ]; then
      echo "❌ Timeout esperando $url (esperado $timeout s)." >&2
      return 1
    fi
    sleep "$POLL_INTERVAL"
  done
}

# ===== ACCIONES =====
# Si --down: bajar y salir
if [ "$DOWN" = true ]; then
  echo "🧹 Ejecutando 'down' del compose: $COMPOSE_FILE"
  down_compose
  echo "✅ Servicios bajados."
  exit 0
fi

# comprobar existencia del compose file
if [ ! -f "$COMPOSE_FILE" ]; then
  echo "ERROR: No se encontró el archivo de compose: $COMPOSE_FILE" >&2
  exit 1
fi

# preparar genesis
if ! ensure_genesis; then
  echo "ERROR: No se pudo obtener genesis. Abortando." >&2
  exit 1
fi

# Registrar DID del issuer en el ledger (si aún no está)
if ! register_issuer_did; then
  echo "ERROR: No se pudo registrar el DID del issuer. Abortando." >&2
  exit 1
fi

# Detener contenedor multitenant si existe (evita puertos/recursos en uso)
stop_existing_multitenant

# rebuild si aplica
if [ "$REBUILD" = true ]; then
  echo "🔧 Reconstruyendo imágenes..."
  build_compose
fi

# arrancar
echo "🚀 Iniciando servicios con compose: $COMPOSE_FILE"
run_compose

# esperar que todos los agentes respondan por su Admin API
echo "⏳ Esperando que los 5 agentes estén listos (timeout ${WAIT_TIMEOUT}s)..."
agent_names=("issuer" "evtol1" "vertiport1" "vertiport2" "holder")
for i in "${!ALL_AGENTS[@]}"; do
  url="${ALL_AGENTS[$i]}"
  name="${agent_names[$i]}"
  if ! wait_for_status "$url" "$WAIT_TIMEOUT"; then
    echo "❌ ${name} no respondió a tiempo. Revisa logs: docker logs acapy-${name}" >&2
    exit 1
  fi
done

echo "🎉 ¡Los 5 agentes están listos!"
echo "  Issuer:     http://localhost:8031"
echo "  eVTOL1:     http://localhost:8051"
echo "  Vertiport1: http://localhost:8061"
echo "  Vertiport2: http://localhost:8071"
echo "  Holder:     http://localhost:8081 (multitenant)"
echo
echo "Para ejecutar la prueba integral, en otra terminal:"
echo "  cd ~/Documentos/TI3/SSI_App"
echo "  python agents/scripts/test_all.py"
