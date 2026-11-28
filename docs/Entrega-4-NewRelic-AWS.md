# Entrega 4 - New Relic en AWS Fargate por el pipeline

Responsable: José Miguel Pardo Díaz (Integrante 2). Complementa
`docs/Entrega-4-NewRelic-Local.md` (Oscar), que cubre el agente y la prueba local.

La ejecución posterior en el ambiente compartido de Oscar se documenta en
[Entrega-4-Ejecucion-Cloud-Oscar.md](Entrega-4-Ejecucion-Cloud-Oscar.md).

> Estado de validación: el cambio de `scripts/prepare_cd.py` y sus pruebas se validaron
> en local con Python 3.11 (95 pruebas aprobadas, sin `tests/test_postgres.py`).
>
> Ejecución en AWS (cuenta del Integrante 2, `us-east-1`, 2026-11-22 UTC-5): el merge del
> PR #22 (commit `b054ece`) disparó la ejecución `9d1c6001-d66f-4a3c-b242-cf2c8da99dca`,
> que terminó en `Succeeded` a las 21:28. La task definition `cb-e3-i2-blacklists:11`
> trae `NEW_RELIC_ENABLED=true`, `NEW_RELIC_APP_NAME=cb-e4-i2-cloud`,
> `OBS_LAB_ENABLED=false` y el secreto `NEW_RELIC_LICENSE_KEY` desde SSM. El agente
> registró `Reporting to` a las 21:23 y la entidad `cb-e4-i2-cloud` muestra transacciones
> por ruta y consultas a PostgreSQL (RDS). Postman pasó 7/7 contra el ALB.
>
> Hallazgo: con la configuración por defecto, el agente cuenta como error las respuestas
> 4xx esperadas (400, 401, 409). Con tráfico de prueba, la transacción con mayor tasa de
> error llegó a 55,56 %. Hay que tenerlo en cuenta al definir Apdex y alertas.

## 1. Alcance

Esta guía activa New Relic en el servicio de Fargate de cada integrante **usando el
pipeline de la Entrega 3**, sin despliegues manuales ni cambios de código por cuenta.

- La imagen es la misma en las cuatro cuentas. El agente se activa en runtime, desde la
  task definition, como establece la sección 8 de la guía local.
- La licencia de New Relic vive en SSM Parameter Store como `SecureString`, igual que
  `DATABASE_URL` y `JWT_SECRET_KEY`. La task definition solo guarda su ARN y ECS la
  resuelve al arrancar la tarea. CodeBuild nunca lee la licencia.
- New Relic es **opcional por cuenta**. Una cuenta que todavía no configure las variables
  de esta guía sigue desplegando exactamente la misma task definition de la Entrega 3.

No cubre la creación de la cuenta de New Relic ni de la clave **Ingest - License**: ver la
sección 3 de la guía local.

## 2. Qué cambia en el repositorio

| Archivo | Cambio |
| --- | --- |
| `scripts/prepare_cd.py` | Si el proyecto CodeBuild define `NR_APP_NAME` y `SSM_NR_LICENSE_ARN`, agrega a la task definition las variables del agente y la licencia como secreto. Sin ellas, la salida es idéntica a la de la Entrega 3 |
| `tests/test_prepare_cd.py` | 11 casos nuevos: sin New Relic, con New Relic, opciones y configuraciones incompletas o inválidas |
| `buildspec-cd.yml` | Solo el comentario de cabecera, para documentar las variables opcionales |
| `deploy/taskdef.template.json` | Sin cambios. La plantilla sigue sirviendo para las cuatro cuentas |

### Variables del proyecto CodeBuild

Son nombres y ARN, no secretos.

| Variable | Obligatoria | Valor | Efecto en la task definition |
| --- | --- | --- | --- |
| `NR_APP_NAME` | Para activar | `cb-e4-i<N>-cloud` | `NEW_RELIC_ENABLED=true`, `NEW_RELIC_APP_NAME`, `NEW_RELIC_LOG=stderr` |
| `SSM_NR_LICENSE_ARN` | Para activar | ARN del parámetro con la licencia | Secreto `NEW_RELIC_LICENSE_KEY` con `valueFrom` |
| `OBS_LAB_ENABLED` | No | `true` o `false` (por defecto `false`) | Habilita `POST /observability/error` solo en la ventana del escenario de errores |
| `NEW_RELIC_HOST` | No | `collector.eu01.nr-data.net` | Solo para cuentas de New Relic en la región EU |

Reglas que valida `prepare_cd.py` antes de generar artefactos (si fallan, el Build se
detiene y no se despliega nada):

- `NR_APP_NAME` y `SSM_NR_LICENSE_ARN` van juntas o ninguna.
- `NR_APP_NAME` solo admite letras, números, punto, guion y guion bajo.
- `SSM_NR_LICENSE_ARN` debe ser un ARN de SSM. Un valor de licencia pegado por error se
  rechaza, para que nunca termine en la task definition.
