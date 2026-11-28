# Entrega 4 - Ejecucion cloud de Oscar

Registro de la ejecucion del integrante 1 sobre el ambiente compartido de evaluacion.
Este documento distingue resultados medidos por el ejecutor, comprobaciones de AWS y
evidencias pendientes de confirmar en New Relic. No contiene credenciales.

## 1. Ambiente y alcance

- SHA bajo prueba: `425722dc3e1dc7d55f3c6c34ca5e7d5442c3611e`.
- Entidad New Relic: `cb-e4-i1-cloud`.
- Servicio: `cb-e3-i1-service`, cluster `cb-e3-i1-cluster`, region `us-east-1`.
- Revision inicial: `cb-e3-i1-blacklists:17`, Fargate, CPU 256, memoria 512 MiB,
  una tarea y un worker de Gunicorn. New Relic activo; laboratorio desactivado.
- API: version `2.2.0`; base de datos PostgreSQL en RDS.
- Generador: Python 3.11.18 y Locust 2.47.0, en un entorno temporal aislado sobre
  Windows. El trafico viaja desde el equipo local hacia el ALB de AWS.
- Horas del ejecutor en UTC; equivalencia para Colombia: UTC-5.

El merge de documentacion posterior puede disparar otro build y despliegue; no cambia
el SHA ni la imagen que se registran como objeto de estas pruebas.
Se ejecutan los escenarios del repositorio, sin modificar workers, capacidad ni limites
para forzar artificialmente una degradacion. Las altas usan correos ficticios.

## 2. Prerrequisitos

La sesion AWS, el despliegue estable y las variables de New Relic se comprobaron por CLI
y, al estar disponible, mediante el servidor MCP oficial de AWS.
Las capturas aportadas en el chat muestran la entidad cloud con operaciones PostgreSQL,
dos condiciones habilitadas y el workflow de correo habilitado. No sustituyen las
capturas de las ventanas de carga ni prueban por si solas la entrega de notificaciones.

| Comprobacion | Resultado observado |
| --- | --- |
| Pipeline que activo New Relic | `b0e538b3-60f7-4bd1-99e7-7a5d48d3d0ec`, `Succeeded`; 27/11/2026 21:41:54 a 21:50:20, Colombia (UTC-5) |
| Salud y version previas | HTTP 200 en `/health` y `/version`; version `2.2.0` |
| Autenticacion previa | Consulta autenticada a un correo ficticio: HTTP 200 |
| Laboratorio previo | `POST /observability/error`: HTTP 404, bandera desactivada |
| Coleccion funcional | Newman 6.2.2, misma coleccion Postman del repositorio: 7 solicitudes y 7 aserciones aprobadas, 0 fallos |
| Ventana funcional | 27/11/2026 22:38:19 a 22:38:22, Colombia (UTC-5) |
| Codigos de la coleccion | 200, 201, 200, 409, 200, 400, 401; los tres 4xx son casos negativos esperados |
| Pruebas del generador | `python -m pytest tests/test_loadtests_settings.py -q --noconftest -p no:cacheprovider`: 24 aprobadas |
| CI del despliegue inicial | Build `cb-e3-i1-build:251608e7-0f25-43e4-8b3f-f3e7957bc7a4`; reporte CodeBuild: 119 aprobadas, 0 fallidas, 0 errores, 0 omitidas |
| Deployment inicial | `d-MLIJZMA2N` |

La coleccion se ejecuto con Newman porque el CLI incluido dentro de Postman no admite
su uso externo como CLI independiente. Se conservaron JUnit y log saneado, sin exportar
el environment privado. Hubo un error de codificacion de consola al mostrar caracteres
Unicode; no fue un fallo del API ni de la coleccion: el proceso Newman termino con
codigo 0 y sus resultados se comprobaron en el log y manifiesto. Se corrigio la salida
UTF-8 del auxiliar local antes de continuar.

### Configuracion de alertas aportada por capturas

