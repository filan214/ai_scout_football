"""P0 tests: config loading, FotMob parsing, HTTP retry policy, ingest skip-if-exists. No network."""

import gzip
import json

import pandas as pd
import pytest
import requests
from pydantic import ValidationError

import pipeline
from scout import clean, config, sources
from scout.config import Settings, load_leagues, load_settings


@pytest.fixture
def settings() -> Settings:
    return load_settings().model_copy(update={"scraping_delay_seconds": 0})


def test_settings_load_and_ingest_seasons(settings):
    assert settings.ingest_seasons() == ["2024-25", "2025-26"]
    assert settings.ambition in settings.ambition_club_rank


def test_settings_reject_bad_weights_and_seasons():
    raw = load_settings().model_dump()
    with pytest.raises(ValidationError, match="need_weights"):
        Settings.model_validate({**raw, "need_weights": {"depth": 0.5, "quality": 0.5, "age": 0.2, "contract": 0.1}})
    with pytest.raises(ValidationError, match="season"):
        Settings.model_validate({**raw, "analysis_season": "2025-27"})
    with pytest.raises(ValidationError):
        Settings.model_validate({**raw, "unknown_key": 1})


def test_leagues_yaml():
    leagues = load_leagues()
    assert len(leagues) == 10
    assert sorted(lg.tier for lg in leagues) == [1] * 5 + [2] * 5
    assert len({lg.fotmob_id for lg in leagues}) == 10
    assert len({lg.transfermarkt_id for lg in leagues}) == 10
    super_lig = next(lg for lg in leagues if lg.key == "super_lig")
    assert super_lig.matches("2024-25") == 36
    assert super_lig.matches("2025-26") == 34


def test_to_season_label():
    assert sources.to_season_label("2025/2026") == "2025-26"
    assert sources.to_season_label("1999/2000") == "1999-00"


def _stat_payload(stat: str, players: list[dict]) -> dict:
    return {"TopLists": [{"StatName": stat, "Title": stat.title(), "StatFormat": "number", "StatList": players}]}


PLAYER = {
    "ParticipantName": "A. Player", "ParticiantId": 101, "TeamId": 9, "TeamName": "FC Test",
    "StatValue": 2.1, "SubStatValue": 40.0, "MinutesPlayed": 1726, "MatchesPlayed": 25,
    "StatValueCount": 23, "Rank": 1, "ParticipantCountryCode": "FRA", "Positions": [34, 32],
}


def test_parse_fotmob_stat_ids_are_strings():
    df = sources.parse_fotmob_stat(_stat_payload("interception", [PLAYER]))
    assert list(df.columns) == sources.RAW_COLUMNS
    row = df.iloc[0]
    assert (row.player_id, row.team_id, row.positions) == ("101", "9", "34,32")
    assert (row.stat_value, row.sub_stat_value, row.minutes_played) == (2.1, 40.0, 1726)


def test_parse_fotmob_stat_empty_list():
    df = sources.parse_fotmob_stat(_stat_payload("saves", []))
    assert df.empty and list(df.columns) == sources.RAW_COLUMNS


class FakeResponse:
    def __init__(self, status: int, content: bytes = b""):
        self.status_code, self.content = status, content

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")


class FakeSession:
    def __init__(self, responses):
        self.responses, self.calls = list(responses), 0

    def get(self, url, timeout, stream):
        self.calls += 1
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def test_get_json_retries_then_decodes_gzip(monkeypatch, settings):
    body = gzip.compress(json.dumps({"ok": 1}).encode())
    fake = FakeSession([requests.ConnectionError("reset"), FakeResponse(503), FakeResponse(200, body)])
    monkeypatch.setattr(sources, "_session", fake)
    assert sources._get_json("https://x", settings) == {"ok": 1}
    assert fake.calls == 3


def test_get_gives_up_after_max_retries(monkeypatch, settings):
    fake = FakeSession([FakeResponse(500)] * 10)
    monkeypatch.setattr(sources, "_session", fake)
    with pytest.raises(requests.HTTPError):
        sources._get("https://x", settings)
    assert fake.calls == settings.scraping_max_retries + 1


def test_get_does_not_retry_403(monkeypatch, settings):
    fake = FakeSession([FakeResponse(403)])
    monkeypatch.setattr(sources, "_session", fake)
    with pytest.raises(sources.NotAvailable):
        sources._get("https://x", settings)
    assert fake.calls == 1


def test_fetch_fotmob_skips_unpublished_lists(monkeypatch, settings):
    names = ["mins_played", "interception", "saves", "rating_team", "goals_team_match"]
    index = {"TopLists": [{"StatName": s} for s in names]}

    def fake_get_json(url, _settings):
        if url.endswith("topstats.json"):
            return index
        stat = url.rsplit("/", 1)[1].removesuffix(".json")
        if stat == "saves":
            raise sources.NotAvailable("403")
        assert "_team" not in stat, "club stat lists must be skipped"
        return _stat_payload(stat, [PLAYER])

    monkeypatch.setattr(sources, "_get_json", fake_get_json)
    df = sources.fetch_fotmob(47, 27110, settings)
    assert sorted(df["stat_name"].unique()) == ["interception", "mins_played"]
    assert set(df["fotmob_season_id"]) == {"27110"}


def test_fetch_fotmob_requires_minutes(monkeypatch, settings):
    monkeypatch.setattr(sources, "_get_json", lambda url, s: {"TopLists": []})
    with pytest.raises(RuntimeError, match="minutes"):
        sources.fetch_fotmob(47, 27110, settings)


