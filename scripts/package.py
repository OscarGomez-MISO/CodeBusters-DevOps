from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

root = Path(__file__).resolve().parents[1]
output = root / "dist" / "blacklists.zip"
output.parent.mkdir(exist_ok=True)
files = [root / "application.py", root / "requirements.txt"]
files.extend((root / "app").rglob("*.py"))
files.extend((root / ".ebextensions").glob("*.config"))
with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
    for path in sorted(files):
        archive.write(path, path.relative_to(root).as_posix())
print(output)