| Objeto | Configuracion |
| --- | --- |
| Politica | `cb-e4-i1-politica`; un issue por condicion y senal |
| Errores 5xx | `cb-e4-i1-errores-5xx`; porcentaje mayor que 5 durante al menos 2 minutos |
| Apdex por duracion | `cb-e4-i1-apdex`; T=0,5 s; critico menor que 0,7 por 3 minutos, warning menor que 0,85 por 3 minutos |
| Agregacion acordada | Ventana 1 minuto, Event timer 60 s, sin relleno ni alerta de perdida de senal |
| Workflow | `cb-e4-i1-workflow`, filtro por la politica propia, correo y notificaciones Activated y Closed habilitadas |

El Apdex calculado con `apdex(duration, t: 0.5)` mide duracion; no se debe confundir
automaticamente con el Apdex de APM afectado por errores reportados por el agente.
La prueba inicial del workflow no encontro issues historicos coincidentes. Su captura
mostraba `Last run: N/A`; la entrega real se comprobo posteriormente en E3 mediante
los correos de apertura y cierre descritos en la seccion 4.

Se mantuvo la configuracion del agente sin marcar globalmente los 4xx como esperados:
la alerta de disponibilidad cuenta solo 5xx mediante `numeric(http.statusCode) >= 500`.
Los 400/401/409 de Postman y los 409 de siembra deben separarse de los fallos reales
del servicio al interpretar Errors Inbox y el Apdex de APM.

## 3. E1 y E2

Se usa como fuente de cierre el reporte HTML de Locust, contrastado con el resumen final
del log. Los percentiles son aproximados por el mecanismo de agregacion de Locust y
las latencias estan en milisegundos, medidas desde el cliente.

| Registro | E1 - Linea base | E2 - Estres |
| --- | --- | --- |
| Run ID | `i1-e1-1128t034021` | `i1-e2-1128t034541` |
| Ventana del reporte, Colombia UTC-5 | 27/11/2026 22:40:23 a 22:43:24 | 27/11/2026 22:45:43 a 22:51:43 |
| Ventana UTC | 28/11/2026 03:40:23 a 03:43:24 | 28/11/2026 03:45:43 a 03:51:43 |
| Plan | 1 usuario / 60 s y 5 usuarios / 120 s | 10 usuarios / 180 s y 25 usuarios / 180 s |
| Solicitudes / fallos | 596 / 0 | 5656 / 0 |
| Latencia promedio | 80,53 ms | 82,43 ms |
| Mediana / p95 / p99 | 79 / 86 / 150 ms | 78 / 97 / 160 ms |
| Maximo | 393 ms | 337 ms |
| Throughput promedio | 3,29 solicitudes/s | 15,68 solicitudes/s |
| Finalizacion | Normal, exit code 0; sin fallos ni excepciones en HTML | Normal, exit code 0; sin fallos ni excepciones en HTML |

Detalle E1: 393 consultas de correos, 169 creaciones, 18 health checks y 16 consultas
de version. La siembra previa creo 20 correos fijos; no forma parte de las 596
solicitudes de los usuarios virtuales. En la siguiente corrida los reutilizara.

El CSV periodico de E1 termina con 595 solicitudes; el HTML y el log final registran
596. Se conserva esa diferencia sin alterar los originales. Las dos fuentes reportan
cero fallos y p95 de 86 ms. Para evitar mezclar snapshots, todos los totales finales de
esta seccion se toman del HTML; el CSV historico respalda la evolucion por escalones.

En E2 el CSV termina con 5655 solicitudes y el HTML/log final con 5656, tambien sin
fallos en ambas fuentes. La misma regla de fuente de cierre se aplica a los dos casos.
Detalle E2: 4012 consultas de correos, 1385 creaciones, 133 health checks y 126 consultas
de version. La serie historica confirma los escalones de 10 y 25 usuarios.

### Hallazgos de carga

