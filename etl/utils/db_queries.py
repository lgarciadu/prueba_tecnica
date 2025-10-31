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
INSERT_WEATHER_OBSERVATION = """
INSERT INTO weather_observations 
(site_id, source, observation_time, fetch_time, temp_c, humidity_pct, 
weather_description, raw_payload, ingestion_run_id)
VALUES (%(site_id)s, %(source)s, %(observation_time)s, %(fetch_time)s, 
        %(temp_c)s, %(humidity_pct)s, %(weather_description)s, 
        %(raw_payload)s, %(ingestion_run_id)s)
ON DUPLICATE KEY UPDATE
    fetch_time = VALUES(fetch_time),
    temp_c = VALUES(temp_c),
    humidity_pct = VALUES(humidity_pct),
    weather_description = VALUES(weather_description),
    raw_payload = VALUES(raw_payload),
    ingestion_run_id = VALUES(ingestion_run_id),
    audit_updated_by = 'etl_job',
    audit_updated_dttm = UTC_TIMESTAMP(3)
"""


def get_insert_weather_observation_query() -> str:
    """
    Retorna la query SQL para insertar/actualizar observaciones meteorológicas.
    
    Returns:
        String con la query SQL de inserción con manejo de duplicados
    """
    return INSERT_WEATHER_OBSERVATION


