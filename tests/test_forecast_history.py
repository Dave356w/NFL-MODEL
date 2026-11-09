import datetime as dt
import json

import pandas as pd
import pytest

import forecast_history as h
import ats_locks as locks

UTC=dt.timezone.utc
KO=dt.datetime(2026,11,10,1,15,tzinfo=UTC)
NOW=KO-dt.timedelta(hours=2)


def latest(now=NOW,**changes):
    row=dict(game_id='2026_09_BUF_MIN',season=2026,week=9,home='MIN',away='BUF',
             gameday='2026-11-09',gametime='20:15',result=None,model_wp=.6,
             spread_line=-3.,fixed_band_spread=4.,ready=True,
             home_availability_evidence='{"blockers": ["inactive list missing"]}')
    row.update(changes)
    return dict(manifest=dict(revision='test',generated_utc=now.isoformat(),config_signature='frozen'),
                board=pd.DataFrame([row]),fixed_band_rules=[])


def test_refreshes_append_and_preserve_blocked_forecasts(tmp_path):
    assert h.record(tmp_path,latest(),NOW)==1
    before=(tmp_path/h.JOURNAL).read_bytes()
    assert h.record(tmp_path,latest(model_wp=.2),NOW)==0
    assert (tmp_path/h.JOURNAL).read_bytes()==before
    later=NOW+dt.timedelta(minutes=10)
    assert h.record(tmp_path,latest(later,model_wp=.4),later)==1
    assert (tmp_path/h.JOURNAL).read_bytes().startswith(before)
    assert h.validate(tmp_path)==2
    row=locks.read(tmp_path/h.JOURNAL)[0]
    assert row['board']['home_availability_evidence']=='{"blockers": ["inactive list missing"]}'
    assert row['basis']=='diagnostic pregame refresh; not an ATS lock'
    assert not (tmp_path/locks.CANDIDATES).exists() and not (tmp_path/locks.LOCKS).exists()


def test_history_refuses_postgame_observations_and_future_forecasts(tmp_path):
    assert h.record(tmp_path,latest(),KO)==0
    assert h.record(tmp_path,latest(NOW+dt.timedelta(seconds=1)),NOW)==0
    assert h.record(tmp_path,latest(result=7),NOW)==0
    assert h.validate(tmp_path)==0


def test_history_rejects_tampering(tmp_path):
    h.record(tmp_path,latest(),NOW)
    row=locks.read(tmp_path/h.JOURNAL)[0]
    row['board']['spread_line']=9
    (tmp_path/h.JOURNAL).write_text(json.dumps(row)+'\n')
    with pytest.raises(ValueError,match='hash mismatch'):h.validate(tmp_path)
