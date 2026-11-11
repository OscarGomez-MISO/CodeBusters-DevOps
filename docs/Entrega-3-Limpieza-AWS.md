# Entrega 3 - Limpieza de recursos AWS

Consolidación: Juan David Cuevas Perdomo (Integrante 4). Aportes: Oscar (contenedor local), Jose Miguel (despliegue manual Fargate), Fabio (CodeBuild/ECR) y Juan David (pipeline y CodeDeploy).

Esta guía elimina **todo lo que crean las guías de la Entrega 3** en una cuenta personal, en un orden que respeta las dependencias y evita que el pipeline vuelva a crear recursos mientras se borran.

> **Cuándo ejecutarla:** solo cuando termine el periodo de disponibilidad exigido para la evaluación y estén guardadas las evidencias. Cada integrante la ejecuta en su propia cuenta. Parar la aplicación no basta: el ALB, RDS, las IP públicas, ECR, S3 y los logs siguen cobrando.
>
> **No borrar recursos de otros proyectos.** Todos los comandos filtran por el prefijo propio `cb-e3-iN`. No se eliminan la VPC por defecto ni sus subnets, ni la GitHub App instalada en el repositorio.

> Estado de validación: pendiente de ejecución completa. Jose Miguel validó solo el borrado de RDS de su sección 14. Registrar aquí la fecha y el resultado reales.

---

## 0. Inventario y orden

| # | Recurso | Guía de origen | Dónde verlo en la consola | Depende de / bloquea | Puede seguir cobrando si se omite |
| --- | --- | --- | --- | --- | --- |
| 1 | Pipeline `cb-e3-iN-pipeline` | Pipeline-CodeDeploy | CodePipeline > Pipelines | Dispara builds y despliegues: se elimina **primero** | Minutos de acción si sigue ejecutando |
| 2 | Webhook de CodeBuild de la Entrega 2 (si se reactivó) | Entrega 2 | CodeBuild > proyecto > Source | Dispara builds en cada push | Minutos de build |
| 3 | Despliegues de CodeDeploy en curso | Pipeline-CodeDeploy | CodeDeploy > Deployments | Mantienen dos task sets | Segunda tarea Fargate |
| 4 | Grupo y aplicación de CodeDeploy | Pipeline-CodeDeploy | CodeDeploy > Applications | Requiere que no haya despliegues en curso | No cobran |
| 5 | Alarmas `cb-e3-iN-tg-*-unhealthy` | Pipeline-CodeDeploy | CloudWatch > Alarms | Usadas por el grupo de despliegue | Cobro mensual por alarma |
| 6 | Proyecto CodeBuild y grupos de reportes | CodeBuild-ECR (Fabio) | CodeBuild > Build projects / Report groups | Usado por el pipeline | Almacenamiento de reportes |
| 7 | Servicio ECS, task sets y tareas | Fargate-Manual | ECS > Clusters > servicio | Mantiene destinos en los target groups y ENI en los security groups | Fargate por segundo e IP pública por hora |
| 8 | Task definitions y cluster | Fargate-Manual | ECS > Task definitions / Clusters | Después del servicio | No cobran |
| 9 | ALB, listener y target groups | Fargate-Manual | EC2 > Load balancers / Target groups | Después del servicio y CodeDeploy; antes de los security groups | **Por hora**, aun sin tráfico; IP públicas del ALB |
| 10 | RDS y su grupo de subnets | Fargate-Manual | RDS > Databases / Subnet groups | Antes de su security group | Instancia por hora, almacenamiento, snapshots y backups retenidos |
| 11 | Repositorio ECR | Fargate-Manual (imágenes también del pipeline) | ECR > Repositories | Ninguna | GB almacenados |
| 12 | Bucket S3 de artefactos | Pipeline-CodeDeploy | S3 > Buckets | Ninguna, después del pipeline | Objetos, versiones y cargas multipart incompletas |
| 13 | Grupos de logs | Fargate-Manual, CodeBuild-ECR | CloudWatch > Log groups | Ninguna | GB almacenados |
| 14 | Parámetros SSM | Fargate-Manual | Systems Manager > Parameter Store | Ninguna | No cobran (estándar) |
| 15 | Roles IAM | Todas | IAM > Roles | Después de los recursos que los usan | No cobran |
| 16 | Conexión GitHub | Pipeline-CodeDeploy | Developer Tools > Settings > Connections | Después del pipeline | No cobra |
| 17 | Security groups | Fargate-Manual | EC2 > Security groups | Al final: requieren que no queden ENI | No cobran |
| 18 | Contenedor, volumen e imagen locales | Contenedor-Local (Oscar) | Docker Desktop | Ninguna | No generan cargos AWS |

