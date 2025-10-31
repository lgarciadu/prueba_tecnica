#!/usr/bin/env python3
"""
Módulo de utilidades para queries SQL
Versión: 1.0

Descripción:
    Centraliza todas las queries SQL utilizadas en el proceso ETL
    para facilitar mantenimiento y actualizaciones.

Uso:
    from utils.db_queries import get_insert_weather_observation_query
    
    query = get_insert_weather_observation_query()
    cursor.execute(query, weather_data)
"""

# Query de inserción/actualización de observaciones meteorológicas
# Utiliza ON DUPLICATE KEY UPDATE para garantizar idempotencia
# La clave única es (site_id, observation_time, temp_c) según init.sql
INSERT_WEATHER_OBSERVATION = """
INSERT INTO weather_observations 
(site_id, observation_time, temp_c, humidity_pct, 
precipitation_mm, ingestion_run_id, fetch_time)
VALUES (%s, %s, %s, %s, %s, %s, %s)
ON DUPLICATE KEY UPDATE
    fetch_time = VALUES(fetch_time),
    temp_c = VALUES(temp_c),
    humidity_pct = VALUES(humidity_pct),
    precipitation_mm = VALUES(precipitation_mm),
    ingestion_run_id = VALUES(ingestion_run_id),
    audit_updated_dttm = UTC_TIMESTAMP(3)
"""


def get_insert_weather_observation_query() -> str:
    """
    Retorna la query SQL para insertar/actualizar observaciones meteorológicas.
    
    Returns:
        String con la query SQL de inserción con manejo de duplicados
    """
    return INSERT_WEATHER_OBSERVATION


