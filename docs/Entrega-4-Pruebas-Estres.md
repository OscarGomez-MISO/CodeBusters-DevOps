# Entrega 4 - Pruebas de carga y estrés con Locust

Responsable: Fabio Andrés Guaidia Ruiz (Integrante 3). Aplica a las cuatro cuentas:
cada integrante corre la carga contra **su propio ALB** y analiza su entidad
`cb-e4-i<N>-cloud` en New Relic.

> Validación original de Fabio: escenario probado **en local** (Gunicorn + SQLite, sin New Relic,
> 2026-11-27 UTC-5; ver sección 9). La ejecución cloud de Oscar se registra en
> [Entrega-4-Ejecucion-Cloud-Oscar.md](Entrega-4-Ejecucion-Cloud-Oscar.md). Las tablas de
> registro (sección 10) se llenan solo con datos observados, con fecha, hora y zona.
> Ejecución cloud de Fabio (cuenta del Integrante 3, 2026-11-27 UTC-5): sección 11.

Archivos:

| Archivo | Contenido |
| --- | --- |
| `loadtests/locustfile.py` | Usuario Locust, siembra de correos, escenarios E1/E2 y guardia de fallos |
| `loadtests/settings.py` | Variables, planes de escalones y guardia, sin importar Locust (CI lo prueba) |
| `loadtests/requirements.txt` | `locust==2.47.0`, en un entorno **separado** de la aplicación |
| `tests/test_loadtests_settings.py` | Pruebas unitarias de la configuración, que corren en el CI existente |

---

## 1. Alcance

Cubre el análisis de **desempeño de servicios y base de datos (20 %)**, con los escenarios
E1 (línea base) y E2 (estrés) del plan del equipo. Las mismas ventanas sirven para el
Apdex de Juan David (`docs/Entrega-4-Apdex-Errores-Alertas.md`, sección 7, pasos 2 y 3).

- No cambia la aplicación, el `Dockerfile`, el pipeline ni `requirements.txt`.
- La carga **no** corre en cada push ni en CodeBuild. Se lanza a mano, con host y duración
  explícitos.
- E3 (error controlado) y E4 (recuperación) usan el script de Juan David, no este archivo.
- Postman demuestra que el API funciona; Locust aporta la carga y los CSV de rendimiento.
  Uno no reemplaza al otro.

## 2. Qué genera la carga

Cada usuario virtual espera entre 0,5 y 1,5 s entre tareas y elige una con estos pesos:

| Tarea | Peso | Proporción | Solicitud | Éxito esperado |
| --- | --- | --- | --- | --- |
| Consulta a DB | 14 | 70 % | `GET /blacklists/<correo sembrado>` | 200 con `is_blacklisted: true` |
| Creación | 5 | 25 % | `POST /blacklists` con un correo único | 201 |
| Sondeo | 1 | 5 % | `GET /health` o `GET /version`, al azar | 200 |

- **Siembra.** Al empezar, crea `seed-000@example.com` hasta `seed-019@example.com` (20 por
  defecto). Los nombres son fijos: en las siguientes corridas responden 409 y no se crean
  de nuevo, así la tabla no crece con las consultas. Si la siembra recibe algo distinto de
  201 o 409 (por ejemplo, 401 por un JWT incorrecto), la corrida se detiene con código 2.
- **Correos únicos.** `load-<run_id>-<12 hex>@example.com`. Son ficticios y llevan el
  identificador de la corrida, para poder contarlos o borrarlos después (sección 8).
- **Agrupación.** Todas las consultas se reportan como `GET /blacklists/[email]`: el CSV
  tiene una fila por endpoint y no una por correo. New Relic agrupa igual, por la ruta
  `GET /blacklists/<string:email>`.
- **Fallos.** Cualquier código distinto del esperado cuenta como fallo de Locust, también
  los 4xx. En E1/E2 no debería haber 4xx: si aparecen, son un problema del escenario o del
  ambiente y no la carga.
- **Privacidad.** El JWT solo viaja en el encabezado `Authorization`. Locust no lo registra
  y el código nunca lo imprime. Los cuerpos llevan datos ficticios.

## 3. Variables