---

## 1. Conservar evidencias antes de borrar

Comprobar que estén guardados, fuera de AWS:

- Capturas de la guía manual (Anexo B), del pipeline (Anexo B) y de los escenarios A, B y C.
- Para cada escenario: SHA, fecha y hora, ID de ejecución, ID de build, ID de despliegue, resultado de pruebas, imagen y digest, versión observada y registro de disponibilidad.
- Registros de disponibilidad de CloudShell (`~/cb-e3-iN-disponibilidad-*.log`): descargarlos con **Actions > Download file**. CloudShell borra el directorio personal tras 120 días sin uso.
- Logs de interés de CloudWatch (por ejemplo, el diagnóstico del caso C):

  ```bash
  aws logs tail $LOG_GROUP --since 7d > ~/${PREFIX}-logs-ecs.txt
  ```

- Reportes JUnit de CodeBuild, si el informe los cita: descargarlos desde CodeBuild > Report groups.

**Datos de RDS:** son datos de prueba. Esta guía borra la base **sin snapshot final** y **los datos se pierden definitivamente**. Si el equipo decide conservarlos, ver la alternativa de la sección 6.

---

## 2. Cargar variables

En una terminal nueva de CloudShell (`us-east-1`), cargar en este orden:

1. Sección 2.2 y Anexo A de `docs/Entrega-3-Fargate-Manual.md` (o `source ~/e3-env.sh`).
2. Sección 2.2 y Anexo A de `docs/Entrega-3-Pipeline-CodeDeploy.md`.
3. Nombres de la guía de Fabio. Confirmarlos con `docs/Entrega-3-CodeBuild-ECR.md`; los valores siguientes son los propuestos:

```bash
export CODEBUILD_PROJECT=${PREFIX}-build            # confirmar con la guía de Fabio
export CODEBUILD_ROLE=${PREFIX}-codebuild-role      # confirmar con la guía de Fabio
```

Comprobar cuenta, región y prefijo antes de borrar nada:

```bash
echo "Cuenta: ********${ACCOUNT_ID: -4} | Region: $AWS_REGION | Prefijo: $PREFIX"
```

Si algún comando responde `NotFound` / `does not exist`, ese recurso ya no existe: continuar con el siguiente.

---

## 3. Detener disparadores y ejecuciones

El objetivo es que nada vuelva a crear builds, imágenes, task sets ni tareas mientras se borra.

```bash
# 3.1 Bloquear la entrada a Deploy, para que ninguna ejecución pendiente despliegue
aws codepipeline disable-stage-transition --pipeline-name $PIPELINE \
  --stage-name Deploy --transition-type Inbound --reason "Limpieza Entrega 3"

# 3.2 Detener ejecuciones en curso
for id in $(aws codepipeline list-pipeline-executions --pipeline-name $PIPELINE \
    --query "pipelineExecutionSummaries[?status=='InProgress'].pipelineExecutionId" --output text); do
  aws codepipeline stop-pipeline-execution --pipeline-name $PIPELINE \
    --pipeline-execution-id $id --abandon --reason "Limpieza Entrega 3"
done

# 3.3 Builds de CodeBuild en curso
for b in $(aws codebuild list-builds-for-project --project-name $CODEBUILD_PROJECT \
    --query 'ids' --output text); do
  st=$(aws codebuild batch-get-builds --ids $b --query 'builds[0].buildStatus' --output text)
  [ "$st" = "IN_PROGRESS" ] && aws codebuild stop-build --id $b > /dev/null
done
```

