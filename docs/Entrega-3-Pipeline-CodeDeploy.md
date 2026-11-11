# Entrega 3 - Pipeline CodePipeline y despliegue Blue/Green con CodeDeploy

Responsable: Juan David Cuevas Perdomo (Integrante 4).

Esta guía conecta el repositorio de GitHub con el servicio ECS/Fargate de la guía manual mediante un pipeline **Source -> Build -> Deploy**. Cada cambio en `main` ejecuta las pruebas, publica la imagen en ECR y la despliega con Blue/Green administrado por CodeDeploy, con rollback automático ante fallo.

> Estado de validación: pendiente de ejecución en cuenta propia. Las secciones 3 y 4 (CodeDeploy y despliegue manual de prueba) solo requieren la guía de Jose Miguel. Las secciones 5 a 7 requieren además el proyecto CodeBuild de Fabio (`buildspec-cd.yml`). Registrar aquí la fecha y el resultado reales cuando se ejecute.

---

## 1. Alcance y decisiones

| Tema | Decisión |
| --- | --- |
| Herramienta | AWS CLI v2 desde AWS CloudShell (`us-east-1`), igual que la guía manual. La conexión GitHub se autoriza en la consola |
| Pipeline | CodePipeline **V2**, modo de ejecución `QUEUED`: los cambios seguidos se encolan y ningún despliegue se cancela por otro |
| Disparador | La propia acción Source con `DetectChanges=true` sobre `main`. Sin GitHub Actions ni webhook de CodeBuild |
| Artefactos | Bucket S3 propio `cb-e3-iN-artifacts-<ACCOUNT_ID>`, privado, con limpieza automática de cargas multipart incompletas |
| Despliegue | `CodeDeployToECS`, Blue/Green con control de tráfico, `CodeDeployDefault.ECSAllAtOnce` |
| Listener | Solo producción (puerto 80). Sin listener de pruebas |
| Rollback | Automático ante `DEPLOYMENT_FAILURE` y ante alarma (`DEPLOYMENT_STOP_ON_ALARM`) |
| Versión anterior | Se elimina 5 minutos después de un despliegue exitoso |
| Detección rápida de fallo | Dos alarmas de CloudWatch sobre `UnHealthyHostCount` de los target groups (sección 3.3) |

### Frontera con los demás componentes

| Quién | Qué crea o entrega |
| --- | --- |
| Jose Miguel (guía manual) | Red, rol de ejecución, SSM, RDS, ECR, ALB, listener, target groups `-tg-blue` y `-tg-green`, cluster y servicio con controlador `CODE_DEPLOY` |
| Fabio (CodeBuild/ECR) | Proyecto CodeBuild y su rol, `buildspec-cd.yml`, `scripts/prepare_cd.py`, `deploy/taskdef.template.json` |
| Esta guía | `deploy/appspec.yaml`, rol de CodeDeploy, aplicación y grupo de despliegue, alarmas, bucket de artefactos, conexión GitHub, rol y pipeline |

### Flujo completo

```text
GitHub main ──push──> Source (CodeConnections) ── SourceArtifact ──>
  Build (CodeBuild de Fabio, buildspec-cd.yml)
     pruebas + JUnit -> docker build/push (tag = SHA) -> dist/cd/
     ── BuildArtifact { taskdef.json, appspec.yaml, imageDetail.json } ──>
  Deploy (CodeDeployToECS)
     1. Sustituye <IMAGE1_NAME> en taskdef.json por ImageURI de imageDetail.json
     2. Registra una nueva revisión de la task definition
     3. Sustituye <TASK_DEFINITION> en appspec.yaml por el ARN de esa revisión
     4. Crea el despliegue en CodeDeploy:
        tarea green -> sana en el target group libre -> listener 80 al green
        -> espera 5 min -> elimina el task set anterior
```

Si una prueba falla, el build falla y la etapa Deploy no se ejecuta. Si el despliegue falla, CodeDeploy deja (o devuelve) el tráfico en la versión anterior.

---

## 2. Requisitos y parámetros

### 2.1 Requisitos

- Guía `docs/Entrega-3-Fargate-Manual.md` ejecutada hasta la sección 12 en la **misma cuenta**: servicio `ACTIVE 1 1`, destino sano y Postman correcto contra el ALB.
- Para las secciones 5 a 7: proyecto CodeBuild de Fabio creado según `docs/Entrega-3-CodeBuild-ECR.md`, con **origen CodePipeline** (sin webhook propio).
- `jq` (CloudShell ya lo trae).
- Acceso de lectura al repositorio `OscarGomez-MISO/CodeBusters-DevOps` desde la cuenta de GitHub que autoriza la conexión.

### 2.2 Parámetros

Cargar primero los parámetros de la guía manual (sección 2.2 y Anexo A). Después agregar estos, idénticos para todos salvo `IDX`, que ya viene del bloque anterior:

```bash
export CD_APP=${PREFIX}-app
export CD_GROUP=${PREFIX}-dg
export CD_ROLE=${PREFIX}-codedeploy-role
export PIPELINE=${PREFIX}-pipeline
export PIPELINE_ROLE=${PREFIX}-pipeline-role
export ARTIFACT_BUCKET=${PREFIX}-artifacts-${ACCOUNT_ID}
export CONNECTION_NAME=${PREFIX}-github
export GITHUB_REPO=OscarGomez-MISO/CodeBusters-DevOps
export BRANCH=main
export CODEBUILD_PROJECT=${PREFIX}-build   # confirmar con la guía de Fabio
```

