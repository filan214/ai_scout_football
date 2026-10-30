"""Build a narrated portfolio walkthrough from verified AI Scout dashboard captures.

Requires Pillow, FFmpeg/FFprobe, and Windows System.Speech (Microsoft David voice).
Run from the repository root: python scripts/build_portfolio_demo.py
"""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "docs" / "demo"
OUTPUT = OUTPUT_DIR / "ai-scout-portfolio-demo.mp4"
WIDTH, HEIGHT = 1920, 1080
BG = "#0c1118"
PANEL = "#101a20"
GREEN = "#56d4a5"
WHITE = "#f6f9f7"
MUTED = "#b9c7c5"
FONT_DIR = Path("C:/Windows/Fonts")

SCENES = [
    {
        "step": "INTRO",
        "title": "AI Scout",
        "body": "Explainable football recruitment, from a squad gap to an evidence-backed shortlist.",
        "detail": "A local Streamlit portfolio walkthrough · public deployment pending",
        "image": None,
        "narration": (
            "AI Scout turns a Premier League recruitment brief into a shortlist you can inspect. "
            "This is a walkthrough of the working local app. Public deployment is still pending."
        ),
    },
    {
        "step": "01 / THE BRIEF",
        "title": "Start with the club",
        "body": (
            "Choose a club, ambition, budget, and age range. "
            "The brief updates squad needs and target lists across the app."
        ),
        "detail": "10 leagues · 2,532 qualifying players",
        "image": "app_home.png",
        "narration": (
            "Start with a club, season ambition, budget, and age range. The dashboard searches ten European leagues "
            "and shows two thousand five hundred thirty two players with enough match time. "
            "The brief updates needs and targets across pages."
        ),
    },
    {
        "step": "02 / SQUAD NEEDS",
        "title": "Find the real gap",
        "body": (
            "Depth, quality, age, and contract risk form a position score. "
            "A low score is not a call to sign someone."
        ),
        "detail": "Arsenal DM: 17.2 / 100 · Low priority",
        "image": "app_needs.png",
        "narration": (
            "Squad needs combine depth, quality against the ambition benchmark, age, and contract risk. "
            "For Arsenal, defensive midfield ranks highest, but its score is only seventeen point two "
            "out of a hundred. "
            "That is low priority, not a claim that a signing is required."
        ),
    },
    {
        "step": "03 / TARGETS",
        "title": "Compare players",
        "body": (
            "Filter by position, age, and market value, then rank by statistics "
            "tailored to that squad's measured gaps."
        ),
        "detail": "20 Arsenal targets · 10-league search",
        "image": "app_targets.png",
        "narration": (
            "The target list filters players by position, age, and market value, then ranks fit with position-specific "
            "statistics. Equi Fernandez leads Arsenal's defensive midfield list with a ninety two point two fit score. "
            "Market value is an affordability estimate, not a predicted transfer fee."
        ),
    },
    {
        "step": "04 / SCOUTING REPORT",
        "title": "Inspect the evidence",
        "body": (
            "Deterministic code chooses the shortlist and verdict. "
            "The language model only explains a checked fact sheet."
        ),
        "detail": "This report: 16 / 16 numbers verified",
        "image": "app_scouting_report.png",
        "narration": (
            "The verdict and ranking come from deterministic code. The language model writes only the scouting "
            "explanation from a fact sheet. For this player, all sixteen numeric claims match the facts, while the "
            "report also flags a small sample of nine hundred eighty seven minutes."
        ),
    },
    {
        "step": "05 / EVALUATION",
        "title": "Show the trade-off",
        "body": "The model beats the eligible pool, but not a simple performance-only picker on next-season output.",
        "detail": "Model +50.9% · naive +54.4% · median value €15m vs €28m",
        "image": "app_evaluation.png",
        "narration": (
            "Evaluation is explicit about weaknesses. All three hundred eleven report numbers passed fact checks. "
            "In the historical backtest, model picks beat the eligible pool by fifty point nine percent, but a simpler "
            "last-season performance picker reached fifty four point four percent. The model picks were cheaper by "
            "median market value: fifteen million euros versus twenty eight million."
        ),
    },
    {
        "step": "06 / ENGINEERING",
        "title": "Built to be auditable",
        "body": (
            "Offline data pipeline → identity matching → league-adjusted features → "
            "needs and ranking → checked reports → evaluation."
        ),
        "detail": "The app reads prepared data; it never scrapes during a session.",
        "image": None,
        "narration": (
            "Under the hood, an offline pipeline cleans FotMob and Transfermarkt data, matches player identities, "
            "adjusts metrics for league strength, computes needs and shortlists, and verifies generated reports. "
            "The app reads prepared data and never scrapes during a session."
        ),
    },
    {
        "step": "OUTRO",
        "title": "Explore the project",
        "body": "The README links the code, reproducible setup, evaluation outputs, and known limitations.",
        "detail": "Decision support, not a prediction of transfers or future performance.",
        "image": None,
        "narration": (
            "The project also includes tests, sensitivity analysis, and documented data limitations. "
            "Explore the README for the setup and evaluation files. This is decision support, not a prediction "
            "of transfers or future performance."
        ),
    },
]


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT_DIR / name), size=size)


