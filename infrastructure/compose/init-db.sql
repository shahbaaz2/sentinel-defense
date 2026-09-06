-- Creates the separate MissionNet and Demo Control databases/roles alongside the default sentinel
-- DB/role created by the postgres image's POSTGRES_USER/POSTGRES_DB env vars.
CREATE USER missionnet WITH PASSWORD 'missionnet';
CREATE DATABASE missionnet OWNER missionnet;
GRANT ALL PRIVILEGES ON DATABASE missionnet TO missionnet;

CREATE USER democontrol WITH PASSWORD 'democontrol';
CREATE DATABASE democontrol OWNER democontrol;
GRANT ALL PRIVILEGES ON DATABASE democontrol TO democontrol;

CREATE EXTENSION IF NOT EXISTS vector;
\connect sentinel
CREATE EXTENSION IF NOT EXISTS vector;
