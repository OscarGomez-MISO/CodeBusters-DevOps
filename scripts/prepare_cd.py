"""Genera los artefactos de CD (Entrega 3) en dist/cd/.

Salida, en la raiz del directorio (contrato con la accion CodeDeployToECS):
  taskdef.json      deploy/taskdef.template.json con los parametros de la cuenta
                    resueltos y la imagen reservada como <IMAGE1_NAME>
  appspec.yaml      copia de deploy/appspec.yaml (<TASK_DEFINITION> intacto)
  imageDetail.json  {"ImageURI": "<repo>:<sha>"} de la imagen publicada

Los parametros de cuenta llegan como variables de entorno del proyecto
CodeBuild; nunca se escriben en el repositorio.
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
CONTAINER_NAME = "blacklists"
CONTAINER_PORT = 5000
IMAGE_PLACEHOLDER = "<IMAGE1_NAME>"
TASKDEF_PLACEHOLDER = "<TASK_DEFINITION>"


def fail(message):
    print("prepare_cd: " + message, file=sys.stderr, flush=True)
    return 1


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
    print("prepare_cd: artefactos listos en dist/cd/ para " + values["IMAGE_URI"].split("/")[-1],
          flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
