#!/bin/bash

GENESIS_URL="http://localhost:9000/genesis"
GENESIS_FILE="genesis.txn"

echo "📥 Descargando genesis..."
wget -q $GENESIS_URL -O $GENESIS_FILE

if [ $? -ne 0 ]; then
  echo "❌ Error descargando genesis"
  exit 1
fi

echo "🚀 Iniciando Issuer..."
docker compose up -d