| Variable | Obligatoria | Por defecto | Uso |
| --- | --- | --- | --- |
| `LOCUST_TOKEN` | Sí | — | JWT del ambiente, **sin** `Bearer ` |
| `LOCUST_SCENARIO` | No | vacío | `e1` o `e2`. Si se define, manda sobre `-u`, `-r` y `-t` |
| `LOCUST_E2_MAX_USERS` | No | `25` | `50` agrega a E2 el escalón opcional de 50 usuarios |
| `LOCUST_RUN_ID` | No | fecha y hora UTC | Identificador de la corrida (`a-z`, `0-9`, `-`, hasta 32) |
| `LOCUST_APP_UUID` | No | UUID del equipo en Postman | `app_uuid` de las creaciones |
| `LOCUST_SEED_EMAILS` | No | `20` | Correos sembrados, de 1 a 200 |
| `LOCUST_MAX_FAILURE_RATIO` | No | `0.05` | Límite del guardia de fallos |
| `LOCUST_GUARD_WINDOW` | No | `60` | Ventana del guardia, en segundos (de 10 a 600) |

Una variable inválida detiene Locust antes de enviar solicitudes, con un mensaje que nunca
incluye el JWT.

## 4. Escenarios

| Escenario | Escalones | Duración | Propósito |
| --- | --- | --- | --- |
| E1 - Línea base | 1 usuario por 60 s, luego 5 usuarios por 120 s; rampa de 1 usuario/s | 3 min | Respuesta, throughput, DB y Apdex antes del estrés |
| E2 - Estrés | 10 usuarios por 180 s, luego 25 por 180 s; rampa de 1 usuario/s | 6 min | Comparar latencia, throughput, errores y Apdex con E1 |
| E2 extendido | Igual que E2 más 50 usuarios por 180 s; rampa de 2 usuarios/s | 9 min | Solo si E2 no muestra degradación y el ambiente lo aguanta |

Los números son puntos de partida del plan, no carga suficiente demostrada. El máximo
permitido es 50 usuarios. El servicio corre con **un worker de Gunicorn** en una tarea
Fargate: no cambiar workers, CPU, memoria ni número de tareas entre E1 y E2 sin anotarlo.
Si E2 no muestra saturación, reportar ese hecho como hallazgo y la limitación; no subir
usuarios sin límite para forzarla.

### Guardia de fallos

Cada 5 s el locustfile calcula la proporción de fallos de los últimos `LOCUST_GUARD_WINDOW`
segundos. Si supera `LOCUST_MAX_FAILURE_RATIO` (5 % durante 60 s, por defecto) con al
menos 20 solicitudes en la ventana, detiene la corrida con código de salida 3. Así se
aplica la regla del plan sin depender de que alguien esté mirando la consola. Igual hay que
detener a mano (`Ctrl+C`) si aparecen timeouts sostenidos.

## 5. Preparación

Desde la raíz del repositorio, en Linux, macOS o CloudShell, con Python 3.11:

```bash
python3.11 -m venv "$HOME/.venvs/cb-e4-locust"
"$HOME/.venvs/cb-e4-locust/bin/pip" install -r loadtests/requirements.txt
"$HOME/.venvs/cb-e4-locust/bin/locust" --version     # locust 2.47.0
```

No instalar Locust en el entorno de la aplicación ni agregarlo a `requirements.txt` o
`requirements-dev.txt`: trae otras dependencias (gevent, Flask para su interfaz web) y no
debe mezclarse con la imagen.

Antes de cargar el ambiente cloud:

1. La entidad `cb-e4-i<N>-cloud` ya recibe tráfico normal (guía AWS, sección 7). No empezar
   el estrés si APM todavía no muestra la entidad.
2. Postman pasa 7/7 contra el ALB propio.
3. `OBS_LAB_ENABLED=false`: la ruta de laboratorio no debe estar activa durante E1/E2.
4. Revisar los límites de ingesta de la cuenta de New Relic y avisar al equipo del horario.
   No apuntar nunca al ALB de otro integrante.

Variables de la sesión (el JWT se pide sin eco y no queda en el historial ni en disco):

