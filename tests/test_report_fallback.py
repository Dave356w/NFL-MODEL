"""Lock policy v7 (owner decision 2026-11-16): lock on complete final reports when inactive lists fail.

The gate is exercised on real collected evidence (official report and inactive pages, resolved
availability, saved board) under v1.25 with the reports-only collection policy. The durability
layer (paired ESPN quote, scoring audit, commit receipt) is policy-agnostic and covered by the
watcher tests, so it is switched off here to isolate the availability gate.
"""
import copy
import datetime as dt
import json

import pytest

import availability_collect as c
import ats_locks as locks
import nfl_model as m
from test_availability_collect import KO, NOW, PLAYERS, SCHEDULE, Sources, resolved, save_board

CUTOFF = KO - dt.timedelta(hours=1)
V125 = 'boxscore-composite-v1.25'


@pytest.fixture(autouse=True)
def v125_without_durability(monkeypatch):
    assert m.REVISION == V125
    durable = tuple(p for p in locks.DURABLE_POLICIES if p not in (locks.FALLBACK_POLICY, locks.NO_REPLACEMENT_POLICY))
    monkeypatch.setattr(locks, 'DURABLE_POLICIES', durable)


def board(tmp_path, inactives=True, report_ok=True, now=NOW, inactive_outage=False):
    source = Sources(); source.now = now; source.inactives = inactives; source.unknown = not report_ok

    def fetch(url):
        if inactive_outage and 'inactiv' in url:
            raise OSError('inactive page outage')
        return source(url)
    state = c.refresh(tmp_path, SCHEDULE, PLAYERS, now=now, fetcher=fetch, force=True, legacy_news=False)
    save_board(tmp_path, resolved(tmp_path, state, asof=now), generated=now)
    return state


def candidates(tmp_path):
    return locks.read(tmp_path / locks.CANDIDATES)


def test_missing_inactive_lists_lock_on_final_reports_with_recorded_reasons(tmp_path):
    board(tmp_path, inactives=False)
    assert locks.record(tmp_path, NOW, policy_version=locks.FALLBACK_POLICY) == dict(candidates=1, locks=0)
    [row] = candidates(tmp_path)
    assert row['policy_version'] == locks.FALLBACK_POLICY and row['availability_gate'] == locks.FALLBACK_GATE
    assert set(row['availability_fallback_reasons']) == {'home', 'away'}
    assert all(any(r.startswith('inactives') for r in v) for v in row['availability_fallback_reasons'].values())
    assert locks.record(tmp_path, CUTOFF, policy_version=locks.FALLBACK_POLICY) == dict(candidates=0, locks=1)
    [lock] = locks.read(tmp_path / locks.LOCKS)
    assert lock['availability_gate'] == locks.FALLBACK_GATE
    locks.validate_store(tmp_path)


def test_complete_inactive_lists_lock_under_the_original_gate(tmp_path):
    board(tmp_path, inactives=True)
    assert locks.record(tmp_path, NOW, policy_version=locks.FALLBACK_POLICY)['candidates'] == 1
    [row] = candidates(tmp_path)
    assert row['availability_gate'] == locks.INACTIVES_GATE and 'availability_fallback_reasons' not in row
    locks.validate_store(tmp_path)


def test_v6_still_requires_inactive_lists(tmp_path):
    board(tmp_path, inactives=False)
    assert locks.record(tmp_path, NOW, policy_version=locks.NO_REPLACEMENT_POLICY) == dict(candidates=0, locks=0)


def test_incomplete_final_report_never_locks_even_under_v7(tmp_path):
    board(tmp_path, inactives=False, report_ok=False)
    assert locks.record(tmp_path, NOW, policy_version=locks.FALLBACK_POLICY) == dict(candidates=0, locks=0)


