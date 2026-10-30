"""Offline pipeline CLI. Implements IMPLEMENTATION_GUIDE §8.

python pipeline.py --stage ingest|clean|features|needs|rank|reports|eval|all [--tiers 1,2] [--refresh]
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from collections.abc import Callable
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from scout import clean, evaluate, features, idmap, llm, needs, rank, report, sources  # noqa: E402
from scout.config import (  # noqa: E402
    DOCS_DIR,
    INTERIM_DIR,
    MANUAL_DIR,
    PROCESSED_DIR,
    RAW_DIR,
    REPORTS_DIR,
    Settings,
    fotmob_profiles_path,
    fotmob_raw_path,
    fotmob_teams_raw_path,
    load_leagues,
    load_settings,
    setup_logging,
    transfermarkt_db_path,
)

log = logging.getLogger("pipeline")

STAGES = ["ingest", "clean", "features", "needs", "rank", "reports", "eval"]


def _short(path: Path) -> str:
    return f"{path.parent.name}/{path.name}"


def _write_parquet(df, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".part")
    df.to_parquet(tmp, index=False)
    tmp.replace(path)


def ingest_fotmob(settings: Settings, tiers: list[int], refresh: bool) -> list[str]:
    """Download raw FotMob player and club lists per league-season; skip files that exist. Returns failures."""
    failures = []
    kinds = [("players", fotmob_raw_path, sources.fetch_fotmob), ("clubs", fotmob_teams_raw_path,
                                                                  sources.fetch_fotmob_team_stats)]
    for league in [lg for lg in load_leagues() if lg.tier in tiers]:
        todo = []
        for season in settings.ingest_seasons():
            for kind, path_fn, fetch in kinds:
                path = path_fn(league.key, season)
                if path.exists() and not refresh:
                    log.info("%s %s %s: exists, skipped (%s)", league.key, season, kind, _short(path))
                else:
                    todo.append((season, kind, path, fetch))
        if not todo:
            continue
        try:
            season_ids = sources.fotmob_season_ids(league.fotmob_id, settings)
        except Exception as exc:
            log.error("%s: FotMob season index failed: %s", league.key, exc)
            failures += [f"{league.key} {s} {k}" for s, k, _, _ in todo]
            continue
        for season, kind, path, fetch in todo:
            started = time.monotonic()
            try:
                if season not in season_ids:
                    raise KeyError(f"FotMob has no {season} for league {league.fotmob_id}: {sorted(season_ids)}")
                df = fetch(league.fotmob_id, season_ids[season], settings)
            except Exception as exc:
                log.error("%s %s %s: failed: %s", league.key, season, kind, exc)
                failures.append(f"{league.key} {season} {kind}")
                continue
            df.insert(0, "league", league.key)
            df.insert(1, "season", season)
            _write_parquet(df, path)
            log.info("%s %s %s: %d rows, %d stat lists, %.0fs -> %s", league.key, season, kind, len(df),
                     df["stat_name"].nunique(), time.monotonic() - started, _short(path))
    return failures


def ingest_transfermarkt(settings: Settings, refresh: bool) -> set[str]:
    """Download transfermarkt-datasets once; log and return the configured competition ids it covers."""
    db_path = transfermarkt_db_path()
    if db_path.exists() and not refresh:
        log.info("transfermarkt: exists, skipped (%s)", _short(db_path))
    else:
        sources.download_transfermarkt(db_path, settings)
    comps = sources.query_transfermarkt(db_path, "SELECT competition_id FROM competitions")
    covered = set(comps["competition_id"])
    leagues = load_leagues()
    for lg in leagues:
        status = "covered" if lg.transfermarkt_id in covered else "MISSING"
        log.info("transfermarkt coverage: tier %d %-20s %-4s %s", lg.tier, lg.name, lg.transfermarkt_id, status)
    log.info("transfermarkt coverage: %d/%d configured leagues", sum(lg.transfermarkt_id in covered for lg in leagues),
             len(leagues))
    return covered


def ingest_fotmob_profiles(settings: Settings, tiers: list[int], covered: set[str], refresh: bool) -> list[str]:
    """Fetch FotMob player profiles for leagues missing from Transfermarkt plus a calibration sample (§15)."""
    leagues = [lg for lg in load_leagues() if lg.tier in tiers]
    gap = [lg.key for lg in leagues if lg.transfermarkt_id not in covered]
    if not gap:
        return []
    mins = clean.read_fotmob_raw(leagues, settings.ingest_seasons(), "mins_played")
    vc = settings.value_calibration
    ids = clean.select_profile_ids(
        mins, gap, [lg.key for lg in leagues if lg.key not in gap], settings.analysis_season,
        settings.squad.reliable_minutes, vc.sample_per_league, vc.seed,
    )
    path = fotmob_profiles_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if refresh:
        path.unlink(missing_ok=True)
    done = set()
    if path.exists():
        with open(path, encoding="utf-8") as fh:
            done = {str(json.loads(line)["id"]) for line in fh if line.strip()}
    todo = [pid for pid in ids if pid not in done]
    log.info("fotmob profiles: %d needed (gap leagues %s + calibration sample), %d exist, %d to fetch",
             len(ids), gap, len(ids) - len(todo), len(todo))
    failures = []
    with open(path, "a", encoding="utf-8") as fh:
        for n, pid in enumerate(todo, 1):
            try:
                profile = sources.fetch_fotmob_player(pid, settings)
            except Exception as exc:
                log.error("fotmob profile %s failed: %s", pid, exc)
                failures.append(f"profile {pid}")
                continue
            fh.write(json.dumps(profile, ensure_ascii=False) + "\n")
            fh.flush()
            if n % 100 == 0:
                log.info("fotmob profiles: %d/%d fetched", n, len(todo))
    return failures


def run_ingest(settings: Settings, tiers: list[int], refresh: bool) -> None:
    """Stage ingest: FotMob stat lists, transfermarkt-datasets, FotMob profiles for TM gaps (§5)."""
    failures = ingest_fotmob(settings, tiers, refresh)
    covered = ingest_transfermarkt(settings, refresh)
    failures += ingest_fotmob_profiles(settings, tiers, covered, refresh)
    if failures:
        raise RuntimeError(f"{len(failures)} downloads failed: {failures[:20]}; re-run to retry them")


def run_clean(settings: Settings, tiers: list[int], refresh: bool) -> None:
    """Stage clean: interim perf / tm tables, Championship gap-fill, processed id_map (§4, §5, §6.1)."""
    leagues = [lg for lg in load_leagues() if lg.tier in tiers]
    seasons = settings.ingest_seasons()
    raw = clean.read_fotmob_raw(leagues, seasons)
    if raw.empty:
        raise RuntimeError("no raw FotMob files; run --stage ingest first")
    perf = clean.build_perf(raw)
    _write_parquet(perf, INTERIM_DIR / "perf.parquet")
    stats = [c for c in perf.columns if c not in clean.PERF_KEYS + ["player_name", "team_id", "team_name",
                                                                       "minutes", "matches", "fotmob_position"]]
    log.info("perf: %d rows, %d players, %d stats, %.1f%% stat cells null", len(perf), perf["fotmob_id"].nunique(),
             len(stats), 100 * perf[stats].isna().to_numpy().mean())
    team_stats = clean.build_team_stats(clean.read_fotmob_teams_raw(leagues, seasons))
    _write_parquet(team_stats, INTERIM_DIR / "team_stats.parquet")
    missing = perf[["league", "season", "team_id"]].drop_duplicates().merge(
        team_stats, on=["league", "season", "team_id"], how="left")["possession"].isna().sum()
    log.info("team_stats: %d club-seasons, possession %.1f-%.1f%%, %d perf clubs without possession", len(team_stats),
             100 * team_stats["possession"].min(), 100 * team_stats["possession"].max(), missing)

    db = transfermarkt_db_path()
    covered_ids = set(sources.query_transfermarkt(db, "SELECT competition_id FROM competitions")["competition_id"])
    covered = [lg for lg in leagues if lg.transfermarkt_id in covered_ids]
    gap = [lg.key for lg in leagues if lg.transfermarkt_id not in covered_ids]
    roster = clean.load_tm_roster(db, covered, seasons)
    id_map, _ = idmap.build_id_map(perf, roster, settings.idmap.name_threshold, settings.idmap.min_club_overlap)
    overrides = pd.read_csv(MANUAL_DIR / "id_overrides.csv", dtype=str)
    id_map = idmap.apply_overrides(id_map, overrides)
    log.info("id_map: %d TM matches (%s), %d overrides", len(id_map), id_map["method"].value_counts().to_dict(),
             len(overrides))
    tm_matched = set(id_map["fotmob_id"])

    tm_players, tm_vals = clean.load_tm_players(db, int(min(seasons)[:4]), settings.as_of_date)
    if gap:
        with open(fotmob_profiles_path(), encoding="utf-8") as fh:
            profiles, fm_vals = clean.parse_profiles([json.loads(x) for x in fh if x.strip()], settings.as_of_date)
        pairs = id_map.loc[id_map["fotmob_id"].isin(profiles["fotmob_id"]), ["fotmob_id", "tm_id"]]
        calibration = clean.fit_value_ratio(pairs, tm_vals, fm_vals, settings.as_of_date,
                                            settings.value_calibration.max_date_gap_days)
        (INTERIM_DIR / "value_calibration.json").write_text(json.dumps(calibration, indent=2), encoding="utf-8")
        log.info("value calibration: TM/SciSports ratio %.3f (n=%d, IQR %.2f-%.2f, by TM value %s)",
                 calibration["ratio"], calibration["n"], calibration["q25"], calibration["q75"],
                 {k: round(v, 2) if v else v for k, v in calibration["median_by_tm_value"].items()})
        gap_players = set(perf.loc[perf["league"].isin(gap), "fotmob_id"])
        missing = gap_players - tm_matched - set(profiles["fotmob_id"])
        if missing:
            log.warning("%d unmatched gap-league players have no FotMob profile yet (re-run ingest)", len(missing))
        use_profile = clean.choose_gap_fill_ids(id_map, tm_players, gap_players, set(profiles["fotmob_id"]),
                                                settings.as_of_date, settings.value_calibration.max_date_gap_days)
        log.info("gap-fill: %d players from FotMob profiles (%d unmatched, %d with stale TM values)",
                 len(use_profile), len(use_profile - tm_matched), len(use_profile & tm_matched))
        g_players, g_vals = clean.gap_fill_rows(profiles, fm_vals, use_profile, calibration["ratio"],
                                                settings.as_of_date)
        tm_players = pd.concat([tm_players, g_players], ignore_index=True)
        tm_vals = pd.concat([tm_vals, g_vals], ignore_index=True)
        profile_rows = pd.DataFrame({"fotmob_id": sorted(use_profile)})
        profile_rows = profile_rows.assign(tm_id="fotmob-" + profile_rows["fotmob_id"], match_score=np.nan,
                                           method="fotmob_profile")
        id_map = pd.concat([id_map[~id_map["fotmob_id"].isin(use_profile)], profile_rows], ignore_index=True)
    _write_parquet(tm_players, INTERIM_DIR / "tm_players.parquet")
    _write_parquet(tm_vals, INTERIM_DIR / "tm_valuations.parquet")
    _write_parquet(id_map, PROCESSED_DIR / "id_map.parquet")
    log.info("tm_players: %d rows %s; tm_valuations: %d rows", len(tm_players),
             tm_players["source"].value_counts().to_dict(), len(tm_vals))

    covered_perf = perf[perf["league"].isin([lg.key for lg in covered])]
    for label, df, ids in [("TM leagues, TM ids", covered_perf, tm_matched),
                           ("all leagues incl. FotMob profiles", perf, set(id_map["fotmob_id"]))]:
        rates = idmap.match_rates(df, ids)
        log.info("match rate (%s): rows %.2f%%, minutes-weighted %.2f%%", label,
                 100 * rates.loc["all", "match_rate"], 100 * rates.loc["all", "minutes_weighted"])
    for league, r in idmap.match_rates(covered_perf, tm_matched).drop(index="all").iterrows():
        log.info("  %-20s rows %.2f%%  minutes-weighted %.2f%%", league, 100 * r["match_rate"],
                 100 * r["minutes_weighted"])
    unmatched = idmap.unmatched_report(covered_perf, roster, tm_matched, top_n=30)
    unmatched.to_csv(INTERIM_DIR / "unmatched.csv", index=False)
    log.info("unmatched: top %d by minutes -> interim/unmatched.csv", len(unmatched))


def run_features(settings: Settings, tiers: list[int], refresh: bool) -> None:
    """Stage features: league strength, player_season with p90/adj/pct, coverage check (§6.2-§6.4)."""
    leagues = [lg for lg in load_leagues() if lg.tier in tiers]
    perf = pd.read_parquet(INTERIM_DIR / "perf.parquet")
    perf = perf[perf["league"].isin([lg.key for lg in leagues])]
    id_map = pd.read_parquet(PROCESSED_DIR / "id_map.parquet")
    tm_players = pd.read_parquet(INTERIM_DIR / "tm_players.parquet")
    tm_vals = pd.read_parquet(INTERIM_DIR / "tm_valuations.parquet")
    team_stats = pd.read_parquet(INTERIM_DIR / "team_stats.parquet")
    season, as_of = settings.analysis_season, settings.as_of_date

    squads = features.squad_values(perf[perf["season"] == season], id_map, clean.value_as_of(tm_vals, as_of))
    strength = features.league_strength(squads, settings.league_strength_floor)
    _write_parquet(strength, PROCESSED_DIR / "league_strength.parquet")
    log.info("league strength (%s, values as of %s, %d clubs, %.1f%% of players valued):", season, as_of,
             len(squads), 100 * squads["valued"].sum() / squads["players"].sum())
    for r in strength.itertuples():
        log.info("  %-20s clubs %2d  median squad €%7.1fm  index %5.1f  factor %.3f", r.league, r.clubs,
                 r.median_squad_value_m, r.index_0_100, r.factor)

    ps = features.build_player_season(perf, id_map, tm_players, tm_vals, team_stats, strength, leagues, settings,
                                      season, as_of)
    final_stats, coverage = features.coverage_check(ps, settings.position_stats, settings.stat_fallbacks,
                                                    settings.coverage_threshold, settings.min_stats_per_group)
    ps = features.add_percentiles(ps, features.stat_columns(perf))
    _write_parquet(ps, PROCESSED_DIR / "player_season.parquet")
    profiles = features.squad_profiles(ps, settings.model_copy(update={"position_stats": final_stats}))
    _write_parquet(profiles, PROCESSED_DIR / "squad_profiles.parquet")
    (PROCESSED_DIR / "coverage.json").write_text(json.dumps(
        {"season": season, "position_stats": final_stats, "coverage": coverage.round(4).to_dict(orient="index")},
        indent=2), encoding="utf-8")
    q = ps[ps["qualifies"]]
    log.info("player_season %s: %d rows, %d qualifying %s; age null %d, market value null %d (qualifying)", season,
             len(ps), len(q), q["position_group"].value_counts().to_dict(), q["age"].isna().sum(),
             q["market_value_m"].isna().sum())
    log.info("position_stats after coverage check: %s", final_stats)


def effective_settings(settings: Settings) -> Settings:
    """Settings with position_stats replaced by the lists that passed the coverage check (§6.2)."""
    coverage = json.loads((PROCESSED_DIR / "coverage.json").read_text(encoding="utf-8"))
    return settings.model_copy(update={"position_stats": coverage["position_stats"]})


def run_needs(settings: Settings, tiers: list[int], refresh: bool) -> None:
    """Stage needs: need scores for every club of the target league (§6.5)."""
    ps = pd.read_parquet(PROCESSED_DIR / "player_season.parquet")
    eff = effective_settings(settings)
    clubs = needs.league_clubs(ps, settings.target_league)
    if settings.target_club not in clubs:
        raise ValueError(f"target_club {settings.target_club!r} is not a {settings.target_league} club: {clubs}")
    all_needs = needs.compute_all_needs(ps, eff)
    _write_parquet(all_needs, PROCESSED_DIR / "needs.parquet")
    log.info("needs: %d clubs x %d groups, ambition %s; priorities %s", len(clubs),
             all_needs["position_group"].nunique(), settings.ambition, all_needs["priority"].value_counts().to_dict())
    mine = all_needs[all_needs["club"] == settings.target_club].sort_values("need_score", ascending=False)
    for r in mine.itertuples():
        log.info("  %s %-2s need %5.1f %-6s depth %5.1f quality %5.1f age %5.1f contract %5.1f (reliable %d/%d)",
                 r.club, r.position_group, r.need_score, r.priority, r.depth_gap, r.quality_gap, r.age_risk,
                 r.contract_risk, r.reliable, settings.squad.depth_targets[r.position_group])


def run_rank(settings: Settings, tiers: list[int], refresh: bool) -> None:
    """Stage rank: shortlist per High/Medium need group of the target club (§6.6)."""
    ps = pd.read_parquet(PROCESSED_DIR / "player_season.parquet")
    all_needs = pd.read_parquet(PROCESSED_DIR / "needs.parquet")
    mine = all_needs[all_needs["club"] == settings.target_club]
    if mine.empty:
        raise ValueError(f"no needs for {settings.target_club!r}; run --stage needs first")
    shortlist = rank.rank_targets(ps, mine, effective_settings(settings))
    _write_parquet(shortlist, PROCESSED_DIR / "shortlist.parquet")
    log.info("shortlist %s: %d players over groups %s", settings.target_club, len(shortlist),
             shortlist.groupby("position_group", sort=False).size().to_dict())
    for r in shortlist[shortlist["rank"] <= 3].itertuples():
        log.info("  %-2s #%d %-24s %-22s %-18s age %2d €%5.1fm fit %5.1f (perf %5.1f age %5.1f value %5.1f) %s",
                 r.position_group, r.rank, r.player_name, r.team_name, r.league, r.age, r.market_value_m, r.fit,
                 r.performance, r.age_score, r.value_score, r.verdict)


def run_reports(settings: Settings, tiers: list[int], refresh: bool) -> None:
    """Stage reports: cached LLM scouting reports for the target club's shortlist (§6.7, §7.1)."""
    ps = pd.read_parquet(PROCESSED_DIR / "player_season.parquet")
    settings = effective_settings(settings)
    mine = needs.compute_needs(ps, settings.target_club, settings)
    shortlist = rank.rank_targets(ps, mine, settings)
    mine = mine.set_index("position_group")
    names = {lg.key: lg.name for lg in load_leagues()}
    sheets = []
    for _, target in shortlist.iterrows():
        player = ps[(ps["fotmob_id"] == target["fotmob_id"]) & (ps["league"] == target["league"])].iloc[0]
        need = mine.loc[target["position_group"]]
        sheets.append(report.build_fact_sheet(player, target, need, settings, names[target["league"]]))
    misses = [fs for fs in sheets
              if not (REPORTS_DIR / f"{report.cache_key(fs, settings.llm.primary_model)}.json").exists()]
    log.info("reports: %d shortlisted players, %d cached, %d to generate (%s, prompt %s)", len(sheets),
             len(sheets) - len(misses), len(misses), settings.llm.primary_model, report.PROMPT_VERSION)
    checks, tokens, spent = [], dict.fromkeys(llm.USAGE_KEYS, 0), dict.fromkeys(llm.USAGE_KEYS, 0)
    (PROCESSED_DIR / "report_fact_sheets.json").write_text(
        json.dumps({"club": settings.target_club, "ambition": settings.ambition, "sheets": sheets},
                   indent=2, ensure_ascii=False), encoding="utf-8")
    failure = None
    try:
        complete = llm.make_completer(settings, report.ScoutingReport) if misses else None
        for (_, target), fs in zip(shortlist.iterrows(), sheets, strict=True):
            record, hit = report.generate_report(fs, settings, complete, REPORTS_DIR)
            check, usage = record["faithfulness"], record.get("usage", {})
            checks.append(check)
            tokens = llm.add_usage(tokens, usage)
            if not hit:
                spent = llm.add_usage(spent, usage)
            log.info("  %-24s %-2s %s  numbers %d/%d verified%s  %s%s", fs["player.name"], fs["player.position"],
                     "cache hit" if hit else f"generated ({record['model_used']}, {record['attempts']} attempt(s), "
                     f"{usage.get('total', 0)} tokens)", check["verified"], check["numbers"],
                     f", missing keys {check['missing_fact_keys']}" if check["missing_fact_keys"] else "",
                     target["verdict"], "  FLAGGED" if record["flagged"] else "")
    except Exception as exc:
        failure = exc
    summary = report.generation_summary(checks, len(sheets), str(failure)[:300] if failure else None)
    (PROCESSED_DIR / "eval").mkdir(parents=True, exist_ok=True)
    (PROCESSED_DIR / "eval" / "faithfulness.json").write_text(json.dumps(
        {"club": settings.target_club, "prompt_version": report.PROMPT_VERSION, "model": settings.llm.primary_model,
         **summary, "tokens": tokens}, indent=2), encoding="utf-8")
    log.info("faithfulness: %s, %d/%d reports, verified rate %s", summary["status"], summary["reports"],
             summary["expected_reports"], summary["verified_rate"])
    log.info("tokens: this run %d (prompt %d, completion %d, reasoning %d); all %d reports %d", spent["total"],
             spent["prompt"], spent["completion"], spent["reasoning"], len(sheets), tokens["total"])
    if failure:
        raise RuntimeError("Report generation incomplete; faithfulness.json records the failure") from failure


