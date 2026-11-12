# Entrega 3 - CodeBuild: pruebas, imagen en ECR y artefactos de CD

Responsable: Fabio Andrés Guaidia Ruiz (Integrante 3) · Equipo CodeBusters

Esta guía crea el proyecto CodeBuild que ejecuta la etapa **Build** del pipeline de `docs/Entrega-3-Pipeline-CodeDeploy.md`. En cada commit de `main` corre las pruebas unitarias con reporte JUnit y, solo si pasan, construye la imagen Docker, la publica en ECR con el SHA del commit y entrega a la etapa Deploy los tres archivos que consume `CodeDeployToECS`.

> Estado de validación: los archivos del repositorio (`buildspec-cd.yml`, `scripts/prepare_cd.py`, `deploy/taskdef.template.json`) se validaron en local: 56 pruebas aprobadas, incluidas las de `tests/test_prepare_cd.py`. Falta la ejecución en una cuenta AWS. Registrar aquí la fecha y el resultado reales cuando se ejecute.

---

## 1. Alcance y decisiones

| Tema | Decisión |
| --- | --- |
| Herramienta | AWS CLI v2 desde AWS CloudShell (`us-east-1`), igual que las otras guías |
| Origen del proyecto | `CODEPIPELINE`: el proyecto solo corre como etapa del pipeline. Sin webhook propio, para que cada push genere una sola ejecución |
| Buildspec | `buildspec-cd.yml`. El `buildspec.yml` de la Entrega 2 (ZIP para Beanstalk) se conserva sin cambios |
| Imagen de CodeBuild | `aws/codebuild/amazonlinux-x86_64-standard:5.0`, la misma de la Entrega 2. Python 3.11 y Docker, x86_64 |
| Modo privilegiado | Activado: lo exige `docker build` dentro de CodeBuild |
| Orden del build | Pruebas -> imagen -> artefactos, en una sola fase. Si una prueba falla, CodeBuild detiene la fase: no se publica imagen ni se generan artefactos |
| Reporte de pruebas | JUnit en el report group `<proyecto>-pytest_reports`, que CodeBuild crea en la primera ejecución |
| Tag de la imagen | SHA completo del commit (`CODEBUILD_RESOLVED_SOURCE_VERSION`). El digest queda en el log del build |
| Imagen base | `python:3.11-slim-bookworm` del `Dockerfile`, descargada de la copia oficial en ECR Public (`public.ecr.aws/docker/library/...`). Evita el límite de descargas anónimas de Docker Hub desde las IP compartidas de CodeBuild. El `Dockerfile` no cambia |
| Parámetros de cuenta | Variables de entorno del proyecto CodeBuild. Son ARN y nombres, no secretos; nunca van en el repositorio |
| Secretos | CodeBuild no lee los secretos. La task definition solo referencia los ARN de SSM; los resuelve ECS al arrancar la tarea |

### Frontera con los demás componentes

| Quién | Qué entrega |
| --- | --- |
| Oscar | `Dockerfile`, `.dockerignore` y arranque con Gunicorn en el puerto 5000 |
| Jose Miguel (guía manual) | Repositorio ECR, rol de ejecución, grupo de logs, parámetros SSM y la estructura de la task definition inicial |
| Esta guía | `buildspec-cd.yml`, `scripts/prepare_cd.py`, `deploy/taskdef.template.json`, rol de CodeBuild y proyecto CodeBuild |
| Juan David (pipeline) | `deploy/appspec.yaml`, bucket de artefactos, conexión GitHub, CodeDeploy y pipeline que invoca este proyecto |

### Qué hace `buildspec-cd.yml`

```text
install   pip install -r requirements-dev.txt + pip check
build     1. pytest -> reports/pytest.xml (JUnit)            si falla: FIN, sin imagen
          2. docker pull de la imagen base desde ECR Public
          3. docker build --platform linux/amd64 + push a ECR  tag = SHA completo
          4. python scripts/prepare_cd.py -> dist/cd/
reports   reports/pytest.xml -> report group <proyecto>-pytest_reports
artifacts dist/cd/{taskdef.json, appspec.yaml, imageDetail.json} en la raíz de BuildArtifact
```

### Qué genera `scripts/prepare_cd.py`

| Archivo | Origen | Contenido |
| --- | --- | --- |
| `taskdef.json` | `deploy/taskdef.template.json` | Misma estructura que la task definition de la guía manual (sección 9), con los parámetros de la cuenta resueltos y `"image": "<IMAGE1_NAME>"` |
| `appspec.yaml` | `deploy/appspec.yaml` | Copia sin cambios. `<TASK_DEFINITION>` lo sustituye la acción Deploy |
| `imageDetail.json` | Variable `IMAGE_URI` del build | `{"ImageURI": "<ECR_URI>:<SHA>"}` |

