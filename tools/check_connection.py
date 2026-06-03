from __future__ import annotations

import argparse
import asyncio
import json
import socket
import sys
import time

import websockets


DEFAULT_TEXT = "连接自检到了喵。"


def check_tcp(host: str, port: int, timeout: float) -> float:
    started_at = time.perf_counter()
    with socket.create_connection((host, port), timeout=timeout):
        return (time.perf_counter() - started_at) * 1000


async def check_websocket(
    host: str,
    port: int,
    text: str,
    duration: float,
    timeout: float,
) -> float:
    uri = f"ws://{host}:{port}"
    payload = {
        "type": "speak",
        "text": text,
        "mood": "连接自检",
        "duration": duration,
    }

    started_at = time.perf_counter()
    async with asyncio.timeout(timeout):
        async with websockets.connect(uri) as websocket:
            await websocket.send(json.dumps(payload, ensure_ascii=False))
    return (time.perf_counter() - started_at) * 1000


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check TCP and WebSocket connectivity to Daimiao PNG VTuber."
    )
    parser.add_argument("--host", required=True, help="Target VTuber host, such as 192.168.50.132")
    parser.add_argument("--port", type=int, default=8765, help="Target WebSocket port, default: 8765")
    parser.add_argument("--timeout", type=float, default=3.0, help="Timeout seconds, default: 3")
    parser.add_argument("--text", default=DEFAULT_TEXT, help="Text to show during WebSocket check")
    parser.add_argument("--duration", type=float, default=2.0, help="Speak duration seconds")
    args = parser.parse_args()

    target = f"{args.host}:{args.port}"
    try:
        tcp_ms = check_tcp(args.host, args.port, args.timeout)
    except OSError as exc:
        print(f"[FAIL] TCP {target}: {exc}")
        return 1

    print(f"[OK] TCP {target}: {tcp_ms:.1f} ms")

    try:
        ws_ms = asyncio.run(
            check_websocket(args.host, args.port, args.text, args.duration, args.timeout)
        )
    except Exception as exc:
        print(f"[FAIL] WebSocket ws://{target}: {exc}")
        return 1

    print(f"[OK] WebSocket ws://{target}: sent speak message in {ws_ms:.1f} ms")
    return 0


if __name__ == "__main__":
    sys.exit(main())
