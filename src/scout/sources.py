"""External data adapters: FotMob, Transfermarkt, UEFA coefficients.

Library / API notes, checked 2026-10-22 against the installed versions (CLAUDE.md rule 5):

ScraperFC 4.5.0, inspected ScraperFC/sofascore.py:
  Sofascore().get_valid_seasons(league: str) -> {season_year: season_id}
  Sofascore().scrape_player_league_stats(year: str, league: str, accumulation="total",
      selected_positions=["Goalkeepers", "Defenders", "Midfielders", "Forwards"]) -> DataFrame
  `league` is a ScraperFC comps.yaml name ("England Premier League"); `year` must be a key returned
  by get_valid_seasons(), i.e. Sofascore's own season "year" string. Its exact format could not be
  confirmed live. Every request goes through a botasaurus headless Chrome to api.sofascore.com.
  NOT USED: api.sofascore.com is blocked by the build machine's ISP (DNS answers
  blockpage.xlaxiata.id, TLS reset), and comps.yaml has no SOFASCORE id for "Belgium Pro League".

FotMob replaces Sofascore. Plain JSON over HTTPS; neither ScraperFC 4.5.0 nor soccerdata 2026.43.0
has a FotMob player-stats reader. Endpoints, verified live for all 10 leagues:
  league index  www.fotmob.com/api/data/leagues?id={league_id}
                -> stats.seasonStatLinks[] = {"Name": "2025/2026", "TournamentId": 27110, ...}
  season index  data.fotmob.com/stats/{league_id}/season/{season_id}/topstats.json
                -> TopLists[].StatName (names containing "_team" are club stats, e.g. goals_team_match;
                   their rows have ParticiantId 0 and no TeamName)
  stat list     data.fotmob.com/stats/{league_id}/season/{season_id}/{stat_name}.json
                -> TopLists[0].StatList[]: ParticiantId (sic), ParticipantName, TeamId, TeamName,
                   StatValue, SubStatValue, MinutesPlayed, MatchesPlayed, StatValueCount, Rank, Positions
                Body is gzip without a Content-Encoding header; some keeper lists answer 403.
  club list     same path with a club stat, e.g. possession_percentage_team.json
                -> TopLists[0].StatList[]: TeamId, ParticipantName (= club), StatValue (possession %),
                   MatchesPlayed; no TeamName key.
  player        www.fotmob.com/api/data/playerData?id={player_id} (plain JSON)
                -> birthDate.utcTime, contractEnd.utcTime, primaryTeam{teamId,teamName},
                   positionDescription{primaryPosition, positions[].strPosShort.label, isMainPosition},
                   marketValues.values[] = {date, value, currency, source: "scisports", teamId, teamName}
  Season format is "YYYY/YYYY" ("2025/2026"); the project label is "2025-26".

Live squads (weekly `live` stage), verified live for all 10 leagues on 2026-11-10:
  league page   www.fotmob.com/api/data/leagues?id={league_id} (default = current season)
                -> details.selectedSeason "2026/2027"; table[].data.table.all[] = {id, name, ...};
                   split phases (e.g. play-offs) put the groups under table[].data.tables[].table.all[]
                   all[] rows also carry idx (position), played, wins, draws, losses, scoresStr "30-7",
                   pts; the sibling xg[] rows carry teamId, xg, xgConceded, xPoints (checked 2026-11-10)
  team page    www.fotmob.com/api/data/teams?id={team_id}
                -> details{id, name}; squad.squad[] = {title: "coach" | "keepers" | "defenders" |
                   "midfielders" | "attackers", members[]: {id (= stat-list ParticiantId), name,
                   dateOfBirth "YYYY-MM-DD", positionIdsDesc "CB,RB", transferValue (EUR)}}
                transferValue equals the latest monthly SciSports value in playerData.marketValues.
                No contract field: contracts come from playerData.contractEnd.

ScraperFC 4.5.0 Transfermarkt (inspected ScraperFC/transfermarkt.py) for the Championship gap-fill:
  get_valid_seasons(league) loops forever if the season <select> is missing; get_player_links and
  scrape_player(player_link) use cloudscraper / plain requests without delays. NOT USED: every
  client (botasaurus request, cloudscraper, requests) gets Transfermarkt's AWS WAF "Human
  Verification" page (HTTP 405). FotMob player profiles fill the gap instead.

transfermarkt-datasets: the official DuckDB file (pub-e682421888d945d684bcae8890b0ec20.r2.dev) is
  blocked by the same ISP, so the Kaggle mirror (davidcariboo/player-scores, same tables as CSV) is
  downloaded and loaded into a local DuckDB file. Upstream data stops at 2026-07-06 (its README).

UEFA country coefficients (replace ClubElo: api.clubelo.com answered HTTP 502 on 2026-10-23).
  comp.uefa.com/v2/coefficients?coefficientRange=OVERALL&coefficientType=MEN_ASSOCIATION&language=EN
  &page=1&pagesize=60&seasonYear={season end year}: the JSON behind UEFA's ranking pages (undocumented).
  data.members[]: member.countryCode ("ENG"), overallRanking{position, totalValue (5-season coefficient),
  baseSeasonYear, targetSeasonYear}, seasonRankings[]{seasonYear, totalValue}. Checked 2026-10-23: the
  2026 totals equal kassiesa.net's independent table (England 119.519, Spain 97.046, Netherlands 67.929).
"""

