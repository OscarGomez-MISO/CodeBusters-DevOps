# Entrega 4 - Apdex, errores y alertas en New Relic

Responsable: Juan David Cuevas Perdomo (Integrante 4). Aplica a las cuatro cuentas:
cada integrante la ejecuta sobre su entidad `cb-e4-i<N>-cloud` (y `-local` cuando se indique).

> Estado: guía y configuración propuestas. El registro de la ejecución cloud de Oscar
> se conserva en [Entrega-4-Ejecucion-Cloud-Oscar.md](Entrega-4-Ejecucion-Cloud-Oscar.md),
> distinguiendo mediciones realizadas y evidencias aún pendientes de New Relic.
> Los valores de las tablas de registro (sección 8) se llenan solo con datos reales, con
> fecha, hora y zona. No presentar los ejemplos de esta guía como configuración aplicada.

Archivo de apoyo: `monitoring/scripts/e3-error-controlado.sh` (escenario E3 acotado: errores
controlados más tráfico normal). Las consultas NRQL están en la sección 6.

---

## 1. Alcance

Cubre los análisis de **Apdex (10 %)**, **registro de errores (10 %)** y **alertas (10 %)**
del enunciado, y los escenarios E3 (error controlado) y E4 (recuperación) del plan del equipo.

- Se usa la instrumentación ya integrada por Oscar (`docs/Entrega-4-NewRelic-Local.md`) y el
  despliegue por pipeline de Jose Miguel (`docs/Entrega-4-NewRelic-AWS.md`). No cambia
  código de la aplicación ni el pipeline.
- La carga (E1/E2) es de Fabio. Aquí solo se indica qué mirar en New Relic durante esas
  ventanas.
- La configuración de New Relic (T, política, condiciones, destino, workflow) vive en cada
  cuenta. Este documento permite repetirla igual en las cuatro.

## 2. Prerrequisitos

1. Entidad cloud `cb-e4-i<N>-cloud` recibiendo tráfico de Fargate (guía AWS, sección 7).
2. Postman 7/7 contra el ALB propio y el JWT del ambiente a mano (no se guarda en el repo).
3. Acceso de administrador a la cuenta propia de New Relic (para Alerts y Settings).
4. Para E3: poder cambiar `OBS_LAB_ENABLED` en el proyecto CodeBuild propio (guía AWS,
   sección 8). Cada cambio es un despliegue Blue/Green completo de unos 9 minutos.

En los comandos y consultas, reemplazar `cb-e4-iN` por el prefijo propio (`cb-e4-i4`, etc.).

---

## 3. Apdex

### 3.1 Umbral T del equipo

**T = 0,5 s**, común para las cuatro entidades. Con ese valor:

| Categoría | Condición | Peso en el índice |
| --- | --- | --- |
| Satisfecha | duración ≤ T (0,5 s) | 1 |
| Tolerable | T < duración ≤ 4T (2 s) | 0,5 |
| Frustrada | duración > 4T, o transacción con error (en el Apdex de APM) | 0 |

`Apdex = (satisfechas + tolerables / 2) / total`.

Justificación: el servicio es un API interno de consulta y registro en una lista negra; una
respuesta de medio segundo es aceptable para otro servicio que lo invoca de forma síncrona.
0,5 s es además el valor por defecto de New Relic, de modo que no hay que ajustar los
umbrales de las vistas estándar. **El valor se confirma con la línea base E1**: si en E1 el
p95 ya supera 0,5 s sin carga, documentarlo y decidir en equipo *antes* de E2. No cambiar T
después de ver resultados para simular degradación.

### 3.2 Fijarlo en New Relic

1. **APM & services** → `cb-e4-iN-cloud` → **Settings** → **Application**.
2. **Apdex T** = `0.5` → **Save**. Repetir en `cb-e4-iN-local` si se compara con local.
3. Evidencia: captura de ese ajuste con la entidad visible.

### 3.3 Dónde se observa

- **Summary** de la entidad: gráfico *Apdex score* con el T usado.
- **Transactions**: Apdex por transacción (ruta parametrizada, por ejemplo
  `GET /blacklists/<string:email>`), útil para ver qué endpoint degrada.
- **Query your data**: consultas A1 a A3 de la sección 6. A2 da la distribución
  satisfechas / tolerables / frustradas; A3 compara E1 con E2.

Puntos que el análisis debe dejar claros:

