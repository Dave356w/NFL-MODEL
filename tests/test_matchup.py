"""Pre-registered H4: pass-matchup term recorded at lock, validated, graded."""
import datetime as dt
import json

import numpy as np
import pandas as pd
import pytest

import grade_ledger as g
import matchup as mu
import validate_data_files as v

NOW = dt.datetime(2026, 10, 8, 16, tzinfo=dt.timezone.utc)
C = mu.COLS


def features():
    rows = []
    rng = np.random.default_rng(0)
    for season in (2019, 2020, 2021, 2022, 2026):
        for week in (1, 2, 5):
            for i in range(4):
                rows.append({"game_id": f"{season}_{week:02d}_{i}", "season": season, "week": week,
                             **{c: 6.2 + rng.normal(0, .5) for c in C.values()}})
    f = pd.DataFrame(rows)
    # a clear mismatch in 2026 week 5: elite home pass offense vs a porous away pass defense
    f.loc[f.game_id == "2026_05_0", [C[("home", "for")], C[("away", "allowed")], C[("away", "for")], C[("home", "allowed")]]] = [8., 8., 6.2, 6.2]
    return f


def test_term_sign_symmetry_and_no_future_weeks():
    f = features()
    t = mu.pass_terms(f, 2026, 5)
    assert t["2026_05_0"] > 1  # mismatch favoring home is positive
    flipped = f.copy()
    for a, b in ((("home", "for"), ("away", "for")), (("home", "allowed"), ("away", "allowed"))):
        flipped[[C[a], C[b]]] = flipped[[C[b], C[a]]].to_numpy()
    assert np.isclose(mu.pass_terms(flipped, 2026, 5)["2026_05_0"], -t["2026_05_0"])  # antisymmetric
    cur5 = f[(f.season == 2026) & (f.week == 5)]
    later = pd.concat([f, cur5.assign(week=9, game_id=lambda d: d.game_id + "x", **{C[("home", "for")]: 99.})])
    assert mu.pass_terms(later, 2026, 5) == t  # a later week's profiles never change an earlier term
    assert mu.pass_terms(f, 2026, 7) == {}


def test_record_once_before_kickoff_and_validate(tmp_path):
    f = features()
    f.to_csv(tmp_path / mu.FEATURES, index=False)
    recs = [{"game_id": "2026_05_0", "season": 2026, "week": 5, "kickoff_utc": "2026-10-09T00:15:00+00:00"},
            {"game_id": "2026_05_1", "season": 2026, "week": 5, "kickoff_utc": "2026-10-08T15:00:00+00:00"}]  # already started
    (tmp_path / "forward_predictions.jsonl").write_text("\n".join(json.dumps(r) for r in recs) + "\n")
    assert mu.record(tmp_path, tmp_path, NOW) == 1
    assert mu.record(tmp_path, tmp_path, NOW) == 0  # append-only, first record only
    assert v.validate_h4(tmp_path / "h4_terms.jsonl") == 1
    p = tmp_path / "h4_terms.jsonl"
    bad = json.loads(p.read_text())
    for b in ({**bad, "captured_utc": "2026-10-09T01:00:00+00:00"}, {**bad, "pass_term": "x"}):
        p.write_text(json.dumps(b) + "\n")
        with pytest.raises(ValueError):
            v.validate_h4(p)


def test_safe_record_never_raises(tmp_path, capsys):
    (tmp_path / "forward_predictions.jsonl").write_text(json.dumps(
        {"game_id": "x", "season": 2026, "week": 5, "kickoff_utc": "2026-10-09T00:15:00+00:00"}) + "\n")
    assert mu.safe_record(tmp_path / "missing_run_dir", tmp_path, NOW) == 0
    assert "h4: skipped" in capsys.readouterr().err


def test_partial_r_recovers_signal_beyond_spread_and_ignores_spread_echo():
    rng = np.random.default_rng(1)
    n = 3000
    spread = rng.normal(0, 6, n)
    term = rng.normal(0, 1, n)
    result = spread + 2 * term + rng.normal(0, 12, n)
    r, lo, hi = mu.partial_r(term, result, spread, reps=300)
    assert lo > 0 and .1 < r < .2
    echo = spread / 6 + rng.normal(0, .1, n)  # a term that is just the spread again carries nothing beyond it
    r2, lo2, hi2 = mu.partial_r(echo, spread + rng.normal(0, 12, n), spread, reps=300)
    assert lo2 < 0 < hi2


def ledger_row(gid, term, result, spread=3.):
    rec = {"experiment": "e", "revision": "r", "game_id": gid, "season": 2026, "week": 5, "home": "H", "away": "A",
           "generated_utc": "2026-10-08T06:00:00+00:00", "kickoff_utc": "2026-10-09T00:15:00+00:00", "model_wp": .6,
           "market_wp": .58, "homefield_wp": .55, "spread_line": spread, "home_moneyline": -150, "away_moneyline": 130}
    return rec, {"game_id": gid, "pass_term": term}, {"game_id": gid, "away_score": 0, "home_score": result, "result": result}


def test_report_block_and_column():
    rng = np.random.default_rng(2)
    parts = [ledger_row(f"g{i}", t, round(3 + 4 * t + rng.normal(0, 3)) or 1) for i, t in enumerate(rng.normal(0, 1, 40))]
    recs, terms, res = zip(*parts)
    out = g.grade(list(recs), pd.DataFrame(list(res)), h4=list(terms))
    assert out.h4_pass_term.notna().all()
    text = g.report_text(out)
    assert "Pre-registered H4" in text and "n=40 graded games" in text and "supported" in text
    assert "H4" not in g.report_text(g.grade(list(recs), pd.DataFrame(list(res))))  # no terms, no block