```bash
export BASE_URL=http://<alb-propio>
read -rs "LOCUST_TOKEN?JWT: " 2>/dev/null || read -rsp "JWT: " LOCUST_TOKEN; echo
export LOCUST_TOKEN
mkdir -p "$HOME/cb-e4-load"
```

La primera forma de `read` es la de zsh (macOS); la segunda, la de bash (Linux, CloudShell).

## 6. Ejecución

Anotar la hora de inicio y de fin. Locust también la registra en UTC en las líneas
`start_utc` y `stop_utc`.

```bash
L="$HOME/.venvs/cb-e4-locust/bin/locust"

# E1 - línea base (3 min)
LOCUST_SCENARIO=e1 LOCUST_RUN_ID=i<N>-e1 "$L" -f loadtests/locustfile.py --headless \
  --host "$BASE_URL" --csv "$HOME/cb-e4-load/i<N>-e1" --csv-full-history \
  --html "$HOME/cb-e4-load/i<N>-e1.html" 2>&1 | tee "$HOME/cb-e4-load/i<N>-e1.log"

# Pausa de al menos 2 minutos, para que E1 y E2 queden separados en New Relic

# E2 - estrés (6 min; agregar LOCUST_E2_MAX_USERS=50 solo para el escalón extendido)
LOCUST_SCENARIO=e2 LOCUST_RUN_ID=i<N>-e2 "$L" -f loadtests/locustfile.py --headless \
  --host "$BASE_URL" --csv "$HOME/cb-e4-load/i<N>-e2" --csv-full-history \
  --html "$HOME/cb-e4-load/i<N>-e2.html" 2>&1 | tee "$HOME/cb-e4-load/i<N>-e2.log"

grep "exit code" "$HOME/cb-e4-load/i<N>-e2.log"
```

La última línea del log indica cómo terminó: `exit code 0` si fue normal, `2` si la siembra
o el host fallaron y `3` si la detuvo el guardia de fallos.

Para una prueba corta sin escenario (por ejemplo, contra el contenedor local), omitir
`LOCUST_SCENARIO` y pasar `-u`, `-r` y `-t`:

```bash
"$L" -f loadtests/locustfile.py --headless --host http://localhost:5005 -u 5 -r 5 -t 30s
```

Los resultados se guardan en `$HOME/cb-e4-load`, **fuera del repositorio**. No llevan el
JWT, pero sí la URL del ALB: compartirlos solo con el equipo.

### Salidas

| Archivo | Uso en el informe |
| --- | --- |
| `*_stats.csv` | Por endpoint: total, fallos, promedio, mediana, p95, p99 y RPS (`Requests/s`) |
| `*_stats_history.csv` | Serie en el tiempo (usuarios, RPS, percentiles): muestra el efecto de cada escalón |
| `*_failures.csv` | Fallos agrupados por endpoint y mensaje (`HTTP 503`, timeouts, etc.) |
| `*.html` | Reporte con gráficos; sirve para una captura **I<N>-LOAD** |
| `*.log` | Hora UTC de inicio y fin, correos sembrados y motivo de parada |

## 7. Correlación con New Relic

Usar la misma ventana en Locust, New Relic y el informe, con zona explícita, y dar 1 a 2
minutos de margen: el agente envía datos más o menos cada minuto. En **Query your data**,
reemplazar `cb-e4-iN` y la ventana:

```sql
-- P1. Servicios: promedio, p95, throughput y errores por transacción en la ventana
SELECT count(*), average(duration), percentile(duration, 95), rate(count(*), 1 second) AS 'RPS', percentage(count(*), WHERE error IS true) AS 'Error %' FROM Transaction WHERE appName = 'cb-e4-iN-cloud' AND transactionType = 'Web' FACET name SINCE '2026-11-28 10:00:00 -0500' UNTIL '2026-11-28 10:05:00 -0500'

-- P2. Evolución por minuto: muestra el cambio entre escalones
SELECT average(duration), percentile(duration, 95), rate(count(*), 1 minute) FROM Transaction WHERE appName = 'cb-e4-iN-cloud' AND transactionType = 'Web' TIMESERIES 1 minute SINCE '2026-11-28 10:00:00 -0500' UNTIL '2026-11-28 10:10:00 -0500'

-- P3. Base de datos: tiempo y llamadas a DB dentro de cada transacción
SELECT average(databaseDuration), percentile(databaseDuration, 95), average(databaseCallCount), average(duration) FROM Transaction WHERE appName = 'cb-e4-iN-cloud' AND transactionType = 'Web' FACET name SINCE '2026-11-28 10:00:00 -0500' UNTIL '2026-11-28 10:05:00 -0500'
```

