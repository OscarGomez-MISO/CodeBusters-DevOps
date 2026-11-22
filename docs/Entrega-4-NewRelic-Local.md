# Entrega 4 - New Relic local

Responsable: Oscar Jobany Gomez Ochoa. Integracion inicial: `feature/NewRelicLocal`
(PR #20). Prueba de actualizacion: `feature/security-dependencies-e4`.

## 1. Alcance y estado

La actualizacion de seguridad usa Flask 3.1.3 y conserva Python 3.11, Gunicorn,
puerto 5000, usuario no root y los contratos del API. La version actual de
`/version` es `2.2.0`; esta entrega no cambia ese valor. Los registros iniciales
siguientes corresponden al stack anterior, con Flask 1.1.4; los resultados de
la actualizacion estan en la seccion 10.
La cuenta New Relic creada con GitHub no instrumenta el
repositorio automaticamente: el agente necesita una licencia de ingesta en runtime.

El cambio agrega el agente oficial `newrelic==14.3.0`, su configuracion sin
credenciales y un arranque optativo. CI no necesita New Relic ni RDS. Las pruebas
usan SQLite y mocks; no hacen llamadas al collector con una licencia real.

Validacion inicial de Oscar (21 de noviembre de 2026): imagen construida y `pip check`
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
El registro del agente y el HTTP 200 no sustituyen esa evidencia. La integracion
inicial se publico en el [PR #20](https://github.com/OscarGomez-MISO/CodeBusters-DevOps/pull/20),
commit `a4aa552556b15419656f766de22aff9091e9d8e1`, integrado en main mediante
`9781274ef5c93b3d2ff99ecf9a86284d5a7553ea`. La actualizacion de seguridad se publica
por separado; consultar su commit y PR, sin atribuirle el SHA del aporte inicial.

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
  las senales de parada lleguen al servidor. La migracion de Flask de la seccion
  10 conserva este contrato de arranque.
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
Usar una clave JWT privada aleatoria de al menos 32 bytes en ambientes reales;
PyJWT actualizado advierte sobre claves cortas. Los ejemplos no son secretos
adecuados para un despliegue publico. Esta prueba no rota claves de AWS ni
modifica el archivo privado `.env.newrelic`.
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

## 10. Actualizacion de seguridad y regresion

Prueba realizada el 21 de noviembre de 2026, Colombia (UTC-5), en la rama
`feature/security-dependencies-e4`, creada desde el main integrado por el PR #20.
Esta seccion registra las pruebas locales previas a la integracion de la rama;
los identificadores definitivos se consultan en su PR. No acredita un despliegue
en AWS: el estado cloud debe comprobarse por separado despues de la integracion.

### Hallazgo y alcance

La captura de Security RX de `cb-e4-i1-local` muestra 19 hallazgos, uno critico
y cuatro altos. Son avisos asociados a dependencias, no prueba de ataques
exitosos ni errores funcionales del API. Los tres avisos visibles fueron:

| Aviso | Contexto revisado antes de actualizar |
| --- | --- |
| CVE-2022-29361, Werkzeug | Aviso disputado por el proveedor, relacionado con servidor/configuracion de desarrollo. El arranque del proyecto usa Gunicorn; no se demostro explotacion. |
| CVE-2024-34069, Werkzeug | Afecta al depurador. Se comprobo `DEBUG=false` en el contenedor local, sin considerar eso una actualizacion de la libreria. |
| CVE-2026-7246, Click | Relacionado con `click.edit()`. No se encontraron llamadas a esa funcion en el codigo de la aplicacion. |

La version afectada sigue siendo deuda de seguridad aunque no se encuentre
alcanzable un escenario concreto. El diagnostico local no describe el estado
de Fargate. No se pago ni activo una demo de Security RX.

### Versiones y compatibilidad

| Paquete | Antes | Candidato validado |
| --- | --- | --- |
| Flask | 1.1.4 | 3.1.3 |
| Werkzeug | 1.0.1 | 3.1.9 |
| Jinja2 | 2.11.3 | 3.1.6 |
| MarkupSafe | 2.0.1 | 3.0.4 |
| itsdangerous | 1.1.0 | 2.2.0 |
| Click | 7.1.2 | 8.5.1 |
| Flask-SQLAlchemy | 2.5.1 | 3.1.1 |
| SQLAlchemy | 1.4.54 | 2.0.58 |
| flask-marshmallow | 0.14.0 | 1.5.0 |
| marshmallow | 3.21.3 | 4.4.0 |
| marshmallow-sqlalchemy | 0.28.2 | 1.6.0 |
| Flask-JWT-Extended | 3.25.1 | 4.7.4 |
| PyJWT | 1.7.1 | 2.15.1 |
| python-dotenv | 1.0.1 | 1.2.4 |

Se mantienen Flask-RESTful 0.3.10, psycopg2-binary 2.9.11, Gunicorn 26.2.0 y
New Relic 14.3.0. Se eligio SQLAlchemy 2.0, evitando sumar la migracion a 2.1.
Se adaptaron `@jwt_required()` y el callback de expiracion a JWT-Extended 4.
Se conserva explicitamente `JWT_IDENTITY_CLAIM=identity`, sin cambiar la clave
de despliegue ni desactivar validaciones; solo se admite HS256. La CLI conserva
el JWT sin expiracion del taller. No cambian columnas, rutas ni `/version`.

### Resultados observados

| Comprobacion | Resultado y evidencia local |
| --- | --- |
| Instalacion | `pip check`: sin requisitos incompatibles. Imagen Linux/amd64, usuario 10001:10001. |
| Auditoria inicial con pip-audit 2.10.1 | 48 entradas, equivalentes a 30 pares distintos paquete/ID de aviso, en seis paquetes. La salida incluia registros repetidos. |
| Auditoria posterior con la misma herramienta | 24 dependencias resueltas, cero hallazgos conocidos y cero paquetes omitidos. Se comprobo que sus versiones coinciden con las instaladas en la imagen. |
| Suite SQLite/mocks y SDK offline | 84 aprobadas, cero fallos/errores/omitidas y sin advertencias. Excluye `tests/test_postgres.py`. |
| Suite completa con PostgreSQL 16 local | 85 aprobadas, cero fallos/errores/omitidas y sin advertencias. PostgreSQL se ejecuto temporalmente en Docker, sin publicar puertos ni usar RDS. |
| Nuevas regresiones | Cinco casos adicionales: token con formato legacy, contrato de token generado y rechazo de algoritmos none/HS384/HS512 sin insertar registros. |
| Compatibilidad entre imagenes | JWT generado por la imagen anterior con JWT-Extended 3.25.1/PyJWT 1.7.1 aceptado por la API actualizada, HTTP 200, con la misma clave ficticia de laboratorio. No se imprimio el token. |
| Postman CLI 1.75.0 | Coleccion original, siete solicitudes y siete aserciones aprobadas, cero fallos. Respuestas 200/201/200/409/200/400/401. Sin publicar resultados en Postman cloud. |
| Estado del candidato | `/health` 200, `/version` 2.2.0, `DEBUG=false` y laboratorio desactivado (ruta 404). |
| New Relic | Registro de `cb-e4-i1-security-local` confirmado por el agente. Pendiente captura APM y comprobacion de vulnerabilidades en esa entidad. |

La primera ejecucion ampliada paso las 79 pruebas originales, pero PyJWT emitio
avisos por claves ficticias de menos de 32 bytes. Se ampliaron solo las fixtures
y el ejemplo publico; no se silencian advertencias ni se modifica la clave real.
La primera prueba PostgreSQL detecto que su fixture esperaba dos proxies y
heredaba `PROXY_HOPS=1` de la imagen. Se fijo `PROXY_HOPS=2` en esa prueba, que
simula dos proxies; el runtime de produccion permanece sin cambios.

Los conteos de pip-audit no se equiparan a los 19 de New Relic: usan fuentes,
identificadores y alcances distintos. Cero avisos conocidos no demuestra ausencia
de vulnerabilidades; no se auditaron paquetes del SO ni recursos de AWS.
La recepcion de inventario y transacciones en New Relic requiere su comprobacion
visual independiente; no registrar los 19 como corregidos solo por pip-audit.

### Reproducir y tomar evidencias

Construir una imagen separada, sin sobrescribir la evidencia inicial:

```powershell
docker build --platform linux/amd64 -t codebusters-blacklists:entrega4-security .
docker run --rm codebusters-blacklists:entrega4-security python -m pip check
```

La imagen comprobada tiene ID
`sha256:381575eebbb0ba0f2be94b1d76085c9cefd492f3b70056a5cba387cb63a30723`.
El ID es local, no un digest ECR ni una referencia desplegada en AWS.

Para repetir la auditoria sin instalar herramientas en la imagen del servicio:

```powershell
$Repo = (Get-Location).Path
docker run --rm --mount "type=bind,source=$Repo,target=/workspace,readonly" python:3.11-slim-bookworm sh -c 'python -m pip install --quiet pip-audit==2.10.1 && python -m pip_audit -r /workspace/requirements.txt --progress-spinner off'
```

Las pruebas unitarias se repiten con el comando de la seccion 4, usando las
dependencias actualizadas de esta rama. Para PostgreSQL, configurar
`POSTGRES_TEST_URL` exclusivamente contra una base local descartable y ejecutar
`python -m pytest -q`; no apuntar esa prueba al RDS de evaluacion.

Artefactos generados en `reports/`, ignorados por Git:

- `requirements-e4-before.txt`: dependencias copiadas de la imagen anterior.
- `pip-audit-e4-before.json` y `pip-audit-e4-after.json`: comparacion con la misma herramienta.
- `pytest-entrega4-security.xml`: 84 casos sin PostgreSQL.
- `pytest-entrega4-security-postgres.xml`: suite completa de 85 casos.
- `postman-entrega4-security.txt`: salida CLI saneada, sin JWT.

El candidato quedo en `http://localhost:5006`, contenedor
`cb-e4-oscar-security-local`, SQLite independiente y entidad
[cb-e4-i1-security-local](https://one.newrelic.com/redirect/entity/ODc0Mjc2MHxBUE18QVBQTElDQVRJT058MTUwMjk2MjY4NQ).
El original de `http://localhost:5005` no se reemplazo. La licencia del archivo
privado solo se suministro en runtime; el candidato usa una clave JWT ficticia
propia, distinta de AWS. En Postman, cambiar `base_url` a localhost:5006 y usar
un token generado dentro de este contenedor, solo como valor privado local.

Capturas propuestas para agregar despues de 2.1 en el informe:

- `I1-SEC-ANTES`: captura original de New Relic con entidad y severidades visibles.
- `I1-SEC-AUDIT`: resultado antes/despues de pip-audit, identificando su alcance.
- `I1-SEC-TEST`: 84 pruebas sin DB externa, 85 con PostgreSQL local y Postman 7/7.
- `I1-SEC-DESPUES`: versiones y hallazgos realmente observados en la entidad nueva;
  esta captura sigue pendiente, no sustituirla por la salida de otra herramienta.

Texto base para el informe, sin afirmar una correccion cloud:

> A partir de los avisos de New Relic se probo una actualizacion coordinada de
> las dependencias en una rama separada. La auditoria posterior con pip-audit no
> reporto vulnerabilidades conocidas en las 24 dependencias analizadas; las 85
> pruebas, incluyendo PostgreSQL local, y las siete aserciones Postman aprobaron.
> Se verifico compatibilidad con un token generado por la imagen anterior y se
> confirmo el registro de una entidad New Relic separada. Quedan pendientes la
> captura posterior de Security RX, la revision del equipo y el despliegue cloud.

El PostgreSQL temporal y su red ya se eliminaron. Para retirar solo el candidato
cuando se hayan obtenido las capturas:

```powershell
docker stop cb-e4-oscar-security-local
docker rm cb-e4-oscar-security-local
```

Ese contenedor guarda unicamente datos ficticios y descartables en su capa de
escritura. No usar `docker system prune` ni eliminar el contenedor original.

## Fuentes oficiales

- [Agente 14.3.0](https://docs.newrelic.com/docs/release-notes/agent-release-notes/python-release-notes/python-agent-14-03-00/).
- [Configuracion y variables](https://docs.newrelic.com/docs/apm/agents/python-agent/configuration/python-agent-configuration/).
- [Wrapper con Gunicorn](https://docs.newrelic.com/docs/apm/agents/python-agent/hosting-services/python-agent-heroku/), solo como referencia del arranque; no se usa Heroku.
- [notice_error para excepciones capturadas](https://docs.newrelic.com/docs/apm/agents/python-agent/python-agent-api/noticeerror-python-agent-api/).
- [Compatibilidad del agente](https://docs.newrelic.com/docs/apm/agents/python-agent/getting-started/compatibility-requirements-python-agent/).
- [Claves de ingesta y API keys](https://docs.newrelic.com/docs/apis/intro-apis/new-relic-api-keys/).
- [Migracion de JWT-Extended 3 a 4](https://flask-jwt-extended.readthedocs.io/en/stable/v4_upgrade_guide.html).
- [Cambios de Flask-SQLAlchemy](https://flask-sqlalchemy.palletsprojects.com/en/stable/changes/).
- [Cambios de Flask-Marshmallow](https://flask-marshmallow.readthedocs.io/en/latest/changelog.html).
- [Cambios y endurecimiento de PyJWT](https://pyjwt.readthedocs.io/en/stable/changelog.html).
- [pip-audit y sus limites](https://github.com/pypa/pip-audit).
- [CVE-2022-29361 y posicion del proveedor](https://github.com/pallets/werkzeug/issues/2420).
- [Aviso del depurador de Werkzeug](https://github.com/pallets/werkzeug/security/advisories/GHSA-2g68-c3qc-8985).
- [Click 8.3.3 y correccion del editor](https://github.com/pallets/click/releases/tag/8.3.3).