def load_uefa(season_year: int, settings: Settings, refresh: bool) -> pd.DataFrame:
    """UEFA association coefficients for the season ending in `season_year`, cached in raw/uefa/ (§7.4)."""
    path = RAW_DIR / "uefa" / f"coefficients_{season_year}.parquet"
    if path.exists() and not refresh:
        return pd.read_parquet(path)
    coeffs = sources.fetch_uefa_coefficients(season_year, settings)
    _write_parquet(coeffs, path)
    return coeffs


def run_eval(settings: Settings, tiers: list[int], refresh: bool) -> None:
    """Stage eval: backtest (§7.2), sensitivity (§7.3), league strength vs UEFA coefficients (§7.4), summary table."""
    leagues = [lg for lg in load_leagues() if lg.tier in tiers]
    names = {lg.key: lg.name for lg in leagues}
    perf = pd.read_parquet(INTERIM_DIR / "perf.parquet")
    perf = perf[perf["league"].isin(names)]
    tables = [pd.read_parquet(p) for p in (PROCESSED_DIR / "id_map.parquet", INTERIM_DIR / "tm_players.parquet",
                                          INTERIM_DIR / "tm_valuations.parquet", INTERIM_DIR / "team_stats.parquet")]
    eff = effective_settings(settings)
    ps = pd.read_parquet(PROCESSED_DIR / "player_season.parquet")
    strength = pd.read_parquet(PROCESSED_DIR / "league_strength.parquet")
    out_dir = PROCESSED_DIR / "eval"
    out_dir.mkdir(parents=True, exist_ok=True)
    img = DOCS_DIR / "img"

    # §7.2 backtest: picks made on season_n data (as of backtest.as_of_date), outcomes in season_n1
    bt = settings.backtest
    ps_n, _ = evaluate.season_table(perf, *tables, leagues, eff, bt.season_n, bt.as_of_date)
    ps_n = evaluate.clubs_as_played(ps_n, settings.target_league)
    clubs_n = needs.league_clubs(ps_n, settings.target_league)
    result = evaluate.backtest(ps_n, ps, settings.target_club, clubs_n, eff)
    (out_dir / "backtest.json").write_text(json.dumps(
        {"season_n": bt.season_n, "season_n1": bt.season_n1, "as_of_date": str(bt.as_of_date), **result},
        indent=2, ensure_ascii=False), encoding="utf-8")
    evaluate.plot_backtest(result, img / "backtest.png")

    # §7.3 sensitivity on the analysis season
    clubs = needs.league_clubs(ps, settings.target_league)
    base_needs = pd.read_parquet(PROCESSED_DIR / "needs.parquet")
    base = evaluate.shortlist_sets(ps, base_needs, clubs, eff)
    target_keys = sorted(k for k in base if k[0] == settings.target_club)
    league_keys = sorted(k for k in base if base_needs.set_index(["club", "position_group"]).loc[k, "priority"]
                         in ("High", "Medium"))
    step = settings.evaluation.perturbation

    def with_needs(s: Settings, ps_var: pd.DataFrame | None = None) -> dict:
        p = ps if ps_var is None else ps_var
        nd = needs.compute_all_needs(p, s)
        return evaluate.shortlist_sets(p, nd, clubs, s)

    variants: dict = {}
    for key in eff.fit_weights:
        for sign in (1, -1):
            s_var = eff.model_copy(update={"fit_weights": evaluate.perturb(eff.fit_weights, key, sign * step)})
            variants[f"fit_weights.{key} {sign * step:+.1f}"] = (lambda s=s_var: evaluate.shortlist_sets(
                ps, base_needs, clubs, s))
    for sign in (1, -1):
        s_var = eff.model_copy(update={"league_strength_floor": eff.league_strength_floor + sign * step})
        variants[f"league_strength_floor {sign * step:+.1f}"] = (lambda s=s_var: with_needs(s, evaluate.season_table(
            perf, *tables, leagues, s, settings.analysis_season, settings.as_of_date)[0]))
        s_var = eff.model_copy(update={"stat_weight_blend": eff.stat_weight_blend + sign * step})
        variants[f"stat_weight_blend {sign * step:+.1f} (extra)"] = (lambda s=s_var: with_needs(s))
    sens = evaluate.sensitivity(base, variants, target_keys, league_keys)
    (out_dir / "sensitivity.json").write_text(json.dumps(
        {"perturbation": step, "target_groups": [list(k) for k in target_keys],
         "league_groups": [list(k) for k in league_keys], "variants": sens}, indent=2, ensure_ascii=False),
        encoding="utf-8")

    # §7.4 league strength vs UEFA country coefficients (leagues with a uefa_country)
    season_year = int(settings.analysis_season[:4]) + 1
    try:
        uefa = evaluate.league_uefa(load_uefa(season_year, settings, refresh), leagues)
        validation = {"status": "ok", "source": "UEFA men's association coefficients", "season_year": season_year,
                      "five_season": evaluate.strength_validation(strength, uefa, "uefa_coefficient"),
                      "single_season": evaluate.strength_validation(strength, uefa, "uefa_season_points")}
        evaluate.plot_league_strength(validation["five_season"], names,
                                      f"UEFA country coefficient (5 seasons to {season_year - 1}/{season_year % 100})",
                                      img / "league_strength_uefa.png")
    except Exception as exc:
        log.error("UEFA coefficients unavailable: %s", exc)
        validation = {"status": "unavailable", "season_year": season_year, "error": str(exc)[:300]}
    (out_dir / "league_strength_validation.json").write_text(json.dumps(validation, indent=2, ensure_ascii=False),
                                                             encoding="utf-8")

    # §7.5 fixed league-wide need-calibration acceptance, independent of player values.
    target_league = next(lg for lg in leagues if lg.key == settings.target_league)
    results = evaluate.season_results(sources.load_club_games(
        transfermarkt_db_path(), target_league.transfermarkt_id, int(settings.analysis_season[:4])))
    team_names = needs.team_clubs(ps, settings.target_league)
    values = ps[ps.league == settings.target_league].groupby("team_id").market_value_m.sum()
    values.index = values.index.map(team_names)
    values.index.name = "club"
    all_ambitions = pd.concat([needs.compute_all_needs(ps, eff.model_copy(update={"ambition": a}))
                              for a in ("survive", "midtable", "top4", "title")], ignore_index=True)
    calibration = evaluate.calibrate_needs(all_ambitions, results, values, eff, target_league.matches(
        settings.analysis_season))
    calibration["clubelo"] = sources.probe_clubelo(settings)
    (out_dir / "need_calibration.json").write_text(json.dumps(calibration, indent=2, ensure_ascii=False),
                                                 encoding="utf-8")
    for check in calibration["checks"]:
        log.info("  need calibration %s: %s | %s | %s", check["check"], "PASS" if check["passed"] else "FAIL",
                 check["observed"], check["requirement"])

    # summary table
    faith = json.loads((out_dir / "faithfulness.json").read_text(encoding="utf-8"))
    pct = lambda x: "n/a" if x is None else f"{100 * x:+.1f}%"  # noqa: E731

    def bt_line(r: dict) -> str:
        if r.get("uplift") is None:
            return "no scored picks"
        return (f"uplift {pct(r['uplift'])} [95% CI {pct(r['ci_low'])} to {pct(r['ci_high'])}], hit rate "
                f"{100 * r['hit_rate']:.0f}%, attrition {100 * r['attrition']:.0f}% "
                f"({r['picks_scored']}/{r['picks']} picks)")

    log.info("evaluation summary")
    log.info("  faithfulness           status %s, rate %s, %d reports (%d numbers verified)",
             faith.get("status", "ok"), faith["verified_rate"], faith["reports"], faith["verified"])
    for group, r in result["groups"].items():
        log.info("  backtest %-13s %s", f"{settings.target_club} {group}", bt_line(r))
    log.info("  backtest %-13s %s", "club overall", bt_line(result["overall"]))
    log.info("  backtest %-13s %s", f"{result['league_pooled']['clubs']} clubs", bt_line(result["league_pooled"]))
    naive, model = result["naive_baseline"]["league_pooled"], result["league_pooled"]
    log.info("  backtest %-13s %s", "naive perf", bt_line(naive))
    log.info("    picks median: performance %.1f -> outcome %.1f, age %.0f, value €%.1fm (model) vs %.1f -> %.1f, "
             "age %.0f, value €%.1fm (naive)", model["median_performance_season_n"], model["median_outcome_season_n1"],
             model["median_age"], model["median_market_value_m"], naive["median_performance_season_n"],
             naive["median_outcome_season_n1"], naive["median_age"], naive["median_market_value_m"])
    fmt = lambda x: "n/a" if x is None else f"{x:.2f}"  # noqa: E731
    for name, row in sens.items():
        t, lg = row["target_club"], row["league_high_medium"]
        log.info("  sensitivity %-34s target mean %s min %s (dropped %d) | league H/M mean %s min %s (dropped %d, "
                 "players %s)", name, fmt(t["mean"]), fmt(t["min"]), t["groups_dropped"], fmt(lg["mean"]),
                 fmt(lg["min"]), lg["groups_dropped"], fmt(lg["players_mean"]))
    if validation["status"] == "ok":
        for label, v in (("5-season", validation["five_season"]), ("2025-26 only", validation["single_season"])):
            log.info("  league strength vs UEFA coefficient (%s): Pearson %.2f, Spearman %.2f (n=%d)", label,
                     v["pearson"], v["spearman"], v["n"])
    else:
        log.info("  league strength vs UEFA coefficients: UNAVAILABLE (%s)", validation["error"][:120])