from __future__ import annotations

import gzip
import io
import json
import logging
import re
import shutil
import time
import zipfile
from datetime import date
from pathlib import Path

import duckdb
import pandas as pd
import requests

from scout.config import Settings

log = logging.getLogger(__name__)

FOTMOB_API = "https://www.fotmob.com/api/data"
FOTMOB_STATS = "https://data.fotmob.com/stats"
KAGGLE_TM_URL = "https://www.kaggle.com/api/v1/datasets/download/davidcariboo/player-scores"
HTTP_TIMEOUT_SECONDS = 60
CLUB_STAT_RE = re.compile(r"_team(_|$)")
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/141.0 Safari/537.36"
)

FOTMOB_TO_CANONICAL: dict[tuple[str, str], tuple[str, str]] = {
    ("mins_played", "stat_value"): ("minutes", "total"),
    ("mins_played", "sub_stat_value"): ("matches", "total"),
    ("goals", "stat_value"): ("goals", "total"),
    ("goal_assist", "stat_value"): ("assists", "total"),
    ("expected_goals", "stat_value"): ("xg", "total"),
    ("expected_goalsontarget", "stat_value"): ("xgot", "total"),
    ("expected_assists", "stat_value"): ("xa", "total"),
    ("total_scoring_att", "stat_value"): ("shots", "per90"),
    ("total_att_assist", "stat_value"): ("key_passes", "total"),
    ("big_chance_created", "stat_value"): ("big_chances_created", "total"),
    ("won_contest", "stat_value"): ("successful_dribbles", "per90"),
    ("accurate_pass", "stat_value"): ("accurate_passes", "per90"),
    ("accurate_pass", "sub_stat_value"): ("accurate_passes_pct", "pct"),
    ("accurate_long_balls", "stat_value"): ("accurate_long_balls", "per90"),
    ("total_tackle", "sub_stat_value"): ("tackles", "total"),
    ("interception", "sub_stat_value"): ("interceptions", "total"),
    ("effective_clearance", "sub_stat_value"): ("clearances", "total"),
    ("outfielder_block", "sub_stat_value"): ("blocks", "total"),
    ("ball_recovery", "sub_stat_value"): ("ball_recoveries", "total"),
    ("defensive_contributions", "sub_stat_value"): ("defensive_actions", "total"),
    ("poss_won_att_3rd", "stat_value"): ("possession_won_final_third", "per90"),
}

RAW_COLUMNS = [
    "stat_name", "stat_title", "stat_subtitle", "stat_format", "substat_format",
    "player_id", "player_name", "team_id", "team_name", "country_code", "positions",
    "stat_value", "sub_stat_value", "minutes_played", "matches_played", "stat_value_count", "rank",
]


class NotAvailable(Exception):
    """The server answered 403/404: the resource does not exist for this league-season."""


_session = requests.Session()
_session.headers.update({"User-Agent": USER_AGENT})
_last_request_at = 0.0


