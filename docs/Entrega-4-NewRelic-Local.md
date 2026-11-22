# Entrega 4 - New Relic local

Responsable: Oscar Jobany Gomez Ochoa. Rama de trabajo: `feature/NewRelicLocal`.

## 1. Alcance y estado

Se conserva Flask 1.1.4, Python 3.11, Gunicorn, puerto 5000, usuario no root y
los contratos del API. La version actual de `/version` es `2.2.0`; esta entrega
no cambia ese valor. La cuenta New Relic creada con GitHub no instrumenta el
repositorio automaticamente: el agente necesita una licencia de ingesta en runtime.

El cambio agrega el agente oficial `newrelic==14.3.0`, su configuracion sin
credenciales y un arranque optativo. CI no necesita New Relic ni RDS. Las pruebas
usan SQLite y mocks; no hacen llamadas al collector con una licencia real.

Validacion de Oscar (21 de noviembre de 2026): imagen construida y `pip check`
correcto; 79 pruebas aprobadas (3 advertencias previas del stack Marshmallow),
excluyendo expresamente `tests/test_postgres.py`. Se probaron arranque sin
monitoreo y con SDK real usando su collector de desarrollo local. Postman CLI
aprobo las siete aserciones tanto con ese collector como con el agente real
configurado para la cuenta de Oscar.

