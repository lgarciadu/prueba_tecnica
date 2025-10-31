# Weather Data Product

Un Data Product completo para la extracción, transformación y carga (ETL) de datos climáticos desde APIs externas hacia una base de datos MySQL.

## 📋 Requisitos

- **Docker** (versión 20.10+)
- **Python** (versión 3.10+)
- **pip** (gestor de paquetes de Python)

## 🚀 Instalación y Configuración

### 1. Levantar MySQL con Docker

```bash
# Levantar el servicio MySQL
docker compose up -d

# Verificar que el contenedor esté funcionando
docker compose ps

# Ver logs del contenedor (opcional)
docker compose logs mysql
```

### 2. Instalar Dependencias de Python

```bash
# Navegar al directorio ETL
cd etl

# Crear entorno virtual
python -m venv .venv

# Activar entorno virtual
# En Linux/Mac:
source .venv/bin/activate
# En Windows:
# .venv\Scripts\activate

# Instalar dependencias
pip install -r requirements.txt
```

### 3. Configurar Variables de Entorno

```bash
# Copiar archivo de ejemplo
cp env.example .env

# Editar archivo .env con tus valores reales
# Especialmente importante: configurar API_KEY
nano .env  # o tu editor preferido
```

**Variables importantes a configurar:**
- `DB_HOST`: Host de MySQL (por defecto: 127.0.0.1)
- `DB_PORT`: Puerto de MySQL (por defecto: 3306)
- `DB_USER`: Usuario de MySQL
- `DB_PASSWORD`: Contraseña de MySQL
- `DB_NAME`: Nombre de la base de datos
- `API_BASE`: URL base para API archive (ETL batch)
- `API_BASE_FORECAST`: URL base para API forecast (ETL streaming, opcional, default: https://api.open-meteo.com/v1/forecast)
- `MAX_WORKERS`: Número de workers paralelos (por defecto: 4 para streaming, 8 para batch)
- `STREAMING_BATCH_SIZE`: Tamaño de lote para streaming (por defecto: 10)

## 🏃‍♂️ Uso

### Ejecutar el Job ETL (Batch/Histórico)

```bash
# Ejecución normal (escribe a la base de datos)
python etl_weather.py

# Ejecución de prueba (no escribe a la base de datos)
python etl_weather.py --dry-run
```

### Ejecutar el Job ETL (Streaming/Forecast)

El ETL en modo streaming procesa datos de forecast en tiempo real y los guarda inmediatamente:

```bash
# Ejecución única (escribe a la base de datos)
python etl_weather_streaming.py

# Ejecución de prueba (no escribe a la base de datos)
python etl_weather_streaming.py --dry-run

# Ejecución continua cada hora (3600 segundos)
python etl_weather_streaming.py --interval 3600

# Ejecución continua cada 15 minutos
python etl_weather_streaming.py --interval 900
```

**Diferencias entre Batch y Streaming:**
- **Batch (`etl_weather.py`)**: Procesa datos históricos (archive API), guarda en lotes grandes
- **Streaming (`etl_weather_streaming.py`)**: Procesa forecast en tiempo real, guarda inmediatamente en lotes pequeños

### Verificar Duplicados

```bash
# Verificar que no hay duplicados en la base de datos
python check_duplicates_mysql.py
```

**Códigos de salida:**
- `0`: No se encontraron duplicados
- `2`: Se encontraron duplicados

## 📊 Estructura del Proyecto

```
weather-data-product/
├── README.md                    # Este archivo
├── docker-compose.yml          # Configuración de Docker
├── mysql/
│   └── init.sql               # Script de inicialización de BD
├── config/
│   └── sites_sample.json      # Sitios meteorológicos de ejemplo
├── etl/
│   ├── etl_weather.py         # Job ETL principal (batch/histórico)
│   ├── etl_weather_streaming.py  # Job ETL en modo streaming
│   ├── check_duplicates_mysql.py  # Verificador de duplicados
│   ├── requirements.txt       # Dependencias Python
│   └── env.example           # Variables de entorno de ejemplo
└── docs/
    └── architecture.md        # Documentación técnica
```

## 🔄 Automatización

### Ejecución Periódica con Cron

Para automatizar la ejecución del ETL, puedes configurar un cron job:

```bash
# Editar crontab
crontab -e

# Ejecutar cada hora (ejemplo)
0 * * * * cd /ruta/al/proyecto/etl && source .venv/bin/activate && python etl_weather.py

# Ejecutar cada 6 horas
0 */6 * * * cd /ruta/al/proyecto/etl && source .venv/bin/activate && python etl_weather.py
```

### Monitoreo y Alertas

Recomendamos implementar:
- Logs estructurados (JSON) para facilitar el análisis
- Alertas por email/Slack cuando el job falla
- Dashboard para monitorear métricas de calidad de datos

## ☁️ Despliegue en Producción

### Opción 1: Google Cloud Platform

1. **Cloud SQL**: Migrar de MySQL local a Cloud SQL
2. **Cloud Dataflow**: Ejecutar el ETL como job de Dataflow
3. **Cloud Scheduler**: Programar ejecuciones periódicas
4. **BigQuery**: Almacenar datos históricos para análisis

### Opción 2: AWS

1. **RDS MySQL**: Base de datos gestionada
2. **Lambda + EventBridge**: ETL serverless
3. **S3 + Athena**: Almacenamiento y consultas

### Configuración para Producción

1. **Variables de entorno**: Usar secretos gestionados (Secret Manager)
2. **Logging**: Configurar Cloud Logging o CloudWatch
3. **Monitoreo**: Implementar alertas y métricas
4. **Escalabilidad**: Ajustar `MAX_WORKERS` según recursos disponibles

## 🛠️ Desarrollo

### Estructura de la Base de Datos

La tabla `weather_observations` incluye:
- **Clave primaria**: `id` (auto-incremental)
- **Clave única**: `(site_id, source, observation_time)` para idempotencia
- **Campos de auditoría**: `audit_created_*`, `audit_updated_*`
- **Datos raw**: `raw_payload` (JSON) para trazabilidad

### Características del ETL

- **Idempotencia**: Re-ejecutar el job no crea duplicados
- **Paralelización**: Procesa múltiples sitios simultáneamente
- **Reintentos**: Manejo automático de errores de red
- **Logging**: Información detallada de ejecución
- **Dry-run**: Modo de prueba sin escribir a BD

## 🐛 Solución de Problemas

### Error de Conexión a MySQL

```bash
# Verificar que MySQL esté corriendo
docker compose ps

# Ver logs de MySQL
docker compose logs mysql

# Reiniciar MySQL
docker compose restart mysql
```

### Error de API Key

```bash
# Verificar que .env esté configurado
cat .env | grep API_KEY

# Obtener API key gratuita en: https://openweathermap.org/api
```

### Verificar Duplicados

```bash
# Ejecutar verificador
python check_duplicates_mysql.py

# Si hay duplicados, revisar logs del ETL
```

## 📈 Próximos Pasos

1. **Validación de datos**: Implementar reglas de calidad
2. **Alertas**: Configurar notificaciones automáticas
3. **Dashboard**: Crear visualizaciones de datos
4. **API**: Exponer datos via REST API
5. **Machine Learning**: Modelos predictivos de clima

## 📞 Soporte

Para problemas o preguntas:
1. Revisar logs del ETL
2. Verificar configuración de variables de entorno
3. Consultar documentación en `docs/architecture.md`