El script falla (y con él el build) si falta alguna variable, si el tag no es un SHA de 40 caracteres o si la plantilla y el AppSpec no coinciden en el contenedor `blacklists` y el puerto `5000`. Antes de escribir, borra lo que hubiera en `dist/cd/`.

---

## 2. Requisitos y parámetros

### 2.1 Requisitos

- Guía `docs/Entrega-3-Fargate-Manual.md` ejecutada en la **misma cuenta**: deben existir el repositorio ECR, el rol de ejecución, el grupo de logs y los dos parámetros SSM.
- El nombre del bucket de artefactos de `docs/Entrega-3-Pipeline-CodeDeploy.md` (sección 2.2). El bucket puede crearse antes o después de esta guía; el rol solo necesita su nombre.
- `main` debe contener `buildspec-cd.yml`, `scripts/prepare_cd.py`, `deploy/taskdef.template.json` y `deploy/appspec.yaml`.

### 2.2 Parámetros

Cargar primero los parámetros de la guía manual (sección 2.2 y Anexo A), que definen `PREFIX`, `ACCOUNT_ID`, `ECR_REPO`, `ECR_URI`, `TASK_FAMILY`, `EXEC_ROLE_ARN`, `LOG_GROUP`, `SSM_DB_ARN` y `SSM_JWT_ARN`. Después agregar:

```bash
export CODEBUILD_PROJECT=${PREFIX}-build
export CODEBUILD_ROLE=${PREFIX}-codebuild-role
export ARTIFACT_BUCKET=${PREFIX}-artifacts-${ACCOUNT_ID}   # mismo valor que la guía del pipeline
```

Son los nombres que ya usan `docs/Entrega-3-Pipeline-CodeDeploy.md` y `docs/Entrega-3-Limpieza-AWS.md`. Agregarlos también a `~/e3-env.sh`.

Comprobar que los recursos de la guía manual existen antes de seguir:

```bash
aws ecr describe-repositories --repository-names $ECR_REPO --query 'repositories[0].repositoryName' --output text
aws iam get-role --role-name ${PREFIX}-ecs-exec-role --query 'Role.RoleName' --output text
aws logs describe-log-groups --log-group-name-prefix $LOG_GROUP --query 'logGroups[0].logGroupName' --output text
aws ssm describe-parameters --parameter-filters Key=Name,Option=BeginsWith,Values=/${PREFIX}/ --query 'Parameters[].Name' --output text
```

Ninguno debe responder `None` ni error.

---

## 3. Rol de servicio de CodeBuild

Permisos mínimos, limitados a los recursos propios:

```bash
cat > /tmp/${PREFIX}-cb-trust.json <<JSON
{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"codebuild.amazonaws.com"},"Action":"sts:AssumeRole"}]}
JSON

cat > /tmp/${PREFIX}-cb-policy.json <<JSON
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "Logs",
      "Effect": "Allow",
      "Action": ["logs:CreateLogGroup","logs:CreateLogStream","logs:PutLogEvents"],
      "Resource": [
        "arn:aws:logs:${AWS_REGION}:${ACCOUNT_ID}:log-group:/aws/codebuild/${CODEBUILD_PROJECT}",
        "arn:aws:logs:${AWS_REGION}:${ACCOUNT_ID}:log-group:/aws/codebuild/${CODEBUILD_PROJECT}:*"
      ]
    },
    {
      "Sid": "ArtefactosPipeline",
      "Effect": "Allow",
      "Action": ["s3:GetObject","s3:GetObjectVersion","s3:PutObject","s3:GetBucketAcl","s3:GetBucketLocation"],
      "Resource": ["arn:aws:s3:::${ARTIFACT_BUCKET}","arn:aws:s3:::${ARTIFACT_BUCKET}/*"]
    },
    {
      "Sid": "ReporteJUnit",
      "Effect": "Allow",
      "Action": ["codebuild:CreateReportGroup","codebuild:CreateReport","codebuild:UpdateReport","codebuild:BatchPutTestCases"],
      "Resource": "arn:aws:codebuild:${AWS_REGION}:${ACCOUNT_ID}:report-group/${CODEBUILD_PROJECT}-*"
    },
    {
      "Sid": "LoginECR",
      "Effect": "Allow",
      "Action": "ecr:GetAuthorizationToken",
      "Resource": "*"
    },
    {
      "Sid": "PublicarImagen",
      "Effect": "Allow",
      "Action": [
        "ecr:BatchCheckLayerAvailability","ecr:BatchGetImage","ecr:GetDownloadUrlForLayer",
        "ecr:InitiateLayerUpload","ecr:UploadLayerPart","ecr:CompleteLayerUpload","ecr:PutImage"
      ],
      "Resource": "arn:aws:ecr:${AWS_REGION}:${ACCOUNT_ID}:repository/${ECR_REPO}"
    }
  ]
}
JSON

aws iam create-role --role-name $CODEBUILD_ROLE \
  --assume-role-policy-document file:///tmp/${PREFIX}-cb-trust.json > /dev/null

aws iam put-role-policy --role-name $CODEBUILD_ROLE --policy-name codebuild-entrega3 \
  --policy-document file:///tmp/${PREFIX}-cb-policy.json

export CODEBUILD_ROLE_ARN=arn:aws:iam::${ACCOUNT_ID}:role/${CODEBUILD_ROLE}
```

