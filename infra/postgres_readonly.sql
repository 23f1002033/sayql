-- Read-only role for SayQL's executor, for the Postgres seam.
-- Apply against the analytics database after ingest has created the tables.
-- The demo itself runs on SQLite; this is for local/Postgres use only.

CREATE ROLE sayql_reader LOGIN PASSWORD 'change_me';
GRANT CONNECT ON DATABASE sayql TO sayql_reader;
GRANT USAGE ON SCHEMA public TO sayql_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO sayql_reader;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO sayql_reader;