def test_select_profile_ids_gap_league_plus_seeded_sample():
    mins = pd.DataFrame({
        "league": ["championship"] * 3 + ["eredivisie"] * 4 + ["la_liga"] * 4,
        "season": ["2024-25", "2025-26", "2025-26"] + ["2025-26"] * 8,
        "player_id": ["c1", "c2", "c3", "e1", "e2", "e3", "e4", "l1", "l2", "l3", "l4"],
        "minutes_played": [10, 20, 3000, 2000, 2000, 100, 2000, 2000, 50, 2000, 2000],
    })
    args = (["championship"], ["eredivisie", "la_liga"], "2025-26", 900, 2, 7)
    ids = clean.select_profile_ids(mins, *args)
    assert {"c1", "c2", "c3"} <= set(ids)
    sampled = set(ids) - {"c1", "c2", "c3"}
    assert len(sampled) == 4 and not sampled & {"e3", "l2"}
    assert clean.select_profile_ids(mins.sample(frac=1, random_state=1), *args) == ids


def test_ingest_skips_existing_files(monkeypatch, tmp_path, settings):
    monkeypatch.setattr(config, "RAW_DIR", tmp_path / "raw")
    fetched = []

    def fake_fetch(league_id, season_id, _settings):
        fetched.append((league_id, season_id))
        return sources.parse_fotmob_stat(_stat_payload("mins_played", [PLAYER]))

    def fake_teams(league_id, season_id, _settings):
        fetched.append(("clubs", league_id, season_id))
        return pd.DataFrame({"stat_name": ["possession_percentage_team"], "team_id": ["9"], "stat_value": [55.0]})

    monkeypatch.setattr(sources, "fotmob_season_ids", lambda lid, s: {"2024-25": 1, "2025-26": 2})
    monkeypatch.setattr(sources, "fetch_fotmob", fake_fetch)
    monkeypatch.setattr(sources, "fetch_fotmob_team_stats", fake_teams)
    tier1 = [lg for lg in load_leagues() if lg.tier == 1]
    pipeline._write_parquet(pd.DataFrame({"x": [1]}), config.fotmob_raw_path(tier1[0].key, "2024-25"))

    assert pipeline.ingest_fotmob(settings, [1], refresh=False) == []
    assert len(fetched) == 2 * len(tier1) * 2 - 1
    saved = pd.read_parquet(config.fotmob_raw_path(tier1[0].key, "2025-26"))
    assert (saved.loc[0, "league"], saved.loc[0, "season"]) == (tier1[0].key, "2025-26")

    fetched.clear()
    assert pipeline.ingest_fotmob(settings, [1], refresh=False) == []
    assert fetched == []


def test_snapshot_end_dates_reads_plain_and_gzipped_tables(tmp_path):
    import zipfile
    from datetime import date

    zip_path = tmp_path / "player-scores.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("games.csv", "game_id,date\n1,2026-07-01\n2,2026-07-06\n3,\n")
        zf.writestr("player_valuations.csv.gz", gzip.compress(b"player_id,date,market_value\n9,2026-06-12,1000\n"))
    assert sources.snapshot_end_dates(zip_path) == {"games": date(2026, 7, 6), "player_valuations": date(2026, 6, 12)}


def test_snapshot_end_dates_missing_table_is_none(tmp_path):
    import zipfile

    zip_path = tmp_path / "player-scores.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("clubs.csv", "club_id\n1\n")
    assert sources.snapshot_end_dates(zip_path) == {"games": None, "player_valuations": None}


def test_parse_fotmob_league_clubs_single_and_split_tables():
    def row(i, name):
        return {"id": i, "name": name}

    single = {"details": {"selectedSeason": "2026/2027"},
              "table": [{"data": {"table": {"all": [row(1, "A"), row(2, "B")]}}}]}
    out = sources.parse_fotmob_league_clubs(single)
    assert out.to_dict("list") == {"team_id": ["1", "2"], "team_name": ["A", "B"], "season": ["2026/2027"] * 2}
    split = {"details": {"selectedSeason": "2026/2027"},
             "table": [{"data": {"tables": [{"table": {"all": [row(1, "A")]}},
                                            {"table": {"all": [row(2, "B"), row(1, "A")]}}]}}]}
    assert sources.parse_fotmob_league_clubs(split)["team_id"].tolist() == ["1", "2"]


def test_parse_fotmob_squad_skips_coach_and_types_fields():
    payload = {"details": {"id": 9825, "name": "Arsenal"}, "squad": {"squad": [
        {"title": "coach", "members": [{"id": 1, "name": "Coach"}]},
        {"title": "keepers", "members": [{"id": 2, "name": "K", "dateOfBirth": "1995-09-15",
                                          "transferValue": 23534518, "positionIdsDesc": "GK"}]},
        {"title": "attackers", "members": [{"id": 3, "name": "S", "dateOfBirth": None, "transferValue": None,
                                            "positionIdsDesc": "ST"}]},
    ]}}
    out = sources.parse_fotmob_squad(payload)
    assert out["fotmob_id"].tolist() == ["2", "3"]
    assert out["team_id"].tolist() == ["9825", "9825"] and out["team_name"].iloc[0] == "Arsenal"
    assert out["date_of_birth"].iloc[0] == pd.Timestamp("1995-09-15") and pd.isna(out["date_of_birth"].iloc[1])
    assert out["market_value_eur"].iloc[0] == 23534518 and pd.isna(out["market_value_eur"].iloc[1])