| Permiso | Por qué |
| --- | --- |
| Logs sobre `/aws/codebuild/<proyecto>` | Registro del build en CloudWatch |
| S3 sobre el bucket de artefactos | Dentro del pipeline, CodeBuild lee `SourceArtifact` y escribe `BuildArtifact` en ese bucket |
| Report groups `<proyecto>-*` | Crear el report group y publicar el JUnit |
| `ecr:GetAuthorizationToken` | `docker login` en ECR. Esta acción no admite restricción por recurso |
| Acciones de capas e imagen sobre el repositorio propio | `docker push` de la imagen |

No necesita `iam:PassRole`, `ssm:GetParameter*` ni permisos de ECS: CodeBuild no lee secretos ni registra la task definition (eso lo hace la acción Deploy con el rol del pipeline). Descargar la imagen base de ECR Public no requiere credenciales.

---

## 4. Proyecto CodeBuild

```bash
cat > /tmp/${PREFIX}-cb-project.json <<EOF
{
  "name": "${CODEBUILD_PROJECT}",
  "description": "Entrega 3: pruebas, imagen en ECR y artefactos de CodeDeploy",
  "serviceRole": "${CODEBUILD_ROLE_ARN}",
  "source": {"type": "CODEPIPELINE", "buildspec": "buildspec-cd.yml"},
  "artifacts": {"type": "CODEPIPELINE"},
  "environment": {
    "type": "LINUX_CONTAINER",
    "image": "aws/codebuild/amazonlinux-x86_64-standard:5.0",
    "computeType": "BUILD_GENERAL1_SMALL",
    "privilegedMode": true,
    "imagePullCredentialsType": "CODEBUILD",
    "environmentVariables": [
      {"name": "ECR_URI",       "value": "${ECR_URI}",       "type": "PLAINTEXT"},
      {"name": "TASK_FAMILY",   "value": "${TASK_FAMILY}",   "type": "PLAINTEXT"},
      {"name": "EXEC_ROLE_ARN", "value": "${EXEC_ROLE_ARN}", "type": "PLAINTEXT"},
      {"name": "SSM_DB_ARN",    "value": "${SSM_DB_ARN}",    "type": "PLAINTEXT"},
      {"name": "SSM_JWT_ARN",   "value": "${SSM_JWT_ARN}",   "type": "PLAINTEXT"},
      {"name": "LOG_GROUP",     "value": "${LOG_GROUP}",     "type": "PLAINTEXT"}
    ]
  },
  "logsConfig": {
    "cloudWatchLogs": {"status": "ENABLED", "groupName": "/aws/codebuild/${CODEBUILD_PROJECT}"}
  },
  "timeoutInMinutes": 20,
  "queuedTimeoutInMinutes": 30
}
EOF

grep -c '""' /tmp/${PREFIX}-cb-project.json    # debe ser 0: ninguna variable quedó vacía

aws codebuild create-project --cli-input-json file:///tmp/${PREFIX}-cb-project.json > /dev/null
```

Si responde que no puede asumir el rol, esperar 15 segundos (propagación de IAM) y repetir.

| Variable | Valor en la cuenta | Uso |
| --- | --- | --- |
| `ECR_URI` | `<cuenta>.dkr.ecr.us-east-1.amazonaws.com/cb-e3-iN-blacklists` | Destino de `docker push` e `ImageURI` |
| `TASK_FAMILY` | `cb-e3-iN-blacklists` | `family` de la task definition |
| `EXEC_ROLE_ARN` | Rol de ejecución de la guía manual | `executionRoleArn` |
| `SSM_DB_ARN` / `SSM_JWT_ARN` | Parámetros `/cb-e3-iN/DATABASE_URL` y `/cb-e3-iN/JWT_SECRET_KEY` | `secrets[].valueFrom`: solo el ARN, nunca el valor |
| `LOG_GROUP` | `/ecs/cb-e3-iN-blacklists` | `awslogs-group` |
| `AWS_REGION` | La aporta CodeBuild | `awslogs-region` y login de ECR |

