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

### New Relic: evidencia acotada de E1

Se inspeccionaron las capturas nuevas de la carpeta privada
`Entrega 4/EvidenciasPruebasE1`: `340 - 343.png` (Summary),
`Transactions 340 - 343.png` y `Database 340 - 343.png`.
Las tres muestran la entidad `cb-e4-i1-cloud` y el selector
`Nov 28, 03:40 - Nov 28, 03:43`, a diferencia de las capturas iniciales de 30 minutos.
El selector visible no expone segundos ni zona horaria; se registra el rango mostrado,
sin afirmar que la imagen certifica por si sola los limites exactos del ejecutor
03:40:23-03:43:24 UTC. Los archivos antiguos `Summary.png`, `Transaction.png` y
`Database.png` no son la fuente de estos valores.

| Vista / metrica | Valor observado en el rango seleccionado |
| --- | --- |
| Summary: tiempo promedio del servicio | 5,09 ms |
| Summary: Apdex nativo de APM | 1,00; T=0,5 s |
| Summary: throughput promedio | 174 solicitudes/min |
| Summary: tasa de errores | 0 % |
| Transactions: mayor tiempo promedio entre transacciones | 7,17 ms; coincide con POST /blacklists en la tabla de Summary |
| Transactions: mayor tasa de errores entre transacciones | 0 % |
| Transactions: mayor throughput entre transacciones | 106 solicitudes/min; no equivale al throughput total de Summary |
| Transactions: participacion del tiempo consumido | GET /blacklists: 53,96 %; POST /blacklists: 41,31 %; GET /health: 4,30 %; GET /version: 0,43 % |
| Databases: participacion del tiempo consumido | Postgres select: 31,57 %; Postgres blacklists select: 31,55 %; rollback: 15,86 %; commit: 11,98 %; blacklists insert: 9,05 % |

En el rango seleccionado de E1, el servicio presento Apdex 1,00 y tasa de errores
0 %, con tiempo interno promedio de 5,09 ms. Las operaciones de lectura de PostgreSQL
representaron aproximadamente el 63,12 % del tiempo consumido de DB mostrado.
Estas participaciones son de tiempo, no de cantidad de solicitudes ni de fallos;
el valor de rollback no demuestra por si solo un error de base de datos.

Los 5,09 ms internos no contradicen los 80,53 ms medidos por Locust: observan limites
distintos y los rangos de las capturas solo se muestran con precision de minuto.
El throughput de APM tampoco se presenta como un recuento identico al del ejecutor.
Las capturas respaldan el comportamiento estable de E1. La comparacion con E2 se
presenta a continuacion, manteniendo separados los rangos y fuentes.

### New Relic: evidencia acotada de E2 y comparacion

Se inspeccionaron `Summary.png`, `Transactions.png` y `Databases.png` de la carpeta
privada `Entrega 4/EvidenciasPruebasE2`. Las tres muestran `cb-e4-i1-cloud` y el
selector `Nov 28, 03:45 - Nov 28, 03:52`. Este rango acotado abarca la corrida E2
registrada por el ejecutor; no se afirma identidad exacta de segundos o zona horaria
a partir del selector, que solo muestra minutos y no expone la zona.

| Vista / metrica | Valor observado en el rango seleccionado |
| --- | --- |
| Summary: tiempo promedio del servicio | 5,04 ms |
| Summary: Apdex nativo de APM | 1,00; T=0,5 s |
| Summary: throughput promedio | 791,86 solicitudes/min |
| Summary: tasa global de errores | 0,018 % |
| Summary: tiempos promedio por transaccion | POST /blacklists: 7,68 ms; GET /blacklists: 4,33 ms; GET /health: 3,48 ms; GET /version: 0,85 ms |
| Summary: otra transaccion observada | `POST <unmatched>`: tasa de errores 100 %, tiempo promedio 1,57 ms; su codigo HTTP y causa no se ven en la captura |
| Transactions: mayor tiempo promedio entre transacciones | 7,68 ms |
| Transactions: mayor throughput entre transacciones | 554 solicitudes/min; no equivale al throughput total de Summary |
| Transactions: mayor tasa de errores entre transacciones | 100 %; es el maximo de un tipo de transaccion, no la tasa global del servicio |
| Transactions: participacion del tiempo consumido | GET /blacklists: 60,11 %; POST /blacklists: 37,21 %; GET /health: 2,30 %; GET /version: 0,37 %; `POST <unmatched>`: 0,0056 %; `GET <unmatched>`: 0,0038 % |
| Databases: participacion del tiempo consumido | Postgres select: 37,66 %; Postgres blacklists select: 26,06 %; rollback: 16,08 %; commit: 12,53 %; blacklists insert: 7,68 % |

| Metrica de Summary | E1 | E2 |
| --- | --- | --- |
| Tiempo interno promedio | 5,09 ms | 5,04 ms |
| Apdex mostrado, T=0,5 s | 1,00 | 1,00 |
| Throughput promedio | 174 solicitudes/min | 791,86 solicitudes/min |
| Tasa global de errores | 0 % | 0,018 % |

