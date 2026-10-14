"""800x480 smart-sorting display for Raspberry Pi + Waveshare DSI screen.

The controller sends one JSON object per line.  Only DISPLAY_COMMIT messages
with drop_ok=true update the success counter; repeated item_id values are
ignored so a serial retry cannot double-count a part.
"""

from __future__ import annotations

import argparse
import json
import queue
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_ITEMS = BASE_DIR / "items.json"
CANVAS_SIZE = (800, 480)


@dataclass
class DisplayState:
    catalog: dict[str, dict[str, Any]]
    current: dict[str, Any] = field(default_factory=dict)
    success_count: int = 0
    status: str = "等待分拣"
    status_color: str = "blue"
    last_update: float = field(default_factory=time.time)
    accepted_ids: set[str] = field(default_factory=set)

    def commit(self, payload: dict[str, Any]) -> bool:
        """Apply one controller event and return whether it was accepted."""
        if payload.get("event") != "DISPLAY_COMMIT":
            return False
        item_id = str(payload.get("item_id", "")).strip()
        if not item_id:
            self.status, self.status_color = "数据错误：缺少 item_id", "red"
            self.last_update = time.time()
            return False
        if item_id in self.accepted_ids:
            self.status, self.status_color = "重复消息，未重复计数", "orange"
            self.last_update = time.time()
            return False
        if payload.get("drop_ok") is not True:
            self.status, self.status_color = "未确认入盒，未计数", "orange"
            self.last_update = time.time()
            return False

        key = str(payload.get("key", "")).strip()
        item = dict(self.catalog.get(key, {}))
        item.update({k: v for k, v in payload.items() if v not in (None, "")})
        item.setdefault("name", "未命名物料")
        item.setdefault("category", "未分类")
        item.setdefault("box_id", "-")
        self.current = item
        controller_count = payload.get("count")
        if isinstance(controller_count, int) and controller_count >= self.success_count + 1:
            self.success_count = controller_count
        else:
            self.success_count += 1
        self.accepted_ids.add(item_id)
        self.status, self.status_color = "分拣成功，已确认入盒", "green"
        self.last_update = time.time()
        return True


def load_catalog(path: Path) -> dict[str, dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("items.json 必须是数组")
    result: dict[str, dict[str, Any]] = {}
    for entry in data:
        if not isinstance(entry, dict) or not entry.get("key"):
            raise ValueError("每个物料必须包含 key")
        result[str(entry["key"])] = entry
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="智能分拣 800x480 屏幕界面")
    parser.add_argument("--serial", help="串口名称，如 COM3 或 /dev/ttyUSB0")
    parser.add_argument("--baudrate", type=int, default=115200)
    parser.add_argument("--items", type=Path, default=DEFAULT_ITEMS)
    parser.add_argument("--demo", action="store_true", help="自动演示三条消息")
    parser.add_argument("--self-test", action="store_true", help="不打开窗口，验证协议和去重逻辑")
    parser.add_argument("--fullscreen", action="store_true")
    return parser.parse_args()


def serial_worker(port: str, baudrate: int, output: queue.Queue[dict[str, Any]], stop: threading.Event) -> None:
    try:
        import serial  # type: ignore
    except ImportError:
        output.put({"event": "APP_ERROR", "message": "缺少 pyserial：请执行 pip install pyserial"})
        return
    try:
        with serial.Serial(port, baudrate=baudrate, timeout=0.2) as connection:
            while not stop.is_set():
                raw = connection.readline()
                if not raw:
                    continue
                try:
                    message = json.loads(raw.decode("utf-8", errors="replace"))
                    if isinstance(message, dict):
                        output.put(message)
                except json.JSONDecodeError:
                    output.put({"event": "APP_ERROR", "message": "收到无法解析的 JSON"})
    except Exception as exc:  # serial connection errors should be visible on the panel
        output.put({"event": "APP_ERROR", "message": f"串口故障：{exc}"})