Verificación:

```bash
aws codebuild batch-get-projects --names $CODEBUILD_PROJECT \
  --query 'projects[0].[source.type,source.buildspec,environment.image,environment.privilegedMode,length(environment.environmentVariables)]' \
  --output text
```

Debe mostrar `CODEPIPELINE  buildspec-cd.yml  aws/codebuild/amazonlinux-x86_64-standard:5.0  True  6`.

Un proyecto con origen `CODEPIPELINE` no se puede lanzar desde la consola de CodeBuild con "Start build": la primera ejecución llega cuando Juan David crea el pipeline (sección 7 de su guía). Compartir con él el nombre del proyecto.

Evidencia `B4-01`: proyecto en la consola (CodeBuild > Proyectos > `cb-e3-iN-build` > Detalles), con origen CodePipeline, buildspec `buildspec-cd.yml`, modo privilegiado y las variables. Tapar el ID de cuenta en `ECR_URI` y en los ARN.

---

## 5. Comprobación local (opcional)

Para revisar los artefactos sin AWS, desde la raíz del repositorio con el entorno virtual activo:

```bash
python -m pytest -q --ignore=tests/test_postgres.py      # incluye tests/test_prepare_cd.py

TASK_FAMILY=cb-e3-i0-blacklists \
EXEC_ROLE_ARN=arn:aws:iam::111122223333:role/cb-e3-i0-ecs-exec-role \
SSM_DB_ARN=arn:aws:ssm:us-east-1:111122223333:parameter/cb-e3-i0/DATABASE_URL \
SSM_JWT_ARN=arn:aws:ssm:us-east-1:111122223333:parameter/cb-e3-i0/JWT_SECRET_KEY \
LOG_GROUP=/ecs/cb-e3-i0-blacklists AWS_REGION=us-east-1 \
IMAGE_URI=111122223333.dkr.ecr.us-east-1.amazonaws.com/cb-e3-i0-blacklists:$(git rev-parse HEAD) \
python scripts/prepare_cd.py

ls dist/cd    # appspec.yaml  imageDetail.json  taskdef.json
```

Los valores son ficticios. `dist/` está en `.gitignore`.

---

## 6. Qué se ve en cada escenario

Complementa la sección 9 de la guía del pipeline. Lo que aporta CodeBuild:

| Caso | Build | Report group | ECR | `BuildArtifact` |
| --- | --- | --- | --- | --- |
| A - CI fallido | `FAILED` en la fase `BUILD`, en el comando de `pytest` | 1 fallida, el resto aprobadas | Sin imagen con ese SHA | No se genera: Deploy no corre |
| B - CI y CD exitosos | `SUCCEEDED` | Todas aprobadas | Imagen `<SHA>` con digest | Los tres archivos |
| C - CI exitoso, CD fallido | `SUCCEEDED` | Todas aprobadas | Imagen `<SHA>` publicada | Los tres archivos; el fallo aparece después, en CodeDeploy |

Comandos de apoyo (el ID del build es el `externalExecutionId` de la etapa Build, sección 10 de la guía del pipeline):

```bash
export BUILD_ID=PEGAR_AQUI_EL_ID_DEL_BUILD     # cb-e3-iN-build:xxxxxxxx-...

aws codebuild batch-get-builds --ids $BUILD_ID \
  --query 'builds[0].[buildStatus,resolvedSourceVersion,startTime,endTime]' --output text

aws codebuild batch-get-builds --ids $BUILD_ID \
  --query 'builds[0].phases[].[phaseType,phaseStatus]' --output text

# Conteo real del JUnit de ese build
export REPORT_ARN=$(aws codebuild batch-get-builds --ids $BUILD_ID --query 'builds[0].reportArns[0]' --output text)
aws codebuild describe-test-cases --report-arn $REPORT_ARN \
  --query 'testCases[].status' --output text | tr '\t' '\n' | sort | uniq -c

# Imagen y digest (casos B y C)
aws ecr describe-images --repository-name $ECR_REPO --image-ids imageTag=<SHA> \
  --query 'imageDetails[0].[imageTags[0],imageDigest,imagePushedAt]' --output text

# Log del build: commit, resultado de pytest y digest
aws logs tail /aws/codebuild/$CODEBUILD_PROJECT --since 30m | grep -E 'Commit|passed|failed|Digest|prepare_cd'
```

