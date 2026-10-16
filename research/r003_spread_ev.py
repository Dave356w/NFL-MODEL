"""Research-only spread decisions from R003 margin probabilities and supplied quotes.

Handicaps use sportsbook notation: home -3 covers when home-minus-away > 3;
away +3 covers when home-minus-away < 3. No prices or outcomes are inferred.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

POLICY = "R003-SPREAD-EV-v1"
ARM = "empirical__R003_score_support"
DEFAULT_PMFS = Path(__file__).resolve().parent / "experiments/R003_score_support/marginal_probabilities.npz"
EPS = 1e-12


def _number(value, name):
    if isinstance(value, (bool, str)):
        raise ValueError(f"{name} must be a finite number")
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{name} must be a finite number") from exc
    if not np.isfinite(number):
        raise ValueError(f"{name} must be a finite number")
    return number


def _distribution(pmf, support):
    p, s = np.asarray(pmf, dtype=float), np.asarray(support, dtype=float)
    if (p.ndim != 1 or s.ndim != 1 or not len(p) or p.shape != s.shape
            or not np.isfinite(p).all() or not np.isfinite(s).all()
            or (p < 0).any() or not np.equal(s, np.floor(s)).all()
            or not (np.diff(s) > 0).all()
            or not np.isclose(p.sum(), 1., atol=2e-6, rtol=0)):
        raise ValueError("A normalized margin PMF on ordered unique integer support is required")
    # Saved research marginals use float32. Normalize only accepted rounding error.
    return p / p.sum(), s


def price_offer(pmf, support, *, side, handicap, american_odds, commission=0., stake_fee=0.):
    """Net expected units for 1u risk, including any offered-line push mass.

    commission is a fraction of winning profit only. stake_fee is a fixed
    nonrefundable cost per 1u risk, charged for every outcome including a push.
    """
    p, margin = _distribution(pmf, support)
    if side not in ("home", "away"):
        raise ValueError("side must be home or away")
    handicap = _number(handicap, "handicap")
    odds = _number(american_odds, "american_odds")
    commission = _number(commission, "commission")
    stake_fee = _number(stake_fee, "stake_fee")
    if not (2 * handicap).is_integer():
        raise ValueError("Only integer and half-point handicaps are supported")
    if abs(odds) < 100:
        raise ValueError("American odds must have magnitude at least 100")
    if not 0 <= commission < 1 or stake_fee < 0:
        raise ValueError("commission must be in [0, 1); stake_fee must be nonnegative")
    adjusted = (margin if side == "home" else -margin) + handicap
    win, lose, push = (float(p[adjusted > 0].sum()), float(p[adjusted < 0].sum()),
                       float(p[adjusted == 0].sum()))
    profit = odds / 100 if odds > 0 else 100 / -odds
    net_profit = profit * (1 - commission)
    ev = win * net_profit - lose - stake_fee
    return dict(side=side, handicap=handicap, american_odds=odds,
                commission=commission, stake_fee=stake_fee,
                cover_probability=win, loss_probability=lose, push_probability=push,
                conditional_cover_probability=win / (win + lose) if win + lose else None,
                win_profit=profit, net_win_profit=net_profit, expected_units=ev)


def evaluate_offers(pmf, support, offers):
    """Choose at most one 1u offer per game, or pass, using model-estimated EV.

    All supplied offers must refer to the same game and include actual prices.
    Equal positive EVs select the first offer; outcomes never enter this API.
    """
    _distribution(pmf, support)
    if not isinstance(offers, list):
        raise ValueError("offers must be a list of quoted spreads")
    rows = []
    required = {"side", "handicap", "american_odds"}
    allowed = required | {"commission", "stake_fee", "quote_id", "book", "quote_utc"}
    for index, offer in enumerate(offers):
        if not isinstance(offer, dict) or not required <= offer.keys() or offer.keys() - allowed:
            raise ValueError("Every offer needs side, handicap and american_odds; unsupported quote fields")
        kwargs = {name: offer[name] for name in required | {"commission", "stake_fee"} if name in offer}
        rows.append(dict(offer_index=index, quote=dict(offer), **price_offer(pmf, support, **kwargs)))
    best = max(rows, key=lambda row: row["expected_units"], default=None)
    selected = best if best is not None and best["expected_units"] > EPS else None
    return dict(policy=POLICY, action="bet" if selected else "pass",
                selected_offer_index=selected["offer_index"] if selected else None,
                selected_offer=selected, offers=rows,
                pass_expected_units=0., selection="maximum net EV, at most one flat 1u bet per game",
                reason="positive model-estimated EV" if selected else "no offer has positive net model-estimated EV")


def load_margin(path, game_id):
    """Read exactly one empirical R003 marginal; reject ambiguous/malformed packs."""
    with np.load(path, allow_pickle=False) as pack:
        ids = pack["game_ids"]
        if ids.ndim != 1 or len(set(ids.tolist())) != len(ids):
            raise ValueError("PMF game IDs must be unique")
        matches = np.flatnonzero(ids == game_id)
        if len(matches) != 1:
            raise ValueError(f"Game not present exactly once in R003 PMFs: {game_id}")
        marginals = pack[ARM + "__margin"]
        if marginals.ndim != 2 or marginals.shape[0] != len(ids):
            raise ValueError("PMF rows must align with game IDs")
        p, s = _distribution(marginals[matches[0]], pack["margin_support"])
    return p, s


def evaluate_request(pmfs, request):
    if not isinstance(request, dict) or set(request) != {"game_id", "offers"}:
        raise ValueError("Request needs exactly game_id and offers; outcomes are not accepted")
    game_id = request["game_id"]
    if not isinstance(game_id, str) or not game_id:
        raise ValueError("game_id must be a nonempty string")
    p, s = load_margin(pmfs, game_id)
    decision = evaluate_offers(p, s, request["offers"])
    return dict(game_id=game_id, arm=ARM, pmf_sha256=hashlib.sha256(Path(pmfs).read_bytes()).hexdigest(),
                quote_basis="user-supplied prices and timestamps; availability is not independently verified",
                evidence="research calculation only; no execution or forward registration", **decision)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("request", type=Path, help="JSON with game_id and quoted offers")
    parser.add_argument("--pmfs", type=Path, default=DEFAULT_PMFS)
    args = parser.parse_args(argv)
    try:
        result = evaluate_request(args.pmfs, json.loads(args.request.read_text()))
    except (ValueError, KeyError, OSError) as exc:
        hint = (". Regenerate missing marginals with: python research/distribution_ablations.py R003"
                if not args.pmfs.exists() else "")
        parser.error(f"{exc}{hint}")
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
