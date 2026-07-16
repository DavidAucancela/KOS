-- Inicialización de PostgreSQL para KOS.
-- Se ejecuta una sola vez al crear el contenedor.

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;      -- búsqueda difusa de texto
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";  -- generación de UUIDs

-- Los esquemas de tablas se gestionan con migraciones (Alembic) desde la Fase 1.
-- Este archivo solo prepara extensiones que requieren superusuario.
