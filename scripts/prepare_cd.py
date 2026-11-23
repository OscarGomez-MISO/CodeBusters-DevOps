"""Genera los artefactos de CD (Entrega 3) en dist/cd/.

Salida, en la raiz del directorio (contrato con la accion CodeDeployToECS):
  taskdef.json      deploy/taskdef.template.json con los parametros de la cuenta
                    resueltos y la imagen reservada como <IMAGE1_NAME>
  appspec.yaml      copia de deploy/appspec.yaml (<TASK_DEFINITION> intacto)
  imageDetail.json  {"ImageURI": "<repo>:<sha>"} de la imagen publicada

Los parametros de cuenta llegan como variables de entorno del proyecto
CodeBuild; nunca se escriben en el repositorio.

New Relic (Entrega 4) es opcional y por cuenta. Si el proyecto CodeBuild define
NR_APP_NAME y SSM_NR_LICENSE_ARN, la task definition activa el agente: agrega
NEW_RELIC_ENABLED=true, el nombre de la app y la licencia como secreto de SSM,
que ECS resuelve al arrancar la tarea. Sin esas variables la task definition
queda igual que en la Entrega 3. OBS_LAB_ENABLED y NEW_RELIC_HOST son opcionales.
"""
import json
import os
from pathlib import Path
import re
import string
import sys

REQUIRED = (
    "TASK_FAMILY",
    "EXEC_ROLE_ARN",
    "SSM_DB_ARN",
    "SSM_JWT_ARN",
    "LOG_GROUP",
    "AWS_REGION",
    "IMAGE_URI",
)
NEW_RELIC_PAIR = ("NR_APP_NAME", "SSM_NR_LICENSE_ARN")
SSM_ARN = re.compile(r"arn:aws[a-z-]*:ssm:[a-z0-9-]+:\d{12}:parameter/\S+")
APP_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}")
CONTAINER_NAME = "blacklists"
CONTAINER_PORT = 5000
IMAGE_PLACEHOLDER = "<IMAGE1_NAME>"
TASKDEF_PLACEHOLDER = "<TASK_DEFINITION>"


def fail(message):
    print("prepare_cd: " + message, file=sys.stderr, flush=True)
    return 1


def add_optional_runtime(container, env):
    """Agrega New Relic y el laboratorio de errores si la cuenta los define."""
    app_name, license_arn = (env.get(name, "").strip() for name in NEW_RELIC_PAIR)
    lab = env.get("OBS_LAB_ENABLED", "").strip().lower()
    host = env.get("NEW_RELIC_HOST", "").strip()

    if bool(app_name) != bool(license_arn):
        return "NR_APP_NAME y SSM_NR_LICENSE_ARN deben definirse juntas o ninguna"
    if lab not in ("", "true", "false"):
        return "OBS_LAB_ENABLED debe ser true o false"
    if (host or lab) and not app_name:
        return "NEW_RELIC_HOST y OBS_LAB_ENABLED requieren NR_APP_NAME y SSM_NR_LICENSE_ARN"
    if not app_name:
        return None
    if not APP_NAME.fullmatch(app_name):
        return "NR_APP_NAME solo admite letras, numeros, punto, guion y guion bajo"
    if not SSM_ARN.fullmatch(license_arn):
        return "SSM_NR_LICENSE_ARN debe ser el ARN de un parametro de SSM"
    if host and not re.fullmatch(r"[a-z0-9.-]+\.nr-data\.net", host):
        return "NEW_RELIC_HOST debe ser un collector de New Relic (*.nr-data.net)"

    environment = container.setdefault("environment", [])
    environment += [
        {"name": "NEW_RELIC_ENABLED", "value": "true"},
        {"name": "NEW_RELIC_APP_NAME", "value": app_name},
        {"name": "NEW_RELIC_LOG", "value": "stderr"},
        {"name": "OBS_LAB_ENABLED", "value": lab or "false"},
    ]
    if host:
        environment.append({"name": "NEW_RELIC_HOST", "value": host})
    container.setdefault("secrets", []).append(
        {"name": "NEW_RELIC_LICENSE_KEY", "valueFrom": license_arn})
    return None


def main(root=None, env=None):
    root = Path(root or Path(__file__).resolve().parents[1])
    env = os.environ if env is None else env
    out = root / "dist" / "cd"

    missing = [name for name in REQUIRED if not env.get(name, "").strip()]
    if missing:
        return fail("faltan variables de entorno: " + ", ".join(missing))
    values = {name: env[name].strip() for name in REQUIRED}

    # El tag debe ser el SHA completo del commit (contrato del plan de trabajo).
    if not re.fullmatch(r"[^:@\s]+:[0-9a-f]{40}", values["IMAGE_URI"]):
        return fail("IMAGE_URI debe ser <repositorio>:<sha de 40 caracteres>")

    template = (root / "deploy" / "taskdef.template.json").read_text(encoding="utf-8")
    try:
        taskdef = json.loads(string.Template(template).substitute(values))
    except (KeyError, ValueError) as error:
        return fail("plantilla de task definition invalida: {}".format(error))

    containers = taskdef["containerDefinitions"]
    if len(containers) != 1 or containers[0]["name"] != CONTAINER_NAME:
        return fail("la task definition debe tener un unico contenedor 'blacklists'")
    if containers[0]["image"] != IMAGE_PLACEHOLDER:
        return fail("la imagen de la plantilla debe ser " + IMAGE_PLACEHOLDER)
    ports = [m["containerPort"] for m in containers[0]["portMappings"]]
    if ports != [CONTAINER_PORT]:
        return fail("el contenedor debe exponer solo el puerto 5000")

    error = add_optional_runtime(containers[0], env)
    if error:
        return fail(error)

    appspec = (root / "deploy" / "appspec.yaml").read_text(encoding="utf-8")
    for expected in (TASKDEF_PLACEHOLDER, 'ContainerName: "blacklists"', "ContainerPort: 5000"):
        if expected not in appspec:
            return fail("deploy/appspec.yaml no contiene " + expected)

    out.mkdir(parents=True, exist_ok=True)
    for stale in out.iterdir():
        stale.unlink()
    (out / "taskdef.json").write_text(json.dumps(taskdef, indent=2) + "\n", encoding="utf-8")
    (out / "appspec.yaml").write_text(appspec, encoding="utf-8")
    (out / "imageDetail.json").write_text(
        json.dumps({"ImageURI": values["IMAGE_URI"]}) + "\n", encoding="utf-8"
    )
    monitoring = "New Relic activo como " + env["NR_APP_NAME"].strip() \
        if env.get("NR_APP_NAME", "").strip() else "New Relic desactivado"
    print("prepare_cd: artefactos listos en dist/cd/ para " + values["IMAGE_URI"].split("/")[-1]
          + " (" + monitoring + ")", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
