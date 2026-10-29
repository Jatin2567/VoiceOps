"""Run the dashboard publicly and its API on loopback in one Render container."""
import os
import signal
import subprocess
import sys
import time
import urllib.request


def main():
    env = os.environ.copy()
    env["BACKEND_API_URL"] = "http://127.0.0.1:8000"
    children = []
    stopping = False

    def stop(_signum=None, _frame=None):
        nonlocal stopping
        stopping = True
        for child in children:
            if child.poll() is None:
                child.terminate()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        backend = subprocess.Popen([
            sys.executable, "scripts/serve_apis.py",
        ], env=env)
        children.append(backend)
        deadline = time.monotonic() + 90
        while not stopping:
            if backend.poll() is not None:
                raise RuntimeError("Backend exited during startup")
            try:
                with urllib.request.urlopen(env["BACKEND_API_URL"] + "/health", timeout=1):
                    break
            except OSError:
                if time.monotonic() >= deadline:
                    raise RuntimeError("Backend health check timed out")
                time.sleep(.5)
        if stopping:
            return 0
        children.append(subprocess.Popen([
            sys.executable, "-m", "streamlit", "run", "frontend/app.py",
            "--global.developmentMode=false",
            "--server.address=127.0.0.1", "--server.port=8501", "--server.baseUrlPath=studio",
            "--server.headless=true", "--browser.gatherUsageStats=false",
        ], env=env))
        while not stopping and all(child.poll() is None for child in children):
            time.sleep(.5)
        return 0 if stopping else 1
    finally:
        stop()
        for child in children:
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()


if __name__ == "__main__":
    sys.exit(main())