Al incrementar la carga de E1 a E2, el throughput promedio crecio aproximadamente
4,77 veces, mientras la latencia media paso de 80,53 a 82,43 ms y el p95 de 86 a 97 ms.
No se observaron fallos de las solicitudes de usuarios virtuales ni excepciones del
generador. Estos resultados no muestran saturacion con hasta 25 usuarios y este perfil
de solicitudes; no permiten afirmar que el servicio soporta una carga ilimitada ni
localizar un cuello de botella de DB sin los datos correspondientes de New Relic.

Los 20 correos de siembra se reutilizan en E2. Sus respuestas 409 son esperadas y no
entran en el contador de solicitudes de los usuarios virtuales, pero pueden aparecer
en APM durante los primeros segundos del escenario. Se deben identificar por su ventana
al analizar la tasa de errores del agente; la alerta de 5xx no los cuenta.

La hora `start_utc` del auxiliar incluye el arranque del proceso. El reporte HTML marca
el inicio de Locust y el log de siembra marca el inicio del trafico tras preparar los
correos. Se usan las ventanas del HTML para correlacionar con New Relic, declarando
que incluyen la preparacion inicial del escenario.

### Capacidad: complemento de CloudWatch

Se consultaron `CPUUtilization` y `MemoryUtilization` de `AWS/ECS`, con dimensiones
del cluster/servicio y periodo de 60 s, usando las ventanas del reporte.

| Metrica | E1 | E2 |
| --- | --- | --- |
| Muestras devueltas | 3 minutos: 22:40, 22:41 y 22:42 UTC-5 | 6 minutos: 22:45 a 22:50 UTC-5 |
| Mayor promedio de CPU por minuto | 12,14 % | 39,18 % |
| Mayor maximo de CPU de las muestras | 13,91 % | 41,22 % |
| Mayor maximo de memoria de las muestras | 16,80 % | 16,80 % |

La CPU subio con el escalon de carga y no alcanzo el 100 % en las muestras devueltas.
La memoria se mantuvo cercana al 16,8 %. Son datos complementarios de ECS, no mediciones
internas de RDS ni sustitutos de las capturas de rendimiento de New Relic. Los bordes
de las ventanas son parciales y no se presentan estos promedios por minuto como el
promedio exacto de toda la corrida.

## 4. E3 y E4

### Preparacion del error controlado

Se cambio unicamente `OBS_LAB_ENABLED` a `true` en `cb-e3-i1-build`, conservando las
otras variables, y se inicio el pipeline fijando el mismo SHA bajo prueba.

| Registro | Valor observado |
| --- | --- |
| Pipeline | `766d8299-e493-4c69-8be3-5a1c3bf2e6c7`, Source/Build/Deploy en `Succeeded` |
| Cambio solicitado | 27/11/2026 22:52:20 UTC-5 |
| Confirmacion del supervisor | 27/11/2026 23:01:25 UTC-5; es la hora de consulta, no se confunde con el instante exacto de cierre AWS |
| Build | `cb-e3-i1-build:730f75d1-1358-4c2a-a09c-af813c0ad93a` |
| Pruebas de este build | 119 aprobadas, 0 fallidas, 0 errores, 0 omitidas |
| Deployment | `d-PLMMQFB2N` |
| Cierre del deployment, AWS | 27/11/2026 23:01:11 UTC-5; `Succeeded`, sin `errorInformation` |
| Revision activa | `cb-e3-i1-blacklists:18`, primaria y estable; New Relic y laboratorio habilitados |
| Registro del agente | Mensaje `Reporting to` para `cb-e4-i1-cloud`, 27/11/2026 22:56:22 UTC-5, leido en CloudWatch |

Se ejecuto el script existente `monitoring/scripts/e3-error-controlado.sh` con duracion
300 s desde Git Bash. Los finales de linea CRLF del checkout Windows se normalizaron
en memoria al enviarlo por stdin, sin modificar el archivo versionado. Un supervisor
local agrego un limite de 360 s y detencion ante codigos distintos de 200 en consultas
normales o de 500/429 en el laboratorio. No se cambio el ritmo ni la logica del script.