- Apdex es un índice entre 0 y 1, no una latencia media ni una encuesta a usuarios reales.
- `apdex(duration, t: 0.5)` de NRQL clasifica solo por duración; el Apdex de la vista
  Summary también cuenta las transacciones con error como frustradas. Si difieren, se
  reportan ambos con su fuente.
- Por el hallazgo de la sección 4.1, los 4xx esperados pueden contar como error y bajar el
  Apdex de APM sin que el servicio sea lento. Indicar qué configuración estaba vigente.
- Comparar ventanas con el mismo T, la misma entidad y la misma carga declarada.

---

## 4. Registro de errores

### 4.1 Hallazgo de partida: 4xx esperados contados como error

En la validación cloud de Jose Miguel, el agente contó como error las respuestas 400, 401 y
409 (configuración por defecto: solo ignora 404). Una transacción llegó a 55,56 % de error
con tráfico de prueba normal. Eso contamina la tasa de error, el Apdex de APM y cualquier
alerta basada en `error IS true`.

Opciones, en orden de preferencia:

| Opción | Cambio | Efecto | Estado |
| --- | --- | --- | --- |
| A | En `newrelic.ini` (archivo de Oscar): `error_collector.expected_status_codes = 400 401 409 415 422` | Siguen visibles en Errors Inbox como *expected*, pero no suben la tasa de error ni bajan el Apdex. Igual en las cuatro cuentas por el mismo commit | **Propuesta, pendiente de acordar con Oscar** y de verificar con datos tras desplegar |
| B | Configuración del lado del servidor en la UI (Settings → Application → Error collection) | Mismo efecto, pero manual en cada cuenta y sobrescribe el archivo local | Alternativa si A no se aprueba |
| C | No tocar el agente; filtrar por código HTTP en las consultas | Las alertas funcionan; las vistas estándar siguen mostrando la tasa contaminada | **Lo que ya hacen las condiciones de la sección 5** |

Las condiciones de alerta usan `http.statusCode >= 500`, así que funcionan con cualquiera
de las tres opciones. Si se adopta A, registrar el SHA desde el que rige y no mezclar en el
informe ventanas anteriores y posteriores sin aclararlo.

### 4.2 Error controlado (ya implementado por Oscar)

`POST /observability/error` existe solo con `OBS_LAB_ENABLED=true` (404 en otro caso).
Exige JWT, lanza `ControlledMonitoringError` dentro de la solicitud, lo reporta con
`notice_error` y el atributo `lab.scenario=controlled_error`, y responde 500 sin tocar datos.
Acepta un error cada 2 s por proceso (Gunicorn usa 1 worker); las llamadas intermedias
responden 429.

### 4.3 Qué cuenta como evidencia

- **Sí**: en **Errors Inbox** o **Events → Errors** de la entidad cloud, la clase
  `...:ControlledMonitoringError`, la transacción `POST /observability/error`, el atributo
  `lab.scenario` y la traza o stack trace, dentro de la ventana de E3
  (consulta ER1 de la sección 6).
- **No basta**: un 500 en Postman o curl, un log en CloudWatch, o los 400/401/409 esperados.
  Tampoco asumir que un 502 del ALB produjo una traza dentro de Flask.
- Mostrar la tasa 5xx frente a la tasa de error del agente (consultas ER2 y ER3) para explicar
  la diferencia descrita en 4.1.

---

## 5. Alertas

### 5.1 Objetos que se crean en cada cuenta

| Objeto | Nombre | Dónde |
| --- | --- | --- |
| Política | `cb-e4-iN-politica`, *Issue creation preference*: **One issue per condition and signal** | Alerts → Alert policies |
| Condición 1 | `cb-e4-iN-errores-5xx` | Dentro de la política |
| Condición 2 | `cb-e4-iN-apdex` | Dentro de la política |
| Destino | `cb-e4-iN-correo` (correo personal del integrante) | Alerts → Destinations → Email |
| Workflow | `cb-e4-iN-workflow` | Alerts → Workflows |

### 5.2 Condiciones (NRQL)

Consultas AL1 y AL2 de la sección 6. Parámetros propuestos:

