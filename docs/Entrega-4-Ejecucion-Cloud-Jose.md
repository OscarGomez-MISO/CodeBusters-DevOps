# Entrega 4 - Ejecución cloud de Jose Miguel (Integrante 2)

Registro de las pruebas E1 a E4 del integrante 2 sobre su propia cuenta AWS y su propia
cuenta de New Relic. Solo contiene datos observados. No incluye JWT, licencia de New Relic,
ID de la cuenta AWS ni el correo completo del destino.

## 1. Ambiente y alcance

- SHA bajo prueba: `e6374570355e92dd7827d557732609f252bd651d` (merge del PR #32 en `main`).
- Entidad New Relic: `cb-e4-i2-cloud` (APM, agente Python 14.3.0), cuenta de región US.
- Servicio: `cb-e3-i2-service`, cluster `cb-e3-i2-cluster`, región `us-east-1`, despliegue
  Blue/Green con CodeDeploy.
- Revisión durante E1 y E2: `cb-e3-i2-blacklists:20`, New Relic activo y laboratorio
  desactivado. Fargate con una tarea.
- API versión `2.2.0`; PostgreSQL en RDS.
- Generador: Locust 2.47.0 en un entorno virtual de AWS CloudShell (Python 3.13), en la
  misma región del ALB. Las latencias no incluyen la red desde Colombia.
- Horas del ejecutor en Colombia (UTC-5). Los paneles de New Relic muestran UTC; se confirma
  porque las consultas de los issues llevan límites con sufijo `Z` que coinciden con la hora
  visible del panel.
- No se modificaron workers, CPU, memoria ni número de tareas para forzar degradación.

## 2. Configuración previa

| Objeto | Configuración |
| --- | --- |
| Apdex T de la entidad | 0,5 s (`I2-APDEX-01`) |
| Política | `cb-e4-i2-politica`; un issue por condición y señal |
| Errores 5xx | `cb-e4-i2-errores-5xx`: porcentaje de 5xx mayor que 5 durante al menos 2 minutos (`I2-ALERT-01`) |
| Apdex por duración | `cb-e4-i2-apdex`: `apdex(duration, t: 0.5)`; crítico menor que 0,7 por 3 minutos, warning menor que 0,85 por 3 minutos (`I2-ALERT-02`) |
| Agregación | Ventana de 1 minuto, Event timer de 1 minuto, sin relleno de huecos ni alerta por pérdida de señal |
| Destino | `cb-e4-i2-correo` (correo personal del integrante, verificado por él) |
| Workflow | `cb-e4-i2-workflow`, filtrado por la política propia; notifica Activated, Acknowledged, Closed e Investigating (`I2-ALERT-03`, `I2-ALERT-04`) |

## 3. E1 y E2

Se ejecutó `loadtests/locustfile.py` en modo headless con `--csv-full-history` y reporte
HTML. Además de E2 estándar (máximo 25 usuarios) se corrió una variante extendida con
`LOCUST_E2_MAX_USERS=50`, para buscar el punto de saturación sin cambiar la infraestructura.
Entre corridas hubo 2 minutos de pausa. Fuente de los totales: `*_stats.csv` (fila
Aggregated) de cada corrida; todas terminaron con exit code 0.

| Registro | E1 - Línea base | E2 - Estrés (25 usuarios) | E2 extendido (50 usuarios) |
| --- | --- | --- | --- |
| Run ID | `i2-e1` | `i2-e2` | `i2-e2x` |
| Ventana UTC-5 | 28/11/2026 04:40:53-04:43:54 | 28/11/2026 04:45:54-04:51:55 | 28/11/2026 04:53:55-05:02:56 |
| Ventana UTC | 09:40:53-09:43:54 | 09:45:54-09:51:55 | 09:53:55-10:02:56 |
| Solicitudes / fallos | 657 / 0 | 6154 / 0 | 14873 / 0 |
| Promedio | 10,0 ms | 9,0 ms | 11,8 ms |
| Mediana / p95 / p99 | 8 / 13 / 73 ms | 8 / 13 / 40 ms | 8 / 30 / 96 ms |
| Máximo | 120 ms | 149 ms | 209 ms |
| Throughput promedio | 3,7 solicitudes/s | 17,1 solicitudes/s | 27,5 solicitudes/s |
| CPU máxima de ECS (CloudWatch) | 13,2 % | 44,8 % | 77,5 % |

Detalle por endpoint:

| Endpoint | E1 | E2 | E2 extendido |
| --- | --- | --- | --- |
| `GET /blacklists/<email>` | 457; p95 12 ms | 4331; p95 12 ms | 10374; p95 28 ms |
| `POST /blacklists` | 158; p95 15 ms | 1522; p95 15 ms | 3753; p95 35 ms |
| `GET /health` | 22 | 145 | 389 |
| `GET /version` | 20 | 156 | 357 |

Evidencia: `I2-LOAD-01` (ventanas, tabla agregada y CPU). Los CSV, HTML y logs de Locust
quedan en `~/cb-e4-load` del CloudShell del integrante.

### Hallazgos de carga

- De E1 a E2 el throughput creció unas 4,6 veces y el p95 se mantuvo en 13 ms.
- Con 50 usuarios el throughput creció un 61 % frente a E2, el p95 subió a 30 ms y el p99
  a 96 ms. La CPU de la tarea llegó a 77,5 %, cerca de su límite.
  Es el primer síntoma de saturación, compatible con el 79 % que reportó Fabio.
- No hubo fallos en ninguna corrida ni se abrió la condición de Apdex. El servicio no se
  degradó lo suficiente para afectar a los usuarios con estos perfiles de carga.
- El generador corre dentro de AWS, de modo que la latencia medida por Locust es cercana a
  la del servidor. Con clientes en Colombia se sumaría la latencia de red.

### New Relic en las mismas ventanas

| Vista | E1 (selector 09:40-09:45 UTC) | E2 (selector 09:45-09:52 UTC) | E2 extendido (selector 09:53-10:04 UTC) |
| --- | --- | --- | --- |
| Apdex APM (T=0,5 s) | 1 | 1 | 1 |
| Tiempo web de la aplicación | 5,60 ms | no registrado | 5,20 ms |
| Throughput promedio | 142,8 rpm | 703,57 rpm | 1,34 k rpm |
| Mayor throughput por transacción | 85 rpm | 490 rpm | 924 rpm |
| Tasa de error | 0 % | 0 % | 0 % |
| Transacción con más tiempo | `GET /blacklists/<email>` 58,48 % | `GET /blacklists/<email>` 60,91 % | `GET /blacklists/<email>` 59,34 % |
| Base de datos | PostgreSQL | PostgreSQL | `Postgres select` 32,85 %, `blacklists select` 28,48 % |

Evidencias: `I2-PERF-E1-01..04`, `I2-PERF-E2-01..04` e `I2-PERF-E2X-01..04` (Summary,
Apdex, Transactions y Databases).

## 4. E3 y E4

### Activación del laboratorio

Se cambió solo `OBS_LAB_ENABLED` a `true` en el proyecto CodeBuild `cb-e3-i2-build` y se
ejecutó el pipeline sobre el mismo `main`. No hubo cambios en git.

| Registro | Valor observado |
| --- | --- |
| Pipeline | `8a96abd7-d0b4-47aa-a07d-ca86186659b5`, `Succeeded`; 05:03:01 a 05:12:40 UTC-5 |
| Deployment | `d-OS97WHI2N` |
| Revisión activa | `cb-e3-i2-blacklists:21`, `OBS_LAB_ENABLED=true`, New Relic activo |
| Agente | Mensaje `Reporting to` para `cb-e4-i2-cloud` a las 10:07:10 UTC |
| Comprobación de la ruta | `POST /observability/error` respondió 500 a las 05:12:33 UTC-5 (una ocurrencia adicional al conteo de E3) |

Evidencia: `I2-PIPE-03`.

### E3: error controlado

Se ejecutó `monitoring/scripts/e3-error-controlado.sh 300` desde CloudShell: un error
controlado cada 2 s y una consulta normal autenticada por segundo.

| Registro E3 | Resultado observado |
| --- | --- |
| Ventana | 28/11/2026 05:13:33-05:18:34 UTC-5 (10:13:33-10:18:34 UTC) |
| Errores controlados | 150 respuestas HTTP 500 |
| Tráfico normal paralelo | 294 consultas HTTP 200 |
| Otros códigos | Ninguno; no hubo 429 |
| Salud al cierre | `/health` 200; exit code 0 |
| CSV | `cb-e4-e3-20261128T101333Z.csv` |

Errors Inbox (`I2-ERROR-01..03`): grupo `app.observability:ControlledMonitoringError`,
mensaje `Controlled error for the observability lab`, 151 ocurrencias (150 de E3 más la
comprobación previa). Atributos de la ocurrencia: `lab.scenario=controlled_error`,
`http.statusCode=500`, `request.method=POST`, transacción
`WebTransaction/Flask/POST /observability/error`, origen `/app/app/observability.py`, función
`controlled_error`, línea 49, `error.expected=false`. Se muestra el stack trace de la
ocurrencia. El grupo queda `Unresolved`; es independiente del issue de alertas.

Tasa 5xx frente a la tasa de error del agente (consulta ER3, `I2-ERROR-04` y `I2-ERROR-05`):

| Minuto UTC | Solicitudes | Tasa 5xx | Tasa error agente |
| --- | --- | --- | --- |
| 10:12 | 9 | 11,11 % | 11,11 % |
| 10:13 | 48 | 27,08 % | 27,08 % |
| 10:14 | 99 | 30,30 % | 30,30 % |
| 10:15 | 97 | 30,93 % | 30,93 % |
| 10:16 | 97 | 30,93 % | 30,93 % |
| 10:17 | 95 | 30,53 % | 30,53 % |
| 10:18 | 84 | 21,43 % | 21,43 % |
| 10:19 | 67 | 0 % | 0 % |
| 10:20 | 67 | 0 % | 0 % |

Las dos tasas coinciden porque en esta ventana no hubo respuestas 4xx: el tráfico normal fue
de 200 y los únicos errores fueron los 500 del laboratorio. En Postman o en E2, los 400, 401
y 409 esperados sí elevarían la tasa del agente sin cambiar la tasa 5xx.

### Ciclo de la alerta

| Paso | Hora UTC (panel) | Hora UTC-5 | Evidencia |
| --- | --- | --- | --- |
| Inicio de E3 | 10:13:33 | 05:13:33 | CSV del script |
| Issue crítico abierto: `cb-e4-i2-cloud query result is > 5.0 for 2 minutes on 'cb-e4-i2-errores-5xx'` | 10:15 | 05:15 | `I2-ALERT-05`, `I2-ALERT-06` |
| Notificación de apertura `Sent` por `cb-e4-i2-workflow` | 10:15 | 05:15 | `I2-ALERT-07` |
| Fin de E3 | 10:18:34 | 05:18:34 | CSV del script |
| Issue cerrado; duración 6 minutos, 1 alert event | 10:22 | 05:22 | `I2-ALERT-08`, `I2-ALERT-09` |
| Notificación de cierre `Sent` | 10:22 | 05:22 | `I2-ALERT-10` |

El Issue Notifications Log prueba el envío desde New Relic y el buzón del destino confirma
la recepción (`I2-ALERT-11..14`): remitente `New Relic Incident Intelligence
<noreply@notifications.newrelic.com>`, mismo hilo con el asunto de la condición.

| Correo | Recibido (UTC-5) | Contenido |
| --- | --- | --- |
| Apertura | 05:15 | `Critical priority issue is active`; política `cb-e4-i2-politica`, condición `cb-e4-i2-errores-5xx`, NRQL de la condición, entidad `cb-e4-i2-cloud`; enviado por el workflow `cb-e4-i2-workflow` |
| Cierre | 05:22 | `Critical priority issue is closed`; `Issue duration: 6 minutes`; misma política, condición y workflow |

La condición de Apdex no se abrió. En la ventana 10:12-10:24 UTC el Summary muestra Apdex
APM de 0,79, con un mínimo cercano a 0,69 durante E3, y tasa de error promedio de 21 %
(`I2-E3-01`, `I2-E3-02`). El Apdex de APM cuenta los errores como frustrados; la condición
usa `apdex(duration, t: 0.5)`, que solo mide duración, y las respuestas siguieron por debajo
de 0,5 s. Es el comportamiento esperado de cada métrica.

### E4: recuperación

| Registro E4 | Resultado observado |
| --- | --- |
| Tráfico de recuperación | 05:18:35-05:21:35 UTC-5: 176 consultas normales, todas HTTP 200 |
| Restauración | `OBS_LAB_ENABLED=false` en CodeBuild; pipeline `b51339b4-cfd9-4c33-9cf5-87810c211a44` iniciado a las 05:18:37 UTC-5, `Succeeded` a las 05:27:16 |
| Revisión final | `cb-e3-i2-blacklists:22`, `PRIMARY`, `STEADY_STATE`, 1 tarea; `OBS_LAB_ENABLED=false`, New Relic activo |
| Laboratorio | `POST /observability/error` responde 404 desde las 05:27:15 UTC-5 |
| Salud y versión | `/health` `{"status": "ok"}`; `/version` `2.2.0` |
| Colección funcional | Newman 6.2.2 con `postman/Blacklists.postman_collection.json` contra el ALB propio, 05:30 UTC-5: 7 solicitudes, 7 aserciones, 0 fallos; códigos 200, 201, 200, 409, 200, 400, 401 |

Evidencias: `I2-PIPE-04` e `I2-FINAL-02`.

## 5. Evidencias

Carpeta privada `Entrega 4/capturas` del integrante:

| Código | Archivos |
| --- | --- |
| I2-APDEX | `I2-APDEX-01-apdex-t`, `I2-PERF-E1-02-apdex`, `I2-PERF-E2-02-apdex`, `I2-PERF-E2X-02-apdex` |
| I2-LOAD | `I2-LOAD-01-resumen-locust` |
| I2-PERF | `I2-PERF-E1-01..04`, `I2-PERF-E2-01..04`, `I2-PERF-E2X-01..04` |
| I2-ERROR | `I2-ERROR-01-errors-inbox`, `I2-ERROR-02-detalle-stack`, `I2-ERROR-03-atributos-lab-scenario`, `I2-ERROR-04/05-tasa-5xx-vs-agente` |
| I2-ALERT | `I2-ALERT-01..04` (configuración), `I2-ALERT-05..07` (apertura y notificación), `I2-ALERT-08..10` (cierre y notificaciones), `I2-ALERT-11..14` (correos recibidos) |
| I2-FINAL | `I2-PIPE-03/04` (laboratorio activo e inactivo), `I2-FINAL-02-newman-7-de-7` |

Las capturas de CloudShell se recortan bajo la barra de AWS para no mostrar el ID de la
cuenta; el ARN de la task definition se muestra sin cuenta.
