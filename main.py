from __future__ import annotations

import argparse
import asyncio
import json
import math
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pygame
import websockets
from websockets.server import WebSocketServerProtocol


WINDOW_WIDTH = 800
WINDOW_HEIGHT = 600
GREEN_SCREEN = (0, 255, 0)
FPS = 60
BUBBLE_FILL = (255, 255, 255)
BUBBLE_OUTLINE = (24, 24, 24)
BUBBLE_TEXT = (20, 20, 20)
DEFAULT_MOOD = "neutral"
FALLBACK_MOOD = "daimiao"

DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8765

BASE_DIR = Path(__file__).resolve().parent
ASSETS_DIR = BASE_DIR / "assets"

MOOD_ALIASES = {
    "": DEFAULT_MOOD,
    "neutral": DEFAULT_MOOD,
    "default": DEFAULT_MOOD,
    "happy": "happy",
    "smile": "happy",
    "annoyed": "annoyed",
    "angry": "annoyed",
    "surprised": "surprised",
    "thinking": "thinking",
    "毒舌": "annoyed",
    "傲娇": "annoyed",
    "慌张": "surprised",
    "看乐子": "happy",
    "老妈子": "annoyed",
    "阴阳怪气": "annoyed",
    "惊喜": "surprised",
    "嘴硬夸奖": "happy",
    "热血": "surprised",
    "护短": "annoyed",
    "欣慰": "happy",
    "崇拜": "surprised",
    "得意": "happy",
    "激动": "surprised",
}


@dataclass(frozen=True)
class CharacterImageSet:
    closed: pygame.Surface
    opened: pygame.Surface


@dataclass
class SpeakState:
    text: str = ""
    mood: str = ""
    started_at: float = 0.0
    duration: float = 0.0
    speaking: bool = False


state = SpeakState()
state_lock = threading.Lock()


def load_character_images() -> dict[str, CharacterImageSet]:
    image_sets: dict[str, CharacterImageSet] = {}
    missing_pairs: list[str] = []

    for closed_path in sorted(ASSETS_DIR.glob("*_closed.png")):
        mood = closed_path.name[: -len("_closed.png")]
        open_path = ASSETS_DIR / f"{mood}_open.png"
        if not open_path.exists():
            missing_pairs.append(str(open_path))
            continue

        closed = prepare_character_image(pygame.image.load(str(closed_path)).convert_alpha())
        opened = prepare_character_image(pygame.image.load(str(open_path)).convert_alpha())
        image_sets[mood] = CharacterImageSet(closed=fit_image(closed), opened=fit_image(opened))

    if missing_pairs:
        raise FileNotFoundError("Missing image file(s): " + ", ".join(missing_pairs))
    if not image_sets:
        raise FileNotFoundError("Missing character image pairs in assets/*_closed.png and assets/*_open.png")

    print("Loaded mood image sets: " + ", ".join(sorted(image_sets)))
    return image_sets


def prepare_character_image(surface: pygame.Surface) -> pygame.Surface:
    result = surface.copy()
    if result.get_bounding_rect(min_alpha=1).size != result.get_size():
        return result

    result.lock()
    try:
        width, height = result.get_size()
        for y in range(height):
            for x in range(width):
                red, green, blue, alpha = result.get_at((x, y))
                if alpha and green >= 180 and red <= 90 and blue <= 90:
                    result.set_at((x, y), (red, green, blue, 0))
    finally:
        result.unlock()
    return result


def fit_image(surface: pygame.Surface) -> pygame.Surface:
    max_width = int(WINDOW_WIDTH * 0.78)
    max_height = int(WINDOW_HEIGHT * 0.72)
    width, height = surface.get_size()
    scale = min(max_width / width, max_height / height, 1.0)
    size = (max(1, int(width * scale)), max(1, int(height * scale)))
    return pygame.transform.smoothscale(surface, size)


def resolve_mood_key(mood: str, image_sets: dict[str, CharacterImageSet]) -> str:
    normalized = (mood or "").strip()
    candidates = [
        normalized,
        normalized.lower(),
        MOOD_ALIASES.get(normalized, ""),
        MOOD_ALIASES.get(normalized.lower(), ""),
        DEFAULT_MOOD,
        FALLBACK_MOOD,
    ]
    for candidate in candidates:
        if candidate in image_sets:
            return candidate
    return next(iter(image_sets))


