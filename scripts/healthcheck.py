#!/usr/bin/env python3
"""
Lightweight healthcheck script for Task Engine containers (API, Worker, Scheduler).
Invoked by container runtime HEALTHCHECK directives.
"""

import os
import sys
import urllib.request


def check_api() -> int:
    port = os.getenv("API_PORT", "8000")
    url = f"http://127.0.0.1:{port}/api/v1/health"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "HealthCheck/1.0"})
        with urllib.request.urlopen(req, timeout=4) as response:
            if response.status == 200:
                return 0
            return 1
    except Exception as exc:
        sys.stderr.write(f"Healthcheck failed: {exc}\n")
        return 1


def check_process(name: str) -> int:
    # Basic check to ensure the target process is running
    # Checks /proc for Linux container environments
    if not os.path.exists("/proc"):
        return 0
    try:
        pids = [pid for pid in os.listdir("/proc") if pid.isdigit()]
        for pid in pids:
            try:
                with open(f"/proc/{pid}/cmdline", "rb") as f:
                    cmdline = f.read().decode("utf-8", errors="ignore")
                    if name in cmdline:
                        return 0
            except FileNotFoundError, PermissionError, ProcessLookupError:
                continue
        sys.stderr.write(f"Process matching '{name}' not found in /proc\n")
        return 1
    except Exception as exc:
        sys.stderr.write(f"Process check failed: {exc}\n")
        return 1


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "api"
    if mode == "api":
        sys.exit(check_api())
    elif mode in ("worker", "scheduler"):
        sys.exit(check_process(mode))
    else:
        sys.stderr.write(f"Unknown healthcheck mode: {mode}\n")
        sys.exit(1)
