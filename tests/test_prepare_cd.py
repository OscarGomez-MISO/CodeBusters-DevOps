import json
from pathlib import Path
import shutil
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import prepare_cd  # noqa: E402

SHA = "0123456789abcdef0123456789abcdef01234567"
ENV = {
    "TASK_FAMILY": "cb-e3-i9-blacklists",
    "EXEC_ROLE_ARN": "arn:aws:iam::111122223333:role/cb-e3-i9-ecs-exec-role",
    "SSM_DB_ARN": "arn:aws:ssm:us-east-1:111122223333:parameter/cb-e3-i9/DATABASE_URL",
    "SSM_JWT_ARN": "arn:aws:ssm:us-east-1:111122223333:parameter/cb-e3-i9/JWT_SECRET_KEY",
    "LOG_GROUP": "/ecs/cb-e3-i9-blacklists",
    "AWS_REGION": "us-east-1",
    "IMAGE_URI": "111122223333.dkr.ecr.us-east-1.amazonaws.com/cb-e3-i9-blacklists:" + SHA,
}


@pytest.fixture
def repo(tmp_path):
    shutil.copytree(ROOT / "deploy", tmp_path / "deploy")
    return tmp_path


def test_generates_the_three_cd_artifacts(repo):
    assert prepare_cd.main(repo, ENV) == 0
    out = repo / "dist" / "cd"
    assert sorted(p.name for p in out.iterdir()) == [
        "appspec.yaml", "imageDetail.json", "taskdef.json"]

    taskdef = json.loads((out / "taskdef.json").read_text())
    container = taskdef["containerDefinitions"][0]
    assert taskdef["family"] == ENV["TASK_FAMILY"]
    assert taskdef["executionRoleArn"] == ENV["EXEC_ROLE_ARN"]
    assert container["name"] == "blacklists"
    assert container["image"] == "<IMAGE1_NAME>"
    assert container["portMappings"][0]["containerPort"] == 5000
    assert {s["valueFrom"] for s in container["secrets"]} == {
        ENV["SSM_DB_ARN"], ENV["SSM_JWT_ARN"]}
    assert "${" not in (out / "taskdef.json").read_text()

    assert json.loads((out / "imageDetail.json").read_text()) == {"ImageURI": ENV["IMAGE_URI"]}
    appspec = (out / "appspec.yaml").read_text()
    assert appspec == (ROOT / "deploy" / "appspec.yaml").read_text()
    assert "<TASK_DEFINITION>" in appspec


def test_fails_without_account_parameters(repo, capsys):
    env = dict(ENV, SSM_JWT_ARN="")
    assert prepare_cd.main(repo, env) == 1
    assert "SSM_JWT_ARN" in capsys.readouterr().err
    assert not (repo / "dist" / "cd").exists()


@pytest.mark.parametrize("tag", ["latest", SHA[:7], ""])
def test_requires_full_commit_sha_as_image_tag(repo, tag):
    env = dict(ENV, IMAGE_URI=ENV["IMAGE_URI"].rsplit(":", 1)[0] + ":" + tag)
    assert prepare_cd.main(repo, env) == 1


def test_removes_stale_artifacts(repo):
    out = repo / "dist" / "cd"
    out.mkdir(parents=True)
    (out / "imagedefinitions.json").write_text("[]")
    assert prepare_cd.main(repo, ENV) == 0
    assert not (out / "imagedefinitions.json").exists()