| Parámetro | `errores-5xx` | `apdex` |
| --- | --- | --- |
| Consulta | `percentage(count(*), WHERE numeric(http.statusCode) >= 500)` sobre `Transaction` web de la entidad | `apdex(duration, t: 0.5)` sobre `Transaction` web de la entidad |
| Ventana de agregación | 1 minuto | 1 minuto |
| Método de streaming | *Event timer*, 60 s (tráfico bajo e irregular) | *Event timer*, 60 s |
| Umbral Critical | **por encima de 5** durante al menos **2 minutos** | **por debajo de 0,7** durante al menos **3 minutos** |
| Umbral Warning | (no) | por debajo de 0,85 durante 3 minutos |
| Pérdida de señal | Desactivada: sin tráfico no hay tasa que evaluar | Desactivada |
| Relleno de huecos | Ninguno | Ninguno |
| Escenario que la dispara | E3 (errores controlados) | E2, solo si el estrés realmente degrada la respuesta |

Notas:

- Antes de guardar, comprobar en **Query your data** que la consulta devuelve valores y que
  el atributo `http.statusCode` existe (`SELECT keyset() FROM Transaction ...`). Si en la
  cuenta se llama distinto, ajustar la consulta y anotarlo.
- Condiciones sin `FACET`: una señal por entidad. Con tráfico de un solo integrante, un
  umbral de 5 % se supera con pocos errores; por eso E3 mantiene tráfico normal en paralelo.
- Si E2 no baja el Apdex de 0,7, la condición 2 no se abre. Se reporta así; **no** se baja
  el umbral ni T para forzarla. La alerta que debe completar el ciclo es la de errores.
- Si el plan gratuito limita alguna capacidad (condiciones, destinos, retención), anotar la
  restricción y acordar una alternativa; no contratar un plan de pago.

### 5.3 Destino y workflow

1. **Destinations** → **Email** → correo propio → **Send test notification**. Ese correo de
   prueba **no** es evidencia del incidente; solo valida el destino.
2. **Workflows** → **Add a workflow** → nombre `cb-e4-iN-workflow`.
   - Filtro: `policyName` = `cb-e4-iN-politica` (o *Policy* en el filtro básico).
   - Notificar al destino `cb-e4-iN-correo`.
   - En la configuración del canal, notificar cuando el issue esté **activado** y **cerrado**,
     para tener evidencia de la recuperación.
3. **Test workflow** solo para validar la ruta; separarlo de la notificación real de E3.

### 5.4 Ciclo que se debe evidenciar

Señal → violación del umbral → **issue/incidente abierto** → **correo del workflow** →
retiro del fallo → **cierre del incidente** → correo de cierre. Registrar la hora de cada
paso (sección 8). La consulta AL3 de la sección 6 lista los eventos de la
política.

---

## 6. Consultas NRQL

Se pegan en **Query your data** de la cuenta propia. Reemplazar `cb-e4-iN` por el prefijo
propio y ajustar `SINCE`/`UNTIL` a la ventana exacta del escenario, con zona explícita
(por ejemplo `SINCE '2026-11-25 10:00:00 -0500' UNTIL '2026-11-25 10:10:00 -0500'`).
Antes de usar `http.statusCode`, confirmar que el atributo existe:
`SELECT keyset() FROM Transaction WHERE appName = 'cb-e4-iN-cloud' SINCE 1 hour ago`.

**Apdex**

```sql
-- A1. Apdex por minuto (T = 0,5 s)
SELECT apdex(duration, t: 0.5) FROM Transaction WHERE appName = 'cb-e4-iN-cloud' AND transactionType = 'Web' TIMESERIES 1 minute SINCE 30 minutes ago

-- A2. Satisfechas / tolerables / frustradas por duración (T = 0,5 s; 4T = 2 s)
SELECT filter(count(*), WHERE duration <= 0.5) AS 'Satisfechas', filter(count(*), WHERE duration > 0.5 AND duration <= 2) AS 'Tolerables', filter(count(*), WHERE duration > 2) AS 'Frustradas por tiempo', count(*) AS 'Total' FROM Transaction WHERE appName = 'cb-e4-iN-cloud' AND transactionType = 'Web' SINCE 30 minutes ago

-- A3. Apdex, promedio, p95 y RPS por transacción en la ventana de un escenario (E1 o E2)
SELECT apdex(duration, t: 0.5), average(duration), percentile(duration, 95), rate(count(*), 1 second) AS 'RPS' FROM Transaction WHERE appName = 'cb-e4-iN-cloud' AND transactionType = 'Web' FACET name SINCE 30 minutes ago
```

**Errores**