def _get(url: str, settings: Settings, stream: bool = False) -> requests.Response:
    """GET with `scraping_delay_seconds` between requests and exponential backoff on failure."""
    global _last_request_at
    attempts = settings.scraping_max_retries + 1
    for attempt in range(1, attempts + 1):
        wait = settings.scraping_delay_seconds - (time.monotonic() - _last_request_at)
        if wait > 0:
            time.sleep(wait)
        _last_request_at = time.monotonic()
        try:
            resp = _session.get(url, timeout=HTTP_TIMEOUT_SECONDS, stream=stream)
            if resp.status_code in (403, 404):
                raise NotAvailable(f"HTTP {resp.status_code} for {url}")
            resp.raise_for_status()
            return resp
        except requests.RequestException as exc:
            if attempt == attempts:
                raise
            backoff = settings.scraping_delay_seconds * 2**attempt
            log.warning("GET %s failed (%s); retry %d/%d in %.0fs", url, exc, attempt, attempts - 1, backoff)
            time.sleep(backoff)
    raise AssertionError("unreachable")


def _get_json(url: str, settings: Settings) -> dict:
    content = _get(url, settings).content
    if content[:2] == b"\x1f\x8b":
        content = gzip.decompress(content)
    return json.loads(content)


def to_season_label(fotmob_name: str) -> str:
    """'2025/2026' -> '2025-26'."""
    start, end = fotmob_name.split("/")
    return f"{start}-{end[-2:]}"


def fotmob_season_ids(league_id: int, settings: Settings) -> dict[str, int]:
    """Map season labels ('2025-26') to FotMob stat-season ids for one league."""
    links = _get_json(f"{FOTMOB_API}/leagues?id={league_id}", settings)["stats"]["seasonStatLinks"]
    ids: dict[str, int] = {}
    for link in links:
        if "/" in link["Name"]:
            ids.setdefault(to_season_label(link["Name"]), int(link["TournamentId"]))
    return ids


def parse_fotmob_stat(payload: dict) -> pd.DataFrame:
    """Flatten one FotMob stat list into long rows, one per player; IDs as strings."""
    top = payload["TopLists"][0]
    rows = [
        {
            "stat_name": top["StatName"],
            "stat_title": top.get("Title"),
            "stat_subtitle": top.get("Subtitle"),
            "stat_format": top.get("StatFormat"),
            "substat_format": top.get("SubstatFormat"),
            "player_id": str(p.get("ParticiantId", p.get("ParticipantId"))),
            "player_name": p["ParticipantName"],
            "team_id": str(p["TeamId"]),
            "team_name": p["TeamName"],
            "country_code": p.get("ParticipantCountryCode"),
            "positions": ",".join(str(x) for x in p.get("Positions") or []),
            "stat_value": p.get("StatValue"),
            "sub_stat_value": p.get("SubStatValue"),
            "minutes_played": p.get("MinutesPlayed"),
            "matches_played": p.get("MatchesPlayed"),
            "stat_value_count": p.get("StatValueCount"),
            "rank": p.get("Rank"),
        }
        for p in top["StatList"]
    ]
    return pd.DataFrame(rows, columns=RAW_COLUMNS)


def fetch_fotmob(league_id: int, season_id: int, settings: Settings) -> pd.DataFrame:
    """Every published player stat list for one league-season, long format, uncleaned."""
    base = f"{FOTMOB_STATS}/{league_id}/season/{season_id}"
    index = _get_json(f"{base}/topstats.json", settings)
    stat_names = [t["StatName"] for t in index["TopLists"] if not CLUB_STAT_RE.search(t["StatName"])]
    frames, missing = [], []
    for stat in stat_names:
        try:
            frames.append(parse_fotmob_stat(_get_json(f"{base}/{stat}.json", settings)))
        except NotAvailable:
            missing.append(stat)
    if missing:
        log.info("league %s season %s: %d lists not published: %s", league_id, season_id, len(missing), missing)
    df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=RAW_COLUMNS)
    if "mins_played" not in set(df["stat_name"]):
        raise RuntimeError(f"FotMob league {league_id} season {season_id}: minutes list missing")
    df.insert(0, "fotmob_league_id", str(league_id))
    df.insert(1, "fotmob_season_id", str(season_id))
    return df


TEAM_STATS = ["possession_percentage_team"]


