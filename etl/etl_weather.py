#!/usr/bin/env python3
"""
ETL Job para datos climáticos
Versión: 1.0
Python objetivo: 3.10+

Descripción:
    Script ETL que extrae datos meteorológicos de una API externa,
    los normaliza y los almacena en MySQL con garantía de idempotencia.

Uso:
    python etl_weather.py [--dry-run]

Ejemplos:
    # Ejecución normal
    python etl_weather.py
    
    # Ejecución de prueba (sin escribir a BD)
    python etl_weather.py --dry-run

Autor: Data Engineering Team
"""

import argparse
import json
import logging
import os
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

import pymysql
import requests
from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from tqdm import tqdm

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


class WeatherETL:
    """Clase principal para el procesamiento ETL de datos climáticos."""
    
    def __init__(self, dry_run: bool = False):
        """
        Inicializa el ETL con configuración desde variables de entorno.
        
        Args:
            dry_run: Si True, no escribe datos a la base de datos
        """
        self.dry_run = dry_run
        self.ingestion_run_id = str(uuid.uuid4())
        
        # Cargar variables de entorno
        load_dotenv()
        
        # Configuración de base de datos
        self.db_config = {
            'host': os.getenv('DB_HOST', '127.0.0.1'),
            'port': int(os.getenv('DB_PORT', 3306)),
            'user': os.getenv('DB_USER', 'root'),
            'password': os.getenv('DB_PASSWORD', 'rootpass'),
            'database': os.getenv('DB_NAME', 'testdb'),
            'charset': 'utf8mb4'
        }
        
        # Configuración de API
        self.api_base = os.getenv('API_BASE', 'https://archive-api.open-meteo.com/v1/archive')
        self.max_workers = int(os.getenv('MAX_WORKERS', 8))
        self.request_timeout = int(os.getenv('REQUEST_TIMEOUT', 30))
        self.max_retries = int(os.getenv('MAX_RETRIES', 3))
        
        # Estadísticas de ejecución
        self.stats = {
            'total_sites': 0,
            'successful': 0,
            'failed': 0,
            'errors': []
        }
        
        logger.info(f"Iniciando ETL - Run ID: {self.ingestion_run_id}")
        logger.info(f"Modo dry-run: {'SÍ' if self.dry_run else 'NO'}")
    
    def load_sites(self) -> List[Dict]:
        """
        Carga la lista de sitios desde el archivo JSON de configuración.
        
        Returns:
            Lista de diccionarios con información de sitios
        """
        try:
            config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'sites_sample.json')
            with open(config_path, 'r', encoding='utf-8') as f:
                sites = json.load(f)
            
            logger.info(f"Cargados {len(sites)} sitios desde configuración")
            return sites
            
        except Exception as e:
            logger.error(f"Error cargando sitios: {e}")
            raise
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((requests.exceptions.RequestException,))
    )
    def fetch_weather_data(self, site: Dict) -> Optional[List[Dict]]:
        """
        Obtiene datos meteorológicos para un sitio específico.
        
        Args:
            site: Diccionario con información del sitio (lat, lon, site_id)
            
        Returns:
            Lista de diccionarios con datos meteorológicos normalizados o None si falla
        """
        try:
            # Construir URL de la API
            params = {
                'latitude': site['latitude'],
                'longitude': site['longitude'],
                'timezone': site['timezone'],
                'start_date': '2025-09-14',
                'end_date': '2025-10-28',
                'hourly': 'temperature_2m,relative_humidity_2m,precipitation',
            }
            
            # Realizar llamada a la API
            response = requests.get(
                self.api_base,
                params=params,
                timeout=self.request_timeout
            )
            response.raise_for_status()
            
            data = response.json()
            
            # Normalizar datos (ahora retorna una lista)
            normalized_data = self._normalize_weather_data(data, site)
            
            logger.debug(f"Datos obtenidos para sitio {site['site_id']} ({site['name']}) - {len(normalized_data)} registros")
            return normalized_data
            
        except requests.exceptions.RequestException as e:
            logger.warning(f"Error en API para sitio {site['site_id']}: {e}")
            raise
        except Exception as e:
            logger.error(f"Error inesperado para sitio {site['site_id']}: {e}")
            return None
    
    def _normalize_weather_data(self, raw_data: Dict, site: Dict) -> List[Dict]:
        """
        Normaliza los datos meteorológicos de la API (formato archive).
        Retorna una lista de registros normalizados para todo el rango de fechas.
        """
        try:
            site_id = site['site_id']
            now_utc = datetime.now(timezone.utc)
            normalized_records = []

            if "hourly" in raw_data:
                hourly = raw_data["hourly"]
                times = hourly.get("time", [])
                temps = hourly.get("temperature_2m", [])
                hums = hourly.get("relative_humidity_2m", [])
                precs = hourly.get("precipitation", [])

                if not times:
                    raise ValueError("No se encontraron timestamps en la respuesta")

                # Procesar TODOS los registros del rango de fechas
                for i in range(len(times)):
                    observation_time = datetime.fromisoformat(times[i])
                    
                    temp_c = temps[i] if i < len(temps) else None
                    humidity_pct = hums[i] if i < len(hums) else None
                    precipitation_mm = precs[i] if i < len(precs) else None

                    normalized_record = {
                        "site_id": site_id,
                        "source": "open-meteo",
                        "observation_time": observation_time,
                        "fetch_time": now_utc,
                        "temp_c": temp_c,
                        "humidity_pct": humidity_pct,
                        "pressure_hpa": None,
                        "weather_description": f"precipitation={precipitation_mm}mm",
                        "raw_payload": json.dumps(raw_data),
                        "ingestion_run_id": self.ingestion_run_id
                    }
                    normalized_records.append(normalized_record)

                logger.debug(f"Procesados {len(normalized_records)} registros para sitio {site_id}")
                return normalized_records

            else:
                raise ValueError("Estructura de respuesta no reconocida (falta 'hourly')")

        except Exception as e:
            logger.error(f"Error normalizando datos para sitio {site_id}: {e}")
            raise

        
    def get_db_connection(self):
        """Obtiene una conexión a la base de datos MySQL."""
        try:
            connection = pymysql.connect(**self.db_config)
            return connection
        except Exception as e:
            logger.error(f"Error conectando a MySQL: {e}")
            raise
    
    def save_weather_data(self, weather_data: Dict) -> bool:
        """
        Guarda los datos meteorológicos en la base de datos.
        
        Args:
            weather_data: Diccionario con datos normalizados
            
        Returns:
            True si se guardó exitosamente, False en caso contrario
        """
        if self.dry_run:
            logger.info(f"[DRY-RUN] Guardando datos para sitio {weather_data['site_id']}")
            return True
        
        try:
            with self.get_db_connection() as conn:
                with conn.cursor() as cursor:
                    # Query de inserción con manejo de duplicados
                    insert_query = """
                    INSERT INTO weather_observations 
                    (site_id, source, observation_time, fetch_time, temp_c, humidity_pct, 
                     pressure_hpa, weather_description, raw_payload, ingestion_run_id)
                    VALUES (%(site_id)s, %(source)s, %(observation_time)s, %(fetch_time)s, 
                            %(temp_c)s, %(humidity_pct)s, %(pressure_hpa)s, %(weather_description)s, 
                            %(raw_payload)s, %(ingestion_run_id)s)
                    ON DUPLICATE KEY UPDATE
                        fetch_time = VALUES(fetch_time),
                        temp_c = VALUES(temp_c),
                        humidity_pct = VALUES(humidity_pct),
                        pressure_hpa = VALUES(pressure_hpa),
                        weather_description = VALUES(weather_description),
                        raw_payload = VALUES(raw_payload),
                        ingestion_run_id = VALUES(ingestion_run_id),
                        audit_updated_by = 'etl_job',
                        audit_updated_dttm = UTC_TIMESTAMP(3)
                    """
                    
                    cursor.execute(insert_query, weather_data)
                    conn.commit()
                    
            logger.debug(f"Datos guardados para sitio {weather_data['site_id']}")
            return True
            
        except Exception as e:
            logger.error(f"Error guardando datos para sitio {weather_data['site_id']}: {e}")
            return False
    
    def process_site(self, site: Dict) -> Tuple[bool, str]:
        """
        Procesa un sitio individual: obtiene datos y los guarda.
        
        Args:
            site: Diccionario con información del sitio
            
        Returns:
            Tupla (éxito, mensaje)
        """
        try:
            # Obtener datos meteorológicos (ahora es una lista)
            weather_data_list = self.fetch_weather_data(site)
            
            if weather_data_list is None or len(weather_data_list) == 0:
                return False, f"No se pudieron obtener datos para {site['name']}"
            
            # Guardar cada registro en base de datos
            successful_saves = 0
            for weather_data in weather_data_list:
                success = self.save_weather_data(weather_data)
                if success:
                    successful_saves += 1
            
            if successful_saves == len(weather_data_list):
                return True, f"Datos procesados exitosamente para {site['name']} - {successful_saves} registros guardados"
            elif successful_saves > 0:
                return False, f"Guardados parcialmente {successful_saves}/{len(weather_data_list)} registros para {site['name']}"
            else:
                return False, f"Error guardando datos para {site['name']}"
                
        except Exception as e:
            error_msg = f"Error procesando {site['name']}: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    def run_etl(self):
        """Ejecuta el proceso ETL completo."""
        try:
            # Cargar sitios
            sites = self.load_sites()
            self.stats['total_sites'] = len(sites)
            
            if not sites:
                logger.warning("No se encontraron sitios para procesar")
                return
            
            logger.info(f"Procesando {len(sites)} sitios con {self.max_workers} workers")
            
            # Procesar sitios en paralelo
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # Enviar tareas
                future_to_site = {
                    executor.submit(self.process_site, site): site 
                    for site in sites
                }
                
                # Procesar resultados con barra de progreso
                with tqdm(total=len(sites), desc="Procesando sitios") as pbar:
                    for future in as_completed(future_to_site):
                        site = future_to_site[future]
                        
                        try:
                            success, message = future.result()
                            
                            if success:
                                self.stats['successful'] += 1
                                logger.info(f"✓ {message}")
                            else:
                                self.stats['failed'] += 1
                                self.stats['errors'].append(message)
                                logger.error(f"✗ {message}")
                                
                        except Exception as e:
                            self.stats['failed'] += 1
                            error_msg = f"Error inesperado procesando {site['name']}: {e}"
                            self.stats['errors'].append(error_msg)
                            logger.error(f"✗ {error_msg}")
                        
                        pbar.update(1)
            
            # Mostrar resumen final
            self._print_summary()
            
        except Exception as e:
            logger.error(f"Error crítico en ETL: {e}")
            sys.exit(1)
    
    def _print_summary(self):
        """Imprime el resumen final de la ejecución."""
        logger.info("=" * 60)
        logger.info("RESUMEN DE EJECUCIÓN ETL")
        logger.info("=" * 60)
        logger.info(f"Run ID: {self.ingestion_run_id}")
        logger.info(f"Total sitios: {self.stats['total_sites']}")
        logger.info(f"Exitosos: {self.stats['successful']}")
        logger.info(f"Fallidos: {self.stats['failed']}")
        logger.info(f"Modo dry-run: {'SÍ' if self.dry_run else 'NO'}")
        
        if self.stats['errors']:
            logger.info("\nErrores encontrados:")
            for error in self.stats['errors'][:5]:  # Mostrar solo los primeros 5
                logger.info(f"  - {error}")
            if len(self.stats['errors']) > 5:
                logger.info(f"  ... y {len(self.stats['errors']) - 5} errores más")
        
        logger.info("=" * 60)


def main():
    """Función principal del script."""
    parser = argparse.ArgumentParser(description='ETL Job para datos climáticos')
    parser.add_argument(
        '--dry-run', 
        action='store_true', 
        help='Ejecutar en modo de prueba sin escribir a la base de datos'
    )
    
    args = parser.parse_args()
    
    # Crear y ejecutar ETL
    etl = WeatherETL(dry_run=args.dry_run)
    etl.run_etl()


if __name__ == '__main__':
    main()
