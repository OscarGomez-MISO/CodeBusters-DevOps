import os
from pathlib import Path
import subprocess
import sys


def main():
    root = Path(__file__).resolve().parents[1]
    artifact = root / "dist" / "blacklists.zip"
    report = root / "reports" / "pytest.xml"
    report.parent.mkdir(exist_ok=True)
    # A failed rerun must not leave an older deployable ZIP in the output path.
    artifact.unlink(missing_ok=True)
    report.unlink(missing_ok=True)
    revision = os.getenv("CODEBUILD_RESOLVED_SOURCE_VERSION", "local")
    print("CI source: " + revision, flush=True)
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q",
         "--ignore=tests/test_postgres.py", "--junitxml=reports/pytest.xml"],
        cwd=root,
    )
    if result.returncode:
        print("Tests failed. No deployable artifact generated.", flush=True)
        return result.returncode

    result = subprocess.run([sys.executable, "scripts/package.py"], cwd=root)
    if result.returncode:
        artifact.unlink(missing_ok=True)
        return result.returncode
    if not artifact.is_file():
        print("Packaging did not produce dist/blacklists.zip.", flush=True)
        return 1
    print("CI passed. Artifact ready: dist/blacklists.zip", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