```sql
-- ER1. Error controlado de E3, con su atributo y mensaje
SELECT timestamp, transactionName, error.class, error.message, lab.scenario FROM TransactionError WHERE appName = 'cb-e4-iN-cloud' AND error.class LIKE '%ControlledMonitoringError' SINCE 30 minutes ago LIMIT 20

-- ER2. Respuestas por código HTTP (separa 4xx esperados de 5xx)
SELECT count(*) FROM Transaction WHERE appName = 'cb-e4-iN-cloud' AND transactionType = 'Web' FACET http.statusCode TIMESERIES 1 minute SINCE 30 minutes ago

-- ER3. Tasa 5xx frente a la tasa de error que calcula el agente
SELECT percentage(count(*), WHERE numeric(http.statusCode) >= 500) AS 'Tasa 5xx', percentage(count(*), WHERE error IS true) AS 'Tasa error agente' FROM Transaction WHERE appName = 'cb-e4-iN-cloud' AND transactionType = 'Web' TIMESERIES 1 minute SINCE 30 minutes ago
```

**Alertas** (AL1 y AL2 van, sin `SINCE`, en la condición; ver 5.2)

```sql
-- AL1. Condición cb-e4-iN-errores-5xx
SELECT percentage(count(*), WHERE numeric(http.statusCode) >= 500) FROM Transaction WHERE appName = 'cb-e4-iN-cloud' AND transactionType = 'Web'

-- AL2. Condición cb-e4-iN-apdex
SELECT apdex(duration, t: 0.5) FROM Transaction WHERE appName = 'cb-e4-iN-cloud' AND transactionType = 'Web'

-- AL3. Incidentes de la política (apertura y cierre)
SELECT timestamp, conditionName, priority, event, state FROM NrAiIncident WHERE policyName = 'cb-e4-iN-politica' SINCE 2 hours ago LIMIT 50
```

Las líneas `--` son solo rótulos de esta guía; copiar únicamente la línea `SELECT`.
Para las capturas, usar **Add to dashboard** desde Query your data si se quiere reunir los
gráficos en un tablero propio; no es obligatorio.

---

## 7. Ejecución por integrante

Orden recomendado y quién aporta cada parte. Usar UTC o UTC-5 de forma explícita y la misma
ventana en Locust, New Relic y el informe.

| Paso | Escenario | Acción | Qué guardar |
| --- | --- | --- | --- |
| 1 | — | Configurar T (3.2), política, condiciones, destino y workflow (5); probar las consultas (6) | Capturas de la configuración |
| 2 | E1 línea base (Fabio) | Correr la carga de Fabio; mirar Apdex y tasa 5xx | Apdex E1, ventana, carga |
| 3 | E2 estrés (Fabio) | Correr la carga; observar si el Apdex cae y si se abre la condición 2 | Apdex E2 vs E1, estado de la condición 2 |
| 4 | Preparar E3 | `OBS_LAB_ENABLED=true` y relanzar el pipeline (guía AWS, sección 8); esperar `Succeeded` | ID de ejecución y revisión ECS |
| 5 | E3 error controlado | Ejecutar el script (abajo) | CSV, hora inicio/fin, error en APM, incidente y correo |
| 6 | E4 recuperación | Esperar el cierre del incidente (al menos 120 s, más si hace falta) | Hora y correo de cierre, Apdex y tasa 5xx normales |
| 7 | Cierre | `OBS_LAB_ENABLED=false`, relanzar, comprobar 404 en la ruta de laboratorio y 200 en `/health` | ID de ejecución, respuestas finales |

E3 con el script (CloudShell o Linux; el JWT no se imprime ni se escribe en disco):

```bash
export BASE_URL=http://<alb-propio>
read -rsp "JWT: " TOKEN; export TOKEN; echo
bash monitoring/scripts/e3-error-controlado.sh 300        # 5 minutos; máximo 600
```

El script verifica `/health` y que la ruta de laboratorio esté activa antes de empezar.
Envía un error cada 2 s y, en paralelo, una consulta normal por segundo a un correo ficticio
(`e3-probe@example.com`), lo que da una tasa 5xx muy por encima del 5 %. Deja un CSV con hora
UTC y código HTTP en `$HOME` (fuera del repo). Si no hay tráfico de Locust disponible, este
tráfico normal basta para la alerta de errores; declararlo así en el informe.

Detener cualquier ejecución (`Ctrl+C`) si aparecen timeouts sostenidos o fallos distintos de
los 500 y 429 esperados.

---

## 8. Evidencias y registro