Agregarlos también a `~/e3-env.sh` para recuperarlos en una terminal nueva. El Anexo A de esta guía recupera los identificadores de los recursos que se crean aquí.

Nombres y valores que **no cambian** entre cuentas (contrato del plan de trabajo):

| Elemento | Valor |
| --- | --- |
| Contenedor / puerto | `blacklists` / `5000` |
| Artefacto de salida del build | `BuildArtifact` |
| Archivos en la raíz del artefacto | `taskdef.json`, `appspec.yaml`, `imageDetail.json` |
| Marcador de imagen en `taskdef.json` | `<IMAGE1_NAME>` |
| Marcador en `appspec.yaml` | `<TASK_DEFINITION>` |
| Identificador de imagen en la acción Deploy | `IMAGE1_NAME` |

---

## 3. CodeDeploy: rol, aplicación, alarmas y grupo de despliegue

Esta sección no depende del trabajo de Fabio.

### 3.1 Rol de servicio de CodeDeploy

CodeDeploy usa este rol para crear task sets en ECS, modificar el listener y leer las alarmas. La política administrada `AWSCodeDeployRoleForECS` incluye esos permisos y el `iam:PassRole` hacia roles de tareas ECS.

```bash
cat > /tmp/${PREFIX}-cd-trust.json <<JSON
{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"codedeploy.amazonaws.com"},"Action":"sts:AssumeRole"}]}
JSON

aws iam create-role --role-name $CD_ROLE \
  --assume-role-policy-document file:///tmp/${PREFIX}-cd-trust.json > /dev/null

aws iam attach-role-policy --role-name $CD_ROLE \
  --policy-arn arn:aws:iam::aws:policy/AWSCodeDeployRoleForECS

export CD_ROLE_ARN=arn:aws:iam::${ACCOUNT_ID}:role/${CD_ROLE}
```

Un rol recién creado tarda unos segundos en propagarse. Si el paso 3.4 responde que no puede asumir el rol, esperar 15 segundos y repetirlo.

### 3.2 Aplicación

```bash
aws deploy create-application --application-name $CD_APP --compute-platform ECS
```

### 3.3 Alarmas para detectar un despliegue fallido

