# CodeBusters-DevOps

Proyecto del equipo CodeBusters para las cuatro entregas de DevOps: despliegue
manual, integracion continua, entrega continua y monitoreo continuo.
Implementa una API de lista negra global de correos con Python 3.11, Flask 3.1.3,
SQLAlchemy, Flask-RESTful, Marshmallow, Flask-JWT-Extended y PostgreSQL.
La version del API es `2.2.0`. No requiere interfaz grafica.

El ambiente final usa Docker, Gunicorn, ECS/Fargate, ALB y RDS; el pipeline usa
CodePipeline, CodeBuild, ECR y CodeDeploy Blue/Green. New Relic instrumenta la
aplicacion y sus operaciones PostgreSQL. Beanstalk corresponde a la Entrega 1,
no al despliegue final. SQLite y mocks permiten ejecutar las pruebas sin RDS.

- [Acceso para el tutor](#acceso-para-el-tutor)
- [Documentacion por entrega](#documentacion-por-entrega)
- [Desarrollo local](#desarrollo-local-powershell)
- [Variables de entorno](#variables-de-entorno)
- [API](#api), [pruebas](#pruebas) y [Postman](#postman)
- [Acceso a New Relic](#acceso-a-new-relic)
- [Evaluacion y cierre](#evaluacion-y-cierre)

## Acceso para el tutor

El equipo mantiene el ambiente compartido de Oscar para la calificacion.
Su disponibilidad depende de conservar la infraestructura; no es un servicio
de produccion ni una URL permanente.

| Elemento | Referencia |
| --- | --- |
| API compartida | [ALB del ambiente de evaluacion](http://cb-e3-i1-alb-459215994.us-east-1.elb.amazonaws.com) |
| Salud, sin token | [GET /health](http://cb-e3-i1-alb-459215994.us-east-1.elb.amazonaws.com/health) |
| Version, sin token | [GET /version](http://cb-e3-i1-alb-459215994.us-east-1.elb.amazonaws.com/version) |
| Coleccion | [Blacklists.postman_collection.json](postman/Blacklists.postman_collection.json) |
| Environment compartido | [AWS-Entrega-3.postman_environment.json](postman/AWS-Entrega-3.postman_environment.json); se reutiliza en la Entrega 4 |
| New Relic | [Consola](https://one.newrelic.com), entidad `cb-e4-i1-cloud`; requiere acceso autorizado |
| Resultados y ventanas de observacion | [Registro cloud de Oscar](docs/Entrega-4-Ejecucion-Cloud-Oscar.md) |

Verificacion publica realizada el 28/11/2026: `/health` respondio HTTP 200 con
`{"status":"ok"}` y `/version` respondio HTTP 200 con `{"version":"2.2.0"}`.
Esto es una comprobacion puntual, no una garantia de disponibilidad futura.

Para probar el negocio, importar la coleccion y el environment AWS en Postman,
seleccionar ese environment y completar `token` con el JWT entregado por canal
privado. `app_uuid` ya contiene un UUID de prueba. Ejecutar los siete casos en
orden; `/version` se comprueba aparte. No se requiere acceso a la consola AWS
para consumir el API. El laboratorio `POST /observability/error` debe permanecer
desactivado (`OBS_LAB_ENABLED=false`) durante la evaluacion normal.

El ALB usa HTTP: utilizar solo correos ficticios y no enviar datos sensibles.
No publicar el JWT, las claves de firma ni la licencia de New Relic.

## Documentacion por entrega

### Entrega 1 - Despliegue manual

Procedimiento de RDS, variables, ZIP, Beanstalk y estrategias:
[despliegue manual en este README](#despliegue-manual-en-elastic-beanstalk).
La API y [Postman](#postman) documentan los casos funcionales.

Configuracion y empaquetado:
[application.py](application.py),
[01_application.config](.ebextensions/01_application.config),
[02_database.config](.ebextensions/02_database.config),
[.env.example](.env.example) y [package.py](scripts/package.py).
Las evidencias historicas de Beanstalk se conservan en el informe de esa entrega;
el ambiente que se mantiene al cierre es Fargate.

### Entrega 2 - Integracion continua

- [CI en AWS](docs/Entrega-2-CI-AWS.md): CodeBuild, conexion GitHub, webhook de
  `main`, bucket S3, reportes JUnit y pruebas de fallo y recuperacion.
- Configuracion: [buildspec.yml](buildspec.yml), [ci.py](scripts/ci.py),
  [package.py](scripts/package.py) y [requirements-dev.txt](requirements-dev.txt).

El alcance de este flujo es pruebas y ZIP; no despliega el API.

### Entrega 3 - Entrega continua

- [Contenedor local](docs/Entrega-3-Contenedor-Local.md): Docker, SQLite,
  persistencia, JWT y validacion sin una base de datos externa.
- [Fargate manual](docs/Entrega-3-Fargate-Manual.md): red, roles, RDS, SSM, ALB,
  imagen inicial, task definition y servicio de cada integrante.
- [CodeBuild y ECR](docs/Entrega-3-CodeBuild-ECR.md): pruebas, imagen por SHA y
  artefactos de despliegue.
- [Pipeline y CodeDeploy](docs/Entrega-3-Pipeline-CodeDeploy.md): Source-Build-Deploy,
  Blue/Green, alarmas, rollback y casos A, B y C.
- [Limpieza AWS](docs/Entrega-3-Limpieza-AWS.md): inventario y retiro ordenado;
  ejecutar solo despues de la calificacion.

Configuracion: [Dockerfile](Dockerfile), [start.py](scripts/start.py),
[buildspec-cd.yml](buildspec-cd.yml), [prepare_cd.py](scripts/prepare_cd.py),
[taskdef.template.json](deploy/taskdef.template.json) y
[appspec.yaml](deploy/appspec.yaml).

### Entrega 4 - Monitoreo continuo

- [New Relic local](docs/Entrega-4-NewRelic-Local.md): agente, licencia privada,
  pruebas locales y actualizacion de dependencias con auditoria de seguridad.
- [New Relic en AWS](docs/Entrega-4-NewRelic-AWS.md): parametros SSM, permisos,
  variables de CodeBuild y activacion del agente por el pipeline.
- [Apdex, errores y alertas](docs/Entrega-4-Apdex-Errores-Alertas.md): consultas
  NRQL, umbrales, workflow de correo y escenarios E1-E4.
- [Pruebas de carga y estres](docs/Entrega-4-Pruebas-Estres.md): perfiles Locust,
  limites, reportes y criterios de observacion.
- [Ejecucion cloud de Oscar](docs/Entrega-4-Ejecucion-Cloud-Oscar.md): resultados
  reales E1-E4, correlacion con AWS/APM, error controlado, atributos y correos.
- [Ejecucion cloud de Jose Miguel](docs/Entrega-4-Ejecucion-Cloud-Jose.md):
  resultados y evidencias de su cuenta independiente.

Configuracion: [newrelic.ini](newrelic.ini),
[.env.newrelic.example](.env.newrelic.example),
[observability.py](app/observability.py), [monitoring](monitoring/README.md),
[locustfile.py](loadtests/locustfile.py) y [settings.py](loadtests/settings.py).
Las guias distinguen configuraciones propuestas de resultados comprobados; no
deben atribuirse las mediciones de una cuenta a los cuatro integrantes.

## Desarrollo local (PowerShell)

Se usa Python 3.11 con versiones fijadas en [requirements.txt](requirements.txt).
La actualizacion de seguridad de la Entrega 4, integrada en `main`, migra el
stack original de Flask 1.1.4 a Flask 3.1.3;
conserva los endpoints, el esquema de datos y el claim JWT `identity` anterior.
Los resultados y limites de esta migracion estan en la seccion 10 de la guia
de [New Relic local](docs/Entrega-4-NewRelic-Local.md). Los resultados de despliegue
y monitoreo se consultan en los registros cloud enlazados arriba.

Para la Entrega 3, consultar [Contenedor local con SQLite](docs/Entrega-3-Contenedor-Local.md).
Permite probar la imagen Docker sin PostgreSQL, RDS ni una cuenta AWS.
Para la Entrega 4, consultar [New Relic local](docs/Entrega-4-NewRelic-Local.md).
Apdex, errores y alertas: [guia](docs/Entrega-4-Apdex-Errores-Alertas.md) y `monitoring/`.
Pruebas de carga y estres: [guia](docs/Entrega-4-Pruebas-Estres.md) y `loadtests/`.
La instrumentacion es optativa: se activa en runtime, sin cambiar el puerto ni
guardar licencias en la imagen. Las pruebas siguen usando SQLite y mocks.
El procedimiento siguiente conserva el desarrollo local con PostgreSQL y supone
que las dependencias se instalan correctamente. En la verificacion documentada,
Windows presento un fallo al instalar el agente New Relic 14.3.0; para ese caso
usar Linux/WSL o la guia de contenedor, sin retirar dependencias del proyecto.

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
Copy-Item .env.example .env
docker compose up -d --wait
.\.venv\Scripts\python.exe -m flask init-db
.\.venv\Scripts\python.exe -m flask generate-token
.\.venv\Scripts\python.exe application.py
```

API local: http://localhost:5000. PostgreSQL requiere Docker Desktop con
contenedores Linux, o un servidor PostgreSQL existente configurado en `DATABASE_URL`.
El servidor de `application.py` es para desarrollo; Beanstalk usa su servidor WSGI.
`init-db` crea las tablas que faltan y conserva los datos existentes; no es un
sistema de migraciones para futuras modificaciones de tablas.

El token generado es un JWT Bearer reutilizable sin expiracion, como permite la
entrega. Se genera por consola y se usa en Postman; no existe un endpoint de login.
Todas las instancias deben compartir `JWT_SECRET_KEY`. Cambiar esta clave invalida
los tokens anteriores. La clave de `.env.example` es solo para desarrollo.

## Variables de entorno

| Variable | Uso |
| --- | --- |
| `DATABASE_URL` | Obligatoria. URL SQLAlchemy de PostgreSQL en el ambiente compartido; SQLite tambien se usa en las pruebas y el contenedor local. |
| `JWT_SECRET_KEY` | Obligatoria. Clave privada compartida para firmar los JWT. |
| `FLASK_APP` | `application.py` para los comandos Flask. |
| `PORT` | Puerto local, por defecto `5000`. |
| `TRUST_PROXY_HEADERS` | `true` detras de los proxies configurados en AWS; `false` localmente sin proxy. |
| `PROXY_HOPS` | `1` para ALB hacia Fargate; `2` para ALB + nginx en Beanstalk. Ajustar a la topologia real. |
| `NEW_RELIC_ENABLED` | `true` activa el wrapper del agente en el arranque del contenedor; por defecto `false`. |
| `NEW_RELIC_APP_NAME` | Nombre de la entidad APM; en el ambiente compartido, `cb-e4-i1-cloud`. |
| `NEW_RELIC_LICENSE_KEY` | Licencia de ingesta privada, inyectada en runtime; nunca en Git ni en la imagen. |
| `NEW_RELIC_HOST` | Colector opcional para cuentas New Relic de otra region; ver la guia AWS. |
| `OBS_LAB_ENABLED` | Por defecto `false`. Habilita la ruta de error controlado solo durante una prueba acordada. |

No subir `.env` ni tokens al repositorio. Si la contrasena RDS tiene caracteres
especiales, codificarlos en la URL de conexion (percent-encoding).

Las variables anteriores son del runtime. En el proyecto CodeBuild de CD se usan
`ECR_URI`, `TASK_FAMILY`, `EXEC_ROLE_ARN`, `SSM_DB_ARN`, `SSM_JWT_ARN` y `LOG_GROUP`.
La Entrega 4 agrega `NR_APP_NAME` y `SSM_NR_LICENSE_ARN`; `prepare_cd.py` los convierte
en configuracion del agente y referencias a secretos de la task definition.
Cada cuenta configura sus propios valores; las guias de Entregas 3 y 4 contienen
los pasos. No copiar los recursos ni las credenciales de otro integrante.

## API

Los endpoints de blacklist exigen `Authorization: Bearer <token>`.

### POST /blacklists

```json
{
  "email": "person@example.com",
  "app_uuid": "4f47a63e-32d9-441b-bf25-7d14b0ca434e",
  "blocked_reason": "Spam"
}
```

`email` y `app_uuid` son obligatorios; `app_uuid` debe ser un UUID valido.
`blocked_reason` es opcional y admite hasta 255 caracteres. Se normaliza el correo
a minusculas y se eliminan espacios exteriores. La base de datos registra la IP
del cliente y la fecha UTC de creacion; estos campos no los proporciona el cliente.

Respuesta `201`:

```json
{"created": true, "message": "Email added to blacklist", "email": "person@example.com"}
```

Un correo duplicado devuelve `409` y `created: false`. Una solicitud invalida
devuelve `400`; tipo de contenido incorrecto, `415`; token ausente o invalido, `401`.

### GET /blacklists/<email>

Respuesta `200` para un correo registrado:

```json
{"email": "person@example.com", "is_blacklisted": true, "blocked_reason": "Spam"}
```

Para un correo no registrado devuelve `is_blacklisted: false` y
`blocked_reason: null`. Un correo invalido devuelve `400`.
Codificar el correo como componente de URL cuando contenga caracteres especiales.

### GET /health

Sin autenticacion. Comprueba conectividad con la base de datos: `200` con
`{"status":"ok"}` o `503` con `{"status":"unavailable"}`.
La ruta `/` ofrece el mismo chequeo.

### GET /version

Sin autenticacion. Devuelve `{"version":"2.2.0"}` en el codigo actual.
La version inicial no incluia esta ruta; `2.0.0` fue una version historica usada
durante las estrategias de despliegue de la Entrega 1.

### POST /observability/error

Ruta de laboratorio, desactivada por defecto: responde `404` cuando
`OBS_LAB_ENABLED=false`. Al habilitarla exige JWT, registra
`ControlledMonitoringError` con `lab.scenario=controlled_error` y responde `500`.
Limita la frecuencia de errores y puede responder `429`. No usarla como health
check ni habilitarla durante la evaluacion normal; ver la guia de escenarios E3/E4.

## Pruebas

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Las pruebas usan SQLite en memoria y verifican autenticacion, validaciones,
duplicados, consultas, auditoria, health checks, observabilidad y utilidades de
CI/CD. La suite de CI no requiere una base externa ni licencias de New Relic.
El ambiente compartido se valida ademas con PostgreSQL/RDS y Postman.

Para reproducir la suite de CD sin la prueba externa:

```powershell
.\.venv\Scripts\python.exe -m pytest -q --ignore=tests/test_postgres.py --junitxml=reports/pytest.xml
```

Para incluir la prueba de persistencia con el PostgreSQL local:

```powershell
$env:POSTGRES_TEST_URL = "postgresql://blacklists:local-password@localhost:5432/blacklists"
.\.venv\Scripts\python.exe -m pytest -q
```

Esta prueba crea un registro unico, comprueba su persistencia desde otra instancia
de la aplicacion y elimina solo ese registro al finalizar.

## Integracion continua - Entrega 2

El flujo de AWS CodeBuild se define en `buildspec.yml`: instala dependencias con
Python 3.11, ejecuta las pruebas y genera el ZIP si pasan. No realiza despliegues.

Para ejecutar el mismo flujo localmente, sin Docker, RDS ni PostgreSQL:

```powershell
.\.venv\Scripts\python.exe scripts/ci.py
```

Las pruebas usan SQLite en memoria y claves JWT exclusivas de pruebas. Los fallos
de dependencias se simulan con mocks. `tests/test_postgres.py` se excluye de este
flujo, aunque `POSTGRES_TEST_URL` este configurada en el equipo.

Resultados: `reports/pytest.xml` (JUnit) y, solo si pasan las pruebas,
`dist/blacklists.zip`. El flujo elimina el ZIP anterior antes de empezar para
evitar publicar un artefacto viejo cuando falla una nueva ejecucion.

La guia [Entrega 2 - CI en AWS](docs/Entrega-2-CI-AWS.md) contiene la configuracion
del proyecto, el disparador GitHub, S3 y las evidencias para el informe.
La rama de integracion acordada para este proyecto es `main`. Configurar el
webhook de CodeBuild con evento `PUSH` y filtro `HEAD_REF` igual a
`^refs/heads/main$` para construir automaticamente los cambios publicados.

## Entrega continua y monitoreo - Entregas 3 y 4

Este flujo es distinto del CI que genera ZIP: [buildspec-cd.yml](buildspec-cd.yml)
ejecuta las pruebas, construye y publica la imagen en ECR con el SHA completo y
genera `taskdef.json`, `appspec.yaml` e `imageDetail.json`. CodeDeploy actualiza
ECS/Fargate mediante Blue/Green; la configuracion y los casos de fallo/recuperacion
estan en la [guia del pipeline](docs/Entrega-3-Pipeline-CodeDeploy.md).

New Relic se activa al arrancar el contenedor, no compilando la licencia dentro
de la imagen. Las pruebas de build siguen sin RDS ni credenciales reales.
Un cambio en `main`, incluso de documentacion, puede iniciar otro pipeline y
despliegue automatico; comprobar su resultado y mantener `OBS_LAB_ENABLED=false`.
No repetir pruebas de error o estres sobre el ambiente compartido sin coordinacion.

## Postman

Importar `postman/Blacklists.postman_collection.json` y
`postman/Local.postman_environment.json`. Seleccionar el ambiente y asignar
`token` al resultado de `flask generate-token`.
La coleccion incluye creacion, consulta, duplicado, correo ausente, validacion,
rechazo sin token y health check. Ejecutarla en orden; genera un correo unico
para evitar duplicados entre ejecuciones.

Para evaluar las entregas 3 y 4, importar
`postman/AWS-Entrega-3.postman_environment.json` y seleccionar
`Blacklists - AWS Entrega 3 (Oscar)`. El ALB compartido es
http://cb-e3-i1-alb-459215994.us-east-1.elb.amazonaws.com.
La coleccion tambien incluye esta URL como valor predeterminado; seleccionar el
environment local la reemplaza por localhost. No reemplazar las rutas
`{{base_url}}` de cada solicitud por direcciones fijas.
El nombre historico del environment no implica que se pruebe otro despliegue:
es el mismo ambiente compartido que se mantiene para el cierre.

Configurar el JWT del ambiente AWS solo como valor local de `token`, manteniendo
su valor compartido vacio. El tutor debe recibirlo por un canal privado para
probar `/blacklists`; `/health` y `/version` no requieren token. No publicar
`JWT_SECRET_KEY` ni tokens en ejemplos, capturas, exports o documentacion.
La marca de variable sensible no sustituye dejar el valor compartido vacio.
El ALB del laboratorio usa HTTP: trabajar solo con datos de prueba.

Para actualizar la documentacion ya publicada, editar la misma coleccion en
Postman (sin borrarla ni crear otra publicacion): actualizar su descripcion y
sus variables con los valores del JSON del repositorio. Importar el environment
AWS y compartir unicamente `base_url` y `app_uuid`. Desde Overview > View complete
documentation > Docs published > Edit published documentation > Edit Settings,
seleccionar el environment AWS, revisar Preview Documentation y finalizar con
Save and republish. Si es la primera publicacion, usar Publish docs > Postman >
Publish en lugar de Docs published.
Comprobar en una ventana privada que la URL mostrada es la del ALB y no hay
credenciales. Los cambios de la coleccion publicada se sincronizan; cambiar
solo el environment activo del Runner no cambia el environment publicado.
Adjuntar el enlace publico al informe.

Mantener el ambiente AWS hasta la calificacion implica consumo y posibles
cargos. Confirmar la fecha de cierre con el tutor y aplicar despues
`docs/Entrega-3-Limpieza-AWS.md`; no eliminar ALB, servicio, RDS ni parametros
mientras se necesite la verificacion.

## Despliegue manual en Elastic Beanstalk

Referencia historica de la Entrega 1. No recrear Beanstalk para probar el ambiente
final de Fargate; usar los enlaces de acceso para el tutor.

1. Crear PostgreSQL en RDS. Permitir puerto 5432 desde el security group de la
   aplicacion y ubicar ambos recursos en redes con conectividad entre si.
2. Crear un ambiente Beanstalk Python 3.11, balanceado, y configurar
   `DATABASE_URL` y `JWT_SECRET_KEY` en las propiedades de entorno.
3. Empaquetar `application.py`, `app/`, `requirements.txt` y `.ebextensions/`
   directamente en la raiz del ZIP. Excluir `.env`, `.venv`, `.git` y pruebas.
   Ejecutar `.\.venv\Scripts\python.exe scripts/package.py` para generar
   `dist/blacklists.zip` con estos archivos.
4. Subir el ZIP como una version de aplicacion. `.ebextensions` configura
   `application:application`, `/health` y crea las tablas en la instancia lider.
   RDS y las variables deben estar disponibles antes del despliegue.
5. Generar un token usando la misma clave del ambiente, probar ambos endpoints
   con Postman y verificar el health check. No es necesario conectar a RDS
   desde el equipo local para generar el token.
6. Para las estrategias, ajustar Auto Scaling a minimo 3 y maximo 6 instancias.
   Desplegar nuevas versiones con una diferencia visible y ejecutar cuatro
   estrategias, por ejemplo All at once, Rolling, Rolling with additional batch
   e Immutable. Registrar instancias, validacion, tiempo, reutilizacion o
   reemplazo de instancias, capturas y hallazgos para cada estrategia.

La configuracion no fija Auto Scaling ni las politicas de despliegue: se cambian
manualmente en AWS como parte del ejercicio. Si falla `init-db`, revisar los logs
de despliegue, variables, credenciales y conectividad hacia RDS.

La confianza en cabeceras de proxy supone que el proceso WSGI solo recibe
trafico desde los proxies del ambiente. Para un ambiente de una sola instancia
con nginx y sin ALB, configurar `PROXY_HOPS=1`.

Referencia: [Desplegar Flask en Elastic Beanstalk](https://docs.aws.amazon.com/elasticbeanstalk/latest/dg/create-deploy-python-flask.html).

## Acceso a New Relic

Compartir la URL interna de APM no concede permisos. Para revision interactiva,
invitar al tutor desde **Administration > User management > Add user** y conceder
acceso solo a la cuenta correspondiente, con rol **Read only** cuando el plan
permita asignarlo. No compartir la sesion del propietario ni dar permisos Admin.
Consultar [gestion de usuarios](https://docs.newrelic.com/docs/accounts/accounts-billing/new-relic-one-user-management/user-management-ui-and-tasks/).

El tipo de usuario limita las vistas disponibles: **Basic** permite consultas y
dashboards personalizados, pero no la interfaz completa de APM; esta requiere
**Full platform**. Revisar el plan y costo antes de aprovisionar usuarios de pago,
incluso si aun no aceptaron la invitacion. Ver [tipos de usuario](https://docs.newrelic.com/docs/accounts/accounts-billing/new-relic-one-user-management/user-type/).

Como alternativa, un dashboard puede compartirse mediante una live URL sin login
en planes **Pro o Enterprise**. Desde el dashboard usar **Share > Share dashboard**,
definir vencimiento y protegerlo con contrasena; no convierte APM ni Errors Inbox
en vistas publicas. Ver [condiciones y procedimiento](https://docs.newrelic.com/docs/query-your-data/explore-query-data/dashboards/share-dashboards-publicly/).
No se declara un enlace publico habilitado mientras no se haya creado y probado.

Las capturas del informe, el video y los registros cloud conservan el respaldo
historico. Para E1-E4 seleccionar sus ventanas exactas; los ultimos 30 minutos
no necesariamente contienen las pruebas. Una consulta normal del tutor puede
generar datos nuevos, pero no recrea por si sola las alertas historicas.

## Evaluacion y cierre

El equipo confirmo la grabacion del video de sustentacion. El informe, el video
y el enlace de documentacion Postman se comparten con el tutor por los canales
academicos acordados. Este README centraliza los procedimientos, configuraciones
y registros tecnicos; no se publican credenciales de los recursos compartidos.

- Mantener el ambiente compartido y el agente New Relic durante la calificacion.
  No ejecutar los procedimientos de limpieza mientras el tutor necesite probar.
- Entregar el JWT por un canal privado y comprobar los permisos de cualquier
  enlace de informe, video, Postman o dashboard compartido con el tutor.
- Conservar las evidencias y los resultados historicos antes de que venza su
  retencion; mantener servicios encendidos no garantiza retencion indefinida.
- Vigilar consumo y alertas de presupuesto. La infraestructura encendida sigue
  generando consumo; no asumir que los creditos cubren todo el periodo.
- Tras confirmar la calificacion, aplicar la [limpieza ordenada de AWS](docs/Entrega-3-Limpieza-AWS.md)
  y el [retiro de New Relic](docs/Entrega-4-NewRelic-AWS.md#9-desactivar-o-retirar).
  Retirar tambien el acceso temporal del tutor y revocar los enlaces compartidos.