- `OBS_LAB_ENABLED` y `NEW_RELIC_HOST` requieren las dos anteriores.
- `NEW_RELIC_HOST` debe terminar en `.nr-data.net`.

## 3. Parámetros

En CloudShell, cargar los parámetros de la guía manual de Fargate (sección 2.2 o Anexo A)
y del pipeline (`CODEBUILD_PROJECT`, `PIPELINE`). Después:

```bash
export NR_APP_NAME=${PREFIX/e3/e4}-cloud           # cb-e3-i2 -> cb-e4-i2-cloud
export SSM_NR_PARAM=/${PREFIX}/NEW_RELIC_LICENSE_KEY
export SSM_NR_LICENSE_ARN=arn:aws:ssm:${AWS_REGION}:${ACCOUNT_ID}:parameter${SSM_NR_PARAM}
echo "$NR_APP_NAME  $SSM_NR_PARAM"
```

El parámetro queda bajo `/${PREFIX}/`. **Comprobar los permisos del rol de ejecución de
ECS antes de activar el agente**: algunas cuentas permiten leer `/${PREFIX}/*`, pero
otras enumeran únicamente los ARN de `DATABASE_URL` y `JWT_SECRET_KEY`.

```bash
aws iam get-role-policy --role-name $EXEC_ROLE --policy-name leer-parametros-ssm \
  --query 'PolicyDocument.Statement[].Resource' --output text
```

Si muestra `arn:aws:ssm:...:parameter/<prefijo>/*`, el nuevo parámetro ya está cubierto.
Si la política enumera ARN individuales, agregar el ARN de `NEW_RELIC_LICENSE_KEY` a
la lista `Resource` de `ssm:GetParameters`, conservando los existentes; no ampliar a
todos los parámetros. Si se usa una clave KMS propia, revisar también su permiso de
descifrado según la guía de ECS.

Si la política se creó con otro nombre, listarlas con
`aws iam list-role-policies --role-name $EXEC_ROLE`. En la cuenta de Oscar se llama
`read-own-runtime-parameters`; el nombre `leer-parametros-ssm` del comando es el ejemplo
de la guía original, no un nombre obligatorio.

## 4. Guardar la licencia en SSM

`read -s` pide la clave sin mostrarla ni dejarla en el historial:

```bash
read -rs -p "Licencia Ingest de New Relic: " NR_LICENSE; echo
[ ${#NR_LICENSE} -ge 40 ] || echo "La licencia parece incompleta"
aws ssm put-parameter --name "$SSM_NR_PARAM" --type SecureString \
  --value "$NR_LICENSE" --overwrite --query Version --output text
unset NR_LICENSE
aws ssm describe-parameters --parameter-filters "Key=Name,Values=$SSM_NR_PARAM" \
  --query 'Parameters[].[Name,Type,LastModifiedDate]' --output text
```

No ejecutar `get-parameter --with-decryption` en una sesión grabada.

## 5. Variables del proyecto CodeBuild

Se agregan a las variables que ya tiene el proyecto, sin tocar las demás:

```bash
aws codebuild batch-get-projects --names $CODEBUILD_PROJECT \
  --query 'projects[0].environment' --output json > ~/${PREFIX}-cb-env.json

jq --arg app "$NR_APP_NAME" --arg arn "$SSM_NR_LICENSE_ARN" '
  .environmentVariables |= (
    map(select(.name != "NR_APP_NAME" and .name != "SSM_NR_LICENSE_ARN"))
    + [{name:"NR_APP_NAME",value:$app,type:"PLAINTEXT"},
       {name:"SSM_NR_LICENSE_ARN",value:$arn,type:"PLAINTEXT"}])' \
  ~/${PREFIX}-cb-env.json > ~/${PREFIX}-cb-env-nr.json

aws codebuild update-project --name $CODEBUILD_PROJECT \
  --environment file://$HOME/${PREFIX}-cb-env-nr.json \
  --query 'project.environment.environmentVariables[].name' --output text
```

Debe listar las seis variables de la Entrega 3 más `NR_APP_NAME` y `SSM_NR_LICENSE_ARN`.

## 6. Orden de integración

1. Cada integrante que vaya a activar New Relic hace las secciones 4 y 5 **antes** del
   merge del PR que trae este cambio. Con el código anterior, las variables nuevas no
   tienen efecto, así que configurarlas antes no rompe nada.
2. Merge del PR a `main`. El pipeline de cada cuenta corre solo:
   - Cuentas con las variables: la tarea nueva arranca con el agente.
   - Cuentas sin las variables: misma task definition de la Entrega 3.
3. Si una cuenta configura las variables después del merge, basta con relanzar su
   pipeline, sin otro commit:

```bash
aws codepipeline start-pipeline-execution --name $PIPELINE --query pipelineExecutionId --output text
```

