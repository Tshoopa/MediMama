"""
Colab launcher for MediMama.

Runs the FastAPI app inside a Colab notebook and exposes it through an ngrok
tunnel so the browser frontend can reach it. Development and demo only; the
supported deployment paths are Docker Compose or a plain uvicorn process.

Usage in a Colab cell:
    import os
    os.environ["NGROK_AUTH_TOKEN"] = "..."
    %run demo_colab.py
"""

import os
import socket
import subprocess
import threading
import time

import nest_asyncio
import uvicorn
from pyngrok import ngrok

PORT = 8000
STARTUP_TIMEOUT_SECONDS = 180

nest_asyncio.apply()


def free_port(port: int) -> None:
    """Terminate any previous tunnel or server still holding the port."""
    try:
        ngrok.kill()
    except Exception as exc:
        print(f"ngrok cleanup skipped: {exc}")

    try:
        subprocess.run(f"fuser -k {port}/tcp", shell=True, check=False)
        time.sleep(2)
    except Exception as exc:
        print(f"port cleanup skipped: {exc}")


def is_port_open(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(1)
        return sock.connect_ex((host, port)) == 0


def wait_until_ready(port: int, timeout: int) -> bool:
    """Poll the port until the server accepts connections or the timeout hits."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if is_port_open(port):
            return True
        time.sleep(1)
    return False


def serve() -> None:
    uvicorn.run("backend.main:app", host="0.0.0.0", port=PORT, log_level="info")


def main() -> None:
    token = os.environ.get("NGROK_AUTH_TOKEN")
    if not token:
        raise RuntimeError(
            "NGROK_AUTH_TOKEN is not set. Export it before running this script."
        )

    free_port(PORT)
    ngrok.set_auth_token(token)

    threading.Thread(target=serve, daemon=True).start()
    print("Starting server. Loading the Meditron weights takes a while.")

    if not wait_until_ready(PORT, STARTUP_TIMEOUT_SECONDS):
        raise RuntimeError(
            f"Server did not become ready within {STARTUP_TIMEOUT_SECONDS}s. "
            "Check the logs above for model loading or import errors."
        )
    public_url = ngrok.connect(PORT).public_url
    print(f"Web UI:   {public_url}")
    print(f"API docs: {public_url}/docs")
    print(f"Endpoint: {public_url}/ask")
    print("\nOpen the Web UI link above. No config.js editing needed — the UI")
    print("and the API are served from the same origin.")

if __name__ == "__main__":
    main()