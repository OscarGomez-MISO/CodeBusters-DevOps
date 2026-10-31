# Entrega 2: guia de pruebas locales y CI para los cuatro integrantes

Cada integrante sigue esta guia en su equipo y en su propia cuenta AWS. Todos
usan el mismo repositorio y la rama de integracion `main`, ya acordada para este
proyecto. El CI se ejecuta en AWS CodeBuild, usando `buildspec.yml`, y termina
al guardar un ZIP en S3. El despliegue en Beanstalk sigue siendo manual.

Objetivo de la comprobacion conjunta: publicar un unico cambio en `main` y
verificar una ejecucion automatica en cada uno de los cuatro proyectos CodeBuild,
con el mismo SHA de origen y artefactos almacenados en las cuentas respectivas.
Este objetivo esta pendiente hasta registrar las cuatro ejecuciones reales.

## 1. Que quedo preparado en el repositorio

- `tests/test_blacklists.py`: escenarios existentes con SQLite en memoria;
  se refuerza que los errores de validacion y autenticacion no crean registros.
- `tests/test_blacklist_post.py`: motivo nulo/vacio, duplicado que conserva el
  registro original, JWT vencido o firmado con otra clave y recuperacion tras
  un error simulado al confirmar la transaccion.
- `tests/test_ci.py`: comprueba en proyectos temporales que el flujo genera
  artefacto solo si las pruebas pasan y elimina cualquier ZIP anterior.
- `scripts/ci.py`: ejecuta pruebas, genera reporte JUnit y despues empaqueta.
- `buildspec.yml`: instala dependencias con Python 3.11 y llama ese flujo.

No se modifico el comportamiento del API. La prueba externa
`tests/test_postgres.py` se excluye explicitamente del CI. No se necesita Docker,
RDS, una base externa ni variables de produccion para ejecutar las pruebas.

Verificacion local del 30 de octubre de 2026: 34 pruebas aprobadas. Son 32 casos
del API/CLI y dos verificaciones del flujo CI. Este resultado local no demuestra
que ya se haya configurado o ejecutado CodeBuild.

El integrante 2 todavia debe revisar y completar su cobertura de GET, `/health`,
su alias `/` y `/version`. El integrante 3 revisara esta base de buildspec y
el integrante 4 la salida S3 y empaquetado al integrar el trabajo del equipo.

## 2. Ejecutar el mismo flujo localmente

Requisitos: Git y Python 3.11. No se requiere Docker, PostgreSQL, una cuenta AWS
configurada en el equipo, un `.env` ni un token del API para ejecutar este CI.

Si todavia no tienes el repositorio, ejecutar en PowerShell:

```powershell
git clone --branch main https://github.com/OscarGomez-MISO/CodeBusters-DevOps.git
Set-Location CodeBusters-DevOps
```

Si ya tienes el repositorio, revisar primero `git status`. Con el arbol de
trabajo limpio, cambiar a `main` y actualizar sin generar un merge local:

```powershell
git switch main
git pull --ff-only origin main
```

Si hay cambios locales, conservarlos en tu rama de trabajo antes de cambiar
de rama. No descartarlos para ejecutar esta guia.

Desde la raiz del repositorio, crear el entorno virtual si no existe:

```powershell
py -3.11 -m venv .venv
```