El agente 14.3.0 registro `cb-e4-i1-local` el 21 de noviembre a las 21:25:07
Colombia (22 de noviembre 02:25:07 UTC), segun su mensaje `Reporting to`.
El servicio se dejo disponible en `http://localhost:5005`, con el laboratorio
desactivado. [Entidad registrada de Oscar](https://one.newrelic.com/redirect/entity/ODc0Mjc2MHxBUE18QVBQTElDQVRJT058MTQwODY4MzI1Mg).
El enlace requiere acceso a su cuenta; no es documentacion publica.

Se generaron 120 solicitudes adicionales a health/version, todas HTTP 200,
entre las 21:25:43 y las 21:31:49 de Colombia del 21 de noviembre
(22 de noviembre, 02:25:43-02:31:49 UTC). Es trafico de desarrollo, no estres
cloud ni una medicion de latencia de APM. Las pausas y el cliente pueden extender
la duracion total. Reporte unitario local: `reports/pytest-entrega4-oscar.xml`,
79 pruebas, 0 fallos, 0 errores y 0 omitidas, con PostgreSQL excluido del comando.

Pendiente: comprobar visualmente las metricas y capturar la entidad en APM.
El registro del agente y el HTTP 200 no sustituyen esa evidencia. Los cambios
de esta rama aun no tienen un commit/PR definitivo; registrar ese SHA al publicar.

La parte cloud corresponde a Jose Miguel; carga a Fabio; Apdex/alertas a Juan
David. Esta guia fija el contrato que esos aportes deben conservar.

## 2. Archivos y arranque

| Archivo | Funcion |
| --- | --- |
| `requirements.txt` | Version fijada del agente |
| `scripts/start.py` | Inicia Gunicorn directamente o mediante `newrelic-admin run-program` |
| `newrelic.ini` | Politica inicial de captura, sin identidad ni licencia |
| `Dockerfile` y `.dockerignore` | Incluyen solo esos archivos de runtime, no entornos privados |
| `app/observability.py` | Nombres de transaccion parametrizados y error de laboratorio optativo |
| `.env.newrelic.example` | Ejemplo local con SQLite y licencia vacia |
| `tests/test_start.py` y `tests/test_observability.py` | Arranque, privacidad y escenarios con SDK simulado |
| `tests/test_agent_runtime.py` | SDK real con collector de desarrollo, licencia ficticia y envio real desactivado, sin cuenta externa |

Comportamiento del CMD de Docker (`python scripts/start.py`):

- Sin `NEW_RELIC_ENABLED` o con `false`: ejecuta el mismo Gunicorn de la entrega 3.
- Con `true`: exige `NEW_RELIC_LICENSE_KEY` y `NEW_RELIC_APP_NAME`, y antepone el
  wrapper del agente al mismo Gunicorn, antes de importar `application.py`.
- No se llama ademas a `newrelic.agent.initialize()` en la app: evitar doble inicio.
- Conserva un worker, `0.0.0.0:5000` y reemplaza el proceso con `exec`, para que
  las senales de parada lleguen al servidor. No se actualiza la imagen a otro Flask.
- `flask init-db` y `flask generate-token` siguen disponibles como comandos
  explicitos del contenedor; no necesitan instrumentar esos procesos breves.

## 3. Preparacion privada de la licencia

En New Relic, entrar a la cuenta que recibira las metricas y buscar API keys o
la instalacion guiada de APM para Python. Obtener una clave de tipo **Ingest -
License** para el agente, no una User API key ni el JWT del microservicio.
No pegarla en chats, capturas ni en un `newrelic.ini` versionado.

Ruta directa: [API keys US](https://one.newrelic.com/api-keys)
Seleccionar **Create a key**, cuenta, tipo **Ingest - License** y un nombre
como `codebusters-e4-oscar-local`. Guardar y copiar la clave al crearla; si ya
hay una clave adecuada disponible, no es obligatorio crear otra.

Desde PowerShell en la raiz del repo:

```powershell
if (-not (Test-Path -LiteralPath .env.newrelic)) {
    Copy-Item -LiteralPath .env.newrelic.example -Destination .env.newrelic
}
notepad .env.newrelic
```

Completar la licencia solamente en ese archivo privado y mantener:

```dotenv
NEW_RELIC_ENABLED=true
NEW_RELIC_APP_NAME=cb-e4-i1-local
NEW_RELIC_LOG=stderr
OBS_LAB_ENABLED=false
```

El ejemplo ya incluye SQLite bajo `/data` y una clave JWT ficticia exclusiva
de desarrollo. No copiar licencias, JWT o claves de AWS para esta prueba.
Para los otros integrantes, cambiar `i1` por su indice. No reutilizar el mismo
nombre para local y cloud: la entidad de Fargate debe terminar en `-cloud`.

Si la cuenta New Relic pertenece a la region EU, habilitar en el archivo privado
la linea `NEW_RELIC_HOST=collector.eu01.nr-data.net`. Para US dejarla comentada.
La region New Relic es independiente de la region AWS.

Comprobar que Git ignora el archivo, sin mostrar su contenido:

```powershell
git check-ignore .env.newrelic
```

No ejecutar `Get-Content .env.newrelic`, `docker inspect` sin filtros, `env` o
comandos de diagnostico que impriman la licencia en una sesion grabada.

## 4. Construir y validar sin RDS

Usar Docker Desktop con contenedores Linux. No iniciar Gunicorn nativamente en
Windows. Se valida el agente dentro de Linux/Python 3.11, no se supone que su
version actual sea compatible con Windows/Python 3.11.

```powershell
$Image = 'codebusters-blacklists:entrega4-local'
$Container = 'cb-e4-oscar-local'
$Volume = 'cb-e4-oscar-sqlite'
$Port = 5005
$BaseUrl = "http://localhost:$Port"

docker build --platform linux/amd64 -t $Image .
if ($LASTEXITCODE -ne 0) { throw 'Fallo la construccion.' }
docker run --rm $Image python -m pip check
docker run --rm $Image python -c "import newrelic; print(newrelic.version)"
docker image inspect $Image --format '{{.Os}}/{{.Architecture}} usuario={{.Config.User}}'
```

Pruebas unitarias, desde un contenedor temporal con el repo en solo lectura:

```powershell
$Repo = (Get-Location).Path
docker run --rm --mount "type=bind,source=$Repo,target=/workspace,readonly" --workdir /workspace --env PYTHONDONTWRITEBYTECODE=1 --env NEW_RELIC_ENABLED=false --env OBS_LAB_ENABLED=false python:3.11-slim-bookworm sh -c 'python -m pip install --quiet -r requirements-dev.txt && python -m pytest -q --ignore=tests/test_postgres.py -p no:cacheprovider'
if ($LASTEXITCODE -ne 0) { throw 'Fallo pytest.' }
```

## 5. Iniciar el API instrumentado

```powershell
docker volume create $Volume
docker run --rm --env-file .env.newrelic --mount "type=volume,source=$Volume,target=/data" $Image flask init-db
if ($LASTEXITCODE -ne 0) { throw 'Fallo la creacion de tablas locales.' }

docker run -d --name $Container -p "127.0.0.1:${Port}:5000" --env-file .env.newrelic --mount "type=volume,source=$Volume,target=/data" $Image
if ($LASTEXITCODE -ne 0) { throw 'Fallo el arranque; revisar nombre o puerto ocupado.' }

Invoke-RestMethod "$BaseUrl/health"
Invoke-RestMethod "$BaseUrl/version"
docker logs --tail 30 $Container
```

Si ya existe un contenedor con ese nombre, revisar primero si es propio; no
eliminar otros contenedores ni sobrescribir datos de otro integrante. Esperar
unos segundos entre el arranque y la primera consulta HTTP si aun no escucha.
Si 5005 esta ocupado, elegir otro puerto del host; el contenedor sigue en 5000.

Para la coleccion Postman, generar el JWT local sin mostrarlo:

```powershell
$Token = (docker run --rm --env-file .env.newrelic $Image flask generate-token | Select-Object -Last 1).Trim()
if ($LASTEXITCODE -ne 0 -or $Token -notmatch '^eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$') {
    throw 'No se pudo generar el JWT local.'
}
Set-Clipboard -Value $Token
```

En el environment local de Postman: `base_url=http://localhost:5005`, `app_uuid`
igual al UUID ficticio del equipo y `token` solo en valor local, nunca compartido.
Ejecutar los siete escenarios en orden. Alternativa CLI sin publicar el resultado:

```powershell
postman collection run postman/Blacklists.postman_collection.json --environment postman/Local.postman_environment.json --env-var "base_url=$BaseUrl" --env-var "token=$Token" --no-report-events --timeout-request 10000
```

## 6. Comprobar los datos en New Relic

La entidad aparecera despues de iniciar el agente y generar trafico; no basta
con crear una entidad o autenticarse con GitHub. Mantener la app encendida y
enviar solicitudes durante un par de minutos, sin hacer estres todavia:

```powershell
1..60 | ForEach-Object {
    Invoke-RestMethod "$BaseUrl/health" | Out-Null
    Invoke-RestMethod "$BaseUrl/version" | Out-Null
    Start-Sleep -Seconds 2
}
```

Estas 60 iteraciones tienen pausas que suman dos minutos, ademas del tiempo del
cliente HTTP. Si Windows demora resolviendo localhost, usar `127.0.0.1` como
host local; no interpretar esa espera como latencia exclusiva del microservicio.

En **APM & services**, buscar `cb-e4-i1-local` en la cuenta correcta y seleccionar
una ventana reciente que incluya el trafico. Verificar transacciones, throughput
y respuesta. Repetir Postman para ver consultas y creaciones en la DB SQLite.
La demostracion PostgreSQL/RDS se hace despues desde el ambiente cloud.

Los nombres se fijan a la plantilla de ruta, por ejemplo
`GET /blacklists/<string:email>`, no al correo de cada solicitud. El prefijo
visible puede depender de la vista New Relic; comprobar la agrupacion real.

No afirmar que hubo exito solamente por ver logs de inicio. Si faltan datos,
revisar: cuenta/region New Relic, tipo y presencia de licencia, nombre de app,
flag `NEW_RELIC_ENABLED`, salida HTTPS hacia el collector y tiempo de cosecha.
No cambiar el tipo de licencia a una API key de usuario para intentar resolverlo.

## 7. Error controlado para Juan David

`POST /observability/error` no existe por defecto (404). Para probarlo, cambiar
`OBS_LAB_ENABLED=true` en el archivo privado y recrear el contenedor propio con
la misma imagen y volumen. Docker lee el env-file al crear, no al reiniciar.

El endpoint exige JWT valido y produce `ControlledMonitoringError` dentro de
una solicitud. La captura se reporta explicitamente con `notice_error` y el
atributo `lab.scenario=controlled_error`; responde 500 JSON sin afectar datos.
Solo permite un error cada dos segundos por proceso; las llamadas intermedias
responden 429 con `Retry-After: 2`. No tiene opciones de SQL, pausa arbitraria,
consumo de memoria, ejecucion de comandos ni modificacion de registros.

```powershell
$ErrorResponse = Invoke-WebRequest "$BaseUrl/observability/error" -Method Post -Headers @{ Authorization = "Bearer $Token" } -SkipHttpErrorCheck
$ErrorResponse.StatusCode
Invoke-RestMethod "$BaseUrl/health"
Invoke-RestMethod "$BaseUrl/version"
```

`-SkipHttpErrorCheck` requiere PowerShell 7. Con Windows PowerShell usar Postman.
Esperar ver 500 para el fallo y 200 para health/version posteriores. Buscar en
New Relic la clase de error y la transaccion de esa ventana. Una respuesta 500
no sustituye la evidencia de recepcion en New Relic. Coordinar cantidad/ventana
con Juan para sus alertas, sin activar fallos de forma permanente.

Este aporte reporta explicitamente la excepcion de laboratorio. No se debe
suponer que todos los errores de DB que ya captura la app se reportan como
excepciones APM: observarlo y ajustar con Juan si hace falta. Los 400/401/409
esperados tampoco demuestran por si solos registro de excepciones.

Al finalizar, volver a `OBS_LAB_ENABLED=false`, recrear el contenedor y comprobar
404 en la ruta de laboratorio y 200 en health/version.

## 8. Privacidad y contrato cloud

`newrelic.ini` no contiene licencia, `app_name` ni `enabled`: esas propiedades
deben llegar del runtime, sin que un valor del ini las reemplace. Configura SQL
ofuscado, captura de parametros desactivada, exclusiones de atributos de headers,
parametros y URI, y reenvio de logs desactivado. Se conserva APM, sin Browser ni
AI monitoring innecesarios para esta API.

Estos ajustes no garantizan anonimizar cualquier dato que se agregue en codigo
futuro ni las politicas que se cambien en New Relic. Trabajar solo con correos
ficticios y revisar las capturas. No exportar cuerpos o licencias como atributos.

Jose debe pasar al runtime de ECS:

| Variable | Contrato |
| --- | --- |
| `NEW_RELIC_ENABLED` | `true` solo cuando esa cuenta ya tenga la configuracion |
| `NEW_RELIC_APP_NAME` | Nombre separado, por ejemplo `cb-e4-i1-cloud` |
| `NEW_RELIC_LICENSE_KEY` | Referencia privada de runtime, no valor en build/image |
| `NEW_RELIC_LOG` | `stderr` |
| `NEW_RELIC_HOST` | Solo si corresponde al collector de la region New Relic |
| `OBS_LAB_ENABLED` | `false` por defecto; `true` solo en la ventana del escenario |

La ausencia de parametros New Relic conserva el arranque anterior. Esta rama no
cambia task definitions, permisos, generador de CD ni proyectos/pipelines AWS.
No poner la licencia en CodeBuild como variable en texto plano ni incluirla en
los artefactos; esa etapa construye, el servicio ejecuta el agente.

## 9. Evidencias y limpieza local

| Evidencia | Contenido |
| --- | --- |
| I1-NR-SETUP | Version del agente, archivos del PR, arranque optativo y claves de variables sin valores privados |
| I1-NR-LOCAL | Entidad `cb-e4-i1-local`, ventana visible y solicitudes reales |
| I1-NR-TEST | Conteo real de pytest y Runner Postman contra localhost |
| I1-NR-ERROR | Flag de laboratorio sin secretos, 500 controlado, clase/traza en APM y salud posterior |

Anotar SHA (cuando exista commit), ID de imagen, fecha/hora y zona, ventana,
resultados reales y limitaciones. No inventar capturas ni copiar cifras de
otras cuentas. Estado de recepcion APM: completar solo despues de comprobarlo.

Para detener y eliminar exclusivamente los recursos locales de esta guia:

```powershell
docker stop $Container
docker rm $Container
# Solo cuando ya no se necesiten los datos ficticios de este volumen:
docker volume rm $Volume
Remove-Variable Token -ErrorAction SilentlyContinue
Set-Clipboard -Value ''
```

No usar `docker system prune`. La licencia privada puede conservarse para la
siguiente ejecucion o retirarse de `.env.newrelic`; no se sube en el PR.

## Fuentes oficiales

- [Agente 14.3.0](https://docs.newrelic.com/docs/release-notes/agent-release-notes/python-release-notes/python-agent-14-03-00/).
- [Configuracion y variables](https://docs.newrelic.com/docs/apm/agents/python-agent/configuration/python-agent-configuration/).
- [Wrapper con Gunicorn](https://docs.newrelic.com/docs/apm/agents/python-agent/hosting-services/python-agent-heroku/), solo como referencia del arranque; no se usa Heroku.
- [notice_error para excepciones capturadas](https://docs.newrelic.com/docs/apm/agents/python-agent/python-agent-api/noticeerror-python-agent-api/).
- [Compatibilidad del agente](https://docs.newrelic.com/docs/apm/agents/python-agent/getting-started/compatibility-requirements-python-agent/).
- [Claves de ingesta y API keys](https://docs.newrelic.com/docs/apis/intro-apis/new-relic-api-keys/).