def fetch_fotmob_team_stats(league_id: int, season_id: int, settings: Settings) -> pd.DataFrame:
    """Club stat lists in TEAM_STATS for one league-season: stat_name, team_id, team_name, stat_value."""
    rows = []
    for stat in TEAM_STATS:
        top = _get_json(f"{FOTMOB_STATS}/{league_id}/season/{season_id}/{stat}.json", settings)["TopLists"][0]
        rows += [{"stat_name": top["StatName"], "team_id": str(p["TeamId"]), "team_name": p["ParticipantName"],
                  "stat_value": p.get("StatValue"), "matches_played": p.get("MatchesPlayed")} for p in top["StatList"]]
    return pd.DataFrame(rows)


PLAYER_KEYS = ["id", "name", "birthDate", "contractEnd", "primaryTeam", "positionDescription", "marketValues"]


def fetch_fotmob_player(player_id: str, settings: Settings) -> dict:
    """Profile of one FotMob player (birth date, contract, positions, market values) for the TM gap-fill."""
    payload = _get_json(f"{FOTMOB_API}/playerData?id={player_id}", settings)
    return {key: payload.get(key) for key in PLAYER_KEYS}


def _league_tables(payload: dict) -> list[dict]:
    """Every table on a FotMob league page: the single league table, or each group of a split phase."""
    tables = []
    for block in payload.get("table") or []:
        data = block.get("data") or {}
        tables += [data["table"]] if data.get("table") else []
        tables += [t["table"] for t in data.get("tables") or [] if t.get("table")]
    return tables


def parse_fotmob_league_clubs(payload: dict) -> pd.DataFrame:
    """Clubs in a FotMob league page's table(s): team_id, team_name, season ('2026/2027')."""
    clubs: dict[str, str] = {}
    for table in _league_tables(payload):
        for row in table.get("all") or []:
            clubs.setdefault(str(row["id"]), row["name"])
    season = (payload.get("details") or {}).get("selectedSeason")
    return pd.DataFrame({"team_id": list(clubs), "team_name": list(clubs.values()), "season": season})


STANDINGS_COLUMNS = ["team_id", "team_name", "position", "played", "wins", "draws", "losses", "goals_for",
                     "goals_against", "points", "xg", "xg_conceded", "xpoints"]
SCORES_RE = re.compile(r"^\s*(\d+)\s*-\s*(\d+)\s*$")


def parse_fotmob_standings(payload: dict) -> pd.DataFrame:
    """League table per club joined with FotMob's xG table; a club in two split-phase groups keeps the first."""
    rows: dict[str, dict] = {}
    for table in _league_tables(payload):
        xg = {str(r.get("teamId", r.get("id"))): r for r in table.get("xg") or []}
        for r in table.get("all") or []:
            team_id = str(r["id"])
            if team_id in rows:
                continue
            scores = SCORES_RE.match(r.get("scoresStr") or "")
            x = xg.get(team_id, {})
            rows[team_id] = {
                "team_id": team_id, "team_name": r.get("name"), "position": r.get("idx"),
                "played": r.get("played"), "wins": r.get("wins"), "draws": r.get("draws"),
                "losses": r.get("losses"), "goals_for": int(scores[1]) if scores else None,
                "goals_against": int(scores[2]) if scores else None, "points": r.get("pts"),
                "xg": x.get("xg"), "xg_conceded": x.get("xgConceded"), "xpoints": x.get("xPoints"),
            }
    df = pd.DataFrame(list(rows.values()), columns=STANDINGS_COLUMNS)
    numeric = STANDINGS_COLUMNS[2:]
    df[numeric] = df[numeric].apply(pd.to_numeric, errors="coerce")
    return df


def fetch_fotmob_league(league_id: int, settings: Settings) -> dict:
    """FotMob league page in its current season: clubs, league table and xG table."""
    return _get_json(f"{FOTMOB_API}/leagues?id={league_id}", settings)


SQUAD_COLUMNS = ["fotmob_id", "player_name", "team_id", "team_name", "date_of_birth", "market_value_eur", "positions"]


