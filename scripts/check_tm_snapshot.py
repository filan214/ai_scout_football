"""Weekly freshness check: has transfermarkt-datasets published data newer than `as_of_date`?

Downloads the Kaggle zip to a temporary folder, reads the latest games/player_valuations dates and compares
them with `as_of_date` in config/settings.yaml. Changes nothing in the project. In GitHub Actions it writes
`newer`, `games_end`, `valuations_end` and `as_of_date` to $GITHUB_OUTPUT.
"""

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from scout import sources  # noqa: E402
from scout.config import load_settings, setup_logging  # noqa: E402


def main() -> int:
    setup_logging()
    settings = load_settings()
    with tempfile.TemporaryDirectory() as tmp:
        ends = sources.snapshot_end_dates(sources.download_transfermarkt_zip(Path(tmp), settings))
    games_end = ends["games"]
    newer = games_end is not None and games_end > settings.as_of_date
    result = {"as_of_date": str(settings.as_of_date), "games_end": str(games_end),
              "valuations_end": str(ends["player_valuations"]), "newer": newer}
    print(json.dumps(result))
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as fh:
            for key, value in result.items():
                fh.write(f"{key}={str(value).lower() if isinstance(value, bool) else value}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
