#!/bin/bash
# ================================================
# Script para iniciar Aries Client con opciones
# Autor: [Tu Nombre]
# ================================================

# ===== CONFIGURACIÓN =====
GENESIS_URL_DEFAULT="http://localhost:9000/genesis"
GENESIS_FILE="aries_client/genesis.txn"
COMPOSE_DIR="aries_client"

# ===== FUNCIONES =====
function show_help() {
  echo "Uso: $0 [opciones]"
  echo
  echo "Opciones:"
  echo "  -u, --url <URL>          URL del archivo genesis (por defecto: $GENESIS_URL_DEFAULT)"
  echo "  -r, --rebuild            Reconstruye los contenedores (docker-compose build --no-cache)"
  echo "  -d, --down               Elimina los contenedores y volúmenes (docker-compose down -v)"
  echo "  -h, --help               Muestra esta ayuda"
  echo
  echo "Ejemplo:"
  echo "  $0 --url http://mi-servidor:9000/genesis --rebuild"
}

# ===== PARSEAR ARGUMENTOS =====
GENESIS_URL=$GENESIS_URL_DEFAULT
REBUILD=false
DOWN=false

while [[ "$#" -gt 0 ]]; do
  case $1 in
    -u|--url) GENESIS_URL="$2"; shift ;;
    -r|--rebuild) REBUILD=true ;;
    -d|--down) DOWN=true ;;
    -h|--help) show_help; exit 0 ;;
    *) echo "Opción desconocida: $1"; show_help; exit 1 ;;
  esac
  shift
done

# ===== DESCARGAR ARCHIVO GENESIS =====
echo "Descargando archivo genesis desde: $GENESIS_URL"
mkdir -p "$COMPOSE_DIR"
wget -q "$GENESIS_URL" -O "$GENESIS_FILE"

if [ $? -ne 0 ]; then
  echo "❌ Error al descargar el archivo genesis desde $GENESIS_URL"
  exit 1
else
  echo "✅ Archivo genesis descargado correctamente en $GENESIS_FILE"
fi

# ===== GESTIONAR DOCKER =====
cd "$COMPOSE_DIR" || { echo "❌ No se encontró el directorio $COMPOSE_DIR"; exit 1; }

if [ "$DOWN" = true ]; then
  echo "🧹 Eliminando contenedores y volúmenes..."
  docker compose down -v
  exit 2
fi

if [ "$REBUILD" = true ]; then
  echo "🔧 Reconstruyendo contenedores..."
  docker compose build --no-cache
fi

echo "🚀 Iniciando contenedores..."
docker compose up -d

cd - >/dev/null

echo "✅ Todo listo. Contenedores en ejecución."