Instalar y ejecutar usando directamente el Python del entorno virtual; no hace
falta activarlo en PowerShell:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe scripts/ci.py
```

Las fixtures crean una base SQLite en memoria independiente por prueba y la
eliminan al terminar. Usan una clave JWT exclusiva de pruebas. No se ejecuta
`flask init-db`, no se levanta PostgreSQL y no se utilizan las credenciales RDS
del ambiente desplegado.

Resultados:

- `reports/pytest.xml`: conteos y resultados en JUnit XML.
- `dist/blacklists.zip`: solo si las pruebas pasan.

El ZIP anterior se elimina antes de ejecutar pytest. Asi, un fallo nuevo no
deja un ZIP viejo que CodeBuild pueda confundir con el artefacto aprobado.
El reporte puede conservarse aunque fallen las pruebas para diagnosticarlo.

Comprobar en la salida que todas las pruebas finalizan aprobadas y que aparece
`CI passed. Artifact ready: dist/blacklists.zip`. El conteo de referencia es 34;
puede aumentar cuando se integren las pruebas de los otros integrantes.

Anotar tambien el commit local con `git rev-parse HEAD`. El codigo local puede
estar desactualizado aunque las pruebas pasen; todos deben usar la misma base.

## 3. Que se comparte y que configura cada cuenta

CodeBuild descarga el contenido de GitHub; no puede leer cambios que solo
existen en un equipo local. La base del CI ya esta integrada en `main`.

| Compartido en GitHub | Propio de cada cuenta AWS |
| --- | --- |
| API, dependencias y pruebas | Proyecto CodeBuild |
| `buildspec.yml` | Conexion autorizada a GitHub |
| `scripts/ci.py` y `scripts/package.py` | Rol IAM del proyecto |
| Rama `main` y commits | Bucket S3 y prefijo de artefactos |
| Misma logica de construccion | Webhook, logs, reportes y resultados |

No se necesita personalizar el buildspec por integrante. El bucket, el rol y la
conexion se seleccionan en la configuracion de cada proyecto AWS, sin guardar
identificadores de una cuenta ni credenciales en los archivos compartidos.

Usar estos nombres como referencia, ajustando el sufijo del bucket para que
sea globalmente unico:

| Integrante | Proyecto CodeBuild | Bucket S3 |
| --- | --- | --- |
| 1 | `codebusters-ci-integrante1` | `codebusters-ci-integrante1-<sufijo-unico>` |
| 2 | `codebusters-ci-integrante2` | `codebusters-ci-integrante2-<sufijo-unico>` |
| 3 | `codebusters-ci-integrante3` | `codebusters-ci-integrante3-<sufijo-unico>` |
| 4 | `codebusters-ci-integrante4` | `codebusters-ci-integrante4-<sufijo-unico>` |

En los siguientes pasos, sustituir `<n>` por 1, 2, 3 o 4. Cada integrante usa
su propia cuenta AWS; los nombres propuestos no crean ni comparten recursos.
La rama definitiva de origen y del webhook es `main` para los cuatro.

## 4. Crear el bucket de artefactos

En AWS, region `us-east-1`, entrar a S3 y crear un bucket de uso general:

| Campo | Valor propuesto |
| --- | --- |
| Nombre | `codebusters-ci-integrante<n>-<sufijo-unico>` |
| Region | `us-east-1` |
| Acceso publico | Bloqueado |
| Propiedad de objetos | ACL deshabilitadas |
| Cifrado | SSE-S3 predeterminado |
| Clave de bucket | No se requiere para SSE-S3; se puede dejar deshabilitada |

No necesitas una politica de acceso publico. El rol de CodeBuild sera quien
escriba los artefactos. El nombre del bucket debe ser unico.

Evidencia E01: configuracion del bucket, region y bloqueo de acceso publico.

## 5. Crear el proyecto CodeBuild

Entrar a CodeBuild > Proyectos de compilacion > Crear proyecto.

### Proyecto y fuente

| Campo | Valor |
| --- | --- |
| Nombre | `codebusters-ci-integrante<n>` |
| Tipo de proyecto | Proyecto de compilacion normal |
| Proveedor de origen | GitHub |
| Repositorio | `OscarGomez-MISO/CodeBusters-DevOps` |
| Version de origen / rama | `main` |

Autorizar el acceso usando una conexion GitHub App de AWS CodeConnections o
el mecanismo que ya tenga permitido la cuenta. La conexion debe quedar
disponible y tener acceso al repositorio. Si no administras el repositorio,
coordinar con su propietario la autorizacion de la aplicacion y los webhooks.
La instalacion GitHub App puede estar autorizada previamente en GitHub, pero
cada proyecto debe tener una conexion utilizable desde su propia cuenta AWS.
No eliminar ni reemplazar los webhooks de los otros integrantes.

### Entorno

| Campo | Valor |
| --- | --- |
| Imagen | Administrada por AWS CodeBuild |
| Computo | EC2, Linux, capacidad pequena disponible |
| Sistema | Amazon Linux |
| Imagen | `aws/codebuild/amazonlinux-x86_64-standard:5.0`, compatible con Python 3.11 |
| Modo privilegiado | Deshabilitado |
| VPC personalizada | Sin configurar para este CI con SQLite |
| Rol de servicio | Crear un rol propio para este proyecto |
| Variables de entorno de la aplicacion | No configurar `DATABASE_URL`, `JWT_SECRET_KEY` ni `POSTGRES_TEST_URL` de produccion |

No crear un runner de GitHub Actions: esta configuracion usa directamente
CodeBuild y el archivo `buildspec.yml`. El CI no requiere las credenciales RDS
ni `JWT_SECRET_KEY` del ambiente Beanstalk. Las fixtures usan su propia clave
de pruebas y SQLite en memoria.

### Buildspec

Seleccionar usar un archivo buildspec del repositorio. Ruta: `buildspec.yml`.

El archivo ya fija Python 3.11 y ejecuta `python scripts/ci.py`. No ingresar
los comandos de pruebas nuevamente desde la consola ni omitir la fase de tests.

### Artefactos

| Campo | Valor |
| --- | --- |
| Tipo | Amazon S3 |
| Bucket | El bucket creado en el paso anterior |
| Ruta o prefijo | `builds` |
| Espacio de nombres / namespace | Build ID, si aparece como opcion |
| Nombre | `blacklists` |
| Empaquetado | None / Sin empaquetar |

El ZIP ya lo crea `scripts/package.py`. Con empaquetado None, CodeBuild copia
ese ZIP como archivo, sin envolverlo en otro ZIP. El buildspec selecciona
unicamente `dist/blacklists.zip`. El Build ID en la ruta evita que los resultados
de distintas ejecuciones se sobrescriban.

### Logs y permisos

Habilitar CloudWatch Logs y conservar la configuracion de logs del proyecto.
Verificar que el rol tenga acceso al bucket elegido y a la conexion de origen.
Los reportes requieren permisos como `codebuild:CreateReportGroup`,
`codebuild:CreateReport`, `codebuild:UpdateReport` y
`codebuild:BatchPutTestCases`, limitados a los reportes del proyecto.

Si usas GitHub App, el rol tambien necesita el permiso de uso de la conexion,
segun la configuracion de AWS CodeConnections. Revisar el mensaje concreto si
aparece AccessDenied; no sustituirlo por permisos administrativos generales.

Evidencia E02: fuente, entorno Python, buildspec y destino de artefactos.

## 6. Activar y verificar el disparador automatico

En la configuracion de origen habilitar reconstruir cuando se publique un cambio
en el repositorio. Configurar un grupo de filtros:

- Evento: `PUSH`.
- Condicion: `START_BUILD`.
- Tipo de filtro: `HEAD_REF`.
- Patron: `^refs/heads/main$`.

Usar compilacion unica y mantener desmarcada la creacion manual del webhook,
salvo que los permisos de la cuenta obliguen a configurarlo manualmente.
El evento y el filtro deben estar en el mismo grupo. Revisar que no haya otro
grupo de filtros que dispare builds adicionales en otras ramas.

Los cuatro proyectos observan el mismo repositorio y la misma rama, pero cada
uno tiene su disparador. Un push puede iniciar las cuatro ejecuciones sin
que un integrante llame manualmente a los proyectos de los demas. Los commits
publicados antes de habilitar los webhooks no se construyen retroactivamente.

Evidencia E03: webhook habilitado y filtro de rama/evento. Una ejecucion manual
puede ayudar a depurar, pero no reemplaza el build automatico desde GitHub.

## 7. Comprobacion conjunta: el mismo cambio inicia los cuatro builds

### Confirmar que todos estan listos

Antes de publicar el cambio de demostracion, completar esta tabla compartida.
Cada integrante verifica su proyecto, no solo la ejecucion local:

| Integrante | Pruebas locales aprobadas | Proyecto y bucket creados | Conexion disponible | Origen `main` | Webhook PUSH a `main` | Listo |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Pendiente | Pendiente | Pendiente | Pendiente | Pendiente | Pendiente |
| 2 | Pendiente | Pendiente | Pendiente | Pendiente | Pendiente | Pendiente |
| 3 | Pendiente | Pendiente | Pendiente | Pendiente | Pendiente | Pendiente |
| 4 | Pendiente | Pendiente | Pendiente | Pendiente | Pendiente | Pendiente |

Se puede iniciar una compilacion manual para depurar una cuenta antes de la
prueba conjunta. Identificarla como diagnostico: no demuestra el webhook.

### Publicar un unico cambio compartido

1. Cuando los cuatro esten listos, elegir una persona para publicar un cambio
   pequeno de documentacion. No hacen falta cuatro commits de prueba distintos.
2. Usar un PR desde una rama propia y fusionarlo en `main`, o un push directo si
   las reglas del repositorio lo permiten. Registrar el SHA final que quedo en
   `main`; puede ser distinto del SHA de la rama si se hizo merge o squash.
3. Compartir ese SHA y la hora con el equipo. Pausar otros cambios en `main`
   hasta que todos recojan las evidencias de esta ejecucion.
4. Cada integrante abre el historial de su proyecto y confirma una ejecucion
   iniciada automaticamente. No pulsar Iniciar compilacion para esa evidencia.
5. Comparar la version de origen del build con el mismo SHA compartido y con el
   mensaje `CI source: <SHA>` de los logs.

Los cuatro builds no necesitan empezar o terminar al mismo segundo. El criterio
es que correspondan al mismo commit y hayan sido activados automaticamente.

### Verificar el resultado en cada cuenta

1. Revisar las fases INSTALL, BUILD y UPLOAD_ARTIFACTS y los logs de pytest.
2. Revisar el reporte `pytest_reports`: conteos reales de pruebas y duracion.
3. Abrir el bucket S3, identificar el objeto de esa ejecucion y descargarlo.
4. Abrir el ZIP: debe contener `application.py`, `requirements.txt`, `app/`
   y `.ebextensions/` directamente en la raiz, sin `.env`, claves o `.venv`.

No desplegar automaticamente el ZIP. Generarlo es el resultado de esta entrega.

### Consolidar la evidencia de los cuatro builds

Commit comun de la demostracion: `[POR COMPLETAR: SHA completo de main]`.

| Integrante | Proyecto y cuenta identificable | Build ID o enlace | Activacion automatica comprobada | SHA coincide | Estado y duracion | URI S3 del ZIP |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | [POR COMPLETAR] | [POR COMPLETAR] | [POR COMPLETAR] | [POR COMPLETAR] | [POR COMPLETAR] | [POR COMPLETAR] |
| 2 | [POR COMPLETAR] | [POR COMPLETAR] | [POR COMPLETAR] | [POR COMPLETAR] | [POR COMPLETAR] | [POR COMPLETAR] |
| 3 | [POR COMPLETAR] | [POR COMPLETAR] | [POR COMPLETAR] | [POR COMPLETAR] | [POR COMPLETAR] | [POR COMPLETAR] |
| 4 | [POR COMPLETAR] | [POR COMPLETAR] | [POR COMPLETAR] | [POR COMPLETAR] | [POR COMPLETAR] | [POR COMPLETAR] |

Adjuntar un resumen de build de cada cuenta que permita ver el SHA y el ID,
mas sus reportes y artefactos. Una captura de una sola cuenta no demuestra las
otras tres ejecuciones. Los cuatro deben usar los mismos archivos de CI.

Evidencias:

- E04: commit y build automatico exitoso, ID y duracion.
- E05: fase de pruebas y reporte JUnit.
- E06: objeto S3 y contenido correcto del ZIP.

## 8. Obtener la ejecucion fallida y recuperar

Coordinar con el equipo antes de introducir un fallo en una rama compartida.
Usar el mismo procedimiento de coordinacion de la seccion 7: los cuatro
proyectos deben estar listos y el equipo debe registrar el SHA comun del fallo.

Una regresion propuesta es cambiar temporalmente el estado de creacion del POST
de `201` a `200`, conservando las pruebas que exigen el contrato `201`. No se ha
aplicado ese cambio en esta implementacion.

1. Publicar el cambio acordado en `main` mediante el mecanismo permitido.
2. Esperar que los cuatro webhooks inicien sus builds.
3. Cada integrante captura la asercion que esperaba 201 y recibio 200, el mismo
   SHA comun y su propio build fallido.
4. Comprobar que no aparece un nuevo ZIP aprobado para el Build ID fallido.
   El bucket puede conservar ZIP de ejecuciones anteriores.
5. Restaurar el comportamiento correcto mediante un nuevo commit o revert del
   cambio acordado. No borrar el historial ni desplegar el cambio defectuoso.
6. Esperar el nuevo build exitoso en las cuatro cuentas y guardar las referencias
   con el SHA comun de recuperacion. Dejar `main` corregida al terminar.

CodeBuild intenta UPLOAD_ARTIFACTS incluso si falla BUILD. En ese caso puede
aparecer un mensaje secundario indicando que no encontro el ZIP: lo importante
es mostrar que el fallo original fue la prueba y que el empaquetado no se ejecuto.
El reporte JUnit y los logs de diagnostico pueden mantenerse.

Evidencias E07: build fallido y asercion de pytest.
Evidencia E08: commit corregido y ejecucion de recuperacion exitosa.

## 9. Datos para el informe de cada integrante

Cada integrante completa esta ficha con sus resultados y los entrega a quien
consolida el documento. Conservar tambien la tabla comparativa de la seccion 7.

| Dato | Resultado real |
| --- | --- |
| Proyecto y region | [POR COMPLETAR] |
| Rama observada | `main` |
| Commit y Build ID exitoso | [POR COMPLETAR] |
| Duracion y conteo de pruebas exitosas | [POR COMPLETAR] |
| URI S3 del ZIP | [POR COMPLETAR] |
| Commit y Build ID fallido | [POR COMPLETAR] |
| Prueba que detecto la regresion | [POR COMPLETAR] |
| Duracion y mensaje del fallo | [POR COMPLETAR] |
| Confirmacion de ausencia de nuevo ZIP aprobado | [POR COMPLETAR] |
| Commit y Build ID de recuperacion | [POR COMPLETAR] |

Texto base de la estrategia de pruebas, ajustar al trabajo final:

> Las pruebas del API se ejecutaron con pytest y SQLite en memoria, usando una
> base independiente por prueba y claves JWT exclusivas del entorno de pruebas.
> Los fallos de dependencias se simularon con mocks. No se requirio conexion a
> PostgreSQL ni RDS durante el CI; esa infraestructura se mantuvo para el ambiente
> desplegado de la aplicacion.

Para los hallazgos escribir solo lo que efectivamente muestran las ejecuciones.
No presentar los 34 casos locales como builds AWS ya ejecutados. Al integrar
pruebas de los companeros el total puede aumentar.

## 10. Si una cuenta no se activa o falla

- No aparece un build: comprobar que el cambio llego a `main` despues de crear
  el webhook, que la conexion tiene acceso al repositorio y que el evento PUSH
  y el patron `^refs/heads/main$` estan habilitados en el mismo grupo.
- Solo arrancan algunos proyectos: revisar los webhooks y permisos de las
  cuentas que faltan; no hace falta modificar el buildspec para cada persona.
- El SHA no coincide: revisar la rama fuente y si entro otro commit en `main`.
  Registrar una nueva prueba comun cuando las cuatro cuentas esten listas.
- Falla DOWNLOAD_SOURCE: comprobar autorizacion GitHub y acceso a la conexion
  desde el rol CodeBuild de esa cuenta.
- Falla INSTALL: capturar el error de runtime o instalacion. Verificar imagen
  compatible con Python 3.11 y salida a internet del entorno administrado.
- Falla BUILD: leer el primer error de pytest o del script. Registrar el
  resultado real; no cambiar las expectativas de pruebas para ocultar un fallo.
- Falla la carga del reporte o S3: comprobar region, bucket y permisos del rol
  para logs, reportes, conexion y artefactos. Ese fallo no demuestra por si solo
  una regresion detectada por las pruebas del API.
- No aparece el archivo local `dist/blacklists.zip`: resolver las pruebas o el
  empaquetado. No reutilizar un ZIP de otra ejecucion como si fuera nuevo.

Si se requiere repetir la demostracion, corregir primero las configuraciones
individuales y despues acordar un unico nuevo commit de prueba en `main`.

## Referencias oficiales

- [Buildspec](https://docs.aws.amazon.com/codebuild/latest/userguide/build-spec-ref.html).
- [pytest y reportes JUnit](https://docs.aws.amazon.com/codebuild/latest/userguide/test-report-pytest.html).
- [Filtros de webhook](https://docs.aws.amazon.com/codebuild/latest/userguide/github-webhook.html).
- [GitHub App y permisos de conexion](https://docs.aws.amazon.com/codebuild/latest/userguide/connections-github-app.html).
- [Empaquetado y rutas S3](https://docs.aws.amazon.com/codebuild/latest/APIReference/API_ProjectArtifacts.html).
- [Fases y carga de artefactos tras un fallo](https://docs.aws.amazon.com/codebuild/latest/userguide/view-build-details-phases.html).
- [Imagenes y runtimes disponibles](https://docs.aws.amazon.com/codebuild/latest/userguide/available-runtimes.html).
