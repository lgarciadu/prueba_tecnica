#!/usr/bin/env python3
"""
ETL Job para datos climáticos en modo STREAMING
Versión: 1.0
Python objetivo: 3.10+

Descripción:
    Script ETL que extrae datos meteorológicos de forecast API en modo streaming,
    los normaliza y los almacena en MySQL inmediatamente a medida que se procesan.
    A diferencia del ETL batch, este procesa y guarda datos uno por uno o en
    pequeños lotes para minimizar la latencia.

Uso:
    python etl_weather_streaming.py [--dry-run] [--interval SECONDS]

Ejemplos:
    # Ejecución normal (una vez)
    python etl_weather_streaming.py
    
    # Ejecución de prueba (sin escribir a BD)
    python etl_weather_streaming.py --dry-run
    
    # Ejecución continua cada 3600 segundos (1 hora)
    python etl_weather_streaming.py --interval 3600

Autor: Basado en etl_weather.py
"""

import argparse
import json
import logging
import os
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Dict, Iterator, List, Optional, Tuple

import pymysql
import requests
from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type, RetryCallState
from tqdm import tqdm

from utils.db_queries import get_insert_weather_observation_query

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


class WeatherETLStreaming:
    """Clase principal para el procesamiento ETL de datos climáticos en modo streaming."""

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
        
        if self._validate_env_variables():
            self.db_config = {
                'host': os.getenv('DB_HOST'),
                'port': int(os.getenv('DB_PORT')),
                'user': os.getenv('DB_USER'),
                'password': os.getenv('DB_PASSWORD'),
                'database': os.getenv('DB_NAME'),
                'charset': 'utf8mb4'
            }
            # API base para forecast (diferente del batch que usa archive)
            self.api_base = os.getenv('API_BASE_FORECAST', 'https://api.open-meteo.com/v1/forecast')
            self.max_workers = int(os.getenv('MAX_WORKERS', '4'))  # Menos workers para streaming
            self.request_timeout = int(os.getenv('REQUEST_TIMEOUT', '30'))
            self.max_retries = int(os.getenv('MAX_RETRIES', '3'))
            self.streaming_batch_size = int(os.getenv('STREAMING_BATCH_SIZE', '10'))  # Tamaño de lote para streaming
        else: 
            raise EnvironmentError("Variables de entorno no configuradas correctamente")

        # Estadísticas de ejecución
        self.stats = {
            'total_sites': 0,
            'successful': 0,
            'failed': 0,
            'records_processed': 0,
            'errors': []
        }
        
        logger.info(f"Iniciando ETL Streaming - Run ID: {self.ingestion_run_id}")
        logger.info(f"Modo dry-run: {'SÍ' if self.dry_run else 'NO'}")
        logger.info(f"Tamaño de lote streaming: {self.streaming_batch_size}")

    def _validate_env_variables(self) -> bool:
        """
        Valida las variables de entorno.
        """
        return all(os.getenv(var) for var in ['DB_HOST', 'DB_PORT', 'DB_USER', 'DB_PASSWORD', 'DB_NAME'])

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
    
    def log_retry_attempt(retry_state: RetryCallState):
        """
        Loggea cada reintento de la API.
        """
        attempt_number = retry_state.attempt_number
        exception = retry_state.outcome.exception()
        next_wait = retry_state.next_action.sleep if retry_state.next_action else None
        site_name = retry_state.args[1].get('name') if len(retry_state.args) > 1 and isinstance(retry_state.args[1], dict) else "Unknown"

        logger.warning(
            f"WARNING: Reintento {attempt_number} para {site_name} "
            f"debido a: {type(exception).__name__} - {exception}. "
            f"Siguiente intento en {next_wait:.1f} segundos." if next_wait else ""
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((requests.exceptions.RequestException,)),
        before_sleep=log_retry_attempt
    )
    def fetch_weather_data(self, site: Dict) -> Optional[Dict]:
        """
        Obtiene datos meteorológicos de forecast API para un sitio específico.
        
        Args:
            site: Diccionario con información del sitio (lat, lon, site_id)
            
        Returns:
            Diccionario con datos raw de la API o None si falla
        """
        # Construir parámetros para forecast API
        params = {
            'latitude': site['latitude'],
            'longitude': site['longitude'],
            'current': 'temperature_2m,relative_humidity_2m,wind_speed_10m',
            'hourly': 'temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m',
            'timezone': site['timezone'],
        }
        
        # Realizar llamada a la API
        response = requests.get(
            self.api_base,
            params=params,
            timeout=self.request_timeout
        )
        
        if response.status_code in (429, 404, 405, 408, 409, 500, 502, 503, 504):
            logger.warning(f"WARNING: Respuesta {response.status_code} de la API para {site['site_id']}. Reintentando...")
            raise requests.exceptions.RequestException(f"Respuesta {response.status_code}")
        elif response.status_code == 200: 
            data = response.json()
            logger.info(f"Datos obtenidos para sitio {site['site_id']} ({site['name']})")
            return data
        else:
            logger.error(f"Estado inesperado para {site['site_id']}: status code: {response.status_code}")
            raise requests.exceptions.RequestException(f"Respuesta {response.status_code}")
    
    def normalize_weather_data_streaming(self, raw_data: Dict, site: Dict) -> Iterator[Dict]:
        """
        Normaliza los datos meteorológicos en modo streaming (generador).
        Procesa tanto datos 'current' como 'hourly' y los yield uno por uno.
        
        Args:
            raw_data: Diccionario con datos raw de la API
            site: Diccionario con información del sitio
            
        Yields:
            Diccionarios con datos normalizados uno por uno
        """
        site_id = site['site_id']
        now_utc = datetime.now(timezone.utc)
        
        try:
            # Procesar datos CURRENT (tiempo actual)
            if 'current' in raw_data:
                current = raw_data['current']
                current_time_str = current.get('time')
                if current_time_str:
                    observation_time = datetime.fromisoformat(current_time_str.replace('Z', '+00:00'))
                    
                    normalized_record = {
                        "site_id": site_id,
                        "observation_time": observation_time,
                        "fetch_time": now_utc,
                        "temp_c": current.get('temperature_2m'),
                        "humidity_pct": current.get('relative_humidity_2m'),
                        "precipitation_mm": str(current.get('precipitation', 0)),
                        "wind_speed_10m": current.get('wind_speed_10m'),  # Nuevo campo
                        "ingestion_run_id": self.ingestion_run_id,
                        "data_type": "current"  # Marca si es current o hourly
                    }
                    yield normalized_record
            
            # Procesar datos HOURLY (pronóstico)
            if "hourly" in raw_data:
                hourly = raw_data["hourly"]
                times = hourly.get("time", [])
                temps = hourly.get("temperature_2m", [])
                hums = hourly.get("relative_humidity_2m", [])
                precs = hourly.get("precipitation", [])
                winds = hourly.get("wind_speed_10m", [])
                
                if times:
                    for i in range(len(times)):
                        observation_time = datetime.fromisoformat(times[i].replace('Z', '+00:00'))
                        
                        # Verificación defensiva
                        temp_c = temps[i] if i < len(temps) else None
                        humidity_pct = hums[i] if i < len(hums) else None
                        precipitation_mm = precs[i] if i < len(precs) else None
                        wind_speed = winds[i] if i < len(winds) else None
                        
                        normalized_record = {
                            "site_id": site_id,
                            "observation_time": observation_time,
                            "fetch_time": now_utc,
                            "temp_c": temp_c,
                            "humidity_pct": humidity_pct,
                            "precipitation_mm": str(precipitation_mm) if precipitation_mm is not None else "0",
                            "wind_speed_10m": wind_speed,
                            "ingestion_run_id": self.ingestion_run_id,
                            "data_type": "hourly"
                        }
                        yield normalized_record
            
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
    
    def save_weather_record_streaming(self, weather_data: Dict) -> bool:
        """
        Guarda un registro meteorológico individual (modo streaming).
        
        Args:
            weather_data: Diccionario con datos normalizados
            
        Returns:
            True si se guardó exitosamente, False en caso contrario
        """
        if self.dry_run:
            logger.debug(f"[DRY-RUN] Guardando registro para {weather_data['site_id']} - {weather_data['observation_time']}")
            return True
        
        try:
            with self.get_db_connection() as conn:
                with conn.cursor() as cursor:
                    insert_query = get_insert_weather_observation_query()
                    
                    # Convertir diccionario a tupla en el orden correcto
                    # Nota: wind_speed_10m no está en la tabla actual, se omite por ahora
                    params = (
                        weather_data['site_id'],
                        weather_data['observation_time'],
                        weather_data['temp_c'],
                        weather_data['humidity_pct'],
                        weather_data['precipitation_mm'],
                        weather_data['ingestion_run_id'],
                        weather_data['fetch_time']
                    )
                    
                    cursor.execute(insert_query, params)
                    conn.commit()
                    return True
            
        except Exception as e:
            logger.warning(f"Error guardando registro individual: {e}")
            return False
    
    def save_weather_batch_streaming(self, weather_data_batch: List[Dict]) -> Tuple[int, int]:
        """
        Guarda un lote pequeño de registros (optimización para streaming).
        
        Args:
            weather_data_batch: Lista de diccionarios con datos normalizados
            
        Returns:
            Tupla (registros_exitosos, total_registros)
        """
        if self.dry_run:
            return len(weather_data_batch), len(weather_data_batch)
        
        if not weather_data_batch:
            return 0, 0
        
        successful = 0
        try:
            with self.get_db_connection() as conn:
                with conn.cursor() as cursor:
                    insert_query = get_insert_weather_observation_query()
                    
                    params_list = []
                    for weather_data in weather_data_batch:
                        params = (
                            weather_data['site_id'],
                            weather_data['observation_time'],
                            weather_data['temp_c'],
                            weather_data['humidity_pct'],
                            weather_data['precipitation_mm'],
                            weather_data['ingestion_run_id'],
                            weather_data['fetch_time']
                        )
                        params_list.append(params)
                    
                    cursor.executemany(insert_query, params_list)
                    conn.commit()
                    successful = len(params_list)
            
            return successful, len(weather_data_batch)
            
        except Exception as e:
            logger.error(f"Error guardando batch streaming: {e}")
            # Fallback: guardar uno por uno
            return self._save_weather_data_fallback(weather_data_batch)
    
    def _save_weather_data_fallback(self, weather_data_list: List[Dict]) -> Tuple[int, int]:
        """Fallback: guarda registros uno por uno si el batch falla."""
        successful = 0
        for weather_data in weather_data_list:
            if self.save_weather_record_streaming(weather_data):
                successful += 1
        return successful, len(weather_data_list)
    
    def process_site_streaming(self, site: Dict) -> Tuple[bool, str, int]:
        """
        Procesa un sitio individual en modo streaming: obtiene datos y los guarda
        inmediatamente a medida que se normalizan.
        
        Args:
            site: Diccionario con información del sitio
            
        Returns:
            Tupla (éxito, mensaje, registros_procesados)
        """
        try:
            # Obtener datos meteorológicos
            raw_data = self.fetch_weather_data(site)
            
            if raw_data is None:
                return False, f"No se pudieron obtener datos para {site['name']}", 0
            
            # Procesar en modo streaming: normalizar y guardar en lotes pequeños
            batch = []
            records_processed = 0
            
            for normalized_record in self.normalize_weather_data_streaming(raw_data, site):
                batch.append(normalized_record)
                records_processed += 1
                
                # Cuando el lote alcanza el tamaño, guardar
                if len(batch) >= self.streaming_batch_size:
                    successful, total = self.save_weather_batch_streaming(batch)
                    batch = []  # Limpiar lote
                    
                    if successful < total:
                        logger.warning(f"Guardados parcialmente {successful}/{total} registros del lote")
            
            # Guardar el lote restante
            if batch:
                successful, total = self.save_weather_batch_streaming(batch)
                if successful < total:
                    logger.warning(f"Guardados parcialmente {successful}/{total} registros del lote final")
            
            if records_processed > 0:
                return True, f"Datos procesados exitosamente para {site['name']} - {records_processed} registros", records_processed
            else:
                return False, f"No se procesaron registros para {site['name']}", 0
                
        except Exception as e:
            error_msg = f"Error procesando {site['name']}: {str(e)}"
            logger.error(error_msg)
            return False, error_msg, 0
    
    def run_etl_streaming(self):
        """Ejecuta el proceso ETL completo en modo streaming."""
        try:
            # Cargar sitios
            sites = self.load_sites()
            self.stats['total_sites'] = len(sites)
            
            if not sites:
                logger.warning("No se encontraron sitios para procesar")
                return
            
            logger.info(f"Procesando {len(sites)} sitios con {self.max_workers} workers (modo streaming)")
            
            # Procesar sitios en paralelo
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # Enviar tareas
                future_to_site = {
                    executor.submit(self.process_site_streaming, site): site 
                    for site in sites
                }
                
                # Procesar resultados con barra de progreso
                with tqdm(total=len(sites), desc="Procesando sitios (streaming)") as pbar:
                    for future in as_completed(future_to_site):
                        site = future_to_site[future]
                        
                        try:
                            success, message, records = future.result()
                            self.stats['records_processed'] += records
                            
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
            logger.error(f"Error crítico en ETL Streaming: {e}")
            sys.exit(1)
    
    def _print_summary(self):
        """Imprime el resumen final de la ejecución."""
        logger.info("=" * 60)
        logger.info("RESUMEN DE EJECUCIÓN ETL STREAMING")
        logger.info("=" * 60)
        logger.info(f"Run ID: {self.ingestion_run_id}")
        logger.info(f"Total sitios: {self.stats['total_sites']}")
        logger.info(f"Exitosos: {self.stats['successful']}")
        logger.info(f"Fallidos: {self.stats['failed']}")
        logger.info(f"Total registros procesados: {self.stats['records_processed']}")
        logger.info(f"Modo dry-run: {'SÍ' if self.dry_run else 'NO'}")
        
        if self.stats['errors']:
            logger.info("\nErrores encontrados:")
            for error in self.stats['errors'][:5]:
                logger.info(f"  - {error}")
            if len(self.stats['errors']) > 5:
                logger.info(f"  ... y {len(self.stats['errors']) - 5} errores más")
        
        logger.info("=" * 60)


