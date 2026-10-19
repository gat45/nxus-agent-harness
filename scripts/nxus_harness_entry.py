"""Point d'entree pour l'empaquetage PyInstaller (voir Makefile/README pour
`pyinstaller`). Pas utilise par l'execution normale `python -m nxus_harness` ;
necessaire car PyInstaller a besoin d'un script, pas d'un module de package."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from nxus_harness.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