def _not_built(phase: str) -> Callable[[Settings, list[int], bool], None]:
    def run(settings: Settings, tiers: list[int], refresh: bool) -> None:
        raise NotImplementedError(f"built in phase {phase}")

    return run


RUNNERS: dict[str, Callable[[Settings, list[int], bool], None]] = {
    "ingest": run_ingest,
    "clean": run_clean,
    "features": run_features,
    "needs": run_needs,
    "rank": run_rank,
    "reports": run_reports,
    "eval": run_eval,
}


def _parse_tiers(value: str) -> list[int]:
    return sorted({int(t) for t in value.split(",") if t.strip()})


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AI Scout offline pipeline (IMPLEMENTATION_GUIDE §8).")
    parser.add_argument("--stage", required=True, choices=[*STAGES, "all"])
    parser.add_argument("--tiers", type=_parse_tiers, help="comma-separated tiers, e.g. 1,2 (default: tiers_enabled)")
    parser.add_argument("--refresh", action="store_true", help="re-download raw files that already exist")
    parser.add_argument("--club", help="Override target club for this run; config is not changed")
    parser.add_argument("--ambition", choices=["survive", "midtable", "top4", "title"],
                        help="Override ambition for this run; config is not changed")
    args = parser.parse_args(argv)

    setup_logging()
    settings = load_settings()
    overrides = {k: v for k, v in {"target_club": args.club, "ambition": args.ambition}.items() if v is not None}
    settings = settings.model_copy(update=overrides)
    tiers = args.tiers or settings.tiers_enabled
    for stage in STAGES if args.stage == "all" else [args.stage]:
        started = time.monotonic()
        log.info("stage %s: start (tiers %s, seasons %s)", stage, tiers, settings.ingest_seasons())
        try:
            RUNNERS[stage](settings, tiers, args.refresh)
        except Exception as exc:
            log.error("stage %s failed: %s", stage, exc, exc_info=not isinstance(exc, NotImplementedError))
            return 1
        log.info("stage %s: done in %.0fs", stage, time.monotonic() - started)
    return 0


if __name__ == "__main__":
    sys.exit(main())