### Resultado E3 y recuperacion E4

| Registro E3 | Resultado observado |
| --- | --- |
| Ventana del script | 27/11/2026 23:01:40 a 23:06:41, Colombia (UTC-5) |
| Ventana UTC | 28/11/2026 04:01:40 a 04:06:41 |
| Duracion solicitada | 300 s |
| Errores controlados | 125 respuestas HTTP 500 |
| Trafico normal paralelo | 210 consultas con HTTP 200 |
| Otros codigos en el CSV | Ninguno: no hubo 429 ni codigos inesperados |
| Salud al cierre | HTTP 200 en `/health` |
| Finalizacion | Exit code 0; supervisor sin parada de seguridad |
| CSV original | `cb-e4-e3-20261128T040139Z.csv` |

En el CSV del escenario, 125 de 335 solicitudes fueron errores controlados (37,31 %).
Ese porcentaje no se atribuye a New Relic: APM tambien observa, por ejemplo, los health
checks del balanceador y puede tener una ventana distinta. El CSV confirma el trafico
enviado y sus codigos, no la recepcion del error por New Relic ni el envio del correo.
El endpoint controlado no modifica datos de negocio y las consultas normales siguieron
respondiendo 200 dentro de esta muestra.

Al cesar los errores se inicio E4 con consultas normales durante 180 s. En paralelo,
se restauro `OBS_LAB_ENABLED=false` en CodeBuild y se inicio el pipeline
`51d839ed-87af-4ad3-a6eb-a033174f9585` a las 23:07:09 UTC-5, fijando el mismo SHA.
El cambio de variable del proyecto no apaga por si solo la ruta de la tarea existente:
es necesario verificar la nueva revision desplegada y su respuesta 404 al finalizar.

| Registro E4 | Resultado observado |
| --- | --- |
| Ventana del ejecutor | 27/11/2026 23:07:14 a 23:10:14, Colombia (UTC-5) |
| Ventana UTC | 28/11/2026 04:07:14 a 04:10:14 |
| Trafico de recuperacion | 83 consultas normales, todas HTTP 200; 0 fallos |
| Errores deliberados durante E4 | Ninguno; el proceso E3 ya habia terminado |
| Build de restauracion | `cb-e3-i1-build:9dc4411e-d583-4c2d-b968-642230fcbd96`; 119 pruebas aprobadas, 0 fallidas, 0 errores, 0 omitidas |
| Deployment de restauracion | `d-4C3F3KC2N`; `Succeeded`, sin `errorInformation`; cierre AWS 27/11/2026 23:15:29 UTC-5 |
| Pipeline de restauracion | `51d839ed-87af-4ad3-a6eb-a033174f9585`, `Succeeded`, sobre el mismo SHA bajo prueba |
| Servicio restaurado | `cb-e3-i1-blacklists:19`, `PRIMARY`, `STEADY_STATE`; 1 tarea deseada y 1 ejecutandose, 0 pendientes |
| Banderas de la revision 19 | `NEW_RELIC_ENABLED=true`, `NEW_RELIC_APP_NAME=cb-e4-i1-cloud`, `OBS_LAB_ENABLED=false` |

La recuperacion comprobada por HTTP no demuestra por si sola que New Relic haya cerrado
un incidente. La condicion evalua ventanas y tiene retrasos de ingestion, por lo que
se conserva por separado el instante observado en Issues & Activity y el correo de cierre.

### Evidencia real del ciclo de alerta

Oscar confirmo la recepcion de ambos correos y aporto cinco capturas en la carpeta
privada `Entrega 4/EvidenciasPruebasE3`. Se inspeccionaron sus contenidos:

| Archivo | Resultado observado |
| --- | --- |
| `CorreoIssueAbierta.png` | `Critical priority issue is active`; condicion `cb-e4-i1-errores-5xx`, resultado mayor que 5,0 durante 2 minutos, entidad `cb-e4-i1-cloud`, politica `cb-e4-i1-politica`; pie de correo identifica `cb-e4-i1-workflow` |
| `CorreoIssueCerrada.png` | `Critical priority issue is closed` para la misma condicion y entidad; `Issue duration: 6 minutes` |
| `Summary.png` | El panel muestra el incremento temporal de errores y descenso del Apdex de APM durante el error controlado, seguido de recuperacion; usa un rango amplio de 30 minutos |
| `Issue.png` | `Current state: Closed`; activado el 28/11/2026 a las 04:04 y cerrado a las 04:10, segun la hora visible del panel; duracion 6 minutos, un evento critico y notificacion por correo |
| `Database.png` | PostgreSQL instrumentado; distribucion del tiempo consumido: select 39,90 %, blacklists select 26,22 %, rollback 17,78 %, commit 10,05 % y blacklists insert 6,05 %; rango de 30 minutos, no exclusivo de E1/E2 |

Los correos prueban la entrega real de notificaciones, no solo la configuracion del
destino. La captura adicional del issue confirma las horas de apertura y cierre con
precision de minuto, pero no muestra su ID ni una etiqueta explicita de zona horaria.
Su consulta incluye limites UTC con sufijo `Z`; la correlacion con E3 es compatible
con que el panel muestre UTC. Esa conversion sigue siendo una inferencia: confirmar
la zona del panel antes de transcribir 23:04 y 23:10 del 27/11 como horas Colombia.
No se deducen segundos exactos ni el mecanismo de cierre a partir de la duracion.

En Summary se observa un Apdex que cae aproximadamente a la franja 0,6-0,7 y luego
regresa cerca de 1. Es una lectura visual del Apdex nativo de APM, no un valor exacto
de E1/E2 ni prueba de activacion de la condicion NRQL de Apdex por duracion. El panel
mezcla carga, errores y recuperacion: sus promedios no se trasladan a una sola corrida.
Database confirma que la instrumentacion observa operaciones de lectura, insercion y
transacciones de PostgreSQL. El peso relativo de `rollback` no prueba por si solo un
error de base de datos; se requiere consultar la transaccion o traza correspondiente.
La captura especifica de `ControlledMonitoringError` y sus atributos sigue pendiente.

### Comprobacion funcional final

El 27/11/2026 a las 23:14:31 UTC-5, con la revision 19 ya primaria, se verificaron
HTTP 200 en `/health`, `/version` (version `2.2.0`) y una consulta autenticada de
blacklist. `POST /observability/error` devolvio 404: la ruta de laboratorio quedo
desactivada sin apagar New Relic. El deployment completo su retencion blue/green a
las 23:15:29 UTC-5 y se comprobo una sola tarea estable.

La coleccion completa se repitio entre 23:14:36 y 23:14:39 UTC-5: 7 solicitudes y
7 aserciones aprobadas, 0 fallos, exit code 0; secuencia 200, 201, 200, 409, 200,
400 y 401. Tiempo medio de respuesta: 98 ms (minimo 71 ms, maximo 176 ms).
Se conservaron `postman-final.xml`, `postman-final.log` y `postman-final.json`.

## 5. Evidencias y limites

Los CSV, HTML y JUnit no se versionan. Los originales estan en la carpeta temporal
`cb-e4-evidence-oscar-20261127` y existe una copia privada, ignorada por Git y Docker,
en `.local/entrega4-evidencias-oscar-20261127`. Las capturas de correo permanecen fuera
del repositorio, en la carpeta privada indicada arriba. El JWT privado no se imprime,
no se exporta en reportes y no se versiona. Antes de compartir capturas, ocultar la
licencia, el token, el identificador de cuenta AWS y el correo completo del destino.

El ejecutor no tiene acceso automatizado a la sesion ni a la API de New Relic. Los
valores de Apdex, tiempo interno del servicio, consultas de DB e incidentes solo se
registran como observados cuando se aporta su evidencia. La latencia de Locust incluye
red y ALB y no equivale al tiempo interno de APM ni al de PostgreSQL.