Webhook de la Entrega 2: si el proyecto `codebusters-ci-integrante4` aún tiene webhook y la Entrega 2 ya no se evalúa, eliminarlo. El proyecto de la Entrega 2 y su bucket no forman parte de esta limpieza: el equipo decide aparte si se borran.

```bash
aws codebuild delete-webhook --project-name codebusters-ci-integrante4
```

---

## 4. CodeDeploy: despliegues activos, grupo y aplicación

Reducir tareas **no** limpia el CD. Un despliegue en curso mantiene dos task sets y puede volver a crear tareas o cambiar el listener. Hay que cerrarlo primero.

```bash
# 4.1 Despliegues que no han terminado
aws deploy list-deployments --application-name $CD_APP --deployment-group-name $CD_GROUP \
  --include-only-statuses Created Queued InProgress Ready --query deployments --output text
```

- Si la salida está vacía, continuar.
- Si hay un despliegue en la **espera de 5 minutos** tras un éxito, lo más limpio es esperar a que termine (`aws deploy wait deployment-successful --deployment-id <ID>`).
- Si hay uno bloqueado, detenerlo con rollback:

  ```bash
  aws deploy stop-deployment --deployment-id <ID> --auto-rollback-enabled
  ```

```bash
# 4.2 Debe quedar un único task set PRIMARY
aws ecs describe-services --cluster $CLUSTER --services $SERVICE \
  --query 'services[0].taskSets[].[id,status,runningCount]' --output text

# 4.3 Pipeline: ya no hay ejecuciones en curso
aws codepipeline delete-pipeline --name $PIPELINE

# 4.4 Grupo de despliegue y aplicación
aws deploy delete-deployment-group --application-name $CD_APP --deployment-group-name $CD_GROUP
aws deploy delete-application --application-name $CD_APP

# 4.5 Alarmas
aws cloudwatch delete-alarms --alarm-names ${PREFIX}-tg-blue-unhealthy ${PREFIX}-tg-green-unhealthy
```

Verificación:

```bash
aws codepipeline list-pipelines --query "pipelines[?starts_with(name,'${PREFIX}')].name" --output text
aws deploy list-applications --query "applications[?starts_with(@,'${PREFIX}')]" --output text
aws cloudwatch describe-alarms --alarm-name-prefix ${PREFIX}- --query 'MetricAlarms[].AlarmName' --output text
```

Las tres deben salir vacías.

---

## 5. CodeBuild (aporte de Fabio)

> Pendiente de confirmar con `docs/Entrega-3-CodeBuild-ECR.md`. Si la guía de Fabio crea recursos adicionales, agregarlos aquí.

```bash
# Grupos de reportes del proyecto (JUnit). Sus nombres empiezan por el del proyecto.
for rg in $(aws codebuild list-report-groups --query 'reportGroups' --output text \
    | tr '\t' '\n' | grep ":report-group/${CODEBUILD_PROJECT}-"); do
  aws codebuild delete-report-group --arn $rg --delete-reports
done

aws codebuild delete-project --name $CODEBUILD_PROJECT
aws logs delete-log-group --log-group-name /aws/codebuild/${CODEBUILD_PROJECT}
```

Verificación:

```bash
aws codebuild list-projects --query "projects[?starts_with(@,'${PREFIX}')]" --output text
aws codebuild list-report-groups --output text | grep -c ":report-group/${PREFIX}" || true
```

El primero debe salir vacío y el conteo debe ser 0.