Sin alarmas, si las tareas nuevas nunca quedan sanas, CodeDeploy espera hasta **60 minutos** antes de declarar el fallo ([Troubleshoot Amazon ECS deployment issues](https://docs.aws.amazon.com/codedeploy/latest/userguide/troubleshooting-ecs.html)). Con una alarma por target group, CodeDeploy detiene el despliegue y hace rollback en pocos minutos. Es un mecanismo de CodeDeploy, no una cancelación manual.

```bash
export ALB_DIM=${ALB_ARN#*:loadbalancer/}     # app/<nombre>/<id>

for color in blue green; do
  if [ $color = blue ]; then TG_ARN=$TG_BLUE_ARN; else TG_ARN=$TG_GREEN_ARN; fi
  aws cloudwatch put-metric-alarm \
    --alarm-name ${PREFIX}-tg-${color}-unhealthy \
    --alarm-description "Entrega 3: destinos no sanos en ${PREFIX}-tg-${color}" \
    --namespace AWS/ApplicationELB --metric-name UnHealthyHostCount \
    --dimensions Name=TargetGroup,Value=${TG_ARN##*:} Name=LoadBalancer,Value=$ALB_DIM \
    --statistic Maximum --period 60 \
    --evaluation-periods 2 --datapoints-to-alarm 2 \
    --threshold 1 --comparison-operator GreaterThanOrEqualToThreshold \
    --treat-missing-data notBreaching
done

aws cloudwatch describe-alarms --alarm-name-prefix ${PREFIX}-tg- \
  --query 'MetricAlarms[].[AlarmName,StateValue]' --output table
```

Se vigilan los dos target groups porque se alternan en cada despliegue: el que hoy recibe tráfico es el próximo libre. Las dos alarmas deben quedar en `OK` (o `INSUFFICIENT_DATA` los primeros minutos). **Si una alarma está en `ALARM` al iniciar un despliegue, CodeDeploy lo detiene de inmediato**: antes de cada escenario comprobar que estén en `OK`.

### 3.4 Grupo de despliegue

```bash
cat > /tmp/${PREFIX}-dg.json <<EOF
{
  "applicationName": "${CD_APP}",
  "deploymentGroupName": "${CD_GROUP}",
  "serviceRoleArn": "${CD_ROLE_ARN}",
  "deploymentConfigName": "CodeDeployDefault.ECSAllAtOnce",
  "deploymentStyle": {
    "deploymentType": "BLUE_GREEN",
    "deploymentOption": "WITH_TRAFFIC_CONTROL"
  },
  "blueGreenDeploymentConfiguration": {
    "deploymentReadyOption": {
      "actionOnTimeout": "CONTINUE_DEPLOYMENT",
      "waitTimeInMinutes": 0
    },
    "terminateBlueInstancesOnDeploymentSuccess": {
      "action": "TERMINATE",
      "terminationWaitTimeInMinutes": 5
    }
  },
  "autoRollbackConfiguration": {
    "enabled": true,
    "events": ["DEPLOYMENT_FAILURE", "DEPLOYMENT_STOP_ON_ALARM"]
  },
  "alarmConfiguration": {
    "enabled": true,
    "ignorePollAlarmFailure": false,
    "alarms": [
      {"name": "${PREFIX}-tg-blue-unhealthy"},
      {"name": "${PREFIX}-tg-green-unhealthy"}
    ]
  },
  "ecsServices": [
    {"clusterName": "${CLUSTER}", "serviceName": "${SERVICE}"}
  ],
  "loadBalancerInfo": {
    "targetGroupPairInfoList": [
      {
        "targetGroups": [
          {"name": "${PREFIX}-tg-blue"},
          {"name": "${PREFIX}-tg-green"}
        ],
        "prodTrafficRoute": {"listenerArns": ["${LISTENER_ARN}"]}
      }
    ]
  }
}
EOF

aws deploy create-deployment-group --cli-input-json file:///tmp/${PREFIX}-dg.json
```

Qué significa cada parte:

| Configuración | Efecto |
| --- | --- |
| `ECSAllAtOnce` | Cuando la tarea nueva está sana, el listener pasa el 100 % del tráfico de una vez |
| `deploymentReadyOption` en `CONTINUE_DEPLOYMENT` con 0 minutos | No se espera aprobación manual para redirigir el tráfico |
| `terminationWaitTimeInMinutes: 5` | La versión anterior sigue viva 5 minutos tras el cambio de tráfico, y luego se elimina |
| `autoRollbackConfiguration` | Ante fallo o alarma, el tráfico queda o vuelve a la versión anterior y el task set nuevo se elimina |
| `targetGroupPairInfoList` | Par blue/green y listener de producción. Sin `testTrafficRoute`: no hay listener de pruebas |

Capacidad: durante un despliegue hay temporalmente **dos tareas** (la original y la nueva). No se configura autoescalado, que además puede interferir con CodeDeploy.

Verificación:

```bash
aws deploy get-deployment-group --application-name $CD_APP \
  --deployment-group-name $CD_GROUP \
  --query 'deploymentGroupInfo.[deploymentConfigName,deploymentStyle.deploymentType,autoRollbackConfiguration.events,ecsServices[0].serviceName]' \
  --output json
```

Evidencia `P3-01`: grupo de despliegue en la consola (CodeDeploy > Aplicaciones > `cb-e3-iN-app`), con tipo Blue/Green, configuración `ECSAllAtOnce`, rollback y alarmas. Tapar los ARN.

---

## 4. Despliegue manual de prueba (sin pipeline)

Valida el grupo de despliegue y el `appspec.yaml` antes de tener el build de Fabio. Despliega la **misma imagen** que ya corre, en una nueva revisión de la task definition.

Ejecutar desde la raíz del repositorio, en una rama que contenga `deploy/appspec.yaml`:

```bash
# 1. Nueva revisión de la task definition actual (misma imagen)
aws ecs describe-task-definition --task-definition $TASK_FAMILY --query taskDefinition \
  | jq 'del(.taskDefinitionArn,.revision,.status,.requiresAttributes,.compatibilities,.registeredAt,.registeredBy)' \
  > /tmp/${PREFIX}-td-manual.json

export TD_MANUAL_ARN=$(aws ecs register-task-definition \
  --cli-input-json file:///tmp/${PREFIX}-td-manual.json \
  --query 'taskDefinition.taskDefinitionArn' --output text)

# 2. AppSpec con el ARN real (lo mismo que hace la acción del pipeline)
jq -n --arg c "$(sed "s|<TASK_DEFINITION>|${TD_MANUAL_ARN}|" deploy/appspec.yaml)" \
  '{revisionType:"AppSpecContent", appSpecContent:{content:$c}}' \
  > /tmp/${PREFIX}-revision.json

# 3. Despliegue
export DEPLOYMENT_ID=$(aws deploy create-deployment \
  --application-name $CD_APP --deployment-group-name $CD_GROUP \
  --revision file:///tmp/${PREFIX}-revision.json \
  --description "Prueba manual Entrega 3" \
  --query deploymentId --output text)
echo $DEPLOYMENT_ID
```

Mientras corre, en **otra** pestaña de CloudShell, observar la disponibilidad (ver sección 8.2):

```bash
while true; do
  printf '%s ' "$(date +%T)"
  curl -s --max-time 3 -w ' HTTP %{http_code}\n' http://$ALB_DNS/version || echo "sin respuesta"
  sleep 2
done | tee ~/${PREFIX}-disponibilidad-manual.log
```

Seguir el despliegue:

```bash
aws deploy get-deployment --deployment-id $DEPLOYMENT_ID \
  --query 'deploymentInfo.[status,deploymentOverview]' --output json

aws deploy wait deployment-successful --deployment-id $DEPLOYMENT_ID
```

El `wait` termina cuando la versión anterior ya se eliminó, es decir, unos 5 minutos después del cambio de tráfico. En la consola de CodeDeploy se ven los pasos: instalación del task set nuevo, redirección de tráfico, espera y eliminación del task set original.

Comprobar el resultado:

```bash
# El listener ahora apunta al target group que antes estaba libre
aws elbv2 describe-listeners --listener-arns $LISTENER_ARN \
  --query 'Listeners[0].DefaultActions[0].TargetGroupArn' --output text | sed 's/.*targetgroup\///'

# Un solo task set PRIMARY con la revisión nueva
aws ecs describe-services --cluster $CLUSTER --services $SERVICE \
  --query 'services[0].taskSets[].[status,taskDefinition,runningCount]' --output text \
  | sed 's/.*task-definition\///'

curl -s http://$ALB_DNS/health
```

Importante para la guía manual: tras el primer despliegue, el target group con tráfico pasa a ser `-tg-green`. Los comandos de la sección 12.1 de la guía manual que consultan `TG_BLUE_ARN` deben hacerse sobre el target group que indique el listener.

Con controlador `CODE_DEPLOY`, `aws ecs update-service --task-definition` **no** despliega versiones nuevas. Solo admite cambios como `--desired-count`.

Evidencia `P4-01`: despliegue manual `Succeeded` en la consola de CodeDeploy con sus pasos. `P4-02`: registro de disponibilidad sin errores durante el cambio.

---

## 5. Conexión GitHub y bucket de artefactos

### 5.1 Conexión GitHub (CodeConnections)

Si la cuenta ya tiene una conexión GitHub **en estado `AVAILABLE`** con acceso al repositorio (por ejemplo, la de la Entrega 2), puede reutilizarse: tomar su ARN y pasar a 5.2. En ese caso no eliminarla durante la limpieza si la Entrega 2 todavía la usa.

Para crear una nueva:

```bash
export CONNECTION_ARN=$(aws codeconnections create-connection \
  --provider-type GitHub --connection-name $CONNECTION_NAME \
  --query ConnectionArn --output text)
```

La conexión nace en `PENDING`. Completarla en la consola: **Developer Tools > Settings > Connections > `cb-e3-iN-github` > Update pending connection**, iniciar sesión en GitHub y elegir la instalación de la GitHub App que tiene acceso a `OscarGomez-MISO/CodeBusters-DevOps`. Si no administras el repositorio, coordinar con su propietario la instalación de la app, igual que en la Entrega 2.

```bash
aws codeconnections get-connection --connection-arn $CONNECTION_ARN \
  --query 'Connection.ConnectionStatus' --output text     # debe decir AVAILABLE
```

No desinstalar la GitHub App del repositorio: la usan los cuatro integrantes.

### 5.2 Bucket de artefactos

```bash
aws s3api create-bucket --bucket $ARTIFACT_BUCKET > /dev/null

aws s3api put-public-access-block --bucket $ARTIFACT_BUCKET \
  --public-access-block-configuration \
  BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true

cat > /tmp/${PREFIX}-lifecycle.json <<'JSON'
{"Rules":[{"ID":"limpieza-artefactos","Status":"Enabled","Filter":{},
  "AbortIncompleteMultipartUpload":{"DaysAfterInitiation":1},
  "Expiration":{"Days":30}}]}
JSON

aws s3api put-bucket-lifecycle-configuration --bucket $ARTIFACT_BUCKET \
  --lifecycle-configuration file:///tmp/${PREFIX}-lifecycle.json
```

En `us-east-1` no se indica `LocationConstraint`. El bucket no tiene versionado: no lo exige CodePipeline y simplifica la limpieza. El cifrado SSE-S3 viene activo por defecto. Los artefactos de cada ejecución expiran a los 30 días.

---

## 6. Rol del pipeline

Permisos mínimos para las tres etapas, limitados a los recursos propios:

```bash
cat > /tmp/${PREFIX}-cp-trust.json <<JSON
{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"codepipeline.amazonaws.com"},"Action":"sts:AssumeRole"}]}
JSON

cat > /tmp/${PREFIX}-cp-policy.json <<JSON
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "Artefactos",
      "Effect": "Allow",
      "Action": ["s3:GetObject","s3:GetObjectVersion","s3:PutObject","s3:GetBucketVersioning","s3:GetBucketLocation","s3:ListBucket"],
      "Resource": ["arn:aws:s3:::${ARTIFACT_BUCKET}","arn:aws:s3:::${ARTIFACT_BUCKET}/*"]
    },
    {
      "Sid": "Source",
      "Effect": "Allow",
      "Action": ["codeconnections:UseConnection","codestar-connections:UseConnection"],
      "Resource": "${CONNECTION_ARN}"
    },
    {
      "Sid": "Build",
      "Effect": "Allow",
      "Action": ["codebuild:StartBuild","codebuild:BatchGetBuilds"],
      "Resource": "arn:aws:codebuild:${AWS_REGION}:${ACCOUNT_ID}:project/${CODEBUILD_PROJECT}"
    },
    {
      "Sid": "Deploy",
      "Effect": "Allow",
      "Action": ["codedeploy:CreateDeployment","codedeploy:GetDeployment","codedeploy:GetApplication","codedeploy:GetApplicationRevision","codedeploy:RegisterApplicationRevision","codedeploy:GetDeploymentConfig"],
      "Resource": [
        "arn:aws:codedeploy:${AWS_REGION}:${ACCOUNT_ID}:application:${CD_APP}",
        "arn:aws:codedeploy:${AWS_REGION}:${ACCOUNT_ID}:deploymentgroup:${CD_APP}/${CD_GROUP}",
        "arn:aws:codedeploy:${AWS_REGION}:${ACCOUNT_ID}:deploymentconfig:*"
      ]
    },
    {
      "Sid": "TaskDefinition",
      "Effect": "Allow",
      "Action": ["ecs:RegisterTaskDefinition","ecs:DescribeTaskDefinition","ecs:TagResource"],
      "Resource": "*"
    },
    {
      "Sid": "PasarRolDeEjecucion",
      "Effect": "Allow",
      "Action": "iam:PassRole",
      "Resource": "${EXEC_ROLE_ARN}",
      "Condition": {"StringEquals": {"iam:PassedToService": "ecs-tasks.amazonaws.com"}}
    }
  ]
}
JSON

aws iam create-role --role-name $PIPELINE_ROLE \
  --assume-role-policy-document file:///tmp/${PREFIX}-cp-trust.json > /dev/null

aws iam put-role-policy --role-name $PIPELINE_ROLE --policy-name pipeline-entrega3 \
  --policy-document file:///tmp/${PREFIX}-cp-policy.json

export PIPELINE_ROLE_ARN=arn:aws:iam::${ACCOUNT_ID}:role/${PIPELINE_ROLE}
```

| Permiso | Por qué |
| --- | --- |
| S3 sobre el bucket propio | Guardar `SourceArtifact` y leer `BuildArtifact` |
| `UseConnection` | Descargar el código desde GitHub. Se incluyen los dos prefijos porque las conexiones antiguas usan `codestar-connections` |
| `StartBuild` / `BatchGetBuilds` | Ejecutar el proyecto de Fabio y esperar su resultado |
| `codedeploy:*` listados | Crear el despliegue y seguirlo |
| `ecs:RegisterTaskDefinition` | La acción registra la revisión a partir de `taskdef.json`. Esta acción de ECS no admite restricción por recurso |
| `iam:PassRole` | La task definition nueva referencia el rol de ejecución de la guía manual |

Si la task definition de Fabio incluyera un rol de tarea (`taskRoleArn`), agregar su ARN al recurso de `iam:PassRole`. La guía manual no crea rol de tarea.

El rol de CodeBuild de Fabio necesita leer y escribir en `ARTIFACT_BUCKET`: cuando CodeBuild corre dentro del pipeline, recibe y entrega los artefactos en ese bucket. Compartirle el nombre.

---

## 7. Pipeline Source -> Build -> Deploy

**Antes de crearlo**: el proyecto `CODEBUILD_PROJECT` debe existir, y `main` debe contener `buildspec-cd.yml` y `deploy/appspec.yaml`. Al crearse, el pipeline se ejecuta una vez sobre el último commit de `main`; esa primera ejecución despliega la versión actual y sirve de línea base.

```bash
cat > /tmp/${PREFIX}-pipeline.json <<EOF
{
  "pipeline": {
    "name": "${PIPELINE}",
    "roleArn": "${PIPELINE_ROLE_ARN}",
    "pipelineType": "V2",
    "executionMode": "QUEUED",
    "artifactStore": {"type": "S3", "location": "${ARTIFACT_BUCKET}"},
    "stages": [
      {
        "name": "Source",
        "actions": [{
          "name": "Source",
          "actionTypeId": {"category": "Source", "owner": "AWS", "provider": "CodeStarSourceConnection", "version": "1"},
          "configuration": {
            "ConnectionArn": "${CONNECTION_ARN}",
            "FullRepositoryId": "${GITHUB_REPO}",
            "BranchName": "${BRANCH}",
            "OutputArtifactFormat": "CODE_ZIP",
            "DetectChanges": "true"
          },
          "outputArtifacts": [{"name": "SourceArtifact"}],
          "runOrder": 1
        }]
      },
      {
        "name": "Build",
        "actions": [{
          "name": "Build",
          "actionTypeId": {"category": "Build", "owner": "AWS", "provider": "CodeBuild", "version": "1"},
          "configuration": {"ProjectName": "${CODEBUILD_PROJECT}"},
          "inputArtifacts": [{"name": "SourceArtifact"}],
          "outputArtifacts": [{"name": "BuildArtifact"}],
          "runOrder": 1
        }]
      },
      {
        "name": "Deploy",
        "actions": [{
          "name": "Deploy",
          "actionTypeId": {"category": "Deploy", "owner": "AWS", "provider": "CodeDeployToECS", "version": "1"},
          "configuration": {
            "ApplicationName": "${CD_APP}",
            "DeploymentGroupName": "${CD_GROUP}",
            "TaskDefinitionTemplateArtifact": "BuildArtifact",
            "TaskDefinitionTemplatePath": "taskdef.json",
            "AppSpecTemplateArtifact": "BuildArtifact",
            "AppSpecTemplatePath": "appspec.yaml",
            "Image1ArtifactName": "BuildArtifact",
            "Image1ContainerName": "IMAGE1_NAME"
          },
          "inputArtifacts": [{"name": "BuildArtifact"}],
          "runOrder": 1
        }]
      }
    ]
  }
}
EOF

aws codepipeline create-pipeline --cli-input-json file:///tmp/${PREFIX}-pipeline.json > /dev/null
```

### 7.1 Cómo consume la acción Deploy el artefacto

| Archivo en `BuildArtifact` | Lo produce | Uso en `CodeDeployToECS` |
| --- | --- | --- |
| `taskdef.json` | Fabio, desde `deploy/taskdef.template.json` | Plantilla de la task definition. La acción reemplaza `<IMAGE1_NAME>` por la imagen y registra una revisión nueva |
| `imageDetail.json` | Fabio, en el build | `{"ImageURI": "<repo>:<SHA>"}`. `Image1ArtifactName` indica en qué artefacto está y `Image1ContainerName=IMAGE1_NAME` qué marcador reemplaza |
| `appspec.yaml` | Esta guía (`deploy/appspec.yaml`), copiado por Fabio | La acción reemplaza `<TASK_DEFINITION>` por el ARN de la revisión registrada y crea el despliegue |

`imagedefinitions.json` **no** se usa: es el formato de la acción ECS estándar (rolling update), no de Blue/Green.

Los tres archivos deben estar en la **raíz** del artefacto, no dentro de `dist/cd/`. Si la acción responde `Exception while trying to read the task definition artifact file` o similar, revisar en S3 el ZIP de `BuildArtifact` de esa ejecución.

### 7.2 Un solo disparador

`DetectChanges=true` registra el disparador del pipeline sobre `main`. No debe haber otro mecanismo que construya lo mismo:

- El proyecto CodeBuild de Fabio debe tener origen **CodePipeline**, sin webhook.
- Sin flujos de GitHub Actions para este build.
- El proyecto de la Entrega 2 (`codebusters-ci-integrante4`) tiene su propio webhook sobre `main` y genera el ZIP de Beanstalk. No despliega, pero ejecuta las mismas pruebas en cada push. Para que cada push corresponda a una sola ejecución en la evidencia, se recomienda desactivar ese webhook mientras duren los escenarios. El proyecto y su configuración se conservan:

```bash
aws codebuild delete-webhook --project-name codebusters-ci-integrante4
```

Si el equipo decide conservarlo, dejarlo indicado en el informe.

### 7.3 Verificación

```bash
aws codepipeline get-pipeline-state --name $PIPELINE \
  --query 'stageStates[].[stageName,latestExecution.status]' --output table
```

La primera ejecución debe terminar con las tres etapas en `Succeeded`. La etapa Deploy incluye la espera de 5 minutos antes de eliminar la versión anterior.

Evidencia `P7-01`: pipeline en la consola con Source, Build y Deploy en verde, y el SHA del commit en la etapa Source. `P7-02`: configuración de la acción Deploy (artefactos, rutas e `IMAGE1_NAME`).

---

## 8. Tráfico, rollback y disponibilidad

### 8.1 Qué ocurre en cada caso

| Situación | Comportamiento esperado |
| --- | --- |
| Prueba unitaria falla | Build `FAILED`. Deploy no se ejecuta (`Didn't Run`). No se publica imagen ni se crea despliegue. Sigue atendiendo la versión anterior |
| Despliegue exitoso | Task set nuevo sano en el target group libre -> listener al 100 % -> 5 min de espera -> se elimina el task set anterior |
| Tareas nuevas no sanas | Alarma `UnHealthyHostCount` en `ALARM` -> CodeDeploy detiene y hace rollback -> el listener sigue en la versión anterior -> se elimina el task set nuevo |
| Falla durante los 5 minutos de espera | Rollback: el listener vuelve al task set original, que todavía existe |
| Falla después de terminar | No hay rollback automático: se recupera con un commit correctivo o revert por PR |

Estos son comportamientos esperados. En el informe solo se afirma lo que se haya observado en el registro de disponibilidad y en la consola.

### 8.2 Registro de disponibilidad

Durante cada escenario, ejecutar en una pestaña aparte el bucle de la sección 4 (cambiando el nombre del archivo de log por el del escenario). Al terminar, resumir:

```bash
grep -c 'HTTP 200' ~/${PREFIX}-disponibilidad-B.log
grep -v 'HTTP 200' ~/${PREFIX}-disponibilidad-B.log      # respuestas distintas de 200 o sin respuesta
```

Si no hay líneas distintas de 200, se puede afirmar que **en ese intervalo y con ese muestreo de 2 segundos** no se observaron interrupciones. No afirmar disponibilidad continua sin ese registro.

### 8.3 Rollback manual (solo si hiciera falta)

Si un despliegue queda bloqueado, se puede detener con rollback:

```bash
aws deploy stop-deployment --deployment-id <ID> --auto-rollback-enabled
```

No usarlo para el caso C: el plan exige que el fallo y la recuperación los produzca la etapa de CD, no una cancelación manual.

---

## 9. Escenarios de evaluación

Cada integrante los ejecuta en su cuenta. Un solo commit por escenario en `main` dispara los cuatro pipelines. **Nadie introduce un fallo deliberado en `main` sin acordar antes día, hora y SHA con el equipo.** Todos los cambios entran por PR y la recuperación se hace con commit correctivo o revert, sin reescribir el historial.

Antes de cada escenario, cada integrante comprueba:

```bash
aws codepipeline get-pipeline-state --name $PIPELINE \
  --query 'stageStates[].[stageName,latestExecution.status]' --output text   # sin InProgress
aws cloudwatch describe-alarms --alarm-name-prefix ${PREFIX}-tg- \
  --query 'MetricAlarms[].[AlarmName,StateValue]' --output text              # OK
curl -s http://$ALB_DNS/version                                              # versión de partida
```

Y deja corriendo el registro de disponibilidad (sección 8.2).

### 9.1 Propuesta de cambios por escenario

La propuesta encadena los tres escenarios para que cada uno parta de un estado conocido. Ajustar los números de versión con Oscar antes de ejecutarla.

| Orden | Commit (PR a `main`) | Escenario |
| --- | --- | --- |
| 1 | Cambiar `app/resources.py` a `{"version": "2.1.0"}` **sin** actualizar `tests/test_get_health_version.py` | **A**: `test_version_without_authentication` falla |
| 2 | Actualizar la prueba para esperar `2.1.0` | **B**: CI y CD exitosos, se despliega 2.1.0 |
| 3 | Cambiar en el `Dockerfile` el `--bind 0.0.0.0:5000` del `CMD` por `0.0.0.0:5001` | **C**: CI pasa, CD falla |
| 4 | Revert del commit 3 por PR | Recuperación de C |

Por qué el caso C es un fallo real de CD: las pruebas unitarias no ejecutan el `Dockerfile`, así que el build aprueba y la imagen se publica. En Fargate, Gunicorn escucha en 5001 mientras el target group revisa `/health` en 5000. La tarea nueva nunca queda sana, la alarma se activa y CodeDeploy hace rollback. No es una prueba unitaria fallida ni una cancelación manual.

### 9.2 Caso A - CI fallido

1. Fusionar el commit 1 a la hora acordada. Registrar el SHA completo.
2. Observar: Source `Succeeded`, Build `Failed`, Deploy `Didn't Run`.
3. En CodeBuild > Report groups: reporte JUnit con el conteo real (por ejemplo, 1 fallida y el resto aprobadas).
4. Comprobar que no hay imagen con ese SHA en ECR ni despliegue nuevo en CodeDeploy.
5. `curl http://$ALB_DNS/version` sigue respondiendo la versión anterior (`2.0.0`).

### 9.3 Caso B - CI y CD exitosos

1. Fusionar el commit 2. Registrar el SHA.
2. Build `Succeeded` con todas las pruebas aprobadas y la imagen `<ECR_URI>:<SHA>` en ECR. Registrar el digest.
3. Deploy: seguir el despliegue en CodeDeploy hasta `Succeeded`.
4. `curl http://$ALB_DNS/version` responde `2.1.0`. Ejecutar la colección Postman contra el ALB (Runner sin token visible).
5. Revisar el registro de disponibilidad y el cambio de target group en el listener.

### 9.4 Caso C - CI exitoso y CD fallido

1. Fusionar el commit 3. Registrar el SHA.
2. Build `Succeeded`: pruebas aprobadas e imagen publicada.
3. Deploy: CodeDeploy crea el task set nuevo, cuyos destinos quedan `unhealthy` en el target group libre.
4. Diagnóstico, con evidencia:

   ```bash
   aws deploy get-deployment --deployment-id <ID> \
     --query 'deploymentInfo.[status,errorInformation,rollbackInfo]' --output json
   aws elbv2 describe-target-health --target-group-arn <TG libre> \
     --query 'TargetHealthDescriptions[].TargetHealth' --output json
   aws logs tail $LOG_GROUP --since 15m | grep -i "listening"
   ```

   Se espera estado `Stopped` o `Failed`, alarma como causa, destinos con `Target.FailedHealthChecks` y Gunicorn escuchando en `0.0.0.0:5001`.
5. Comprobar que `curl http://$ALB_DNS/version` siguió respondiendo `2.1.0` durante el intento (registro de disponibilidad) y que el listener no cambió de target group.
6. Recuperación: fusionar el revert (commit 4). El pipeline despliega correctamente y `/version` responde `2.1.0` desde un task set nuevo. Esperar a que las alarmas vuelvan a `OK` antes de fusionar el revert.

Si el despliegue de C tardara mucho en fallar, revisar que las alarmas estén en el grupo de despliegue (sección 3.4). Sin ellas, CodeDeploy puede esperar hasta 60 minutos.

---

## 10. Evidencias por caso

Guardar por cada caso, en cada cuenta:

| Dato | Cómo obtenerlo |
| --- | --- |
| SHA completo | Etapa Source del pipeline, o `git rev-parse HEAD` tras actualizar `main` |
| Fecha y hora | De la ejecución del pipeline (indicar zona horaria) |
| ID de ejecución del pipeline | Comando abajo |
| ID del build | Comando abajo |
| ID del despliegue | Comando abajo (no existe en el caso A) |
| Resultado de pruebas | Reporte JUnit en CodeBuild: total, aprobadas y fallidas reales |
| Imagen y digest | `aws ecr describe-images` (no existe en el caso A) |
| Versión observada | `curl /version` antes y después, más el registro de disponibilidad |
| Capturas | Pipeline, build, reporte de pruebas, ECR, despliegue en CodeDeploy, target groups, Postman |
| Hallazgos | Dos o tres frases con lo observado |

Comandos de apoyo:

```bash
export EXEC_ID=$(aws codepipeline list-pipeline-executions --pipeline-name $PIPELINE \
  --max-items 1 --query 'pipelineExecutionSummaries[0].pipelineExecutionId' --output text)

aws codepipeline get-pipeline-execution --pipeline-name $PIPELINE --pipeline-execution-id $EXEC_ID \
  --query 'pipelineExecution.[status,artifactRevisions[0].revisionId]' --output text

aws codepipeline list-action-executions --pipeline-name $PIPELINE \
  --filter pipelineExecutionId=$EXEC_ID \
  --query 'actionExecutionDetails[].[stageName,status,startTime,output.executionResult.externalExecutionId]' \
  --output table

export SHA=PEGAR_AQUI_EL_SHA_COMPLETO
aws ecr describe-images --repository-name $ECR_REPO --image-ids imageTag=$SHA \
  --query 'imageDetails[0].[imageTags[0],imageDigest,imagePushedAt]' --output text

aws deploy list-deployments --application-name $CD_APP --deployment-group-name $CD_GROUP \
  --max-items 3 --query deployments --output text
```

`externalExecutionId` corresponde al ID del build en la etapa Build y al ID del despliegue en la etapa Deploy.

Plantilla para el informe:

```text
Caso: A | B | C
Integrante / cuenta: Integrante 4 / ********1234
SHA: <40 caracteres>
Fecha/hora (UTC-5): 2026-11-__ __:__
Ejecución pipeline: <id>
Build: <id> - Pruebas: __ aprobadas, __ fallidas
Imagen: <repo>:<SHA> - digest sha256:...
Despliegue CodeDeploy: d-XXXXXXXXX - Estado: ...
Versión antes / después: ... / ...
Disponibilidad: __ respuestas 200 de __ muestras entre hh:mm y hh:mm
Hallazgos: ...
```

Cuidados al capturar: igual que la guía manual. Tapar el ID de cuenta y los ARN, y no mostrar secretos, tokens ni la URL de la conexión.

---

## 11. Problemas frecuentes

| Síntoma | Causa probable |
| --- | --- |
| Source falla con `Unable to use Connection` | Conexión en `PENDING`, sin acceso al repositorio, o falta `UseConnection` en el rol |
| El pipeline no arranca con un push | `DetectChanges` en `false` o rama distinta de `main` |
| Build falla con `AccessDenied` sobre S3 | El rol de CodeBuild de Fabio no tiene acceso a `ARTIFACT_BUCKET` |
| Deploy: `The provided role does not have sufficient permissions` / `PassRole` | Falta `iam:PassRole` sobre el rol de ejecución en el rol del pipeline |
| Deploy: no encuentra `taskdef.json` o `appspec.yaml` | Los archivos no están en la raíz de `BuildArtifact` |
| Deploy: `Invalid IMAGE1_NAME` o imagen sin reemplazar | El marcador en `taskdef.json` no es exactamente `<IMAGE1_NAME>` o falta `imageDetail.json` |
| `The ECS service cannot be found` / contenedor no coincide | Nombre de contenedor o puerto distinto de `blacklists` / `5000` en task definition o AppSpec |
| Despliegue detenido al empezar | Una alarma estaba en `ALARM` al iniciar |
| Despliegue tarda mucho y termina en timeout | Alarmas no configuradas en el grupo; revisar sección 3.3 |
| `Deployment group's ECS service must be configured for CODE_DEPLOY` | El servicio no se creó con `--deployment-controller type=CODE_DEPLOY` (guía manual, sección 11) |

---

## 12. Costos de esta guía

| Recurso | Cobro |
| --- | --- |
| CodePipeline V2 | Por minuto de ejecución de acciones; marginal en este proyecto |
| CodeDeploy en ECS | Sin costo adicional |
| Segunda tarea durante cada despliegue | Fargate por segundo mientras ambas versiones conviven (hasta 5 minutos después del cambio) |
| Alarmas de CloudWatch | Por alarma y por mes; dos alarmas estándar |
| Bucket S3 | Por GB almacenado; los artefactos expiran a 30 días |
| Conexión GitHub | Sin costo |

La eliminación está en `docs/Entrega-3-Limpieza-AWS.md`.

---

## Anexo A. Recuperar identificadores en una terminal nueva

Después de cargar la sección 2.2 y el Anexo A de la guía manual, y el bloque de la sección 2.2 de esta guía:

```bash
export CD_ROLE_ARN=arn:aws:iam::${ACCOUNT_ID}:role/${CD_ROLE}
export PIPELINE_ROLE_ARN=arn:aws:iam::${ACCOUNT_ID}:role/${PIPELINE_ROLE}
export CONNECTION_ARN=$(aws codeconnections list-connections \
  --query "Connections[?ConnectionName=='${CONNECTION_NAME}'].ConnectionArn | [0]" --output text)
export ALB_DIM=${ALB_ARN#*:loadbalancer/}
```

Si se reutilizó una conexión existente, cambiar `CONNECTION_NAME` por su nombre.

## Anexo B. Lista de capturas

| Captura | Sección | Qué muestra |
| --- | --- | --- |
| `P3-01` | 3 | Grupo de despliegue: Blue/Green, `ECSAllAtOnce`, rollback, alarmas, target groups y listener |
| `P3-02` | 3 | Alarmas en `OK` |
| `P4-01` | 4 | Despliegue manual `Succeeded` con sus pasos |
| `P4-02` | 4 | Registro de disponibilidad durante el despliegue manual |
| `P5-01` | 5 | Conexión GitHub `Available` |
| `P7-01` | 7 | Pipeline con las tres etapas en verde y el SHA en Source |
| `P7-02` | 7 | Configuración de la acción Deploy |
| `A-*`, `B-*`, `C-*` | 9 | Evidencias de cada escenario según la sección 10 |

## Referencias

- [Acción CodeDeployToECS](https://docs.aws.amazon.com/codepipeline/latest/userguide/action-reference-ECSbluegreen.html)
- [Blue/Green administrado por CodeDeploy](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/deployment-type-bluegreen.html)
- [AppSpec para ECS](https://docs.aws.amazon.com/codedeploy/latest/userguide/reference-appspec-file-structure-resources.html)
- [Rollback con alarmas en CodeDeploy](https://docs.aws.amazon.com/codedeploy/latest/userguide/deployments-rollback-and-redeploy.html)
- [Troubleshoot Amazon ECS deployment issues](https://docs.aws.amazon.com/codedeploy/latest/userguide/troubleshooting-ecs.html)
- [Conexiones GitHub (CodeConnections)](https://docs.aws.amazon.com/dtconsole/latest/userguide/connections-create-github.html)
