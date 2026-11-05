#!/bin/sh
set -eu

: "${TEXT_TO_SQL_DB_USER:=text_to_sql_reader}"
: "${TEXT_TO_SQL_DB_PASSWORD:?TEXT_TO_SQL_DB_PASSWORD must be set}"

psql -v ON_ERROR_STOP=1 \
    --username "$POSTGRES_USER" \
    --dbname "$POSTGRES_DB" \
    -v role="$TEXT_TO_SQL_DB_USER" \
    -v password="$TEXT_TO_SQL_DB_PASSWORD" \
    -v database="$POSTGRES_DB" \
    -v test_database="${POSTGRES_DB}_test" <<'EOSQL'
SELECT format(
    'CREATE ROLE %I LOGIN PASSWORD %L',
    :'role',
    :'password'
)
WHERE NOT EXISTS (
    SELECT 1 FROM pg_roles WHERE rolname = :'role'
)
\gexec

SELECT format(
    'ALTER ROLE %I PASSWORD %L',
    :'role',
    :'password'
)
\gexec

SELECT format(
    'GRANT CONNECT ON DATABASE %I TO %I',
    :'database',
    :'role'
)
\gexec

SELECT format(
    'GRANT CONNECT ON DATABASE %I TO %I',
    :'test_database',
    :'role'
)
WHERE EXISTS (
    SELECT 1 FROM pg_database WHERE datname = :'test_database'
)
\gexec
EOSQL
