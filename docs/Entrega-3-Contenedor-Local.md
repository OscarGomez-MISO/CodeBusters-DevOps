# Entrega 3 - Contenedor local con SQLite

Responsable: Oscar Jobany Gomez Ochoa.

Esta guia permite construir y probar el contenedor del microservicio sin RDS,
PostgreSQL externo ni cuenta AWS. Las pruebas unitarias usan SQLite en memoria;
el API dentro del contenedor usa un archivo SQLite en un volumen Docker local.
El despliegue productivo en Fargate utilizara PostgreSQL/RDS, no este archivo.

## 1. Alcance de este cambio

- `Dockerfile`: Python 3.11 sobre Debian Bookworm, Gunicorn, puerto 5000,
  logs de acceso/error en consola y usuario no root `10001:10001`.
  Se deshabilita el socket de control de Gunicorn con `--no-control-socket`:
  no se necesita para el API y evita crear archivos en un home sin permisos.
- `.dockerignore`: lista permitida de entradas al build; solo Dockerfile,
  requirements, application.py y archivos Python de app. No enviar `.env`,
  `.git`, entornos virtuales, bases locales, pruebas ni artefactos.
- `requirements.txt`: incorpora Gunicorn 26.2.0, disponible en PyPI y compatible
  con Python 3.11. Las dependencias previas y los endpoints se conservan.
- El comando de arranque no crea tablas ni genera tokens. La configuracion
  productiva y el CI/CD de contenedores corresponden a los siguientes PR.

No se modifican `buildspec.yml`, `scripts/ci.py`, el ZIP de la Entrega 2 ni
`compose.yaml`, que sigue siendo el entorno anterior con PostgreSQL.
No hace falta ejecutar `docker compose up` para seguir esta guia.

## 2. Requisitos y preparacion

Ejecutar los comandos PowerShell desde la raiz del repositorio.

- Docker Desktop iniciado, usando contenedores Linux.
- Git y Python 3.11 para ejecutar las pruebas fuera del contenedor.
- Postman de escritorio para la coleccion, o Postman CLI como alternativa.
- Puerto local 5000 libre. Si esta ocupado, cambiar solo `$Port` a 5001 u otro
  puerto disponible y usar ese mismo valor en Postman; el contenedor sigue en 5000.

```powershell
git status
docker version
```

Comprobar la rama y conservar cualquier cambio propio antes de actualizar el
repositorio. Despues de integrar el PR, los companeros pueden usar `main`
actualizada; antes del merge deben usar la rama que contiene este Dockerfile.

## 3. Pruebas unitarias sin base externa

Si ya existe `.venv` con Python 3.11, no es necesario recrearlo.

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m pytest -q --ignore=tests/test_postgres.py --junitxml=reports/pytest.xml
```

Esperar salida exitosa y registrar los conteos realmente observados. El reporte
queda en `reports/pytest.xml`, excluido de Git. La prueba externa PostgreSQL se
excluye explicitamente; no se necesitan las variables de produccion ni editar
el `.env` existente. Las fixtures del API usan su configuracion de pruebas.

Gunicorn se ejecuta dentro de Linux/Docker; no intentar iniciarlo directamente
en Windows. Instalar la dependencia con pip en Windows no significa que el
servidor pueda ejecutarse alli.

## 4. Construir y revisar la imagen

```powershell
$Image = 'codebusters-blacklists:entrega3-local'
$Container = 'cb-e3-oscar-local'
$Volume = 'cb-e3-oscar-sqlite'
$Port = 5000
$BaseUrl = "http://localhost:$Port"

docker build --pull --platform linux/amd64 -t $Image .
if ($LASTEXITCODE -ne 0) { throw 'Fallo la construccion de la imagen.' }

docker image inspect $Image --format '{{.Id}} {{.Os}}/{{.Architecture}} {{.Config.User}}'
docker run --rm $Image python -m pip --no-cache-dir check
docker run --rm $Image gunicorn --version
```

El resultado debe indicar Linux/amd64 y usuario `10001:10001`. Estos comandos
de inspeccion no arrancan el API y no necesitan secretos. La etiqueta de la base
puede recibir actualizaciones: registrar el ID/digest realmente utilizado, no
afirmar que todos los builds independientes tendran el mismo ID.

## 5. Preparar configuracion y tablas locales

Usar un secreto ficticio, exclusivo de esta prueba. No copiar uno de AWS.
Si otro integrante ejecuta la guia en el mismo equipo, debe cambiar los nombres
del contenedor y volumen para no compartir ni eliminar datos ajenos.

```powershell
$LocalSecret = 'only-local-container-demo-not-for-aws'
$RuntimeArgs = @(
    '--env', 'DATABASE_URL=sqlite:////data/blacklists.db',
    '--env', "JWT_SECRET_KEY=$LocalSecret",
    '--env', 'TRUST_PROXY_HEADERS=false',
    '--mount', "type=volume,source=$Volume,target=/data"
)

