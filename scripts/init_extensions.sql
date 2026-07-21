-- Runs automatically on first Postgres container init (docker-entrypoint-initdb.d).
-- Enables extensions required by the WhatsApp Agent MVP schema.
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "postgis";
CREATE EXTENSION IF NOT EXISTS "vector";
