#!/usr/bin/env python3
"""
Script para verificar duplicados en la tabla weather_observations
Versión: 1.0
Python objetivo: 3.10+

Descripción:
    Conecta a MySQL y verifica si existen registros duplicados
    basados en la clave única (site_id, source, observation_time).

Uso:
    python check_duplicates_mysql.py

Códigos de salida:
    0: No se encontraron duplicados
    2: Se encontraron duplicados

Autor: Data Engineering Team
"""

import os
import sys
from typing import List, Tuple

import pymysql
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()


def get_db_connection():
    """
    Obtiene una conexión a la base de datos MySQL.
    
    Returns:
        Conexión a MySQL
    """
    config = {
        'host': os.getenv('DB_HOST', '127.0.0.1'),
        'port': int(os.getenv('DB_PORT', 3306)),
        'user': os.getenv('DB_USER', 'root'),
        'password': os.getenv('DB_PASSWORD', 'rootpass'),
        'database': os.getenv('DB_NAME', 'testdb'),
        'charset': 'utf8mb4'
    }
    
    try:
        connection = pymysql.connect(**config)
        return connection
    except Exception as e:
        print(f"ERROR: No se pudo conectar a MySQL: {e}")
        sys.exit(1)


def check_duplicates() -> Tuple[bool, List[Tuple]]:
    """
    Verifica si existen duplicados en la tabla weather_observations.
    
    Returns:
        Tupla (hay_duplicados, lista_de_duplicados)
    """
    query = """
    SELECT 
        site_id, 
        source, 
        observation_time, 
        COUNT(*) AS cnt
    FROM weather_observations
    GROUP BY site_id, source, observation_time
    HAVING cnt > 1
    ORDER BY cnt DESC, site_id, observation_time
    """
    
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(query)
                duplicates = cursor.fetchall()
                
                return len(duplicates) > 0, duplicates
                
    except Exception as e:
        print(f"ERROR ejecutando consulta: {e}")
        sys.exit(1)


def main():
    """Función principal del script."""
    print("Verificando duplicados en weather_observations...")
    
    # Verificar duplicados
    has_duplicates, duplicates = check_duplicates()
    
    if not has_duplicates:
        print("OK: no duplicate groups found.")
        sys.exit(0)
    else:
        print(f"ERROR: Se encontraron {len(duplicates)} grupos duplicados:")
        print()
        
        # Mostrar ejemplos de duplicados
        print("Ejemplos de duplicados encontrados:")
        print("-" * 80)
        print(f"{'Site ID':<8} {'Source':<15} {'Observation Time':<20} {'Count':<5}")
        print("-" * 80)
        
        for site_id, source, obs_time, count in duplicates[:10]:  # Mostrar máximo 10
            print(f"{site_id:<8} {source:<15} {str(obs_time):<20} {count:<5}")
        
        if len(duplicates) > 10:
            print(f"... y {len(duplicates) - 10} grupos más")
        
        print("-" * 80)
        print(f"Total de grupos duplicados: {len(duplicates)}")
        print()
        print("Recomendación: Revisar el proceso ETL para evitar duplicados.")
        
        sys.exit(2)


if __name__ == '__main__':
    main()
