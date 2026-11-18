
"""
Colab launcher for MediMama in local MedGemma mode.

- Runs FastAPI inside Google Colab.
- Exposes the application through ngrok.
- Stores MedGemma model cache in Google Drive.
- Reuses downloaded model files in subsequent sessions.

Before running:
1. Mount Google Drive.
2. Set HF_TOKEN and NGROK_AUTH_TOKEN in Colab Secrets.
3. Install requirements-demo.txt.
4. Run: %run demo_colab.py
"""

import os
import socket
import subprocess
import threading
import time
from pathlib import Path

import json
from urllib.request import urlopen
import nest_asyncio
import uvicorn
from pyngrok import ngrok


# ---------------------------------------------------------
# 1. Configuration
# ---------------------------------------------------------

PORT = int(os.environ.get("PORT", "8000"))
STARTUP_TIMEOUT_SECONDS = 600

os.environ.setdefault("INFERENCE_MODE", "local")
# Persistent model cache on Google Drive.
DEFAULT_MODEL_CACHE = (
    "/content/drive/MyDrive/models/qwen3_4b_cache"
)

os.environ.setdefault(
    "LOCAL_MODEL_CACHE_DIR",
    DEFAULT_MODEL_CACHE
)


os.environ.setdefault(
    "TRANSLATION_BACKEND",
    "local"
)

os.environ.setdefault(
    "LOCAL_MODEL_ID",
    "Qwen/Qwen3-4B-Instruct-2507"
)

DEFAULT_MODEL_CACHE = (
    "/content/drive/MyDrive/models/qwen3_4b_cache"
)

os.environ.setdefault(
    "LOCAL_MODEL_DTYPE",
    "float16"
)

# Ensure the cache directory exists.
MODEL_CACHE_DIR = Path(
    os.environ["LOCAL_MODEL_CACHE_DIR"]
)

MODEL_CACHE_DIR.mkdir(
    parents=True,
    exist_ok=True
)

nest_asyncio.apply()


# ---------------------------------------------------------
# 2. Port and ngrok cleanup
# ---------------------------------------------------------

def free_port(port: int) -> None:
    """Clean up previous ngrok tunnels and processes using the port."""

    try:
        ngrok.kill()
        print("[INFO] Previous ngrok tunnels stopped.")

    except Exception as exc:
        print(f"[INFO] ngrok cleanup skipped: {exc}")

    try:
        subprocess.run(
            ["fuser", "-k", f"{port}/tcp"],
            check=False,
            capture_output=True,
            text=True
        )

        time.sleep(2)

    except Exception as exc:
        print(f"[WARNING] Port cleanup skipped: {exc}")


# ---------------------------------------------------------
# 3. Server readiness checks
# ---------------------------------------------------------

def is_port_open(
    port: int,
    host: str = "127.0.0.1"
) -> bool:

    with socket.socket(
        socket.AF_INET,
        socket.SOCK_STREAM
    ) as sock:

        sock.settimeout(1)

        return (
            sock.connect_ex((host, port)) == 0
        )


def wait_until_ready(port: int, timeout: int) -> bool:
    """
    Wait until FastAPI is running and the generation model is loaded.
    """

    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:

        if is_port_open(port):
            try:
                with urlopen(
                    f"http://127.0.0.1:{port}/health/ready",
                    timeout=3,
                ) as response:

                    status = json.load(response)

                if status.get("generation", {}).get("ready") is True:
                    return True

            except Exception:
                pass

        time.sleep(2)

    return False


# ---------------------------------------------------------
# 4. FastAPI server
# ---------------------------------------------------------

def serve() -> None:

    print("[INFO] Starting FastAPI application...")

    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=PORT,
        log_level="info"
    )


# ---------------------------------------------------------
# 5. Main launcher
# ---------------------------------------------------------

def main() -> None:

    # Check inference mode before starting the server.
    inference_mode = os.environ.get("INFERENCE_MODE", "local").strip().lower()
    if inference_mode not in ("local", "api"):
        raise RuntimeError(
            f"INFERENCE_MODE must be 'local' or 'api', got: {inference_mode!r}"
        )
    # Read ngrok token from environment.
    token = os.environ.get(
        "NGROK_AUTH_TOKEN",
        ""
    ).strip()

    if not token:

        raise RuntimeError(
            "NGROK_AUTH_TOKEN is missing. "
            "Add it to Colab Secrets and load it before running this script."
        )

    print("=" * 60)
    print("MediMama - Local Qwen3 Demo")
    print("=" * 60)

    print(f"[INFO] Model: {os.environ['LOCAL_MODEL_ID']}")
    print(f"[INFO] Model cache: {MODEL_CACHE_DIR}")
    print(f"[INFO] Inference mode: {inference_mode}")

    print(
        "[INFO] Starting server. "
        "Loading Qwen3 weights may take several minutes."
    )

    # Clean up previous server and tunnel.
    free_port(PORT)

    # Register ngrok token.
    try:

        ngrok.set_auth_token(token)

        print("[INFO] ngrok authentication configured.")

    except Exception as exc:

        if "Authtoken already set in configuration file" in str(exc):

            print(
                "[INFO] ngrok token is already configured. "
                "Using the existing configuration."
            )

        else:
            raise

    # Start FastAPI in a background thread.
    server_thread = threading.Thread(
        target=serve,
        daemon=True
    )

    server_thread.start()

    # Wait for server startup.
    print("[INFO] Waiting for FastAPI...")

    if not wait_until_ready(
        PORT,
        STARTUP_TIMEOUT_SECONDS
    ):

        raise RuntimeError(
            f"Server did not become ready within "
            f"{STARTUP_TIMEOUT_SECONDS} seconds. "
            "Check the logs for model loading errors."
        )

    print("[INFO] FastAPI is accepting connections.")

    # Create public ngrok tunnel.
    tunnel = ngrok.connect(PORT)

    public_url = tunnel.public_url

    print("\n" + "=" * 60)
    print("MediMama is running!")
    print("=" * 60)

    print(f"\nWeb UI:   {public_url}")
    print(f"API docs: {public_url}/docs")
    print(f"Endpoint: {public_url}/ask")

    print("\nModel cache:")
    print(MODEL_CACHE_DIR)

    print("\nOpen the Web UI link above.")
    print("The UI and API are served from the same origin.")

    print("\nKeep this Colab session running while using the demo.")


# ---------------------------------------------------------
# 6. Entry point
# ---------------------------------------------------------

if __name__ == "__main__":
    main()
