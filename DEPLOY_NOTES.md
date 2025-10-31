# Notas de Despliegue - Weather Data Product

## 🚀 Comandos para Levantar y Probar el Sistema

### 1. Preparar el Entorno

```bash
# Navegar al directorio del proyecto
cd "/Users/lgarciaduart/Documents/Prueba tecnica Meli/weather-data-product"

# Verificar que Docker esté funcionando
docker --version
docker compose --version  # v2 (nuevo)
docker-compose --version   # v1 (antiguo)
```

### 2. Levantar MySQL con Docker

```bash
# Verificar versión de Docker Compose
docker compose version  # v2 (nuevo)
# o
docker-compose --version  # v1 (antiguo)

# Levantar el servicio MySQL
# Para Docker Compose v2:
docker compose up -d
# Para Docker Compose v1:
docker-compose up -d

# Verificar que el contenedor esté corriendo
docker compose ps  # v2
docker-compose ps  # v1

# Ver logs para confirmar inicialización
docker compose logs mysql  # v2
docker-compose logs mysql  # v1
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

### Problema: "docker-compose up se queda pegado"

**Causas comunes y soluciones:**

1. **Ejecutar en segundo plano con `-d`:**
```bash
# En lugar de: docker compose up
# Usar: docker compose up -d
docker compose up -d

# Esto inicia los contenedores en segundo plano
# Puedes seguir usando la terminal mientras los servicios corren
```

2. **Verificar si MySQL está iniciando:**
```bash
# Ver logs en tiempo real
docker compose logs -f mysql

# Presiona Ctrl+C para salir de los logs
# Si ves mensajes de "ready for connections", MySQL está funcionando
```

3. **Limpiar y reiniciar si es necesario:**
```bash
# Detener y eliminar contenedores
docker compose down

# Eliminar volúmenes (¡CUIDADO! Esto borra los datos)
# docker compose down -v

# Levantar de nuevo
docker compose up -d

# Esperar unos segundos y verificar estado
sleep 10
docker compose ps
```

4. **Verificar que el puerto 3306 no esté ocupado:**
```bash
# En Mac/Linux:
lsof -i :3306

# Si está ocupado, detén el otro servicio o cambia el puerto en docker-compose.yml
```

5. **Revisar estado del contenedor:**
```bash
# Ver estado actual
docker compose ps

# Ver logs de error
docker compose logs mysql | tail -50

# Verificar salud del contenedor
docker inspect weather-mysql | grep -A 10 Health
```

### Error: "No se pudo conectar a MySQL"
```bash
# Verificar que MySQL esté corriendo
docker compose ps  # v2
docker-compose ps  # v1

# Reiniciar MySQL
docker compose restart mysql  # v2
docker-compose restart mysql  # v1

# Ver logs de error
docker compose logs mysql  # v2
docker-compose logs mysql  # v1
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
2. Verificar logs de MySQL: `docker compose logs mysql` (v2) o `docker-compose logs mysql` (v1)
3. Consultar README.md para más detalles
4. Revisar docs/architecture.md para contexto técnico
