"""Launch a packaged app against disposable data and check startup health."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path


def main() -> None:
    executable = Path(sys.argv[1]).resolve()
    if not executable.is_file():
        raise SystemExit(f"Packaged executable missing: {executable}")
    with tempfile.TemporaryDirectory(prefix="blipkit-package-") as directory:
        root = Path(directory)
        log = root / "launch.log"
        environment = dict(os.environ, BLIPKIT_DATA_DIR=str(root / "data"))
        with log.open("w", encoding="utf-8") as output:
            process = subprocess.Popen(
                [str(executable)], env=environment, stdout=output, stderr=subprocess.STDOUT
            )
            try:
                process.wait(timeout=8)
                raise RuntimeError(f"App exited during startup: {process.returncode}")
            except subprocess.TimeoutExpired:
                pass
            finally:
                if process.poll() is None:
                    process.terminate()
                    process.wait(timeout=10)
        contents = log.read_text(encoding="utf-8", errors="replace")
        if "Traceback" in contents:
            raise RuntimeError(contents)
        if not (root / "data/Projects/Starter.bkproj/project.json").is_file():
            raise RuntimeError(f"Starter project was not created. Log: {contents}")
    print("Packaged app stayed alive for 8 seconds, created its project, and logged no traceback.")


if __name__ == "__main__":
    main()
