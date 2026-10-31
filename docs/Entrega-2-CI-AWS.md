# Entrega 2: pruebas y CI en la cuenta del integrante 1

Esta guia acompana la rama `feature-TestAndCIBase`. El CI se ejecuta en AWS
CodeBuild, usando `buildspec.yml`, y termina al guardar un ZIP en S3. El
despliegue en Beanstalk sigue siendo manual.

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

En PowerShell, desde la raiz del repositorio:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe scripts/ci.py
```

Resultados:

- `reports/pytest.xml`: conteos y resultados en JUnit XML.
- `dist/blacklists.zip`: solo si las pruebas pasan.

El ZIP anterior se elimina antes de ejecutar pytest. Asi, un fallo nuevo no
deja un ZIP viejo que CodeBuild pueda confundir con el artefacto aprobado.
El reporte puede conservarse aunque fallen las pruebas para diagnosticarlo.

## 3. Publicar el codigo antes de configurar AWS

CodeBuild descarga el contenido de GitHub; no puede leer cambios que solo
existen en tu equipo local. Revisar, crear el commit y publicar esta rama.
Estos comandos son instrucciones, no acciones ya ejecutadas por el asistente:

```powershell
git status --short --branch
git add .gitignore README.md buildspec.yml scripts/ci.py tests/test_blacklists.py tests/test_blacklist_post.py tests/test_ci.py docs/Entrega-2-CI-AWS.md
git diff --cached --stat
git commit -m "Agrega pruebas POST y base CI con SQLite para CodeBuild"
git push -u origin feature-TestAndCIBase
```

Para configurar y depurar tu proyecto se puede usar esa rama. Antes de cerrar
la entrega se debe integrar el codigo y demostrar el disparador sobre la rama
principal acordada. El enunciado dice `master` y el repositorio usa `main`:
confirmar la equivalencia con el docente o acordar `master` con el equipo.
Una ejecucion solo sobre la rama de desarrollo no demuestra ese requisito.

## 4. Crear el bucket de artefactos

En AWS, region `us-east-1`, entrar a S3 y crear un bucket de uso general:

| Campo | Valor propuesto |
| --- | --- |
| Nombre | `codebusters-ci-integrante1-<sufijo-unico>` |
| Region | `us-east-1` |
| Acceso publico | Bloqueado |
| Propiedad de objetos | ACL deshabilitadas |
| Cifrado | SSE-S3 predeterminado |

No necesitas una politica de acceso publico. El rol de CodeBuild sera quien
escriba los artefactos. El nombre del bucket debe ser unico.

Evidencia E01: configuracion del bucket, region y bloqueo de acceso publico.

## 5. Crear el proyecto CodeBuild

Entrar a CodeBuild > Proyectos de compilacion > Crear proyecto.

### Proyecto y fuente

| Campo | Valor |
| --- | --- |
| Nombre | `codebusters-ci-integrante1` |
| Tipo de proyecto | Proyecto de compilacion normal |
| Proveedor de origen | GitHub |
| Repositorio | `OscarGomez-MISO/CodeBusters-DevOps` |
| Rama para el diagnostico inicial | `feature-TestAndCIBase` |

Autorizar el acceso usando una conexion GitHub App de AWS CodeConnections o
el mecanismo que ya tenga permitido la cuenta. La conexion debe quedar
disponible y tener acceso al repositorio. Si no administras el repositorio,
coordinar con su propietario la autorizacion de la aplicacion y los webhooks.

### Entorno

| Campo | Valor |
| --- | --- |
| Imagen | Administrada por AWS CodeBuild |
| Computo | EC2, Linux, capacidad pequena disponible |
| Sistema | Ubuntu |
| Runtime/imagen | Imagen estandar compatible con Python 3.11; por ejemplo `aws/codebuild/standard:7.0` |
| Modo privilegiado | Deshabilitado |
| VPC personalizada | Sin configurar para este CI con SQLite |
| Rol de servicio | Crear un rol propio para este proyecto |

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
- Tipo de filtro: `HEAD_REF`.
- Patron temporal para esta rama: `^refs/heads/feature-TestAndCIBase$`.

Antes de la demostracion final, cambiar el patron a la rama principal acordada:
`^refs/heads/main$` o `^refs/heads/master$`. Debe coincidir con la decision
documentada sobre el enunciado. Registrar la rama exacta, sin confundirla con
el nombre del proyecto CodeBuild.

Evidencia E03: webhook habilitado y filtro de rama/evento. Una ejecucion manual
puede ayudar a depurar, pero no reemplaza el build automatico desde GitHub.

## 7. Obtener la ejecucion exitosa

1. Con proyecto y webhook listos, publicar un cambio real en la rama observada.
   Puede ser una mejora de documentacion; no se necesita alterar el API.
2. Confirmar que CodeBuild se inicia automaticamente. Comparar el SHA del commit
   de GitHub con la version de origen del build.
3. Revisar las fases INSTALL, BUILD y UPLOAD_ARTIFACTS y los logs de pytest.
4. Revisar el reporte `pytest_reports`: conteos reales de pruebas y duracion.
5. Abrir el bucket S3, identificar el objeto de esa ejecucion y descargarlo.
6. Abrir el ZIP: debe contener `application.py`, `requirements.txt`, `app/`
   y `.ebextensions/` directamente en la raiz, sin `.env`, claves o `.venv`.

No desplegar automaticamente el ZIP. Generarlo es el resultado de esta entrega.

Evidencias:

- E04: commit y build automatico exitoso, ID y duracion.
- E05: fase de pruebas y reporte JUnit.
- E06: objeto S3 y contenido correcto del ZIP.

## 8. Obtener la ejecucion fallida y recuperar

Coordinar con el equipo antes de introducir un fallo en una rama compartida.
Los cuatro proyectos pueden usar los mismos commits para su demostracion.

Una regresion propuesta es cambiar temporalmente el estado de creacion del POST
de `201` a `200`, conservando las pruebas que exigen el contrato `201`. No se ha
aplicado ese cambio en esta implementacion.

1. Publicar el cambio acordado en la rama observada.
2. Esperar que el webhook inicie el build.
3. Capturar la asercion que esperaba 201 y recibio 200, el SHA y el build fallido.
4. Comprobar que no aparece un nuevo ZIP aprobado para el Build ID fallido.
   El bucket puede conservar ZIP de ejecuciones anteriores.
5. Restaurar el comportamiento correcto mediante un nuevo commit o revert del
   cambio acordado. No borrar el historial ni desplegar el cambio defectuoso.
6. Esperar el nuevo build exitoso y guardar su referencia.

CodeBuild intenta UPLOAD_ARTIFACTS incluso si falla BUILD. En ese caso puede
aparecer un mensaje secundario indicando que no encontro el ZIP: lo importante
es mostrar que el fallo original fue la prueba y que el empaquetado no se ejecuto.
El reporte JUnit y los logs de diagnostico pueden mantenerse.

Evidencias E07: build fallido y asercion de pytest.
Evidencia E08: commit corregido y ejecucion de recuperacion exitosa.

## 9. Datos para el informe del integrante 1

| Dato | Resultado real |
| --- | --- |
| Proyecto y region | [POR COMPLETAR] |
| Rama observada y decision main/master | [POR COMPLETAR] |
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

## Referencias oficiales

- [Buildspec](https://docs.aws.amazon.com/codebuild/latest/userguide/build-spec-ref.html).
- [pytest y reportes JUnit](https://docs.aws.amazon.com/codebuild/latest/userguide/test-report-pytest.html).
- [Filtros de webhook](https://docs.aws.amazon.com/codebuild/latest/userguide/github-webhook.html).
- [GitHub App y permisos de conexion](https://docs.aws.amazon.com/codebuild/latest/userguide/connections-github-app.html).
- [Empaquetado y rutas S3](https://docs.aws.amazon.com/codebuild/latest/APIReference/API_ProjectArtifacts.html).
- [Fases y carga de artefactos tras un fallo](https://docs.aws.amazon.com/codebuild/latest/userguide/view-build-details-phases.html).
