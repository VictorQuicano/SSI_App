#!/bin/bash
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<-EOSQL
    CREATE DATABASE postgres_wallet;
    GRANT ALL PRIVILEGES ON DATABASE postgres_wallet TO $POSTGRES_USER;
EOSQL