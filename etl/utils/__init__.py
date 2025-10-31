"""
Módulo de utilidades para el ETL de datos meteorológicos.
"""

from .db_queries import (
    get_insert_weather_observation_query,
    INSERT_WEATHER_OBSERVATION
)

__all__ = [
    'get_insert_weather_observation_query',
    'INSERT_WEATHER_OBSERVATION'
]