## 7. Verificación

### En AWS

```bash
# Ejecución y despliegue
aws codepipeline get-pipeline-state --name $PIPELINE \
  --query 'stageStates[].[stageName,latestExecution.status]' --output text

# Revisión activa: variables del agente y nombre del secreto (nunca su valor)
TD=$(aws ecs describe-services --cluster $CLUSTER --services $SERVICE \
  --query "services[0].taskSets[?status=='PRIMARY'].taskDefinition | [0]" --output text)
aws ecs describe-task-definition --task-definition $TD \
  --query "taskDefinition.containerDefinitions[0].[environment[?starts_with(name,'NEW_RELIC') || name=='OBS_LAB_ENABLED'], secrets[].name]" \
  --output json

# Mensaje del agente en los logs de la tarea
aws logs tail $LOG_GROUP --since 20m --format short | grep -i -E "new relic|newrelic|Reporting to" | tail -5

# Servicio sano
curl -s http://$ALB_DNS/health; echo
curl -s http://$ALB_DNS/version; echo
```

Esperado:
- Las tres etapas en `Succeeded`.
- `NEW_RELIC_ENABLED=true` y el nombre `cb-e4-i<N>-cloud` en la task definition.
- `NEW_RELIC_LICENSE_KEY` en la lista de secretos.
- Un mensaje `Reporting to` en los logs.
- `/health` 200 y `/version` 2.2.0.

### En New Relic

1. Generar tráfico normal: correr la colección de Postman contra el ALB y repetir
   `/health` durante un par de minutos. El agente envía datos cada minuto, más o menos.
2. **APM & services**: abrir `cb-e4-i<N>-cloud`. No confundir con `cb-e4-i<N>-local`, que
   recibe el tráfico de la máquina local.
3. Comprobar Summary (tiempo de respuesta, throughput, error rate y Apdex), Transactions
   agrupadas por ruta (por ejemplo `GET /blacklists/<string:email>`, no una por correo) y
   **Databases**, con las operaciones de PostgreSQL en RDS. La vista local usa SQLite.

Un mensaje en los logs o un HTTP 200 no reemplazan la captura de la entidad recibiendo
datos.

Con despliegues CodeDeploy Blue/Green, verificar el task set `PRIMARY` y las tareas
que atienden tráfico. No tomar una revisión guardada más reciente ni el campo general
`service.taskDefinition` como prueba suficiente de lo que está ejecutándose.

## 8. Escenario de errores (Juan David)

Para habilitar `POST /observability/error` (guía local, sección 7) solo durante la ventana
acordada:

```bash
jq '.environmentVariables |= (map(select(.name != "OBS_LAB_ENABLED"))
    + [{name:"OBS_LAB_ENABLED",value:"true",type:"PLAINTEXT"}])' \
  ~/${PREFIX}-cb-env-nr.json > ~/${PREFIX}-cb-env-lab.json
aws codebuild update-project --name $CODEBUILD_PROJECT --environment file://$HOME/${PREFIX}-cb-env-lab.json >/dev/null
aws codepipeline start-pipeline-execution --name $PIPELINE --query pipelineExecutionId --output text
```

Al terminar, volver a `~/${PREFIX}-cb-env-nr.json` con el mismo `update-project`, relanzar
el pipeline y comprobar `404` en la ruta de laboratorio y `200` en `/health`. Cada cambio
es un despliegue Blue/Green completo, de unos 9 minutos.

## 9. Desactivar o retirar

- **Desactivar el agente:** quitar `NR_APP_NAME` y `SSM_NR_LICENSE_ARN` del proyecto
  CodeBuild (volver a `~/${PREFIX}-cb-env.json`) y relanzar el pipeline.
- **Limpieza después de la calificación:** además de la guía de limpieza de la Entrega 3,
  borrar el parámetro y, en New Relic, la entidad, las condiciones de alerta y los
  workflows de la cuenta propia.

```bash
aws ssm delete-parameter --name "$SSM_NR_PARAM"
```

## 10. Evidencias (prefijo I<N>)

| Código | Contenido |
| --- | --- |
| I<N>-NR-CB | Variables del proyecto CodeBuild: nombres y ARN, sin valores secretos |
| I<N>-PIPE | SHA, ejecución Source-Build-Deploy en `Succeeded` y revisión de la task definition |
| I<N>-NR-TD | Variables `NEW_RELIC_*` y nombre del secreto en la task definition activa |
| I<N>-NR-CLOUD | Entidad `cb-e4-i<N>-cloud` con tráfico de Fargate y ventana visible |
| I<N>-NR-DB | Vista Databases con las operaciones de PostgreSQL |
| I<N>-FINAL | Postman 7/7 contra el ALB y estado final del servicio |

Anotar fecha, hora y zona de cada captura. No mostrar la licencia, el JWT ni el ID de la
cuenta AWS.