def wrap(draw: ImageDraw.ImageDraw, value: str, face: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    lines: list[str] = []
    current = ""
    for word in value.split():
        candidate = f"{current} {word}".strip()
        if current and draw.textbbox((0, 0), candidate, font=face)[2] > max_width:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def draw_lines(
    draw: ImageDraw.ImageDraw,
    value: str,
    x: int,
    y: int,
    max_width: int,
    face: ImageFont.FreeTypeFont,
    fill: str,
    spacing: int,
) -> int:
    for line in wrap(draw, value, face, max_width):
        draw.text((x, y), line, font=face, fill=fill)
        y += face.size + spacing
    return y


def render_slide(scene: dict[str, str | None], target: Path, index: int) -> None:
    canvas = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((0, 0, 14, HEIGHT), fill=GREEN)
    draw.text((74, 72), "AI SCOUT  /  PORTFOLIO DEMO", font=font("segoeuib.ttf", 25), fill=GREEN)

    screenshot = scene["image"]
    left_width = 490 if screenshot else 820
    title_size = 67 if screenshot else 95
    draw.text((74, 185), str(scene["step"]), font=font("segoeuib.ttf", 27), fill=MUTED)
    title_bottom = draw_lines(
        draw, str(scene["title"]), 74, 250, left_width, font("segoeuib.ttf", title_size), WHITE, 10
    )
    body_bottom = draw_lines(
        draw, str(scene["body"]), 74, title_bottom + 56, left_width, font("segoeui.ttf", 31), WHITE, 17
    )
    detail_top = max(body_bottom + 76, 785)
    draw.rounded_rectangle((72, detail_top, 72 + left_width, min(detail_top + 160, 970)), radius=18, fill=PANEL)
    draw_lines(draw, str(scene["detail"]), 96, detail_top + 28, left_width - 50, font("segoeuib.ttf", 27), GREEN, 10)
    draw.text((74, 1014), "FotMob / Transfermarkt data · local Streamlit app", font=font("segoeui.ttf", 20), fill=MUTED)
    draw.text((1810, 1014), f"{index + 1:02d} / {len(SCENES):02d}", font=font("segoeuib.ttf", 21), fill=MUTED)

    if screenshot:
        source = Image.open(ROOT / "docs" / "img" / str(screenshot)).convert("RGB")
        source = source.crop(
            (0, 50, source.width, min(source.height, 1115 if screenshot == "app_scouting_report.png" else 1046))
        )
        source.thumbnail((1270, 880), Image.Resampling.LANCZOS)
        sx = 610 + (1270 - source.width) // 2
        sy = 90 + (880 - source.height) // 2
        draw.rounded_rectangle(
            (sx - 13, sy - 13, sx + source.width + 13, sy + source.height + 13), radius=20, fill="#243337"
        )
        canvas.paste(source, (sx, sy))
    else:
        for radius, alpha in ((440, 25), (320, 35), (205, 50)):
            color = tuple(
                (int(GREEN[i : i + 2], 16) * alpha + int(BG[i : i + 2], 16) * (255 - alpha)) // 255 for i in (1, 3, 5)
            )
            draw.ellipse((1460 - radius, 430 - radius, 1460 + radius, 430 + radius), outline=color, width=4)
        draw.text((1390, 342), "⚽", font=font("seguiemj.ttf", 150), fill=GREEN)

    canvas.save(target, optimize=True)


def ps_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def narrate(text: str, target: Path) -> None:
    command = (
        "$ErrorActionPreference = 'Stop'; "
        "Add-Type -AssemblyName System.Speech; "
        "$speaker = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
        "$speaker.SelectVoice('Microsoft David Desktop'); "
        "$speaker.Rate = 1; "
        f"$speaker.SetOutputToWaveFile({ps_quote(str(target))}); "
        f"$speaker.Speak({ps_quote(text)}); "
        "$speaker.Dispose()"
    )
    subprocess.run(["powershell.exe", "-NoProfile", "-Command", command], check=True, capture_output=True)
    if not target.exists() or target.stat().st_size < 1000:
        raise RuntimeError(f"Narration was not generated: {target}")


def duration(path: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)],
        check=True,
        capture_output=True,
        text=True,
    )
    return float(json.loads(result.stdout)["format"]["duration"])


def encode_scene(slide: Path, voice: Path, target: Path) -> None:
    seconds = duration(voice) + 0.9
    fade_out = max(seconds - 0.45, 0)
    filters = (
        f"[0:v]fade=t=in:st=0:d=0.35,fade=t=out:st={fade_out:.2f}:d=0.45,format=yuv420p[v];"
        f"[1:a]apad=pad_dur=0.9,afade=t=in:st=0:d=0.15,"
        f"afade=t=out:st={fade_out:.2f}:d=0.35[a]"
    )
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-loop",
            "1",
            "-framerate",
            "30",
            "-i",
            str(slide),
            "-i",
            str(voice),
            "-filter_complex",
            filters,
            "-map",
            "[v]",
            "-map",
            "[a]",
            "-t",
            f"{seconds:.2f}",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "20",
            "-r",
            "30",
            "-c:a",
            "aac",
            "-b:a",
            "160k",
            str(target),
        ],
        check=True,
    )


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="scout-demo-") as temporary:
        temp = Path(temporary)
        parts: list[Path] = []
        for index, scene in enumerate(SCENES):
            slide = temp / f"slide_{index:02d}.png"
            voice = temp / f"voice_{index:02d}.wav"
            video = temp / f"scene_{index:02d}.mp4"
            render_slide(scene, slide, index)
            narrate(str(scene["narration"]), voice)
            encode_scene(slide, voice, video)
            parts.append(video)
            print(f"Scene {index + 1}/{len(SCENES)}: {duration(video):.1f}s")
            if index == 0:
                cover = Image.open(slide)
                cover.resize((1280, 720), Image.Resampling.LANCZOS).save(OUTPUT_DIR / "thumbnail.png")
        playlist = temp / "concat.txt"
        playlist.write_text("".join(f"file '{part.name}'\n" for part in parts), encoding="utf-8")
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(playlist),
                "-c",
                "copy",
                str(OUTPUT),
            ],
            check=True,
            cwd=temp,
        )
    print(f"Built {OUTPUT}")


if __name__ == "__main__":
    main()