docker volume create $Volume
docker run --rm @RuntimeArgs $Image flask init-db
if ($LASTEXITCODE -ne 0) { throw 'Fallo la inicializacion de tablas.' }
```

`/data` es escribible por el usuario del contenedor. El volumen nuevo conserva
esa propiedad y mantiene las tablas entre contenedores. No usar SQLite en
memoria para este paso: el siguiente proceso no compartiria esa base.

`init-db` crea tablas faltantes; no es una herramienta de migraciones.
`/health` comprueba conectividad con la base, no la existencia de todas las
tablas: una respuesta 200 no reemplaza la inicializacion y las pruebas del API.

## 6. Iniciar el API y consultar su estado

```powershell
docker run --detach --name $Container --platform linux/amd64 --publish "127.0.0.1:${Port}:5000" @RuntimeArgs $Image
if ($LASTEXITCODE -ne 0) { throw 'Fallo la creacion del contenedor.' }

docker logs $Container
Invoke-RestMethod "$BaseUrl/health"
Invoke-RestMethod "$BaseUrl/version"
```

La publicacion se limita a localhost; no expone esta demostracion en la red.
Si la primera consulta se adelanta al arranque del worker, esperar unos segundos
y repetirla. Gunicorn debe informar el puerto 5000 y su worker en los logs.

Resultados esperados:

| Consulta | Codigo HTTP | Cuerpo |
| --- | --- | --- |
| `GET /health` | 200 | `{"status":"ok"}` |
| `GET /version` | 200 | `{"version":"2.0.0"}` |

No hay reinicio automatico ni inicializacion implicita. La imagen tampoco
define un HEALTHCHECK Docker; el balanceador/tarea configurara su health check
en AWS. Para la comprobacion local se usan las consultas HTTP anteriores.

## 7. Ejecutar la coleccion Postman

Generar un token usando la configuracion del contenedor local:

```powershell
$Token = (docker exec $Container flask generate-token).Trim()
if ($LASTEXITCODE -ne 0 -or -not $Token) { throw 'No se pudo generar el token.' }
```

En Postman de escritorio:

1. Importar `postman/Blacklists.postman_collection.json` y
   `postman/Local.postman_environment.json`.
2. Seleccionar el environment local y establecer `base_url` en la URL de
   `$BaseUrl`. No cambiar el environment que se use para otra cuenta AWS.
3. Para copiar el token local, ejecutar `$Token | Set-Clipboard` y pegarlo en
   el valor local de `token`. Conservar el `app_uuid` de ejemplo.
4. Ejecutar la coleccion completa en orden. El correo se genera de forma unica
   por ejecucion, por lo que se puede repetir sin borrar la base.
5. Capturar los resultados sin mostrar el token y limpiar el portapapeles
   con `Set-Clipboard -Value ''` al terminar.

Alternativa con Postman CLI, sin publicar resultados en su catalogo:

```powershell
postman collection run postman/Blacklists.postman_collection.json -e postman/Local.postman_environment.json --env-var "base_url=$BaseUrl" --env-var "token=$Token" --no-report-events --timeout-request 10000
if ($LASTEXITCODE -ne 0) { throw 'La coleccion Postman fallo.' }
```

El token pasado por CLI es exclusivamente local y ficticio; no usar este
procedimiento para exponer secretos productivos en argumentos o capturas.
Sin login, Postman CLI puede advertir que no publicara resultados en su nube;
el resultado local se comprueba en las aserciones y el codigo de salida.

| Caso de la coleccion | Resultado esperado |
| --- | --- |
| Health check | 200, status ok |
| Agregar correo | 201, created true |
| Consultar bloqueado | 200, is_blacklisted true y motivo Spam |
| Rechazar duplicado | 409, created false |
| Consultar ausente | 200, is_blacklisted false y motivo null |
| UUID invalido | 400 |
| Solicitud sin token | 401 |

La coleccion tiene siete casos y no incluye `/version`; comprobarlo aparte.

## 8. Comprobar persistencia y revisar logs

Guardar el correo creado por la coleccion, detener y volver a iniciar:

```powershell
docker stop $Container
docker start $Container
docker logs --tail 30 $Container
```

Repetir la consulta de ese mismo correo con token: debe seguir bloqueado.
Esto valida el volumen local; no demuestra persistencia distribuida en Fargate.
No montar este archivo SQLite como sustituto de RDS en AWS.

## 9. Problemas frecuentes

| Sintoma | Comprobacion |
| --- | --- |
| No conecta al daemon | Iniciar Docker Desktop y seleccionar contenedores Linux |
| Nombre de contenedor ocupado | Revisar `docker ps -a`; elegir otro nombre o limpiar solo el propio |
| Puerto ocupado | Cambiar `$Port` y `$BaseUrl`; no cambiar el puerto interno 5000 |
| Gunicorn termina al arrancar | Revisar `docker logs`; DATABASE_URL y JWT_SECRET_KEY son obligatorias |
| Error SQLite de permisos | Usar volumen nuevo creado para esta guia; no reutilizar uno con propietario distinto |
| POST falla por tablas inexistentes | Ejecutar init-db con la misma imagen, variables y volumen |
| Coleccion responde 401 | Regenerar token con el secreto actual y comprobar el environment seleccionado |
| `/health` responde 503 | Revisar conectividad/configuracion y logs de la base |

No incluir `.env` en la imagen para resolver errores de configuracion.

## 10. Limpieza local

Primero conservar las evidencias necesarias. Estos comandos eliminan solo los
recursos con los nombres usados en esta guia, no otros contenedores del equipo:

```powershell
docker stop $Container
docker rm $Container
docker volume inspect $Volume
# El siguiente comando borra definitivamente los datos SQLite de esta prueba.
docker volume rm $Volume
# Opcional, cuando ya no se necesite la imagen local:
docker image rm $Image
Remove-Variable Token, LocalSecret, RuntimeArgs -ErrorAction SilentlyContinue
```

No ejecutar `docker system prune` ni borrados generales de volumenes.
Estos recursos son locales y no generan cargos AWS. La limpieza de los servicios
AWS se documentara con los PR de infraestructura/pipeline y la guia consolidada.

## 11. Verificacion local realizada

Fecha: 8 de noviembre de 2026, zona America/Bogota (UTC-5).
Rama: `feature/DockerConfig-ogomezo`; base `91651f2`. La verificacion se realizo
con los cambios locales de este PR, todavia sin commit propio ni merge a main.

| Comprobacion | Resultado observado |
| --- | --- |
| Python del entorno virtual | 3.11.9 |
| Docker Engine / Docker Desktop | 29.8.2 / 4.94.0, motor Linux/amd64 |
| Python / Gunicorn de la imagen | 3.11.18 / 26.2.0 |
| pytest antes y despues del cambio | 50 aprobadas, 0 fallidas; tres avisos de obsolescencia preexistentes |
| Dependencias | pip check exitoso en el entorno local y en la imagen Linux |
| CI anterior ejecutado localmente | `python scripts/ci.py` exitoso, JUnit y ZIP generados |
| Usuario y contenido de imagen | UID 10001; solo entradas de runtime, sin .env ni pyc y sin DATABASE_URL/JWT_SECRET_KEY incorporadas |
| Configuracion ausente | La aplicacion rechaza el arranque sin DATABASE_URL, como antes |
| HTTP sobre la imagen final | /health 200 con status ok; /version 200 con version 2.0.0 |
| Postman CLI 1.75.0 | 7 solicitudes y 7 aserciones aprobadas; salida 0 |
| Persistencia | POST 201 antes del reemplazo; GET posterior conserva correo y motivo al reutilizar el volumen |
| Logs de la imagen final | Gunicorn en 0.0.0.0:5000; sin ERROR, Traceback ni Permission denied en las comprobaciones realizadas |

ID de la imagen final verificada:

```text
sha256:4419f8f889008ae0b6858220eb18aeab94307917582043883294b85e551750f8
```

Durante la revision se detecto inclusion de caches Python y un intento del
socket de control de Gunicorn de escribir en un home sin permisos. Se ajusto
`.dockerignore` y se deshabilito ese socket; la imagen final paso la revision
de contenido y las consultas HTTP sin esos errores. El registro de prueba
persistio despues de eliminar y recrear el contenedor usando el mismo volumen.

Esta comprobacion no es un despliegue AWS, no prueba compatibilidad real con
RDS ni cubre los tres escenarios del pipeline. Se conservan las dependencias
legadas del curso; no se realizo una auditoria de vulnerabilidades.

## Referencias

- Gunicorn y compatibilidad Python: https://pypi.org/project/gunicorn/26.2.0/
- Configuracion Gunicorn: https://gunicorn.org/reference/settings/
- Construccion de imagenes: https://docs.docker.com/build/building/best-practices/
- Volumenes Docker: https://docs.docker.com/engine/storage/volumes/
