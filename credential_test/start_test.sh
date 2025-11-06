#!/bin/bash
# ================================================
# Script para iniciar Aries Client con opciones
# Autor: [Tu Nombre]
# ================================================

# ===== CONFIGURACIÓN =====
GENESIS_URL_DEFAULT="http://localhost:9000/genesis"
GENESIS_LOCAL_PATH="./genesis/genesis.txn"
COMPOSE_FILE_DEFAULT="docker-compose-agents.yml"
PROJECT_NAME="aries_test"
ISSUER_ADMIN_URL="http://localhost:8031/status"
HOLDER_ADMIN_URL="http://localhost:8041/status"
WAIT_TIMEOUT=60
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
  if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    echo "docker compose -f \"$COMPOSE_FILE\" -p \"$PROJECT_NAME\""
  elif command -v docker-compose >/dev/null 2>&1; then
    echo "docker-compose -f \"$COMPOSE_FILE\" -p \"$PROJECT_NAME\""
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

# esperar que los agentes respondan por su Admin API
echo "⏳ Esperando que Issuer y Holder estén listos (timeout ${WAIT_TIMEOUT}s)..."
if ! wait_for_status "$ISSUER_ADMIN_URL" "$WAIT_TIMEOUT"; then
  echo "❌ Issuer no respondió a tiempo. Revisa logs: docker logs acapy-issuer" >&2
  exit 1
fi
if ! wait_for_status "$HOLDER_ADMIN_URL" "$WAIT_TIMEOUT"; then
  echo "❌ Holder no respondió a tiempo. Revisa logs: docker logs acapy-holder" >&2
  exit 1
fi

echo "🎉 ¡Ambos agentes están listos!"
echo "Issuer admin: http://localhost:8031"
echo "Holder admin: http://localhost:8041"
echo
echo "Para ejecutar la prueba, en otra terminal:"
echo "  python3 connect_and_issue.py"
