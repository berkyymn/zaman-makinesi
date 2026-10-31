"""
GitHub Actions'ta çalışır: kurulum dosyasından version.json ve sürüm notlarını üretir.
    python packaging/write_version_json.py dist/ZamanMakinesi-Setup.exe
"""

import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from version import __version__  # noqa: E402

setup = Path(sys.argv[1])
release = json.loads((ROOT / "release.json").read_text(encoding="utf-8"))
# min_supported yeni sürümden büyük olursa herkes sonsuza kadar "güncelle" ekranında kalır
if tuple(map(int, release["min_supported"].split("."))) > tuple(map(int, __version__.split("."))):
    raise SystemExit(f'release.json: min_supported ({release["min_supported"]}) sürümden ({__version__}) büyük olamaz')

repo = os.environ["GITHUB_REPOSITORY"]
tag = os.environ["GITHUB_REF_NAME"]

data = {
    "latest": __version__,
    "min_supported": release["min_supported"],
    "url": f"https://github.com/{repo}/releases/download/{tag}/{setup.name}",
    "sha256": hashlib.sha256(setup.read_bytes()).hexdigest(),
    "notes": release.get("notes", ""),
}
(setup.parent / "version.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

download = f"https://github.com/{repo}/releases/latest/download/{setup.name}"
notes = (data["notes"] + "\n\n" if data["notes"] else "") + f"İndir: {download}\n"
(setup.parent / "notes.md").write_text(notes, encoding="utf-8")
print(json.dumps(data, indent=2))  # Windows konsolu Türkçe karakter basamayabiliyor