def parse_speak_message(payload: dict[str, Any]) -> tuple[str, str, float] | None:
    if payload.get("type") != "speak":
        return None

    text = str(payload.get("text", "")).strip()
    mood = str(payload.get("mood", "")).strip()
    try:
        duration = float(payload.get("duration", 0))
    except (TypeError, ValueError):
        duration = 0.0

    if not text or duration <= 0:
        print("Invalid speak message: text must be non-empty and duration must be > 0")
        return None

    return text, mood, min(duration, 60.0)


async def handle_client(websocket: WebSocketServerProtocol) -> None:
    async for message in websocket:
        try:
            payload = json.loads(message)
        except json.JSONDecodeError as exc:
            print(f"Invalid JSON: {exc}")
            continue

        if not isinstance(payload, dict):
            print("Invalid message: JSON root must be an object")
            continue

        speak = parse_speak_message(payload)
        if speak is None:
            continue

        text, mood, duration = speak
        with state_lock:
            state.text = text
            state.mood = mood
            state.duration = duration
            state.started_at = time.monotonic()
            state.speaking = True


async def websocket_main(host: str, port: int) -> None:
    async with websockets.serve(handle_client, host, port):
        print(f"WebSocket server listening on ws://{host}:{port}")
        await asyncio.Future()


def start_websocket_server(host: str, port: int) -> threading.Thread:
    def runner() -> None:
        try:
            asyncio.run(websocket_main(host, port))
        except Exception as exc:
            print(f"WebSocket server stopped: {exc}")

    thread = threading.Thread(target=runner, daemon=True)
    thread.start()
    return thread


def wrap_subtitle(
    text: str,
    font: pygame.font.Font,
    max_width: int,
    max_lines: int = 2,
) -> list[str]:
    words = list(text) if " " not in text else text.split(" ")
    lines: list[str] = []
    current = ""
    separator = "" if " " not in text else " "

    for word in words:
        candidate = word if not current else current + separator + word
        if font.size(candidate)[0] <= max_width:
            current = candidate
            continue

        if current:
            lines.append(current)
        current = word
        if len(lines) == max_lines:
            break

    if current and len(lines) < max_lines:
        lines.append(current)

    if len(lines) > max_lines:
        lines = lines[:max_lines]

    if lines and font.size(lines[-1])[0] > max_width:
        lines[-1] = trim_to_width(lines[-1], font, max_width)

    if len(lines) == max_lines and "".join(lines) != text.replace(" ", ""):
        lines[-1] = trim_to_width(lines[-1] + "...", font, max_width)

    return lines


def trim_to_width(text: str, font: pygame.font.Font, max_width: int) -> str:
    suffix = "..."
    while text and font.size(text + suffix)[0] > max_width:
        text = text[:-1]
    return text + suffix if text else suffix


def draw_outlined_text(
    screen: pygame.Surface,
    font: pygame.font.Font,
    text: str,
    center_x: int,
    y: int,
) -> None:
    outline_color = (0, 0, 0)
    fill_color = (255, 255, 255)
    for dx, dy in ((-2, 0), (2, 0), (0, -2), (0, 2), (-2, -2), (2, -2), (-2, 2), (2, 2)):
        outline = font.render(text, True, outline_color)
        rect = outline.get_rect(centerx=center_x, y=y)
        screen.blit(outline, rect.move(dx, dy))

    fill = font.render(text, True, fill_color)
    rect = fill.get_rect(centerx=center_x, y=y)
    screen.blit(fill, rect)


