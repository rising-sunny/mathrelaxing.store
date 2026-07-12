from pathlib import Path

ROOT = Path("/var/www/mathrelaxing.store")
TERMS = ("run_auto_pin_cycle", "auto-pin", "pinterest_jobs", "pinterest")
SUFFIXES = {".py", ".service", ".timer", ".sh", ".txt", ".toml"}

for path in ROOT.rglob("*"):
    if not path.is_file() or path.suffix not in SUFFIXES:
        continue
    if "__pycache__" in path.parts:
        continue
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        continue
    for i, line in enumerate(text.splitlines(), 1):
        if any(term in line.lower() for term in TERMS):
            print(f"{path.relative_to(ROOT)}:{i}:{line[:220]}")
