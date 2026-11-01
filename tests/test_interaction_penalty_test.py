import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"research"))
import interaction_penalty_test as t
import production_qualification as independent
from test_product_production import fixture


def test_production_reproduces_exact_fit_and_no_interactions_is_joint_refit():
    train, test = fixture()
    p, raw, fit = t.fit_arm(train,test,2023,1,"production")
    expected = t.m.fit_composite(train,t.m.PRODUCT_RECIPE,2023,1)
    assert np.allclose(p,t.m.apply_fit(test,expected),atol=1e-12)
    assert np.allclose(raw,t.m.apply_fit(test,expected,raw=True),atol=1e-12)
    p0, raw0, zero = t.fit_arm(train,test,2023,1,"no_interactions")
    main=t.m.feature_names(t.m.PRODUCT_RECIPE["family"])
    reference,_=independent.fit_predict(train,test,main,[],.1,.1,True)
    assert np.allclose(raw0,reference,atol=1e-10,rtol=0)
    assert np.allclose(p0,t.m.favorite_penalized_wp(reference,test.q),atol=1e-10)
    for name in t.m.PRODUCT_CONTEXT_NAMES:
        assert zero["beta"][zero["names"].index(name)] == 0
    # Jointly fitting without interactions changes the remaining coefficients.
    assert not np.allclose(np.asarray(fit["beta"])[:len(main)],
                           np.asarray(zero["beta"])[:len(main)])


def test_stronger_arm_keeps_main_recipe_and_prior_week_guards():
    train,test=fixture()
    _,_,fit=t.fit_arm(train,test,2023,1,"ridge_3")
    assert fit["recipe"]["ridge"]==.1
    assert fit["recipe"]["interaction_ridge"]==3
    assert fit["recipe"]["favorite_penalty"]==.2
    train.loc[train.index[0],["season","week"]]=[2023,1]
    with pytest.raises(ValueError,match="current or future"):
        t.fit_arm(train,test,2023,1,"production")


def test_selection_cannot_see_evaluation_labels_or_use_brier_or_roi():
    d=pd.DataFrame({"season":[2021,2022,2023,2024],
                    "home won":[1.,0.,1.,0.],
                    "ridge_0.3":[.8,.2,.01,.99],
                    "ridge_1":[.7,.3,.99,.01],
                    "ridge_3":[.6,.4,.99,.01]})
    choice,meta=t.choose_prior(d,2023)
    assert choice=="ridge_0.3" and meta["selection_max_season"]==2022
    changed=d.copy()
    changed.loc[changed.season.ge(2023),["home won",*t.STRONGER]]=0.
    assert t.choose_prior(changed,2023)==(choice,meta)
    tied=d.copy()
    for col in t.STRONGER:
        tied[col]=.5
    assert t.choose_prior(tied,2023)[0]=="ridge_3"
    with pytest.raises(ValueError,match="two completed"):
        t.choose_prior(d[d.season.ge(2022)],2023)


def score_fixture():
    rows=[]
    for year in (*t.YEARS,"all"):
        for arm in ("production","selected_stronger","market"):
            candidate=arm=="selected_stronger"
            rows.append(dict(season=year,arm=arm,
                             ll_delta=-.01 if candidate else 0.,
                             brier_delta=-.005 if candidate else 0.,
                             log_loss=.59 if candidate else .60,
                             brier=.19 if candidate else .20,
                             ll_delta_ci95=[-.02,-.001],
                             brier_delta_ci95=[-.01,-.001]))
    return rows


def test_gate_requires_each_season_both_metrics_and_paired_intervals():
    scores=score_fixture()
    assert t.decision_gate(scores)["passed"]
    row=next(r for r in scores if r["season"]==2024 and r["arm"]=="selected_stronger")
    row["brier_delta"]=.0001
    assert not t.decision_gate(scores)["passed"]
    row["brier_delta"]=-.005
    pooled=next(r for r in scores if r["season"]=="all" and r["arm"]=="selected_stronger")
    pooled["ll_delta_ci95"][1]=.00001
    assert not t.decision_gate(scores)["passed"]
    pooled["ll_delta_ci95"][1]=-.001
    pooled["brier"]=.201
    assert not t.decision_gate(scores)["passed"]
    assert not t.decision_gate(scores)["production_adoption"]


def test_bootstrap_keeps_season_weights_and_pairs_game_differences():
    d=pd.DataFrame({"season":[2023]*4+[2024]*2,
                    "week":[1,1,2,2,1,2]})
    # Constant differences within each season: all draws must equal the
    # original 4/6 and 2/6 season-weighted mean.
    values=np.array([-1.,-1.,-1.,-1.,2.,2.])
    assert t.bootstrap_interval(d,values,reps=300)==pytest.approx([0.,0.])
    with pytest.raises(ValueError,match="Incomplete"):
        t.bootstrap_interval(d,values[:-1])


def test_research_output_cannot_target_production():
    with pytest.raises(ValueError,match="production outputs"):
        t.run(t.ROOT/"data"/"interaction_experiment")
    with pytest.raises(ValueError,match="10000"):
        t.run(reps=10)