def run_continuous(etl_instance: WeatherETLStreaming, interval_seconds: int):
    """
    Ejecuta el ETL en modo continuo (streaming periódico).
    
    Args:
        etl_instance: Instancia del ETL
        interval_seconds: Intervalo entre ejecuciones en segundos
    """
    logger.info(f"Iniciando modo continuo - ejecutando cada {interval_seconds} segundos")
    logger.info("Presiona Ctrl+C para detener")
    
    try:
        while True:
            logger.info(f"\n{'='*60}")
            logger.info(f"Ejecutando ciclo de streaming - {datetime.now().isoformat()}")
            logger.info(f"{'='*60}\n")
            
            # Crear nueva instancia para cada ejecución (nuevo run_id)
            etl = WeatherETLStreaming(dry_run=etl_instance.dry_run)
            etl.run_etl_streaming()
            
            logger.info(f"\nEsperando {interval_seconds} segundos hasta la próxima ejecución...")
            time.sleep(interval_seconds)
            
    except KeyboardInterrupt:
        logger.info("\n\nDeteniendo modo continuo. Hasta luego!")


def main():
    """Función principal del script."""
    parser = argparse.ArgumentParser(description='ETL Job para datos climáticos en modo streaming')
    parser.add_argument(
        '--dry-run', 
        action='store_true', 
        help='Ejecutar en modo de prueba sin escribir a la base de datos'
    )
    parser.add_argument(
        '--interval',
        type=int,
        default=None,
        help='Ejecutar en modo continuo cada N segundos (ej: --interval 3600 para cada hora)'
    )
    
    args = parser.parse_args()
    
    # Crear instancia del ETL
    etl = WeatherETLStreaming(dry_run=args.dry_run)
    
    # Ejecutar una vez o en modo continuo
    if args.interval and args.interval > 0:
        run_continuous(etl, args.interval)
    else:
        etl.run_etl_streaming()


if __name__ == '__main__':
    main()