Evidencias sugeridas por caso: `<caso>-CB-01` fases del build, `<caso>-CB-02` reporte de pruebas en Report groups, `<caso>-CB-03` imagen en ECR (o su ausencia en el caso A). Tapar el ID de cuenta.

---

## 7. Problemas frecuentes

| Síntoma | Causa probable |
| --- | --- |
| `Cannot connect to the Docker daemon` | El proyecto no tiene `privilegedMode: true` |
| `toomanyrequests` al descargar la imagen base | Se está bajando de Docker Hub. Revisar que el paso de ECR Public del buildspec se ejecute y que el `FROM` del `Dockerfile` exista en `public.ecr.aws/docker/library/` |
| `no basic auth credentials` / `denied` en `docker push` | Falta `ecr:GetAuthorizationToken` o las acciones de push sobre el repositorio, o `ECR_URI` apunta a otra cuenta o región |
| `prepare_cd: faltan variables de entorno` | Variable vacía o ausente en el proyecto (sección 4) |
| `IMAGE_URI debe ser <repositorio>:<sha de 40 caracteres>` | El build no se lanzó desde el pipeline y `CODEBUILD_RESOLVED_SOURCE_VERSION` no es un SHA |
| `AccessDenied` sobre S3 al empezar o terminar | El rol no tiene acceso a `ARTIFACT_BUCKET` o el nombre del bucket no coincide con el del pipeline |
| El reporte JUnit no aparece | Faltan permisos `codebuild:*Report*` sobre `report-group/<proyecto>-*` |
| La tarea nueva falla con `exec format error` | Imagen construida para ARM. El buildspec usa `--platform linux/amd64` y la imagen de CodeBuild es x86_64; no cambiar a una imagen ARM |
| Deploy no encuentra `taskdef.json` | Los archivos deben quedar en la raíz del artefacto: `base-directory: dist/cd` y `discard-paths: yes` |

---

## 8. Costos

| Recurso | Cobro |
| --- | --- |
| CodeBuild `BUILD_GENERAL1_SMALL` | Por minuto de build. Cada ejecución tarda unos pocos minutos; la capa gratuita cubre 100 min/mes en cuentas que la tengan |
| ECR | Por GB almacenado. Cada commit a `main` agrega una imagen; se borran en la limpieza |
| CloudWatch Logs del build | Por GB ingerido y almacenado; marginal |
| Report group | Sin costo adicional |

---

## 9. Eliminación

Los pasos están consolidados en `docs/Entrega-3-Limpieza-AWS.md`: sección 5 (proyecto, report groups y log group), sección 9.1 (imágenes ECR) y sección 10 (rol `cb-e3-iN-codebuild-role`, con su política en línea `codebuild-entrega3`). Esta guía no crea recursos adicionales.

---

## Anexo A. Recuperar identificadores en una terminal nueva

Después de cargar la sección 2.2 y el Anexo A de la guía manual, y el bloque de la sección 2.2 de esta guía:

```bash
export CODEBUILD_ROLE_ARN=arn:aws:iam::${ACCOUNT_ID}:role/${CODEBUILD_ROLE}
```

## Anexo B. Lista de capturas

| Captura | Sección | Qué muestra |
| --- | --- | --- |
| `B3-01` | 3 | Rol `cb-e3-iN-codebuild-role` con la política `codebuild-entrega3` |
| `B4-01` | 4 | Proyecto CodeBuild: origen CodePipeline, `buildspec-cd.yml`, modo privilegiado y variables |
| `A-CB-*`, `B-CB-*`, `C-CB-*` | 6 | Fases del build, reporte JUnit e imagen en ECR por caso |

## Referencias

- [Referencia de buildspec](https://docs.aws.amazon.com/codebuild/latest/userguide/build-spec-ref.html)
- [Docker en CodeBuild (modo privilegiado)](https://docs.aws.amazon.com/codebuild/latest/userguide/sample-docker.html)
- [Reportes de pruebas en CodeBuild](https://docs.aws.amazon.com/codebuild/latest/userguide/test-reporting.html)
- [Variables de entorno de CodeBuild](https://docs.aws.amazon.com/codebuild/latest/userguide/build-env-ref-env-vars.html)
- [Archivo imageDetail.json para CodeDeployToECS](https://docs.aws.amazon.com/codepipeline/latest/userguide/file-reference.html#file-reference-ecs-bluegreen)
- [Imágenes oficiales de Docker en ECR Public](https://gallery.ecr.aws/docker)