Si `databaseDuration` no aparece, revisar con
`SELECT keyset() FROM Transaction WHERE appName = 'cb-e4-iN-cloud' SINCE 1 hour ago` y usar
la vista **Databases** de la entidad. Para el Apdex de la misma ventana, usar la consulta
A3 de la guía de Juan David.

Capturas para **I<N>-PERF**, todas con la entidad y la ventana visibles:

1. **Summary**: tiempo de respuesta, throughput, error rate y Apdex durante E1 y E2.
2. **Transactions**: las rutas más lentas o con más tiempo consumido.
3. **Databases**: operaciones de PostgreSQL (`SELECT`/`INSERT` sobre `blacklists`), con
   tiempo y throughput.
4. Opcional: una traza lenta (**Transaction traces**) si New Relic capturó alguna.

Al interpretar:

- La latencia de Locust es la del **cliente** (red, ALB, contenedor). `duration` en APM es
  el tiempo **dentro** del proceso, y `databaseDuration` es solo la parte de DB. No
  compararlas como si fueran la misma medida: la diferencia es parte del análisis.
- La vista Databases muestra las llamadas a DB **desde la aplicación**. No mide RDS por
  dentro (CPU, conexiones, IOPS); para eso está CloudWatch, que complementa pero no
  reemplaza las capturas de New Relic.
- Si un valor no está disponible (p95 de DB, traza lenta), decirlo. No estimarlo ni
  inventarlo.

## 8. Cierre y limpieza

1. Confirmar en el log que Locust terminó (`exit code 0` o `3`) y que no queda ningún
   proceso corriendo.
2. `curl -s "$BASE_URL/health"` devuelve 200.
3. `unset LOCUST_TOKEN` al terminar la sesión.
4. Los correos `seed-*` y `load-*@example.com` son ficticios y pueden quedarse mientras se
   califica. Para contarlos o borrarlos después, desde un cliente `psql` con acceso a la
   RDS propia:

```sql
SELECT count(*) FROM blacklists WHERE email LIKE 'load-%@example.com';
-- Solo después de la calificación, y solo en la base de datos propia:
DELETE FROM blacklists WHERE email LIKE 'load-%@example.com' OR email LIKE 'seed-%@example.com';
```

5. Los CSV y reportes de `$HOME/cb-e4-load` se conservan como evidencia privada hasta la
   calificación.

## 9. Validación local realizada

2026-11-27, UTC-5, macOS, Python 3.11, `locust==2.47.0`. API con Gunicorn (1 worker) y
SQLite en `127.0.0.1`, sin New Relic. **No representa el desempeño en AWS**: sirve solo
para comprobar el escenario.

| Prueba | Resultado observado |
| --- | --- |
| Corrida manual, 5 usuarios, 20 s | 80 solicitudes, 0 fallos; 20 correos sembrados |
| Segunda corrida | Siembra con 0 creados y 20 existentes (409), sin error |
| Sin `LOCUST_TOKEN` | Se detiene antes de enviar solicitudes |
| JWT inválido | Siembra recibe 401 y la corrida termina con código 2 |
| Sin `--host` | Locust se detiene con código 2 |
| API apagada a los 12 s, ventana del guardia de 10 s | Guardia: 36,7 % de fallos; corrida detenida con código 3 |
| E1 completo | 1 usuario por 60 s y luego 5 por 120 s (180 s); 651 solicitudes, 0 fallos |

Mezcla observada en E1: 470 consultas (72,2 %), 143 creaciones (22,0 %) y 38 sondeos
(5,8 %). La proporción varía en cada corrida porque cada tarea se elige al azar según su
peso.

Pruebas unitarias: `python -m pytest -q --ignore=tests/test_postgres.py` con 119 pruebas
aprobadas, incluidas las 24 de `tests/test_loadtests_settings.py`.

## 10. Registro por integrante