| Código | Contenido mínimo |
| --- | --- |
| I<N>-APDEX | Ajuste de Apdex T, valor de Apdex en E1 y E2 con ventana y entidad visibles |
| I<N>-ERROR | Errors Inbox o traza de `ControlledMonitoringError` con `lab.scenario`, mensaje y ventana de E3 |
| I<N>-ALERT | Condición (umbral y duración visibles), issue abierto, correo del workflow y cierre |
| I<N>-FINAL | Ruta de laboratorio en 404, `/health` 200 y Postman tras E4 |

No mostrar licencia, JWT, ID de la cuenta AWS ni el correo completo del destino.

Registro (llenar solo con datos observados):

| Integrante | SHA | T | Apdex E1 (ventana) | Apdex E2 (ventana) | E3 inicio–fin | Incidente abierto | Correo recibido | Incidente cerrado | Observaciones |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 - Oscar | `425722dc3e1dc7d55f3c6c34ca5e7d5442c3611e` | 0,5 s | 1,00 en Summary; selector visible 28/11 03:40-03:43, sin segundos ni zona explicitos | 1,00 en Summary; selector visible 28/11 03:45-03:52, sin segundos ni zona explicitos | 27/11/2026 23:01:40-23:06:41 UTC-5 | Confirmado por correo e Issue.png: 28/11 04:04 en hora del panel; falta ID y confirmar zona | Si, apertura y cierre; capturas inspeccionadas y recepcion confirmada por Oscar | Confirmado por correo e Issue.png: 28/11 04:10 en hora del panel, duracion 6 minutos | E1/E2: vistas APM y DB acotadas inspeccionadas; errores globales 0 % / 0,018 %. `POST <unmatched>` en E2 requiere detalle, no se infiere causa. E3: 125 respuestas 500 y 210 consultas 200. E4: 83 consultas 200. Final: Postman 7/7 y laboratorio 404; revision 19 estable. Detalles en el registro de Oscar |
| 2 - Jose Miguel | | | | | | | | | |
| 3 - Fabio | | | | | | | | | |
| 4 - Juan David | | | | | | | | | |

---

## 9. Guía para el informe (secciones 2, 3 y 4 del documento)

Cada sección describe **capacidades de la herramienta** y las **respalda con capturas y
datos propios**:

- **Apdex:** concepto, T elegido y su justificación, dónde se configura y se ve (Summary,
  Transactions, NRQL), comparación E1/E2, efecto de los 4xx y de los errores en el índice.
- **Errores:** Errors Inbox (agrupación, stack trace, atributos, marcado como esperado),
  eventos `TransactionError`, tasa de error de APM frente a tasa 5xx, uso de `notice_error`
  para excepciones capturadas por la app, y qué no prueba un 500 aislado.
- **Alertas:** políticas, condiciones NRQL (ventana, streaming, umbrales, duración, pérdida
  de señal), preferencia de issues, destinos y workflows, ciclo completo observado con
  tiempos reales, y limitaciones encontradas (plan gratuito, retraso de datos).

Consolidar los hallazgos de los cuatro integrantes en una tabla comparativa (sección 8) en
lugar de cuatro textos repetidos.

---

## 10. Limpieza

Al terminar E4: `OBS_LAB_ENABLED=false` desplegado y verificado (paso 7). Después de la
calificación, seguir [la guía de limpieza de AWS](Entrega-3-Limpieza-AWS.md) para la
infraestructura y [la sección 9 de la guía New Relic en AWS](Entrega-4-NewRelic-AWS.md#9-desactivar-o-retirar)
para el parámetro de licencia y los objetos de New Relic. No retirar el ambiente
compartido antes de la fecha de evaluación acordada.

---

## Fuentes oficiales

- [Apdex](https://docs.newrelic.com/docs/apm/new-relic-apm/apdex/apdex-measure-user-satisfaction/)
- [Configuración del agente Python: error collector](https://docs.newrelic.com/docs/apm/agents/python-agent/configuration/python-agent-configuration/#error-collector-settings)
- [notice_error (agente Python)](https://docs.newrelic.com/docs/apm/agents/python-agent/python-agent-api/noticeerror-python-agent-api/)
- [Condiciones NRQL](https://docs.newrelic.com/docs/alerts/create-alert/create-alert-condition/create-nrql-alert-conditions/)
- [Workflows](https://docs.newrelic.com/docs/alerts/get-notified/alert-event-workflows/)
- [Importar dashboards](https://docs.newrelic.com/docs/query-your-data/explore-query-data/dashboards/dashboards-charts-import-export-data/)
