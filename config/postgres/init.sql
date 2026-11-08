-- Mirrors what you enable on Azure Database for PostgreSQL Flexible Server
-- (azure.extensions = VECTOR) so app code is identical locally and in Azure.
CREATE EXTENSION IF NOT EXISTS vector;