Llenar solo con datos observados. Ventanas con zona explícita.

| Integrante | SHA | E1 inicio–fin | E1 solicitudes / fallos | E1 p95 agregado (Locust) | E2 inicio–fin | E2 usuarios máx. | E2 solicitudes / fallos | E2 p95 agregado (Locust) | Observaciones |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 - Oscar | `425722dc3e1dc7d55f3c6c34ca5e7d5442c3611e` | 27/11/2026 22:40:23-22:43:24 UTC-5 | 596 / 0 | 86 ms | 27/11/2026 22:45:43-22:51:43 UTC-5 | 25 | 5656 / 0 | 97 ms | Fuente: HTML final, contrastado con log; diferencias del CSV periódico declaradas en el registro de Oscar |
| 2 - Jose Miguel | `e6374570355e92dd7827d557732609f252bd651d` | 28/11/2026 04:40:53-04:43:54 UTC-5 | 657 / 0 | 13 ms | 28/11/2026 04:45:54-04:51:55 UTC-5 | 25 | 6154 / 0 | 13 ms | Fuente: `*_stats.csv` (Aggregated), exit code 0; Locust en CloudShell `us-east-1`, sin red desde Colombia. E2 extendido con 50 usuarios, 04:53:55-05:02:56 UTC-5: 14873 / 0, p95 30 ms, p99 96 ms, CPU máx. 77,5 % (E1 13,2 %, E2 44,8 %). New Relic: Apdex 1 y 0 % de error en las tres ventanas. Detalle en [Entrega-4-Ejecucion-Cloud-Jose.md](Entrega-4-Ejecucion-Cloud-Jose.md) |
| 3 - Fabio | `425722dc3e1dc7d55f3c6c34ca5e7d5442c3611e` | 27/11/2026 23:06:52-23:09:49 UTC-5 | 593 / 0 | 110 ms | 27/11/2026 23:14:43-23:20:40 UTC-5 | 25 | 5451 / 0 | 260 ms | Cliente: Mac en Colombia hacia ALB us-east-1 (~95 ms de base). E2 extendido a 50 usuarios 23:40:05-23:49:01: 13208 / 0, p95 260 ms, ~43 rps. Detalle en la sección 11 |
| 4 - Juan David | | | | | | | | | |

Evidencias por integrante:

| Código | Contenido mínimo |
| --- | --- |
| I<N>-LOAD | Comando o escenario, inicio/fin, reporte HTML o tabla `*_stats.csv` y referencia a los CSV |
| I<N>-PERF | New Relic: Summary, Transactions y Databases en la misma ventana de E1 y E2 |

No mostrar el JWT, la licencia de New Relic ni el ID de la cuenta AWS.

## 11. Ejecución cloud del Integrante 3

