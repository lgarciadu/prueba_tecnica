-- Script de inicialización de la base de datos para el Data Product de clima
-- Versión: 1.0
-- Descripción: Crea la base de datos y tabla para observaciones meteorológicas

-- Crear la base de datos si no existe
CREATE DATABASE IF NOT EXISTS testdb;
USE testdb;

-- Asegurar que el usuario use mysql_native_password para compatibilidad
ALTER USER 'weather_user'@'%' IDENTIFIED WITH mysql_native_password BY 'weather_pass';
FLUSH PRIVILEGES;

-- Eliminar tabla si existe (para facilitar reinicios en desarrollo)
DROP TABLE IF EXISTS weather_observations;

-- Crear tabla principal de observaciones meteorológicas
CREATE TABLE weather_observations (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    site_id VARCHAR(64) NOT NULL,
    observation_time DATETIME(3) NOT NULL,
    temp_c DECIMAL(5,2) NULL,
    humidity_pct TINYINT NULL,
    precipitation_mm VARCHAR(255) NULL,
    ingestion_run_id VARCHAR(64) NULL,
    fetch_time DATETIME(3) NOT NULL DEFAULT (UTC_TIMESTAMP(3)),
    audit_created_dttm DATETIME(3) DEFAULT (UTC_TIMESTAMP(3)),
    audit_updated_dttm DATETIME(3) NULL,
    
    -- Clave única compuesta para garantizar idempotencia
    UNIQUE KEY uq_site_source_obs (site_id, observation_time, temp_c),
    
    -- Índices para optimizar consultas frecuentes
    INDEX idx_site_obs_time (site_id, observation_time),
    INDEX idx_ingestion_run (ingestion_run_id),
    INDEX idx_audit_created (audit_created_dttm)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;