def parse_fotmob_squad(payload: dict) -> pd.DataFrame:
    """Players of one FotMob team page, coach excluded; market_value_eur = SciSports transferValue."""
    team = payload.get("details") or {}
    rows = [
        {
            "fotmob_id": str(m["id"]),
            "player_name": m.get("name"),
            "team_id": str(team.get("id")),
            "team_name": team.get("name"),
            "date_of_birth": m.get("dateOfBirth"),
            "market_value_eur": m.get("transferValue"),
            "positions": m.get("positionIdsDesc"),
        }
        for group in (payload.get("squad") or {}).get("squad") or []
        if group.get("title") != "coach"
        for m in group.get("members") or []
    ]
    df = pd.DataFrame(rows, columns=SQUAD_COLUMNS).drop_duplicates("fotmob_id")
    df["date_of_birth"] = pd.to_datetime(df["date_of_birth"], errors="coerce")
    df["market_value_eur"] = pd.to_numeric(df["market_value_eur"], errors="coerce")
    return df


def fetch_fotmob_squad(team_id: str, settings: Settings) -> pd.DataFrame:
    """Current squad of one FotMob team."""
    return parse_fotmob_squad(_get_json(f"{FOTMOB_API}/teams?id={team_id}", settings))


def download_transfermarkt_zip(dest_dir: Path, settings: Settings) -> Path:
    """Download the transfermarkt-datasets zip (Kaggle mirror, no login needed) into `dest_dir`."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    zip_path = dest_dir / "player-scores.zip"
    part = zip_path.with_name(zip_path.name + ".part")
    with _get(KAGGLE_TM_URL, settings, stream=True) as resp, open(part, "wb") as fh:
        for chunk in resp.iter_content(chunk_size=1 << 20):
            fh.write(chunk)
    part.replace(zip_path)
    log.info("downloaded %s (%.0f MB)", zip_path.name, zip_path.stat().st_size / 1e6)
    return zip_path


def snapshot_end_dates(zip_path: Path) -> dict[str, date | None]:
    """Latest `date` in the games and player_valuations tables of a transfermarkt-datasets zip.

    The weekly freshness check compares these with `as_of_date`: upstream updates paused at 2026-07-06.
    """
    ends: dict[str, date | None] = {}
    with zipfile.ZipFile(zip_path) as zf:
        for table in ("games", "player_valuations"):
            member = next((m for m in zf.namelist() if re.fullmatch(rf"{table}\.csv(\.gz)?", Path(m).name)), None)
            if member is None:
                ends[table] = None
                continue
            with zf.open(member) as fh:
                dates = pd.read_csv(fh, usecols=["date"], compression="gzip" if member.endswith(".gz") else None)
            latest = pd.to_datetime(dates["date"], errors="coerce").max()
            ends[table] = None if pd.isna(latest) else latest.date()
    return ends


def download_transfermarkt(db_path: Path, settings: Settings) -> Path:
    """Download transfermarkt-datasets (Kaggle mirror) and load every CSV table into one DuckDB file."""
    dest_dir = db_path.parent
    zip_path = download_transfermarkt_zip(dest_dir, settings)
    csv_dir = dest_dir / "csv"

    tmp_db = db_path.with_name(db_path.name + ".part")
    tmp_db.unlink(missing_ok=True)
    csv_dir.mkdir(exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf, duckdb.connect(str(tmp_db)) as con:
        for member in zf.namelist():
            match = re.fullmatch(r"([a-z_]+)\.csv(\.gz)?", Path(member).name)
            if not match:
                continue
            target = csv_dir / Path(member).name
            with zf.open(member) as src, open(target, "wb") as out:
                shutil.copyfileobj(src, out)
            table = match.group(1)
            con.execute(f"CREATE OR REPLACE TABLE {table} AS SELECT * FROM read_csv_auto('{target.as_posix()}')")
            rows = con.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
            log.info("transfermarkt table %-22s %9d rows", table, rows)
    tmp_db.replace(db_path)
    shutil.rmtree(csv_dir)
    zip_path.unlink()
    return db_path


def query_transfermarkt(db_path: Path, sql: str) -> pd.DataFrame:
    """Run a read-only SQL query against the local transfermarkt-datasets DuckDB file."""
    with duckdb.connect(str(db_path), read_only=True) as con:
        return con.execute(sql).df()


def load_club_games(db_path: Path, competition_id: str, season: int) -> pd.DataFrame:
    """Completed club results from the local games/club_games tables, no network."""
    with duckdb.connect(str(db_path), read_only=True) as con:
        return con.execute("""
            SELECT cg.game_id, CAST(cg.club_id AS VARCHAR) AS club_id, c.name AS club,
                   cg.own_goals, cg.opponent_goals, g.date
            FROM club_games cg JOIN games g USING (game_id) JOIN clubs c USING (club_id)
            WHERE g.competition_id = ? AND g.season = ?
              AND g.home_club_goals IS NOT NULL AND g.away_club_goals IS NOT NULL
              AND cg.own_goals IS NOT NULL AND cg.opponent_goals IS NOT NULL
            ORDER BY cg.club_id, cg.game_id
        """, [competition_id, season]).df()


def probe_clubelo(settings: Settings) -> dict:
    """Exactly one dated ClubElo attempt per eval run; failure is explicit, never a zero rating."""
    url = f"http://api.clubelo.com/{settings.as_of_date}"
    try:
        response = _session.get(url, timeout=settings.evaluation.clubelo_timeout_seconds)
        response.raise_for_status()
        ratings = pd.read_csv(io.StringIO(response.text))
        if not {"Club", "Elo"} <= set(ratings) or ratings.empty:
            raise ValueError("response has no Club/Elo rating rows")
        ratings["Elo"] = pd.to_numeric(ratings["Elo"], errors="raise")
        return {"status": "available", "url": url, "attempts": 1, "rows": len(ratings),
                "calibration_measure": "league results; ClubElo is not used"}
    except (requests.RequestException, ValueError, pd.errors.ParserError) as exc:
        return {"status": "unavailable", "url": url, "attempts": 1, "error": str(exc)[:300],
                "spearman": None, "matched_clubs": 0}


def probe_llm_access(settings: Settings, key: str) -> dict:
    """One minimal request, no retries/fallbacks or optional model parameters; redact credentials."""
    url = settings.llm.base_url.rstrip("/") + "/chat/completions"
    result = {"model": settings.llm.primary_model, "attempts": 1, "http_status": None,
              "error_type": None, "error_message": None, "request_id": None}
    try:
        response = _session.post(
            url, headers={"Authorization": "Bearer " + key},
            json={"model": settings.llm.primary_model, "messages": [{"role": "user", "content": "Reply OK."}]},
            timeout=settings.llm.timeout_seconds, allow_redirects=False,
        )
        result["http_status"] = response.status_code
        result["request_id"] = response.headers.get("X-ZenMux-RequestId")
        try:
            payload = response.json()
        except ValueError:
            payload = {}
        result["status"] = "ok" if response.status_code == 200 else "failed"
        if result["status"] == "ok":
            result["usage"] = payload.get("usage", {})
        else:
            error = payload.get("error", {})
            if isinstance(error, dict):
                result["error_type"] = error.get("type")
                result["error_message"] = str(error.get("message", "No error.message returned"))
            else:
                result["error_message"] = "Provider returned no structured error"
    except requests.RequestException as exc:
        result.update(status="failed", error_type=type(exc).__name__, error_message=str(exc))
    if result["error_message"]:
        result["error_message"] = result["error_message"].replace(key, "[MASKED]")
    return result


UEFA_COEFFICIENTS = "https://comp.uefa.com/v2/coefficients"


def fetch_uefa_coefficients(season_year: int, settings: Settings) -> pd.DataFrame:
    """UEFA men's association coefficients for the season ending in `season_year`.

    One row per association: country_code, country, position, coefficient (5-season total),
    season_points (that season alone), base_season_year, target_season_year.
    """
    url = (f"{UEFA_COEFFICIENTS}?coefficientRange=OVERALL&coefficientType=MEN_ASSOCIATION&language=EN"
           f"&page=1&pagesize=60&seasonYear={season_year}")
    rows = []
    for m in _get_json(url, settings)["data"]["members"]:
        overall = m["overallRanking"]
        season = next((s for s in m.get("seasonRankings", []) if s["seasonYear"] == season_year), {})
        rows.append({
            "country_code": m["member"]["countryCode"], "country": m["member"]["countryName"],
            "position": overall["position"], "coefficient": overall["totalValue"],
            "season_points": season.get("totalValue"), "base_season_year": overall.get("baseSeasonYear"),
            "target_season_year": overall.get("targetSeasonYear"),
        })
    return pd.DataFrame(rows)