El throughput de APM crecio aproximadamente 4,55 veces entre los rangos seleccionados,
mientras el tiempo interno promedio se mantuvo alrededor de 5 ms y el Apdex mostrado
en 1,00. En PostgreSQL, las lecturas representaron aproximadamente 63,12 % del tiempo
consumido en E1 y 63,72 % en E2. El tiempo consumido y el volumen de operaciones
aumentan visualmente con la carga, pero las capturas no demuestran un cuello de
botella de DB ni proporcionan un p95 exacto por consulta.

No se declara que E2 tuvo cero errores en New Relic: Summary muestra 0,018 % global
y una transaccion `POST <unmatched>` con 100 % de errores dentro de su propio grupo.
La causa y el codigo HTTP requieren consultar el detalle de esa transaccion; no se
atribuyen automaticamente a la siembra, autenticacion, un error 5xx ni al escenario E3,
que ocurrio despues. Locust registro cero fallos de sus usuarios virtuales, una fuente
y un conjunto de solicitudes distintos. Tampoco se equipara el maximo por transaccion
de Transactions con la tasa global ni se confunde la participacion del tiempo con
el porcentaje de solicitudes.

Texto breve para el informe:

> Al aumentar la carga de E1 a E2, New Relic mostro un incremento del throughput
> promedio de 174 a 791,86 solicitudes/min, con tiempo interno cercano a 5 ms y
> Apdex de 1,00 en ambos rangos seleccionados. Las lecturas concentraron cerca del
> 63 % del tiempo consumido en PostgreSQL, sin evidencia de saturacion en estas
> capturas. Aunque Locust no registro fallos, APM mostro una tasa global de errores
> de 0,018 % en E2 y una transaccion POST no asociada a una ruta reconocida, cuyo
> diagnostico requiere revisar su detalle.

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

Oscar confirmo la recepcion de ambos correos y actualizo las capturas en la carpeta
privada `Entrega 4/EvidenciasPruebasE3`. Se inspeccionaron los ocho archivos actuales,
incluyendo las vistas acotadas y las dos partes del detalle del incidente:

| Archivo | Resultado observado |
| --- | --- |
| `CorreoIssueAbierta.png` | `Critical priority issue is active`; condicion `cb-e4-i1-errores-5xx`, resultado mayor que 5,0 durante 2 minutos, entidad `cb-e4-i1-cloud`, politica `cb-e4-i1-politica`; pie de correo identifica `cb-e4-i1-workflow` |
| `CorreoIssueCerrada.png` | `Critical priority issue is closed` para la misma condicion y entidad; `Issue duration: 6 minutes` |
| `Summary.png` | Selector 28/11 04:04-04:12; tiempo interno promedio 5,24 ms, Apdex 0,80 con T=0,5 s, throughput 41 solicitudes/min y errores globales 20,43 %; actividad del issue activado a las 04:04 y cerrado a las 04:10 en hora del panel |
| `Issue.png` | `Current state: Closed`; activado el 28/11/2026 a las 04:04 y cerrado a las 04:10, segun la hora visible del panel; duracion 6 minutos, un evento critico y notificacion por correo |
| `Transactions.png` | Mismo rango 04:04-04:12; participacion del tiempo consumido: GET /blacklists 75,10 %, GET /health 16,55 % y POST /observability/error 8,35 %; mayor tiempo promedio 6,59 ms y mayor throughput por transaccion 25 solicitudes/min |
| `Databases.png` | Mismo rango 04:04-04:12; participacion del tiempo consumido de PostgreSQL: select 44,60 %, blacklists select 32,17 % y rollback 23,23 % |
| `Error-P1.png` | Detalle del issue critico cerrado y consulta NRQL que cuenta HTTP 5xx; umbral mayor que 5 durante 2 minutos y serie con aumento temporal de errores, seguido de retorno a la linea base |
| `Error-P2.png` | Continuacion del issue: cronologia con 1 alert event y 1 resolved, etiquetas de la condicion, agente 14.3.0 y mapa de dependencias de la aplicacion con la base de datos |

Los correos prueban la entrega real de notificaciones, no solo la configuracion del
destino. La captura adicional del issue confirma las horas de apertura y cierre con
precision de minuto, pero no muestra su ID ni una etiqueta explicita de zona horaria.
Su consulta incluye limites UTC con sufijo `Z`; la correlacion con E3 es compatible
con que el panel muestre UTC. Esa conversion sigue siendo una inferencia: confirmar
la zona del panel antes de transcribir 23:04 y 23:10 del 27/11 como horas Colombia.
No se deducen segundos exactos ni el mecanismo de cierre a partir de la duracion.

### E3: observacion del servicio y recuperacion

El rango nuevo 28/11 04:04-04:12 del panel incluye parte del error controlado y parte
de la recuperacion; no cubre los cinco minutos completos del script E3, cuyo inicio
fue 04:01:40 UTC, ni representa una corrida E4 aislada. El selector no expone segundos
ni una etiqueta de zona horaria. Las metricas siguientes se atribuyen a ese rango
visible, no a toda la ejecucion del script.

