"""Start an isolated Ollama service, list model metadata, and stop only that process."""
import os
import socket
import subprocess
from unittest.mock import patch

from preciso_mcp import setup_cli as setup


def main():
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    endpoint = f"http://127.0.0.1:{port}"
    started = []
    popen = subprocess.Popen
    def launch(*args, **kwargs):
        process = popen(*args, **kwargs)
        started.append(process)
        return process
    try:
        with patch.dict(os.environ, {"OLLAMA_BASE_URL": endpoint, "OLLAMA_NUM_PARALLEL": "1", "OLLAMA_MAX_LOADED_MODELS": "1"}), \
                patch.object(setup, "confirm", return_value=True), patch.object(setup.subprocess, "Popen", side_effect=launch):
            models = setup.ensure_ollama_models()
            assert len(started) == 1 and started[0].poll() is None
            assert setup.ensure_ollama_models() == models
            assert len(started) == 1, "Started another process for a ready service"
        print("Ollama startup passed: consent path, custom local endpoint, readiness, no duplicate start. No model inference.")
    finally:
        for process in started:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)


if __name__ == "__main__":
    main()