def choose_font(pygame: Any, size: int) -> Any:
    candidates = [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/simhei.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            return pygame.font.Font(candidate, size)
    return pygame.font.Font(None, size)


def draw_text(screen: Any, font: Any, text: str, xy: tuple[int, int], color: tuple[int, int, int], center: bool = False) -> None:
    surface = font.render(str(text), True, color)
    rect = surface.get_rect()
    if center:
        rect.center = xy
    else:
        rect.topleft = xy
    screen.blit(surface, rect)


def draw_panel(screen: Any, pygame: Any, rect: tuple[int, int, int, int], color: tuple[int, int, int], radius: int = 12) -> None:
    pygame.draw.rect(screen, color, rect, border_radius=radius)


def resolve_image(item: dict[str, Any]) -> Path | None:
    image = item.get("image")
    if not image:
        return None
    candidate = Path(str(image))
    if not candidate.is_absolute():
        candidate = BASE_DIR / candidate
    return candidate if candidate.exists() else None


def draw_image_placeholder(screen: Any, pygame: Any, fonts: dict[str, Any], item: dict[str, Any], rect: tuple[int, int, int, int]) -> None:
    draw_panel(screen, pygame, rect, (238, 242, 248), 10)
    image_path = resolve_image(item)
    if image_path:
        try:
            image = pygame.image.load(str(image_path)).convert()
            image = pygame.transform.smoothscale(image, (rect[2] - 16, rect[3] - 16))
            screen.blit(image, (rect[0] + 8, rect[1] + 8))
            return
        except pygame.error:
            pass
    draw_text(screen, fonts["small"], "暂无图片", (rect[0] + rect[2] // 2, rect[1] + rect[3] // 2 - 12), (105, 115, 130), True)
    draw_text(screen, fonts["tiny"], str(item.get("name", "等待下一件")), (rect[0] + rect[2] // 2, rect[1] + rect[3] // 2 + 18), (105, 115, 130), True)


def run_ui(state: DisplayState, args: argparse.Namespace) -> None:
    try:
        import pygame
    except ImportError as exc:
        raise SystemExit("未安装 pygame，请执行：python -m pip install pygame") from exc

    pygame.init()
    flags = pygame.FULLSCREEN if args.fullscreen else 0
    screen = pygame.display.set_mode(CANVAS_SIZE, flags)
    pygame.display.set_caption("智能分拣 · 分拣结果看板")
    clock = pygame.time.Clock()
    fonts = {"title": choose_font(pygame, 24), "big": choose_font(pygame, 34), "medium": choose_font(pygame, 26), "small": choose_font(pygame, 20), "tiny": choose_font(pygame, 16)}
    messages: queue.Queue[dict[str, Any]] = queue.Queue()
    stop = threading.Event()
    reader: threading.Thread | None = None
    if args.serial:
        reader = threading.Thread(target=serial_worker, args=(args.serial, args.baudrate, messages, stop), daemon=True)
        reader.start()

    demo = [
        {"event": "DISPLAY_COMMIT", "item_id": "demo-001", "key": "red_cylinder", "drop_ok": True, "count": 1},
        {"event": "DISPLAY_COMMIT", "item_id": "demo-002", "key": "blue_cube", "drop_ok": True, "count": 2},
        {"event": "DISPLAY_COMMIT", "item_id": "demo-002", "key": "blue_cube", "drop_ok": True, "count": 3},
    ]
    demo_index, next_demo = 0, pygame.time.get_ticks() + 800
    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                running = False
        if args.demo and demo_index < len(demo) and pygame.time.get_ticks() >= next_demo:
            messages.put(demo[demo_index])
            demo_index += 1
            next_demo = pygame.time.get_ticks() + 2200
        while True:
            try:
                message = messages.get_nowait()
            except queue.Empty:
                break
            if message.get("event") == "APP_ERROR":
                state.status, state.status_color = str(message.get("message", "应用故障")), "red"
                state.last_update = time.time()
            else:
                state.commit(message)

        screen.fill((247, 249, 252))
        pygame.draw.rect(screen, (25, 55, 96), (0, 0, 800, 58))
        draw_text(screen, fonts["title"], "智能分拣 · 分拣结果看板", (22, 16), (255, 255, 255))
        draw_text(screen, fonts["small"], f"累计成功  {state.success_count:03d} 件", (638, 19), (231, 241, 255), False)
        # Main information area: picture left, structured values right.
        draw_image_placeholder(screen, pygame, fonts, state.current, (24, 82, 300, 252))
        draw_panel(screen, pygame, (348, 82, 428, 252), (255, 255, 255), 10)
        draw_text(screen, fonts["tiny"], "当前物料", (372, 102), (100, 112, 130))
        draw_text(screen, fonts["big"], state.current.get("name", "等待物料到位"), (372, 127), (26, 39, 58))
        draw_text(screen, fonts["tiny"], "分类", (372, 190), (100, 112, 130))
        draw_text(screen, fonts["medium"], state.current.get("category", "—"), (430, 183), (25, 93, 160))
        draw_text(screen, fonts["tiny"], "目标料盒", (372, 237), (100, 112, 130))
        draw_text(screen, fonts["medium"], f"#{state.current.get('box_id', '—')}", (465, 230), (25, 93, 160))
        draw_text(screen, fonts["tiny"], "物料编号", (570, 237), (100, 112, 130))
        draw_text(screen, fonts["small"], state.current.get("item_id", "—"), (650, 234), (43, 54, 70))

        status_colors = {"green": (36, 126, 79), "orange": (178, 105, 16), "red": (176, 54, 54), "blue": (33, 86, 145)}
        color = status_colors.get(state.status_color, status_colors["blue"])
        pygame.draw.rect(screen, color, (24, 358, 752, 86), border_radius=10)
        draw_text(screen, fonts["small"], "状态", (45, 374), (225, 240, 255))
        draw_text(screen, fonts["medium"], state.status, (110, 368), (255, 255, 255))
        draw_text(screen, fonts["tiny"], "ESC 退出   |   串口消息：每行一条 JSON   |   只在确认入盒后计数", (45, 417), (225, 240, 255))
        pygame.display.flip()
        clock.tick(30)

    stop.set()
    if reader:
        reader.join(timeout=0.5)
    pygame.quit()


def run_self_test(catalog: dict[str, dict[str, Any]]) -> None:
    state = DisplayState(catalog)
    assert state.commit({"event": "DISPLAY_COMMIT", "item_id": "t-1", "key": "red_cylinder", "drop_ok": True})
    assert state.success_count == 1
    assert not state.commit({"event": "DISPLAY_COMMIT", "item_id": "t-1", "key": "red_cylinder", "drop_ok": True})
    assert state.success_count == 1
    assert not state.commit({"event": "DISPLAY_COMMIT", "item_id": "t-2", "key": "red_cylinder", "drop_ok": False})
    assert state.success_count == 1
    print("SELF-TEST OK: 成功计数、重复消息去重、未入盒消息拦截均通过")


def main() -> None:
    args = parse_args()
    catalog = load_catalog(args.items)
    if args.self_test:
        run_self_test(catalog)
    else:
        run_ui(DisplayState(catalog), args)


if __name__ == "__main__":
    main()
