#!/usr/bin/env python3
"""Recreate Dot Reflex publication charts from preserved JSON receipts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
EVAL = ROOT / "evaluation"
PROVENANCE = ROOT / "provenance"
ASSETS = ROOT / "assets"

WIDTH = 1800
BG = "#FAFAF8"
INK = "#121316"
MUTED = "#686D76"
GRID = "#DDE0E5"
BORDER = "#C9CDD4"
WHITE = "#FFFFFF"
DOT_RED = "#FF073A"

SERIES = [
    ("Dot Reflex · QLoRA", "adapter_metrics.json", "#168AF0"),
    ("Qwen3 · Recovery prompt", "prompt_only_metrics.json", "#8F98C4"),
    ("Qwen3 · Minimal prompt", "base_metrics.json", "#35B58D"),
    ("Deterministic rules", "heuristic_metrics.json", "#D3D6DE"),
]

def first_font(*candidates: str) -> Path:
    for candidate in candidates:
        path = Path(candidate)
        if path.exists():
            return path
    raise RuntimeError("No supported system font found for chart generation")


FONT_REGULAR = first_font(
    "/System/Library/Fonts/SFNS.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
)
FONT_BOLD = first_font(
    "/System/Library/Fonts/SFNS.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
)
FONT_MONO = first_font(
    "/System/Library/Fonts/SFNSMono.ttf",
    "/System/Library/Fonts/Supplemental/Andale Mono.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
)


def font(size: int, *, bold: bool = False, mono: bool = False) -> ImageFont.FreeTypeFont:
    path = FONT_MONO if mono and FONT_MONO.exists() else FONT_BOLD if bold else FONT_REGULAR
    return ImageFont.truetype(str(path), size=size)


def load_metrics() -> list[dict[str, Any]]:
    rows = []
    for name, filename, color in SERIES:
        payload = json.loads((EVAL / filename).read_text(encoding="utf-8"))
        rows.append({"name": name, "file": filename, "color": color, "data": payload})
    return rows


def canvas(height: int) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    image = Image.new("RGB", (WIDTH, height), BG)
    draw = ImageDraw.Draw(image)
    draw.rectangle((18, 18, WIDTH - 19, height - 19), outline=BORDER, width=1)
    return image, draw


def paste_logo(image: Image.Image, path: Path, box: tuple[int, int, int, int]) -> None:
    logo = Image.open(path).convert("RGBA")
    logo.thumbnail((box[2] - box[0], box[3] - box[1]), Image.Resampling.LANCZOS)
    x = box[0] + (box[2] - box[0] - logo.width) // 2
    y = box[1] + (box[3] - box[1] - logo.height) // 2
    image.paste(logo, (x, y), logo)


def draw_header(
    image: Image.Image,
    draw: ImageDraw.ImageDraw,
    *,
    title: str,
    subtitle: str,
    badge: str,
) -> int:
    paste_logo(image, ASSETS / "dot-mark.png", (64, 52, 124, 112))
    draw.text((142, 46), title, fill=INK, font=font(52, bold=True))
    draw.text((142, 111), subtitle, fill=MUTED, font=font(23))
    badge_font = font(18, bold=True, mono=True)
    bbox = draw.textbbox((0, 0), badge, font=badge_font)
    badge_w = bbox[2] - bbox[0] + 36
    draw.rounded_rectangle(
        (WIDTH - 64 - badge_w, 58, WIDTH - 64, 100),
        radius=21,
        fill="#FFF0F3",
        outline="#FF9AB0",
        width=1,
    )
    draw.text((WIDTH - 64 - badge_w + 18, 69), badge, fill="#B50029", font=badge_font)
    draw.line((64, 166, WIDTH - 64, 166), fill=BORDER, width=1)
    return 192


def draw_legend(image: Image.Image, draw: ImageDraw.ImageDraw, y: int) -> None:
    x = 70
    qwen = Image.open(ASSETS / "qwen-logo.png").convert("RGBA")
    qwen.thumbnail((30, 30), Image.Resampling.LANCZOS)
    for index, (name, _, color) in enumerate(SERIES):
        draw.rounded_rectangle((x, y, x + 23, y + 23), radius=5, fill=color)
        if index in {1, 2}:
            image.paste(qwen, (x - 3, y - 3), qwen)
        draw.text((x + 34, y - 1), name, fill=INK, font=font(19, bold=index == 0))
        x += 410


def footer(draw: ImageDraw.ImageDraw, y: int, left: str, right: str) -> None:
    draw.line((64, y, WIDTH - 64, y), fill=INK, width=1)
    draw.text((64, y + 18), left, fill=MUTED, font=font(16))
    right_font = font(15, mono=True)
    right_box = draw.textbbox((0, 0), right, font=right_font)
    draw.text((WIDTH - 64 - (right_box[2] - right_box[0]), y + 18), right, fill=MUTED, font=right_font)


def percent(value: float) -> str:
    number = value * 100
    return f"{number:.1f}" if not number.is_integer() else f"{number:.0f}"


def benchmark_overview(metrics: list[dict[str, Any]]) -> Path:
    image, draw = canvas(1000)
    y = draw_header(
        image,
        draw,
        title="Dot Reflex 14B · Agent Recovery Bench v0",
        subtitle="Qwen3-14B-Base · rank-64 QLoRA · 1,000 static cases + 200 stateful episodes",
        badge="SYNTHETIC · NOT SWE-BENCH",
    )
    draw_legend(image, draw, y)

    panels = [
        ("Recovery action accuracy", "static", "recovery_action_accuracy", False),
        ("Macro F1 · 10 controls", "static", "macro_f1", False),
        ("Stateful recovery", "live", "successful_recovery_rate", False),
        ("Calibration error · ECE", "static", "expected_calibration_error_10_bin", True),
    ]
    panel_y0, panel_y1 = 265, 838
    gap = 24
    panel_w = (WIDTH - 128 - gap * 3) // 4
    for panel_index, (label, section, key, lower) in enumerate(panels):
        x0 = 64 + panel_index * (panel_w + gap)
        x1 = x0 + panel_w
        draw.rounded_rectangle((x0, panel_y0, x1, panel_y1), radius=18, fill=WHITE, outline=GRID)
        draw.text((x0 + 24, panel_y0 + 24), label, fill=INK, font=font(23, bold=True))
        if lower:
            draw.text((x0 + 24, panel_y0 + 57), "lower is better", fill=MUTED, font=font(16))
        plot_top, plot_bottom = panel_y0 + 120, panel_y1 - 76
        draw.line((x0 + 45, plot_bottom, x1 - 32, plot_bottom), fill=BORDER, width=2)
        values = [row["data"][section][key] for row in metrics]
        max_value = 0.75 if lower else 1.0
        bar_gap = 16
        bar_w = (panel_w - 98 - bar_gap * 3) // 4
        for i, (row, value) in enumerate(zip(metrics, values)):
            bx0 = x0 + 45 + i * (bar_w + bar_gap)
            bx1 = bx0 + bar_w
            height = max(3, int((plot_bottom - plot_top) * min(value / max_value, 1.0)))
            by0 = plot_bottom - height
            draw.rounded_rectangle((bx0, by0, bx1, plot_bottom), radius=7, fill=row["color"])
            value_text = percent(value)
            value_font = font(24, bold=True)
            tb = draw.textbbox((0, 0), value_text, font=value_font)
            draw.text((bx0 + (bar_w - (tb[2] - tb[0])) / 2, by0 - 37), value_text, fill=INK, font=value_font)
            short = ["REFLEX", "PROMPT", "BASE", "RULES"][i]
            short_font = font(13, bold=i == 0, mono=True)
            sb = draw.textbbox((0, 0), short, font=short_font)
            draw.text((bx0 + (bar_w - (sb[2] - sb[0])) / 2, plot_bottom + 16), short, fill=MUTED, font=short_font)

    footer(
        draw,
        884,
        "Held-out synthetic trajectories. Raw aggregate receipts included. No production or transfer claim.",
        "DOT R&D · 27 AUG 2026 · GREEDY DECODE · H200 RECEIPT",
    )
    output = EVAL / "benchmark_overview.png"
    image.save(output, optimize=True)
    return output


def action_accuracy(metrics: list[dict[str, Any]]) -> Path:
    image, draw = canvas(980)
    start_y = draw_header(
        image,
        draw,
        title="Per-control accuracy",
        subtitle="Agent Recovery Bench v0 · 100 held-out synthetic cases per action",
        badge="10-WAY CONTROL TAXONOMY",
    )
    actions = [
        "continue",
        "verify",
        "retry_differently",
        "replan",
        "rollback",
        "branch",
        "switch_model",
        "ask_human",
        "stop_successfully",
        "stop_failure",
    ]
    labels = [
        "CONTINUE",
        "VERIFY",
        "RETRY\nDIFFERENTLY",
        "REPLAN",
        "ROLLBACK",
        "BRANCH",
        "SWITCH\nMODEL",
        "ASK\nHUMAN",
        "STOP\nSUCCESS",
        "STOP\nFAILURE",
    ]
    left = 360
    top = start_y + 90
    cell_w = 132
    cell_h = 112
    for index, label in enumerate(labels):
        cx = left + index * cell_w + cell_w // 2
        parts = label.split("\n")
        for line_index, part in enumerate(parts):
            label_font = font(14, bold=True, mono=True)
            tb = draw.textbbox((0, 0), part, font=label_font)
            draw.text((cx - (tb[2] - tb[0]) / 2, top - 54 + line_index * 18), part, fill=MUTED, font=label_font)

    for row_index, row in enumerate(metrics):
        y0 = top + row_index * cell_h
        y1 = y0 + cell_h - 12
        if row_index == 0:
            draw.rounded_rectangle((52, y0 - 8, WIDTH - 52, y1 + 8), radius=16, fill="#EDF7FF")
        draw.text((72, y0 + 26), row["name"], fill=INK, font=font(22, bold=row_index == 0))
        draw.text((72, y0 + 57), f"macro F1 {row['data']['static']['macro_f1']:.3f}", fill=MUTED, font=font(16, mono=True))
        for column, action in enumerate(actions):
            value = row["data"]["static"]["by_action"][action]["accuracy"]
            x0 = left + column * cell_w + 6
            x1 = x0 + cell_w - 12
            base = row["color"]
            fill = base if value >= 0.999 else "#F5F5F3" if value == 0 else "#E8EBEF"
            outline = base if value >= 0.999 else GRID
            draw.rounded_rectangle((x0, y0, x1, y1), radius=13, fill=fill, outline=outline)
            value_text = percent(value)
            value_color = WHITE if value >= 0.999 and row_index < 3 else INK
            if row_index == 3:
                value_color = INK
            value_font = font(25, bold=True)
            tb = draw.textbbox((0, 0), value_text, font=value_font)
            draw.text((x0 + (x1 - x0 - (tb[2] - tb[0])) / 2, y0 + 31), value_text, fill=value_color, font=value_font)

    footer(
        draw,
        860,
        "Accuracy (%) · balanced benchmark · no failed prediction silently retried",
        "SOURCE · evaluation/*_metrics.json",
    )
    output = EVAL / "action_accuracy.png"
    image.save(output, optimize=True)
    return output


def efficiency(metrics: list[dict[str, Any]]) -> Path:
    image, draw = canvas(900)
    start_y = draw_header(
        image,
        draw,
        title="Decision efficiency",
        subtitle="Mean generated tokens and measured H200 latency · same 1,000-case static benchmark",
        badge="RUN-SPECIFIC RECEIPT",
    )
    draw_legend(image, draw, start_y)
    panels = [
        ("Mean generated tokens", "average_added_tokens", 100.0, "tokens"),
        ("Mean decision latency", "average_decision_latency_ms", 7000.0, "seconds"),
    ]
    for panel_index, (title, key, maximum, unit) in enumerate(panels):
        x0 = 64 + panel_index * 844
        x1 = x0 + 816
        y0, y1 = 270, 760
        draw.rounded_rectangle((x0, y0, x1, y1), radius=18, fill=WHITE, outline=GRID)
        draw.text((x0 + 28, y0 + 24), title, fill=INK, font=font(26, bold=True))
        for row_index, row in enumerate(metrics):
            raw = float(row["data"]["static"][key])
            y = y0 + 102 + row_index * 89
            label = ["REFLEX", "PROMPT", "BASE", "RULES"][row_index]
            draw.text((x0 + 28, y + 8), label, fill=MUTED, font=font(15, bold=row_index == 0, mono=True))
            bar_x0, bar_x1 = x0 + 150, x1 - 112
            draw.rounded_rectangle((bar_x0, y, bar_x1, y + 38), radius=12, fill="#F0F1F3")
            bar_value = max(3, int((bar_x1 - bar_x0) * min(raw / maximum, 1.0)))
            draw.rounded_rectangle((bar_x0, y, bar_x0 + bar_value, y + 38), radius=12, fill=row["color"])
            display = f"{raw:.1f}" if unit == "tokens" else ("<0.001 s" if raw < 1 else f"{raw / 1000:.2f} s")
            display_font = font(18, bold=True, mono=True)
            db = draw.textbbox((0, 0), display, font=display_font)
            draw.text((x1 - 26 - (db[2] - db[0]), y + 8), display, fill=INK, font=display_font)
        draw.text((x0 + 28, y1 - 58), "Lower is faster / shorter; quality is reported separately.", fill=MUTED, font=font(16))

    footer(
        draw,
        804,
        "Latency includes model generation on the original H200 run; it is not normalized across serving stacks.",
        "GREEDY DECODE · BATCH CONFIG PER RECEIPT",
    )
    output = EVAL / "efficiency.png"
    image.save(output, optimize=True)
    return output


def line_chart(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    series: list[tuple[list[tuple[float, float]], str, int]],
    *,
    x_range: tuple[float, float],
    y_range: tuple[float, float],
    x_ticks: list[float],
    y_ticks: list[float],
) -> None:
    x0, y0, x1, y1 = box
    for tick in y_ticks:
        py = y1 - (tick - y_range[0]) / (y_range[1] - y_range[0]) * (y1 - y0)
        draw.line((x0, py, x1, py), fill=GRID, width=1)
        if y_range[1] - y_range[0] <= 0.05:
            label = f"{tick:.3f}"
        elif y_range[1] < 1:
            label = f"{tick:.2f}"
        else:
            label = f"{tick:.1f}"
        tb = draw.textbbox((0, 0), label, font=font(14, mono=True))
        draw.text((x0 - 14 - (tb[2] - tb[0]), py - 8), label, fill=MUTED, font=font(14, mono=True))
    for tick in x_ticks:
        px = x0 + (tick - x_range[0]) / (x_range[1] - x_range[0]) * (x1 - x0)
        draw.line((px, y1, px, y1 + 7), fill=BORDER, width=1)
        label = str(int(tick))
        tb = draw.textbbox((0, 0), label, font=font(14, mono=True))
        draw.text((px - (tb[2] - tb[0]) / 2, y1 + 13), label, fill=MUTED, font=font(14, mono=True))
    draw.line((x0, y1, x1, y1), fill=BORDER, width=2)
    for points, color, width in series:
        mapped = []
        for x, y in points:
            if x_range[0] <= x <= x_range[1] and y_range[0] <= y <= y_range[1]:
                px = x0 + (x - x_range[0]) / (x_range[1] - x_range[0]) * (x1 - x0)
                py = y1 - (y - y_range[0]) / (y_range[1] - y_range[0]) * (y1 - y0)
                mapped.append((px, py))
        if len(mapped) > 1:
            draw.line(mapped, fill=color, width=width, joint="curve")
        for px, py in mapped:
            draw.ellipse((px - 3, py - 3, px + 3, py + 3), fill=color)


def training_dynamics() -> Path:
    receipt = json.loads((PROVENANCE / "run_receipt.json").read_text(encoding="utf-8"))
    train = [(float(item["step"]), float(item["loss"])) for item in receipt["log_history"] if "loss" in item]
    validation = [(float(item["step"]), float(item["eval_loss"])) for item in receipt["log_history"] if "eval_loss" in item]
    image, draw = canvas(900)
    draw_header(
        image,
        draw,
        title="QLoRA training dynamics",
        subtitle="6,000 train · 600 validation · one epoch · 375 optimizer steps · NVIDIA H200",
        badge="REPRODUCIBLE RUN RECEIPT",
    )
    panels = [
        (64, 250, 780, 740, "Warm-up and rapid fit", (0.0, 50.0), (0.0, 1.7), [0, 10, 20, 30, 40, 50], [0.0, 0.4, 0.8, 1.2, 1.6]),
        (880, 250, 1736, 740, "Stable phase detail", (15.0, 375.0), (0.08, 0.10), [50, 100, 150, 200, 250, 300, 350], [0.08, 0.085, 0.09, 0.095, 0.10]),
    ]
    for x0, y0, x1, y1, title, xr, yr, xt, yt in panels:
        draw.rounded_rectangle((x0, y0 - 62, x1, y1 + 54), radius=18, fill=WHITE, outline=GRID)
        draw.text((x0 + 24, y0 - 39), title, fill=INK, font=font(24, bold=True))
        plot_box = (x0 + 80, y0 + 20, x1 - 30, y1 - 40)
        line_chart(
            draw,
            plot_box,
            [(train, "#168AF0", 4), (validation, DOT_RED, 4)],
            x_range=xr,
            y_range=yr,
            x_ticks=xt,
            y_ticks=yt,
        )
        draw.text((x1 - 120, y1 + 5), "STEP", fill=MUTED, font=font(13, mono=True))
    draw.line((73, 202, 105, 202), fill="#168AF0", width=5)
    draw.text((116, 190), "training window loss", fill=INK, font=font(18))
    draw.line((330, 202, 362, 202), fill=DOT_RED, width=5)
    draw.text((373, 190), "validation loss", fill=INK, font=font(18))
    draw.text((1190, 190), "final validation 0.08640", fill=INK, font=font(19, bold=True, mono=True))
    footer(
        draw,
        804,
        "Aggregate train loss 0.11566 includes the warm-up. Final logged train window loss: 0.08596.",
        "SOURCE · provenance/run_receipt.json",
    )
    output = EVAL / "training_dynamics.png"
    image.save(output, optimize=True)
    return output


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    metrics = load_metrics()
    outputs = [
        benchmark_overview(metrics),
        action_accuracy(metrics),
        efficiency(metrics),
        training_dynamics(),
    ]
    sources = [EVAL / row[1] for row in SERIES] + [PROVENANCE / "run_receipt.json"]
    receipt = {
        "generator": "scripts/generate_charts.py",
        "claims_scope": "held-out synthetic Agent Recovery Bench v0",
        "sources": {str(path.relative_to(ROOT)): sha256(path) for path in sources},
        "outputs": {str(path.relative_to(ROOT)): sha256(path) for path in outputs},
    }
    (EVAL / "chart_receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    for output in outputs:
        print(output.relative_to(ROOT))


if __name__ == "__main__":
    main()