Summary muestra un Apdex de 0,80 para el rango seleccionado. La serie comienza cerca
de 0,6-0,7 y luego regresa cerca de 1, mientras la serie de errores desciende desde
aproximadamente el 30 % hasta la linea base. Son lecturas visuales de la evolucion,
distintas del 20,43 % global y del Apdex 0,80 que figuran en los indicadores.

La tabla de Summary identifica `POST /observability/error` con 100 % de errores y
tiempo promedio de 2,14 ms. Las consultas normales `GET /blacklists` y `GET /health`
registran errores 0 % y tiempos promedio de 6,59 ms y 4,38 ms, respectivamente.
Esto respalda la separacion entre la ruta de fallo deliberado y las rutas normales;
no se presenta el 100 % de la ruta controlada como indisponibilidad total del API.
El Apdex nativo de APM no se equipara a la condicion NRQL basada solo en duracion,
y las capturas no prueban que esta ultima haya abierto otro incidente.

En DB se observan lecturas y rollback; las dos categorias de lectura suman 76,77 %
del tiempo consumido mostrado. No se infiere que el rollback sea la causa de los
errores HTTP ni que exista saturacion de PostgreSQL. El error deliberado se origina
en la ruta de laboratorio y no requiere una falla de DB.

`Error-P1.png` y `Error-P2.png` son dos partes del detalle del issue de alertas,
no del error de aplicacion en Errors Inbox. Confirman la condicion, su cronologia y
la resolucion del evento, pero no muestran el nombre `ControlledMonitoringError`,
su mensaje, stack trace ni el atributo `lab.scenario=controlled_error`.
El codigo de `app/observability.py` define esa excepcion y ese atributo; esa
configuracion no sustituye una captura que demuestre su recepcion en New Relic.
Se conserva pendiente unicamente ese detalle especifico de la excepcion dentro de
I1-ERROR; la transaccion controlada y el ciclo del incidente ya estan respaldados.
Las etiquetas de cuenta, politica y condicion en la segunda imagen no se confunden
con el identificador del issue; este ultimo sigue sin verse.

### Resumen de las vistas APM de E1, E2 y E3/recuperacion

| Metrica de Summary | E1 | E2 | E3 y recuperacion |
| --- | --- | --- | --- |
| Selector del panel, 28/11 | 03:40-03:43 | 03:45-03:52 | 04:04-04:12 |
| Tiempo interno promedio | 5,09 ms | 5,04 ms | 5,24 ms |
| Apdex nativo mostrado, T=0,5 s | 1,00 | 1,00 | 0,80 |
| Throughput promedio | 174 solicitudes/min | 791,86 solicitudes/min | 41 solicitudes/min |
| Errores globales | 0 % | 0,018 % | 20,43 % |
| Proposito | Linea base | Carga creciente | Fallo deliberado y observacion de recuperacion |

El menor throughput de E3 no se interpreta como perdida de capacidad: se uso otro
perfil de trafico y el rango incluye la detencion de los errores y recuperacion.
La tasa de 20,43 % de APM tampoco se equipara al 37,31 % del CSV del script, porque
sus ventanas y conjuntos de solicitudes son distintos.

Texto breve para el informe:

> En el rango 04:04-04:12 del panel, que incluye parte de E3 y su recuperacion,
> New Relic mostro Apdex de 0,80 y errores globales de 20,43 %. La ruta de error
> deliberado registro 100 % de errores, mientras las consultas de blacklist y salud
> mantuvieron 0 % de errores. El issue critico paso de activo a cerrado, con duracion
> de seis minutos y correos reales de apertura y cierre; las graficas muestran el
> descenso de errores y la recuperacion del Apdex al cesar el fallo controlado.

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
| I1-PERF / I1-APDEX E1 | Tres capturas acotadas inspeccionadas en EvidenciasPruebasE1: selector 28/11 03:40-03:43; Summary 5,09 ms, Apdex 1,00 y errores 0 %; Transactions y PostgreSQL documentados en la seccion 3. La imagen no expone segundos ni zona |
| I1-PERF / I1-APDEX E2 | Summary, Transactions y Databases inspeccionados en EvidenciasPruebasE2: selector 28/11 03:45-03:52; 5,04 ms, Apdex 1,00, 791,86 solicitudes/min y errores globales 0,018 %; comparacion y limites en la seccion 3 |
| I1-ERROR | Vistas acotadas E3/recuperacion inspeccionadas: errores globales 20,43 %; POST /observability/error con errores 100 % y rutas normales con 0 %. Las dos partes del issue no muestran la excepcion ControlledMonitoringError ni lab.scenario: ese detalle sigue pendiente |
| I1-ALERT | Configuracion, issue cerrado, cronologia de 1 evento resuelto y correos reales comprobados; apertura 04:04 y cierre 04:10 del 28/11 en hora del panel, duracion 6 minutos; falta ID del issue y confirmar zona horaria |
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