### Capturas a conservar en el informe compartido

| Evidencia | Fuente y estado |
| --- | --- |
| I1-NR-CLOUD / I1-NR-DB iniciales | Capturas aportadas en el chat: entidad cloud, transacciones y PostgreSQL visibles |
| I1-LOAD | HTML de E1/E2 y tablas anteriores, medidos por el ejecutor |
| I1-PERF / I1-APDEX E1 | Pendiente: Summary, Transactions y Databases en 22:40:23-22:43:24 UTC-5 |
| I1-PERF / I1-APDEX E2 | Pendiente: mismas vistas en 22:45:43-22:51:43 UTC-5 |
| I1-ERROR | Summary muestra el aumento de errores; falta el detalle de ControlledMonitoringError y lab.scenario en E3 |
| I1-ALERT | Configuracion, issue cerrado y correos reales comprobados; apertura 04:04 y cierre 04:10 del 28/11 en hora del panel, duracion 6 minutos; falta ID y confirmar zona horaria |
| I1-FINAL | Coleccion final 7/7, salud 200, version 2.2.0 y laboratorio 404; restauracion AWS Succeeded, revision 19 estable |

Para tomar las capturas, usar un rango personalizado con fecha, hora y zona visibles.
Si New Relic muestra UTC, convertir con las ventanas de la tabla de E1/E2; no usar la
hora del equipo como si fuera necesariamente la zona del panel. Esperar la ingestion
antes de concluir que falta una transaccion. En Databases se requiere PostgreSQL.

### Consultas de correlacion

En Query your data, para E1 (duraciones en segundos):

```sql
SELECT count(*), average(duration), percentile(duration, 95),
       rate(count(*), 1 second) AS 'RPS', apdex(duration, t: 0.5),
       percentage(count(*), WHERE numeric(http.statusCode) >= 500) AS '5xx %'
FROM Transaction
WHERE appName = 'cb-e4-i1-cloud' AND transactionType = 'Web'
FACET name
SINCE '2026-11-28 03:40:23 +0000' UNTIL '2026-11-28 03:43:24 +0000'
```

Para E2, conservar el SELECT y cambiar unicamente el rango por:

```sql
SINCE '2026-11-28 03:45:43 +0000' UNTIL '2026-11-28 03:51:43 +0000'
```

DB en E1; repetir con el rango de E2 y contrastar con Databases:

```sql
SELECT average(databaseDuration), percentile(databaseDuration, 95),
       average(databaseCallCount), average(duration)
FROM Transaction
WHERE appName = 'cb-e4-i1-cloud' AND transactionType = 'Web'
FACET name
SINCE '2026-11-28 03:40:23 +0000' UNTIL '2026-11-28 03:43:24 +0000'
```

Si un atributo no existe, comprobarlo con `keyset()` y usar las vistas de APM en lugar
de inventar un cero. La primera consulta usa duracion para Apdex; los errores esperados
de siembra deben distinguirse del Apdex nativo del agente.

### Validacion adicional y limites del equipo local

La suite completa tiene 119 casos aprobados en CodeBuild sobre Linux, confirmados en
el JUnit del despliegue inicial. En Windows se ejecutaron los 24 casos de configuracion
del generador. El intento adicional de instalar toda la aplicacion en otro entorno
temporal Windows fallo al compilar `newrelic==14.3.0` (`DistutilsPlatformError` no
definido en su backend); no se presenta como una corrida de 119 casos local ni se
cambiaron dependencias para eludirlo. Esto no impidio ejecutar Locust ni Newman.

Antes de esta rama, el check de SonarCloud de `425722d` estaba en `failure`, con
`Quality Gate failed`: `new_security_rating=3` (C; requerido A). Se distingue de
CodeBuild y del resultado funcional. Esta rama de evidencia no modifica codigo ni
descarta hallazgos para convertir ese check en verde.