def test_no_downgrade_after_a_complete_inactive_list_candidate(tmp_path):
    board(tmp_path, inactives=True)
    locks.record(tmp_path, NOW, policy_version=locks.FALLBACK_POLICY, finalize=False)
    later = NOW + dt.timedelta(minutes=5)
    state = board(tmp_path, now=later)
    for team in ('BAL', 'JAX'):  # a later inactive-list check fails with a parser error
        state['teams'][team]['inactives']['error'] = 'parser error'
    save_board(tmp_path, resolved(tmp_path, state, asof=later), generated=later)
    # Control: the same failed board in a store without the earlier candidate saves a fallback.
    fresh = tmp_path / 'fresh'; (fresh / 'latest').mkdir(parents=True)
    for name in ('manifest.json', 'fixed_band_rules.json', 'board.csv'):
        (fresh / 'latest' / name).write_bytes((tmp_path / 'latest' / name).read_bytes())
    assert locks.record(fresh, later, policy_version=locks.FALLBACK_POLICY, finalize=False)['candidates'] == 1
    assert candidates(fresh)[0]['availability_gate'] == locks.FALLBACK_GATE
    assert locks.record(tmp_path, later, policy_version=locks.FALLBACK_POLICY, finalize=False)['candidates'] == 0
    assert locks.record(tmp_path, CUTOFF, policy_version=locks.FALLBACK_POLICY)['locks'] == 1
    [lock] = locks.read(tmp_path / locks.LOCKS)
    assert lock['availability_gate'] == locks.INACTIVES_GATE and lock['generated_utc'] == NOW.isoformat()


def rewrite(tmp_path, rows):
    for r in rows:
        r['candidate_sha256'] = locks.digest({k: v for k, v in r.items() if k != 'candidate_sha256'})
    (tmp_path / locks.CANDIDATES).write_text(''.join(json.dumps(r) + '\n' for r in rows))
    (tmp_path / locks.LOCKS).unlink(missing_ok=True)


@pytest.mark.parametrize('change', [
    dict(availability_gate=locks.INACTIVES_GATE),            # claims complete lists it did not have
    dict(availability_fallback_reasons={}),                 # fallback without reasons
    dict(availability_fallback_reasons={'home': ['inactives: x']}),  # names only one failing side
    dict(availability_gate='anything'),
])
def test_store_rejects_mislabelled_fallbacks(tmp_path, change):
    board(tmp_path, inactives=False)
    locks.record(tmp_path, NOW, policy_version=locks.FALLBACK_POLICY, finalize=False)
    rewrite(tmp_path, [dict(copy.deepcopy(r), **change) for r in candidates(tmp_path)])
    with pytest.raises(ValueError):
        locks.validate_store(tmp_path)


def test_store_rejects_a_complete_gate_carrying_fallback_reasons(tmp_path):
    board(tmp_path, inactives=True)
    locks.record(tmp_path, NOW, policy_version=locks.FALLBACK_POLICY, finalize=False)
    rewrite(tmp_path, [dict(r, availability_fallback_reasons={'home': ['inactives: x']}) for r in candidates(tmp_path)])
    with pytest.raises(ValueError):
        locks.validate_store(tmp_path)


def test_store_rejects_a_fallback_saved_after_a_complete_candidate(tmp_path):
    board(tmp_path, inactives=True)
    locks.record(tmp_path, NOW, policy_version=locks.FALLBACK_POLICY, finalize=False)
    first = candidates(tmp_path)
    later = NOW + dt.timedelta(minutes=5)
    other = tmp_path / 'other'; other.mkdir()
    board(other, inactives=False, now=later)
    locks.record(other, later, policy_version=locks.FALLBACK_POLICY, finalize=False)
    rewrite(tmp_path, first + candidates(other))
    with pytest.raises(ValueError, match='after a complete inactive-list candidate'):
        locks.validate_store(tmp_path)


def test_v125_uses_v7_and_v1_24_keeps_v5(monkeypatch):
    monkeypatch.undo()  # production policy tuple, not the test's durability switch
    assert locks.policy_for_revision(V125) == locks.FALLBACK_POLICY
    assert locks.policy_for_revision('boxscore-composite-v1.24') == locks.REPLACEMENT_POLICY
    assert locks.FALLBACK_POLICY in locks.DURABLE_POLICIES