Cuenta AWS del Integrante 3 (`us-east-1`) y entidad `cb-e4-i3-cloud` en su cuenta de New
Relic (región US). Commit `425722dc` (merge del PR #25), ejecución de pipeline `76a09c4c`,
despliegue `d-7FXMNK92N`, task definition `cb-e3-i3-blacklists:16`: 0,25 vCPU, 512 MB y
1 worker síncrono de Gunicorn. Locust corrió desde un Mac en Colombia. Postman: 7/7 antes
de la carga.

Nota del despliegue: el primer intento de Deploy de `76a09c4c` falló con *Another deployment
to the AWS CodeDeploy deployment group ... is already in progress*. Había otro despliegue en
curso de una ejecución detenida con `--abandon` cuando ya estaba en Deploy. Se reintentó la
etapa y terminó en `Succeeded`. Detener una ejecución en Deploy no cancela su despliegue en
CodeDeploy.

| Escalón | Ventana UTC-5 | rps (mediana) | p50 / p95 cliente (Locust) | App prom. (NR) | DB prom. (NR) | Apdex (NRQL, T = 0,5) | CPU tarea (máx.) | p95 ALB→tarea |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| E1 (1 → 5 usuarios) | 23:06:52-23:09:49 | 3,3 (promedio) | 97 / 110 ms | 5,2 ms GET, 8,0 ms POST | 2,6 ms GET, 4,5 ms POST | 1,00 | 13 % | — |
| E2, 10 usuarios | 23:14:43-23:17:40 | 9,0 | 97 / 100 ms | ~5 ms | ~2,5 ms | 1,00 | 20 % | — |
| E2, 25 usuarios | 23:17:40-23:20:40 | 22,2 | 120 / 190 ms | 4,8 ms GET, 8,4 ms POST | 2,5 ms GET, 5,1 ms POST | 1,00 | 40 % | — |
| E2x, 10 usuarios | 23:40:05-23:43:01 | 9,2 | 99 / 110 ms | ~7 ms | ~4 ms | 1,00 (Summary, ventana E2x) | 22 % | 14-18 ms |
| E2x, 25 usuarios | 23:43:01-23:46:01 | 22,7 | 98 / 110 ms | ~7 ms | ~4 ms | 1,00 (Summary, ventana E2x) | 45 % | 22-23 ms |
| E2x, 50 usuarios | 23:46:01-23:49:01 | 43,2 | 140 / 260 ms | ~8 ms | ~5 ms | 1,00 (Summary, ventana E2x) | 79 % | 109-120 ms |

Fuentes: Locust `*_stats.csv` y `*_stats_history.csv` (p50/p95 como mediana de la serie
por escalón, sin la rampa), New Relic (`FROM Transaction` facetado por `name`, y
`FROM Metric` para el throughput), CloudWatch `AWS/ECS CPUUtilization` y
`AWS/ApplicationELB TargetResponseTime` p95. En las tres corridas, 0 fallos y el guardia
de fallos no se activó. Memoria estable en 16-17 %.

Hallazgos:

1. **La app y PostgreSQL no se degradaron.** Con hasta 43 rps, el tiempo dentro de la app
   (5-8 ms) y el de DB (2,5-5 ms) casi no cambiaron, y el Apdex se mantuvo en 1,00.
2. **El límite está en el cómputo de la tarea.** A 50 usuarios la CPU llegó a 79 % de
   0,25 vCPU y el p95 del ALB hacia la tarea pasó de ~23 a ~110 ms. APM no ve ese tiempo
   porque es espera antes de que el único worker síncrono tome la solicitud. Opciones a
   evaluar: más workers o hilos de Gunicorn, más vCPU o una segunda tarea. No se aplicaron
   en esta entrega.
3. **La latencia del cliente incluye la red.** Unos 95 ms de base desde Colombia hasta
   `us-east-1`. No se compara directamente con `duration` de APM.
4. **New Relic muestrea los eventos `Transaction`.** A 50 usuarios la serie de eventos se
   quedó en ~20 rps (límite por defecto del agente), mientras que `FROM Metric
   apm.service.transaction.duration` mostró los ~43 rps reales. Para throughput bajo carga
   alta conviene usar métricas; los percentiles de eventos siguen siendo una muestra.
5. **New Relic cuenta más solicitudes que Locust.** Las diferencias vienen de los health
   checks del ALB (`GET /health`) y de la siembra (`POST /blacklists`).
6. New Relic marca la RDS como *uninstrumented database*. Es lo esperado: APM mide la DB
   desde la aplicación y no instala un agente en RDS.

Evidencias, fuera del repositorio porque contienen la URL del ALB o datos de la cuenta:
`I3-NR-LOCAL`, `I3-NR-CLOUD`, `I3-PIPE`, `I3-LOAD`, `I3-PERF-E1`, `I3-PERF-E2` e
`I3-PERF-E2X`, junto con los CSV y reportes HTML de Locust. E3/E4 (errores y alertas) se
ejecutan aparte con la guía de Apdex, errores y alertas.

## Fuentes oficiales

- [Opciones de configuración de Locust](https://docs.locust.io/en/stable/configuration.html)
- [Formas de carga personalizadas (LoadTestShape)](https://docs.locust.io/en/stable/custom-load-shape.html)
- [Resultados en CSV](https://docs.locust.io/en/stable/retrieving-stats.html)
- [Databases en APM](https://docs.newrelic.com/docs/apm/apm-ui-pages/monitoring/databases-page-view-operations-throughput-response-time/)
- [Atributos del evento Transaction](https://docs.newrelic.com/attribute-dictionary/?event=Transaction)
