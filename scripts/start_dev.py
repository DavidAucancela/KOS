#!/usr/bin/env python3
"""Levanta dev-api encontrando puerto disponible automáticamente."""

import socket
import subprocess


def find_free_port(start_port: int = 8000, max_attempts: int = 10) -> int:
    """Encuentra el primer puerto disponible partiendo de start_port."""
    for port in range(start_port, start_port + max_attempts):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("127.0.0.1", port))
                s.listen(1)
                return port
        except OSError:
            continue
    raise RuntimeError(
        f"No hay puertos disponibles en rango {start_port}-{start_port + max_attempts}"
    )


if __name__ == "__main__":
    port = find_free_port()
    print(f"🚀 Levantando API en puerto {port}")
    if port != 8000:
        print(f"   ⚠️  Puerto 8000 en uso, usando {port}")
        print(f"   📍 http://localhost:{port}/docs")

    cmd = [
        "uv",
        "run",
        "uvicorn",
        "kos_api.main:app",
        "--reload",
        f"--port={port}",
    ]
    subprocess.run(cmd)
