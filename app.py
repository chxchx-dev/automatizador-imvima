from __future__ import annotations

import os
import sys
from pathlib import Path


def _restart_with_project_venv() -> None:
    if getattr(sys, "frozen", False) or sys.prefix != sys.base_prefix:
        return

    project_dir = Path(__file__).resolve().parent
    if os.name == "nt":
        interpreter = project_dir / ".venv" / "Scripts" / "python.exe"
    else:
        interpreter = project_dir / ".venv" / "bin" / "python"

    if interpreter.is_file():
        os.execv(str(interpreter), [str(interpreter), str(Path(__file__).resolve()), *sys.argv[1:]])


def main() -> None:
    _restart_with_project_venv()
    from sigavi.ui import run_app

    run_app()


if __name__ == "__main__":
    main()
