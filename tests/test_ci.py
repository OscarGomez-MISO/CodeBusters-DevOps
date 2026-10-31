from pathlib import Path
import shutil
import subprocess
import sys
from xml.etree import ElementTree

import pytest


@pytest.mark.parametrize("test_passes", [True, False], ids=["success", "failure"])
def test_ci_packages_only_after_passing_tests(tmp_path, test_passes):
    root = Path(__file__).resolve().parents[1]
    (tmp_path / "scripts").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "dist").mkdir()
    shutil.copyfile(root / "scripts" / "ci.py", tmp_path / "scripts" / "ci.py")
    (tmp_path / "tests" / "test_example.py").write_text(
        "def test_example():\n    assert {}\n".format(test_passes), encoding="utf-8"
    )
    (tmp_path / "scripts" / "package.py").write_text(
        "from pathlib import Path\n"
        "Path('dist/blacklists.zip').write_bytes(b'new-artifact')\n",
        encoding="utf-8",
    )
    artifact = tmp_path / "dist" / "blacklists.zip"
    artifact.write_bytes(b'old-artifact')

    result = subprocess.run([sys.executable, "scripts/ci.py"], cwd=tmp_path,
                            capture_output=True, text=True)
    assert result.returncode == (0 if test_passes else 1), result.stdout + result.stderr
    report = ElementTree.parse(tmp_path / "reports" / "pytest.xml").getroot()
    suite = report.find("testsuite")
    assert suite.attrib["failures"] == ("0" if test_passes else "1")
    if test_passes:
        assert artifact.read_bytes() == b'new-artifact'
    else:
        assert not artifact.exists()
