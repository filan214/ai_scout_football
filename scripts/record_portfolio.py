"""Record the local Streamlit portfolio walkthrough with Playwright (silent video).

Optional tooling: pip install playwright; python -m playwright install chromium.
Start Streamlit first. Run with --inspect to check the live controls before recording.
"""

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "demo"


def walkthrough(page, chapters, check=False):
    """Navigate the actual app; no mocked data, overlays, or report generation."""
    started = time.monotonic()

    def hold(seconds=6):
        page.wait_for_timeout(700 if check else seconds * 1000)
        if page.locator('[data-testid="stException"]').count():
            raise RuntimeError(page.locator('[data-testid="stException"]').inner_text())

    def chapter(label):
        chapters.append({"seconds": round(time.monotonic() - started, 1), "title": label})
        print(label, flush=True)

    def show(locator, seconds=7):
        page.wait_for_timeout(600)
        locator.evaluate("""el => {
            let parent = el.parentElement;
            while (parent) {
                if (parent.scrollHeight > parent.clientHeight &&
                    ['auto','scroll'].includes(getComputedStyle(parent).overflowY)) {
                    parent.scrollTo({top:parent.scrollTop + el.getBoundingClientRect().top
                        - parent.getBoundingClientRect().top - 80, behavior:'smooth'});
                    return;
                }
                parent = parent.parentElement;
            }
            el.scrollIntoView({behavior:'smooth',block:'center'});
        }""")
        hold(seconds)

    def expand(label, seconds=7):
        summary = page.locator("summary").filter(has_text=label)
        summary.click()
        show(summary, seconds)

    def navigate(label, heading):
        page.get_by_role("link", name=label, exact=True).click()
        page.get_by_role("heading", name=heading, exact=True).wait_for(timeout=60000)
        show(page.get_by_role("heading", name=heading, exact=True), 2)

    def ambition(value):
        slider = page.locator('input[aria-label="Season ambition"]')
        page.wait_for_timeout(1200)
        current = int(slider.input_value())
        for _ in range(abs(value - current)):
            slider.press("ArrowRight" if value > current else "ArrowLeft")
            page.wait_for_timeout(1000)
        slider.press("Tab")

    chapter("Home and recruitment brief")
    hold(7)
    page.get_by_role("combobox", name="Premier League club").fill("West Ham")
    page.get_by_role("option", name="West Ham United", exact=True).click()
    page.get_by_text("Current brief: West Ham United", exact=False).wait_for()
    ambition(3)
    page.get_by_text("Current brief: West Ham United · Challenge for the title", exact=False).wait_for()
    hold(7)
    page.screenshot(path=str(OUT / "silent-thumbnail.png"))
    chapter("Squad needs and ambition comparison")
    navigate("Squad needs", "Where does West Ham United need help?")
    hold(7)
    ambition(0)
    page.get_by_text("Benchmark for stay in the league", exact=False).wait_for()
    hold(6)
    ambition(3)
    page.get_by_text("Benchmark for challenge for the title", exact=False).wait_for()
    hold(6)
    show(page.get_by_role("heading", name="Why each position scored this way"), 9)
    expand("How is the need score calculated?", 8)
    expand("See the detailed statistics behind each position", 8)
    page.locator("summary").filter(has_text="See the detailed statistics behind each position").click()
    expand("See the squad players behind these scores", 7)
    page.screenshot(path=str(OUT / "evidence-preview.png"))
    chapter("DM and FB targets with upgrade checks")
    navigate("Targets", "Who fits West Ham United?")
    hold(5)
    show(page.get_by_role("heading", name="Defensive midfield (DM)", exact=True), 9)
    expand("How were Defensive midfield", 8)
    show(page.get_by_role("heading", name="Full-back (FB)", exact=True), 9)
    expand("How were Full-back", 8)
    page.screenshot(path=str(OUT / "targets-preview.png"))
    chapter("Scouting reports and cited facts")
    navigate("Scouting report", "The case for each player")
    page.get_by_text("Fact check passed:", exact=False).wait_for()
    hold(8)
    show(page.get_by_role("heading", name="What stands out"), 3)
    page.locator("summary").filter(has_text="See the facts behind this statement").first.click()
    hold(8)
    show(page.get_by_role("heading", name="What to check further"), 8)
    show(page.get_by_role("heading", name="The case for each player"), 2)
    page.get_by_role("combobox", name="Position", exact=True).fill("Full-back")
    page.get_by_role("combobox", name="Position", exact=True).press("ArrowDown")
    page.get_by_role("combobox", name="Position", exact=True).press("Enter")
    page.get_by_role("heading", name="Hugo Bueno", exact=True).wait_for()
    show(page.get_by_role("heading", name="Hugo Bueno", exact=True), 9)
    page.screenshot(path=str(OUT / "report-preview.png"))
    show(page.get_by_role("heading", name="What to check further"), 6)
    expand("Explore the full fact sheet", 7)
    chapter("Evaluation: verification, backtest and stability")
    navigate("Evaluation", "How well does AI Scout hold up?")
    hold(8)
    show(page.get_by_role("heading", name="2. Did past picks perform well a season later?"), 3)
    expand("Compare all backtest results and uncertainty ranges", 9)
    show(page.get_by_role("heading", name="3. Do small scoring changes reshuffle the shortlist?"), 3)
    expand("See the detailed ranking-stability results", 7)
    show(page.get_by_role("heading", name="4. Does the league adjustment reflect wider results?"), 8)
    chapter("Calibration limitation and frozen experiment")
    show(page.get_by_role("heading", name="5. Need calibration"), 12)
    page.screenshot(path=str(OUT / "calibration-preview.png"))
    expand("Quality-stat experiment: frozen selection and stop-rule result", 10)
    chapter("Return to the recruitment brief")
    navigate("Home", "Find the right next signing")
    hold(7)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inspect", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        options = {"viewport": {"width": 1920, "height": 1080}}
        if not args.inspect and not args.check:
            options.update(record_video_dir=str(OUT / "raw"),
                           record_video_size={"width": 1920, "height": 1080})
        context = browser.new_context(**options)
        capture_start = time.monotonic()
        page = context.new_page()
        page.goto("http://localhost:8501")
        page.get_by_role("heading", name="Find the right next signing").wait_for(timeout=60000)
        if page.get_by_role("button", name="Don't show again").count():
            page.get_by_role("button", name="Don't show again").click()
        if args.inspect:
            print(page.locator("body").inner_text())
            print(page.locator("input").evaluate_all("els => els.map(e=>e.outerHTML)"))
            page.screenshot(path=str(OUT / "preview.png"))
        else:
            chapters = []
            trim_start = time.monotonic() - capture_start
            try:
                walkthrough(page, chapters, check=args.check)
            except Exception:
                page.screenshot(path=str(OUT / "recording-error.png"))
                print(page.locator("body").inner_text())
                raise
            finally:
                video = page.video
                context.close()
                if video:
                    video.save_as(str(OUT / "walkthrough-raw.webm"))
            if not args.check:
                (OUT / "chapters.json").write_text(json.dumps({
                    "trim_start_seconds": trim_start, "chapters": chapters,
                    "resolution": "1920x1080", "audio": False,
                }, indent=2), encoding="utf-8")
                destination = OUT / "ai-scout-silent-walkthrough.mp4"
                subprocess.run([
                    "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-ss", str(trim_start), "-i", str(OUT / "walkthrough-raw.webm"),
                    "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "20",
                    "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(destination),
                ], check=True)
                probe = subprocess.run([
                    "ffprobe", "-v", "error", "-show_streams", "-show_format",
                    "-of", "json", str(destination),
                ], check=True, capture_output=True, text=True)
                metadata = json.loads(probe.stdout)
                assert not any(stream["codec_type"] == "audio" for stream in metadata["streams"])
                (OUT / "recording-verification.json").write_text(
                    json.dumps(metadata, indent=2), encoding="utf-8")
                print(f"Saved silent video: {destination}", flush=True)
        browser.close()


if __name__ == "__main__":
    main()