---

## 6. Servicio ECS, task definitions y cluster (aporte de Jose Miguel)

Corresponde al paso 1 de la sección 14 de la guía manual. `delete-service --force` elimina el servicio con sus task sets.

```bash
aws ecs update-service --cluster $CLUSTER --service $SERVICE --desired-count 0 > /dev/null
aws ecs delete-service --cluster $CLUSTER --service $SERVICE --force > /dev/null
aws ecs wait services-inactive --cluster $CLUSTER --services $SERVICE

# Tareas sueltas (por ejemplo, una init-db que siguiera corriendo)
for t in $(aws ecs list-tasks --cluster $CLUSTER --query taskArns --output text); do
  aws ecs stop-task --cluster $CLUSTER --task $t --reason "Limpieza Entrega 3" > /dev/null
done
aws ecs list-tasks --cluster $CLUSTER --query taskArns --output text   # vacío

# Todas las revisiones: manuales y las registradas por el pipeline
for td in $(aws ecs list-task-definitions --family-prefix $TASK_FAMILY \
    --query taskDefinitionArns --output text); do
  aws ecs deregister-task-definition --task-definition $td > /dev/null
done

aws ecs delete-cluster --cluster $CLUSTER > /dev/null
```

Las revisiones dadas de baja quedan como `INACTIVE` y no cobran. Si se quiere borrarlas por completo: `aws ecs delete-task-definitions --task-definitions <arn> ...` (hasta 10 por llamada).

---

## 7. ALB, listener y target groups (aporte de Jose Miguel)

Solo después de eliminar el servicio y el grupo de CodeDeploy, que los referencian. Borrar el ALB elimina también su listener.

```bash
aws elbv2 delete-load-balancer --load-balancer-arn $ALB_ARN
aws elbv2 wait load-balancers-deleted --load-balancer-arns $ALB_ARN
aws elbv2 delete-target-group --target-group-arn $TG_BLUE_ARN
aws elbv2 delete-target-group --target-group-arn $TG_GREEN_ARN
```

Si un target group responde `ResourceInUse`, el listener o el servicio aún existen: revisar las secciones 4 y 6.

---

## 8. RDS (aporte de Jose Miguel)

> **Advertencia: se pierden todos los datos de la base, de forma irreversible.**

Decisiones explícitas de esta guía:

| Tema | Decisión | Motivo |
| --- | --- | --- |
| Snapshot final | **No** se crea (`--skip-final-snapshot`) | Datos de prueba; un snapshot sigue cobrando almacenamiento |
| Backups automáticos | Se eliminan (`--delete-automated-backups`) | La guía manual los crea con retención 0; se fuerza por si alguien la cambió |
| Protección contra borrado | Se desactiva si estuviera activa | La guía manual la crea desactivada |

```bash
# Protección contra borrado (solo si está activa)
aws rds describe-db-instances --db-instance-identifier $DB_ID \
  --query 'DBInstances[0].DeletionProtection' --output text
# Si responde True:
aws rds modify-db-instance --db-instance-identifier $DB_ID \
  --no-deletion-protection --apply-immediately > /dev/null

aws rds delete-db-instance --db-instance-identifier $DB_ID \
  --skip-final-snapshot --delete-automated-backups > /dev/null
aws rds wait db-instance-deleted --db-instance-identifier $DB_ID      # 5 a 10 min
aws rds delete-db-subnet-group --db-subnet-group-name ${PREFIX}-db-subnets
```

**Alternativa, si el equipo decide conservar los datos:** en lugar de `--skip-final-snapshot`, usar `--final-db-snapshot-identifier ${PREFIX}-db-final`. Ese snapshot cobra por GB al mes hasta que se elimine con `aws rds delete-db-snapshot`.

Snapshots manuales y backups retenidos que puedan quedar:

```bash
aws rds describe-db-snapshots --snapshot-type manual \
  --query "DBSnapshots[?starts_with(DBInstanceIdentifier,'${PREFIX}')].DBSnapshotIdentifier" --output text
aws rds describe-db-instance-automated-backups \
  --query "DBInstanceAutomatedBackups[?starts_with(DBInstanceIdentifier,'${PREFIX}')].DBInstanceIdentifier" --output text
```

Ambos deben salir vacíos, salvo el snapshot final de la alternativa si se decidió conservarlo.

---

## 9. ECR y S3

### 9.1 Repositorio ECR

Contiene la imagen inicial de la guía manual y todas las publicadas por el pipeline (una por SHA).

```bash
aws ecr describe-images --repository-name $ECR_REPO --query 'length(imageDetails)'   # cuántas hay
aws ecr delete-repository --repository-name $ECR_REPO --force > /dev/null
```

`--force` borra el repositorio con sus imágenes.

### 9.2 Bucket de artefactos del pipeline

Hay que vaciarlo, incluidas las versiones y las cargas multipart incompletas, antes de borrarlo.

```bash
# Cargas multipart incompletas (no se ven como objetos, pero cobran)
aws s3api list-multipart-uploads --bucket $ARTIFACT_BUCKET \
  --query 'Uploads[].[Key,UploadId]' --output text | while read -r key id; do
  [ -z "$key" ] || [ "$key" = "None" ] && continue
  aws s3api abort-multipart-upload --bucket $ARTIFACT_BUCKET --key "$key" --upload-id "$id"
done

# Objetos actuales
aws s3 rm s3://$ARTIFACT_BUCKET --recursive --quiet

# Versiones y marcadores de borrado (solo existen si alguien activó el versionado)
aws s3api get-bucket-versioning --bucket $ARTIFACT_BUCKET --query Status --output text
for tipo in Versions DeleteMarkers; do
  aws s3api list-object-versions --bucket $ARTIFACT_BUCKET \
    --query "${tipo}[].[Key,VersionId]" --output text | while read -r key ver; do
    [ -z "$key" ] || [ "$key" = "None" ] && continue
    aws s3api delete-object --bucket $ARTIFACT_BUCKET --key "$key" --version-id "$ver" > /dev/null
  done
done

aws s3api delete-bucket --bucket $ARTIFACT_BUCKET
```

Si la guía de Fabio crea otro bucket (por ejemplo, para caché de CodeBuild), vaciarlo y borrarlo con los mismos pasos.

---

## 10. Logs, secretos, roles y conexión

```bash
# 10.1 CloudWatch Logs (el de CodeBuild se borró en la sección 5)
aws logs delete-log-group --log-group-name $LOG_GROUP

# 10.2 Parámetros SSM (secretos)
aws ssm delete-parameter --name /${PREFIX}/DATABASE_URL
aws ssm delete-parameter --name /${PREFIX}/JWT_SECRET_KEY

# 10.3 Rol de ejecución ECS (Jose Miguel)
aws iam detach-role-policy --role-name $EXEC_ROLE \
  --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy
aws iam delete-role-policy --role-name $EXEC_ROLE --policy-name leer-parametros-ssm
aws iam delete-role --role-name $EXEC_ROLE

# 10.4 Rol de CodeDeploy (Juan David)
aws iam detach-role-policy --role-name $CD_ROLE \
  --policy-arn arn:aws:iam::aws:policy/AWSCodeDeployRoleForECS
aws iam delete-role --role-name $CD_ROLE

# 10.5 Rol del pipeline (Juan David)
aws iam delete-role-policy --role-name $PIPELINE_ROLE --policy-name pipeline-entrega3
aws iam delete-role --role-name $PIPELINE_ROLE
```

Rol de CodeBuild (Fabio): sus políticas dependen de su guía. Quitar todas antes de borrarlo:

```bash
for p in $(aws iam list-attached-role-policies --role-name $CODEBUILD_ROLE \
    --query 'AttachedPolicies[].PolicyArn' --output text); do
  aws iam detach-role-policy --role-name $CODEBUILD_ROLE --policy-arn $p
done
for p in $(aws iam list-role-policies --role-name $CODEBUILD_ROLE \
    --query 'PolicyNames' --output text); do
  aws iam delete-role-policy --role-name $CODEBUILD_ROLE --policy-name $p
done
aws iam delete-role --role-name $CODEBUILD_ROLE
```

Si la consola de CodeBuild creó una política administrada por el cliente (`CodeBuildBasePolicy-...`), eliminarla también en IAM > Policies, una vez separada del rol.

No eliminar `AWSServiceRoleForECS` ni otros roles vinculados a servicios: los crea AWS, no cobran y pueden usarlos otros trabajos.

Conexión GitHub: eliminarla solo si la creó la Entrega 3 y nada más la usa (por ejemplo, el proyecto de la Entrega 2).

```bash
aws codeconnections delete-connection --connection-arn $CONNECTION_ARN
```

No desinstalar la GitHub App del repositorio en GitHub: la comparten los cuatro integrantes.

---

## 11. Red

La Entrega 3 **no crea** NAT Gateway, Elastic IP, VPC ni subnets: usa la VPC por defecto y una IP pública en cada tarea. Las IP públicas de las tareas y de los nodos del ALB se liberan al borrar las tareas y el ALB.

```bash
# 11.1 Interfaces que aún usan los security groups (deben ir desapareciendo)
aws ec2 describe-network-interfaces \
  --filters Name=group-id,Values=$ALB_SG,$TASK_SG,$RDS_SG \
  --query 'NetworkInterfaces[].[NetworkInterfaceId,Status,Description]' --output table

# 11.2 Security groups, en este orden por sus referencias
aws ec2 delete-security-group --group-id $RDS_SG
aws ec2 delete-security-group --group-id $TASK_SG
aws ec2 delete-security-group --group-id $ALB_SG
```

Si responde `DependencyViolation`, una interfaz del ALB, de una tarea o de RDS todavía se está liberando. Esperar unos minutos y repetir. No borrar a mano interfaces que no pertenezcan a estos grupos.

Comprobar que no haya recursos de red con cobro creados por error:

```bash
aws ec2 describe-nat-gateways --filter Name=state,Values=available,pending \
  --query 'NatGateways[].[NatGatewayId,VpcId]' --output text
aws ec2 describe-addresses --query 'Addresses[].[PublicIp,AllocationId,AssociationId]' --output text
```

Si aparece algo, comprobar si es de la Entrega 3 antes de borrarlo. Puede ser de otro trabajo de la cuenta.

---

## 12. Limpieza local (aporte de Oscar)

En la máquina donde se siguió `docs/Entrega-3-Contenedor-Local.md`, sección 10. No genera cargos AWS. Con PowerShell y las variables de esa guía:

```powershell
docker stop $Container
docker rm $Container
docker volume rm $Volume      # borra definitivamente los datos SQLite locales
docker image rm $Image        # opcional
Remove-Variable Token, LocalSecret, RuntimeArgs -ErrorAction SilentlyContinue
```

En CloudShell, si se construyeron imágenes o se clonó el repositorio:

```bash
docker image ls | grep ${ECR_REPO} && docker image rm $(docker image ls -q ${ECR_URI})
rm -rf /tmp/repo /tmp/${PREFIX}-*.json
```

No ejecutar `docker system prune` ni borrados generales.

---

## 13. Verificación final por región

En `us-east-1`, todos los comandos deben salir vacíos (o `0`), salvo recursos de otros trabajos:

```bash
aws codepipeline list-pipelines --query "pipelines[?starts_with(name,'${PREFIX}')].name" --output text
aws deploy list-applications --query "applications[?starts_with(@,'${PREFIX}')]" --output text
aws codebuild list-projects --query "projects[?starts_with(@,'${PREFIX}')]" --output text
aws ecs list-clusters --query "clusterArns[?contains(@,'${PREFIX}')]" --output text
aws elbv2 describe-load-balancers --query "LoadBalancers[?starts_with(LoadBalancerName,'${PREFIX}')].LoadBalancerName" --output text
aws elbv2 describe-target-groups --query "TargetGroups[?starts_with(TargetGroupName,'${PREFIX}')].TargetGroupName" --output text
aws rds describe-db-instances --query "DBInstances[?starts_with(DBInstanceIdentifier,'${PREFIX}')].DBInstanceIdentifier" --output text
aws rds describe-db-snapshots --query "DBSnapshots[?starts_with(DBInstanceIdentifier,'${PREFIX}')].DBSnapshotIdentifier" --output text
aws ecr describe-repositories --query "repositories[?starts_with(repositoryName,'${PREFIX}')].repositoryName" --output text
aws s3api list-buckets --query "Buckets[?starts_with(Name,'${PREFIX}')].Name" --output text
aws logs describe-log-groups --query "logGroups[?contains(logGroupName,'${PREFIX}')].logGroupName" --output text
aws ssm describe-parameters --parameter-filters Key=Name,Option=BeginsWith,Values=/${PREFIX}/ --query 'Parameters[].Name' --output text
aws cloudwatch describe-alarms --alarm-name-prefix ${PREFIX}- --query 'MetricAlarms[].AlarmName' --output text
aws iam list-roles --query "Roles[?starts_with(RoleName,'${PREFIX}')].RoleName" --output text
aws codeconnections list-connections --query "Connections[?starts_with(ConnectionName,'${PREFIX}')].ConnectionName" --output text
aws ec2 describe-security-groups --filters Name=group-name,Values="${PREFIX}-*" --query 'SecurityGroups[].GroupName' --output text
```

Los recursos se crearon en `us-east-1`. Para descartar que alguno quedara por error en otra región (por ejemplo, por una consola en otra región), revisar los que más cobran:

```bash
for r in $(aws ec2 describe-regions --query 'Regions[].RegionName' --output text); do
  alb=$(aws elbv2 describe-load-balancers --region $r --query 'length(LoadBalancers)' --output text 2>/dev/null)
  rds=$(aws rds describe-db-instances --region $r --query 'length(DBInstances)' --output text 2>/dev/null)
  ecs=$(aws ecs list-clusters --region $r --query 'length(clusterArns)' --output text 2>/dev/null)
  nat=$(aws ec2 describe-nat-gateways --region $r --filter Name=state,Values=available --query 'length(NatGateways)' --output text 2>/dev/null)
  echo "$r ALB=$alb RDS=$rds ECS=$ecs NAT=$nat"
done
```

Cualquier valor distinto de 0 debe revisarse para confirmar si pertenece a otro trabajo.

### Costos posteriores

- Revisar **Billing and Cost Management > Bills** y **Cost Explorer** filtrando por servicio (ELB, ECS/Fargate, RDS, EC2-Other para IP públicas, ECR, S3, CloudWatch).
- La información de facturación llega con **24 a 48 horas de retraso**: repetir la revisión uno o dos días después de la limpieza y confirmar que los cargos diarios bajaron a cero para esos servicios.
- Es normal que aparezcan cargos de las horas previas a la limpieza.

Evidencia `L-01`: salida de la verificación final sin recursos del prefijo. `L-02`: Cost Explorer uno o dos días después.

---

## Registro de ejecución

| Integrante | Fecha de limpieza | Verificación final vacía | Revisión de costos (fecha) | Observaciones |
| --- | --- | --- | --- | --- |
| 1 - Oscar | | | | |
| 2 - Jose Miguel | | | | |
| 3 - Fabio | | | | |
| 4 - Juan David | | | | |
