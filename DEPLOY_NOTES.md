# Notas de Despliegue - Weather Data Product

## 🚀 Comandos para Levantar y Probar el Sistema

### 1. Preparar el Entorno

```bash
# Navegar al directorio del proyecto
cd "/Users/lgarciaduart/Documents/Prueba tecnica Meli/weather-data-product"

# Verificar que Docker esté funcionando
docker --version
docker compose --version
```

### 2. Levantar MySQL con Docker

```bash
# Levantar el servicio MySQL
docker compose up -d

# Verificar que el contenedor esté corriendo
docker compose ps

# Ver logs para confirmar inicialización
docker compose logs mysql
```

### 3. Configurar Python y Dependencias

```bash
# Navegar al directorio ETL
cd etl

# Crear entorno virtual
python3 -m venv .venv

# Activar entorno virtual
source .venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt
```

### 4. Configurar Variables de Entorno

```bash
# Copiar archivo de ejemplo
cp env.example .env

# Editar archivo .env si desea cambiar las credenciales de la DB o demas configuraciones
nano .env
```

**Contenido mínimo del archivo .env:**
```bash
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=root
DB_PASSWORD=rootpass
DB_NAME=testdb
API_BASE=https://api.openweathermap.org/data/2.5/weather
MAX_WORKERS=8
REQUEST_TIMEOUT=30
MAX_RETRIES=3
LOG_LEVEL=INFO
```

### 5. Ejecutar el ETL

```bash
# Verificar que el entorno virtual esté activo
source .venv/bin/activate

# Ejecutar en modo dry-run (recomendado para primera prueba)
python etl_weather.py --dry-run

# Ejecutar ETL real
python etl_weather.py
```

### 6. Verificar Resultados

```bash
# Verificar que no hay duplicados
python check_duplicates_mysql.py

# Conectar a MySQL para ver datos (opcional)
docker exec -it weather-mysql mysql -u root -prootpass testdb

# Conectarse a la DB usando Datagrip, DBeaver, etc.. y verificar (opcional)
**Comandos SQL útiles:**
```sql
-- Ver estructura de la tabla
DESCRIBE weather_observations;

-- Ver conteo de registros
SELECT COUNT(*) FROM weather_observations;

-- Ver últimos registros
SELECT site_id, observation_time, temp_c, humidity_pct 
FROM weather_observations 
ORDER BY audit_created_dttm DESC 
LIMIT 10;

-- Verificar duplicados manualmente
SELECT site_id, source, observation_time, COUNT(*) as cnt
FROM weather_observations
GROUP BY site_id, source, observation_time
HAVING cnt > 1;
```

## 🔧 Solución de Problemas Comunes

### Error: "No se pudo conectar a MySQL"
```bash
# Verificar que MySQL esté corriendo
docker compose ps

# Reiniciar MySQL
docker compose restart mysql

# Ver logs de error
docker compose logs mysql
```

### Error: "No se encontraron sitios"
```bash
# Verificar archivo de configuración
cat ../config/sites_sample.json

# Verificar permisos
ls -la ../config/sites_sample.json
```

## 📊 Validación del Sistema

### Checklist de Funcionamiento

- [ ] MySQL se levanta correctamente con Docker
- [ ] El entorno virtual de Python se crea y activa
- [ ] Las dependencias se instalan sin errores
- [ ] El archivo .env se configura correctamente
- [ ] El ETL ejecuta en modo dry-run sin errores
- [ ] El ETL ejecuta en modo real y escribe datos
- [ ] El verificador de duplicados retorna código 0
- [ ] Los datos se pueden consultar en MySQL

### Comandos de Validación Rápida

```bash
# Verificar estructura del proyecto
find . -type f -name "*.py" -o -name "*.sql" -o -name "*.json" -o -name "*.yml" | sort

# Verificar que todos los archivos existen
ls -la docker-compose.yml mysql/init.sql config/sites_sample.json etl/*.py

# Verificar permisos de ejecución
chmod +x etl/*.py
```

## 🎯 Próximos Pasos

1. **Configurar API Key real** de OpenWeatherMap
2. **Ejecutar ETL completo** y verificar datos
3. **Configurar cron job** para automatización
4. **Implementar monitoreo** básico
5. **Planificar migración** a cloud para producción

## 📞 Soporte

Si encuentras problemas:
1. Revisar logs del ETL: `python etl_weather.py --dry-run`
2. Verificar logs de MySQL: `docker compose logs mysql`
3. Consultar README.md para más detalles
4. Revisar docs/architecture.md para contexto técnico