def draw_speech_bubble(
    screen: pygame.Surface,
    font: pygame.font.Font,
    lines: list[str],
    character_rect: pygame.Rect,
) -> None:
    if not lines:
        return

    padding_x = 26
    padding_y = 16
    line_height = font.get_linesize()
    text_width = max(font.size(line)[0] for line in lines)
    text_height = line_height * len(lines)
    bubble_width = min(max(text_width + padding_x * 2, 240), WINDOW_WIDTH - 56)
    bubble_height = text_height + padding_y * 2
    bubble_x = (WINDOW_WIDTH - bubble_width) // 2
    bubble_y = max(24, character_rect.top - bubble_height - 26)
    bubble_rect = pygame.Rect(bubble_x, bubble_y, bubble_width, bubble_height)

    tail_tip = (
        min(max(character_rect.centerx + 28, bubble_rect.left + 52), bubble_rect.right - 52),
        min(character_rect.top + 34, WINDOW_HEIGHT - 28),
    )
    tail_base_y = bubble_rect.bottom - 2
    tail_base_center_x = min(max(tail_tip[0] - 34, bubble_rect.left + 54), bubble_rect.right - 54)
    tail_outline = [
        (tail_base_center_x - 22, tail_base_y),
        (tail_base_center_x + 22, tail_base_y),
        tail_tip,
    ]
    tail_fill = [
        (tail_base_center_x - 17, tail_base_y - 1),
        (tail_base_center_x + 17, tail_base_y - 1),
        (tail_tip[0], tail_tip[1] - 6),
    ]

    pygame.draw.polygon(screen, BUBBLE_OUTLINE, tail_outline)
    pygame.draw.rect(screen, BUBBLE_OUTLINE, bubble_rect, border_radius=20)
    inner_rect = bubble_rect.inflate(-6, -6)
    pygame.draw.polygon(screen, BUBBLE_FILL, tail_fill)
    pygame.draw.rect(screen, BUBBLE_FILL, inner_rect, border_radius=17)

    text_y = bubble_rect.y + padding_y
    for index, line in enumerate(lines):
        rendered = font.render(line, True, BUBBLE_TEXT)
        text_rect = rendered.get_rect(centerx=bubble_rect.centerx, y=text_y + index * line_height)
        screen.blit(rendered, text_rect)


def draw_subtitle(screen: pygame.Surface, text: str, character_rect: pygame.Rect) -> None:
    max_width = int(WINDOW_WIDTH * 0.68)
    for size in (34, 30, 26, 22):
        font = pygame.font.SysFont(
            "microsoftyahei,pingfangsc,notosanscjk,arialunicode,simsun",
            size,
            bold=True,
        )
        lines = wrap_subtitle(text, font, max_width)
        if len(lines) <= 2 and all(font.size(line)[0] <= max_width for line in lines):
            break

    draw_speech_bubble(screen, font, lines, character_rect)


def snapshot_state() -> SpeakState:
    with state_lock:
        return SpeakState(
            text=state.text,
            mood=state.mood,
            started_at=state.started_at,
            duration=state.duration,
            speaking=state.speaking,
        )


def expire_speaking_if_needed(now: float) -> SpeakState:
    with state_lock:
        if state.speaking and now - state.started_at >= state.duration:
            state.speaking = False
            state.text = ""
            state.mood = ""
            state.duration = 0.0
        return SpeakState(
            text=state.text,
            mood=state.mood,
            started_at=state.started_at,
            duration=state.duration,
            speaking=state.speaking,
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Daimiao PNG VTuber window.")
    parser.add_argument(
        "--host",
        default=DEFAULT_HOST,
        help=f"WebSocket bind host, default: {DEFAULT_HOST}",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help=f"WebSocket port, default: {DEFAULT_PORT}",
    )
    return parser.parse_args()


def run_app(host: str, port: int) -> None:
    pygame.init()
    pygame.display.set_caption("Daimiao PNG VTuber")
    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    clock = pygame.time.Clock()
    image_sets = load_character_images()

    start_websocket_server(host, port)

    running = True
    while running:
        now = time.monotonic()
        current = expire_speaking_if_needed(now)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        screen.fill(GREEN_SCREEN)

        floating_y = int(math.sin(now * 2.0) * 5)
        mood_key = resolve_mood_key(current.mood, image_sets)
        character_images = image_sets[mood_key]
        if current.speaking:
            mouth_open = int((now - current.started_at) / 0.16) % 2 == 1
            image = character_images.opened if mouth_open else character_images.closed
        else:
            image = image_sets[resolve_mood_key("", image_sets)].closed

        character_rect = image.get_rect(center=(WINDOW_WIDTH // 2, 300 + floating_y))
        screen.blit(image, character_rect)

        if current.speaking and current.text:
            draw_subtitle(screen, current.text, character_rect)

        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()


if __name__ == "__main__":
    try:
        args = parse_args()
        run_app(args.host, args.port)
    except FileNotFoundError as exc:
        print(exc)
        sys.exit(1)
