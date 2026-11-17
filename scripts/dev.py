"""Cross-platform local launcher for the built frontend and FastAPI API."""

import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def ollama_executable() -> str | None:
    """Find an approved existing runtime; never download software on startup."""
    configured = os.environ.get("SIRE_OLLAMA_EXE")
    portable = Path.home() / "AppData/Local/Programs/SIRE-Ollama/ollama.exe"
    return (
        configured
        or shutil.which("ollama")
        or (str(portable) if portable.is_file() else None)
    )


def ollama_running() -> bool:
    """Check loopback readiness without using configured external proxies."""
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open("http://127.0.0.1:11434/api/tags", timeout=2) as response:
            return response.status == 200
    except (urllib.error.URLError, TimeoutError):
        return False


def main() -> None:
    """Serve the built app on loopback; never open a public listener by default."""
    if not (ROOT / "web/dist/index.html").is_file():
        raise SystemExit("Build the frontend first: cd web; npm ci; npm run build")
    from app.core.config import STATE

    if not (STATE / "scenarios/manifest.json").is_file():
        subprocess.run(
            [sys.executable, str(ROOT / "scripts/seed_scenarios.py")],
            cwd=ROOT,
            check=True,
        )
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    print("SIRE: http://127.0.0.1:8000 | API: http://127.0.0.1:8000/docs", flush=True)
    service = None
    log = None
    executable = ollama_executable()
    if executable and not ollama_running():
        runtime = ROOT / ".runtime"
        runtime.mkdir(exist_ok=True)
        log = (runtime / "ollama.log").open("ab")
        service = subprocess.Popen(
            [executable, "serve"],
            stdout=log,
            stderr=log,
            env=dict(
                env,
                OLLAMA_HOST="127.0.0.1:11434",
                OLLAMA_NO_CLOUD="1",
                OLLAMA_MAX_LOADED_MODELS="1",
                OLLAMA_NUM_PARALLEL="1",
            ),
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
    try:
        code = subprocess.call(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app.api.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                "8000",
            ],
            cwd=ROOT,
            env=env,
        )
    except KeyboardInterrupt:
        code = 130
    finally:
        if service and service.poll() is None:
            service.terminate()
            try:
                service.wait(timeout=10)
            except subprocess.TimeoutExpired:
                service.kill()
                service.wait()
        if log:
            log.close()
    raise SystemExit(code)


if __name__ == "__main__":
    main()
