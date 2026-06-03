from __future__ import annotations

import argparse
import asyncio
import json

import websockets


DEFAULT_TEXT = "老大，这波居然没猫车，算你有点本事喵。"


async def send_message(host: str, port: int, text: str, mood: str, duration: float) -> None:
    uri = f"ws://{host}:{port}"
    payload = {
        "type": "speak",
        "text": text,
        "mood": mood,
        "duration": duration,
    }
    async with websockets.connect(uri) as websocket:
        await websocket.send(json.dumps(payload, ensure_ascii=False))
    print(f"Sent speak message to {uri}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Send a test speak message to Daimiao PNG VTuber.")
    parser.add_argument("--host", default="127.0.0.1", help="WebSocket host, default: 127.0.0.1")
    parser.add_argument("--port", type=int, default=8765, help="WebSocket port, default: 8765")
    parser.add_argument("--text", default=DEFAULT_TEXT, help="Subtitle text")
    parser.add_argument("--mood", default="嘴硬夸奖", help="Mood label")
    parser.add_argument("--duration", type=float, default=4.2, help="Speak duration in seconds")
    args = parser.parse_args()

    asyncio.run(send_message(args.host, args.port, args.text, args.mood, args.duration))


if __name__ == "__main__":
    main()
