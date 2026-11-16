"""Download (only if missing) and SHA-256-verify the source PDFs in data/source_manifest.csv.

Run as: python -I tools/fetch_sources.py   (stdlib only; standalone)
"""
import csv
import hashlib
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data" / "source_manifest.csv"
CHUNK = 1 << 20


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(CHUNK), b""):
            h.update(block)
    return h.hexdigest()


def verify(path: Path, sha256: str) -> None:
    """Raise ValueError if the file's SHA-256 differs from the manifest digest."""
    actual = sha256_of(Path(path))
    if actual != sha256.lower():
        raise ValueError(f"SHA-256 mismatch for {path}: expected {sha256}, got {actual}")


def read_manifest(manifest: Path = MANIFEST) -> list[dict]:
    with open(manifest, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def download(url: str, dest: Path, sha256: str) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")
    req = urllib.request.Request(url, headers={"User-Agent": "tb-state-score-fetch/1.0"})
    with urllib.request.urlopen(req, timeout=120) as resp, open(part, "wb") as out:
        while block := resp.read(CHUNK):
            out.write(block)
    try:
        verify(part, sha256)
    except ValueError:
        part.unlink(missing_ok=True)
        raise
    part.replace(dest)


def main() -> int:
    rows = read_manifest()
    for row in rows:
        dest = ROOT / row["file"]
        if not dest.exists():
            print(f"downloading {row['file']}")
            download(row["url"], dest, row["sha256"])
        verify(dest, row["sha256"])
    print(f"{len(rows)} files verified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
