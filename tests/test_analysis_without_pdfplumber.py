"""The analyses (Q1-Q4 and the exploratory script) run on the committed extracted data
with the standard library only: importing them must not import pdfplumber (plan §11)."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# A fresh interpreter in which any import of pdfplumber raises.
PROBE = """
import importlib, sys
class Block:
    def find_spec(self, name, path=None, target=None):
        if name == "pdfplumber" or name.startswith("pdfplumber."):
            raise ImportError("pdfplumber is blocked in this test")
        return None
sys.meta_path.insert(0, Block())
sys.modules.pop("pdfplumber", None)
sys.path.insert(0, sys.argv[1])
for mod in sys.argv[2:]:
    importlib.import_module(mod)
assert "pdfplumber" not in sys.modules
print("ok")
"""

MODULES = ["src.q1_reproduce", "src.q2_robust", "src.q3_validity", "src.q4_change",
           "src.explore_udst"]


def test_analyses_import_without_pdfplumber():
    r = subprocess.run([sys.executable, "-I", "-c", PROBE, str(ROOT), *MODULES],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == "ok"


def test_the_guard_does_block_pdfplumber():
    r = subprocess.run([sys.executable, "-I", "-c", PROBE, str(ROOT), "src.extract.annex"],
                       capture_output=True, text=True)
    assert r.returncode != 0 and "pdfplumber is blocked" in r.stderr
