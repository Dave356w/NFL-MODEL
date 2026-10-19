from pathlib import Path
import numpy as np
import pandas as pd
from research import production_sanity as s


def test_independent_grading_skip_push_away_missing_and_pending():
    args=([3.,3.+1e-11,4.,-2.,1.,4.,np.nan],[3.,3.,3.,-3.,0.,3.,3.],[3.,4.,3.,0.,0.,np.nan,7.])
    assert s.independent_grades(*args,favorite_on_tie=False).tolist()==['S','S','P','W','P','','']
    # Production: a matching line is a favorite bet, graded like any other.
    assert s.independent_grades(*args).tolist()==['P','W','P','W','P','','']


def test_independent_zero_edge_favorite_away_and_pickem_skip():
    grades=s.independent_grades([-7.,-7.,0.,0.],[-7.,-7.,0.,0.],[-10.,-3.,5.,np.nan])
    assert grades.tolist()==['W','L','S','S']


def test_independent_moneyline_payouts_loss_tie_neutral_and_missing():
    d=pd.DataFrame({'model_wp':[.6,.4,.6,.5,.4,.6], 'home won':[1.,0.,.5,1.,1.,np.nan],
                    'home_moneyline':[-150.]*6,'away_moneyline':[130.]*6})
    grades,units=s.independent_moneyline(d)
    assert grades.tolist()==['W','W','P','','L','']
    np.testing.assert_allclose(units,[2/3,1.3,0.,np.nan,-1.,np.nan],equal_nan=True)


def test_independent_median_uses_losses_ties_and_only_prior_seasons():
    x=np.tile([1.,4.,8.,12.],80)
    d=pd.DataFrame({'season':np.repeat([2021,2022],160),'model_spread':x,'result':x+2})
    rule=s.median_rule(d,2023)
    assert rule['magnitudes']==[3.,6.,10.,14.]
    poison=d.assign(season=2023,result=-1000.)
    assert s.median_rule(pd.concat([d,poison]),2023)==rule
    tied=d.assign(result=0.)
    assert s.median_rule(pd.concat([d,tied]),2023)['magnitudes']==[1.5,3.,5.,7.]


def test_current_production_snapshot_passes_independent_audit():
    data=Path(__file__).resolve().parents[1]/'data'
    audit=s.inspect(data)
    assert audit['status']=='PASS' and all(audit['checks'].values())
    rule=next(x for x in audit['rules'] if x['season']==2026)
    assert rule['magnitudes']==[3.,4.,7.,14.] and rule['training_max_season']==2025
    total=next(x for x in audit['historical'] if x['season']=='All')
    assert total['selected']+total['skips']==total['opportunities']
    if total['opportunities']==895:
        assert (total['wins'],total['losses'],total['pushes'],total['skips'])==(473,397,25,0)
    for r in audit['historical']:
        if r['favorite']:
            assert r['favorite']['bets']==r['common_moneyline']['bets']


def test_missing_data_has_explicit_empty_state(tmp_path):
    assert s.inspect(tmp_path)['status']=='No historical inputs yet'
    assert 'No historical inputs yet' in s.report(tmp_path)
