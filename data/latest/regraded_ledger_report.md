# boxscore-composite-v1.18 retrospective ledger replay

Reconstructed predictions at each original snapshot moneyline. Original snapshots are unchanged. This is hindsight, not native forward evidence.

Snapshots: 87; unique games: 43. Repeated snapshots are not independent games.
Summary uses the earliest original snapshot per game, globally and within each original revision. Revision groups overlap and must not be pooled.
Ties push in returns and are excluded from binary scores. Pending games remain ungraded. Market baseline uses each snapshot moneyline.

                   group  games  pending  wins  losses  pushes     units       roi   roi_se  market_null_roi  favorite_units  favorite_roi  binary_games  log_loss  market_log_loss    brier  market_brier
        All unique games     43        0    27      15       1 -0.680642 -0.015829 0.114319        -0.041027        0.279833      0.006663            42  0.689877         0.677913 0.245800      0.238619
boxscore-composite-v1.12      1        0     0       1       0 -1.000000 -1.000000      NaN        -0.040264       -1.000000     -1.000000             1  1.579691         1.567153 0.630375      0.626253
boxscore-composite-v1.13      1        0     0       1       0 -1.000000 -1.000000      NaN        -0.040000       -1.000000     -1.000000             1  1.622113         1.609438 0.644037      0.640000
boxscore-composite-v1.14      1        0     0       1       0 -1.000000 -1.000000      NaN        -0.040785       -1.000000     -1.000000             1  1.663882         1.651078 0.657068      0.653118
boxscore-composite-v1.16     42        0    27      14       1  0.319358  0.007604 0.114588        -0.041045        1.279833      0.031215            41  0.668174         0.656224 0.236420      0.229164
boxscore-composite-v1.17     14        0     9       4       1  0.401868  0.028705 0.188371        -0.040787        0.401868      0.028705            13  0.622306         0.574300 0.217136      0.194824
boxscore-composite-v1.18     28        0    18      10       0 -0.055582 -0.001985 0.146334        -0.041151        0.904892      0.033515            28  0.690836         0.695608 0.246072      0.245792

       original_revision         game_id  original_model_wp  model_wp bet_result  bet_units
boxscore-composite-v1.12  2026_05_TB_DAL           0.644547  0.793961          L  -1.000000
boxscore-composite-v1.13  2026_05_TB_DAL           0.632918  0.802519          L  -1.000000
boxscore-composite-v1.14  2026_05_TB_DAL           0.619215  0.810598          L  -1.000000
boxscore-composite-v1.16 2026_05_BAL_ATL           0.709701  0.636071          L  -1.000000
boxscore-composite-v1.16  2026_05_CHI_GB           0.498569  0.498569          L  -1.000000
boxscore-composite-v1.16 2026_05_CIN_MIA           0.257985  0.257985          W   0.281690
boxscore-composite-v1.16 2026_05_CLE_NYJ           0.543821  0.543821          W   0.740741
boxscore-composite-v1.16 2026_05_DEN_LAC           0.413441  0.413441          W   0.520833
boxscore-composite-v1.16 2026_05_DET_ARI           0.342853  0.342853          W   0.400000
boxscore-composite-v1.16 2026_05_HOU_TEN           0.242192  0.247778          W   0.277778
boxscore-composite-v1.16 2026_05_IND_PIT           0.540172  0.540172          W   0.675676
boxscore-composite-v1.16   2026_05_LV_NE           0.611193  0.611193          W   0.520833
boxscore-composite-v1.16  2026_05_MIN_NO           0.482003  0.482003          W   0.704225
boxscore-composite-v1.16 2026_05_NYG_WAS           0.576515  0.576515          P   0.000000
boxscore-composite-v1.16 2026_05_PHI_JAX           0.795347  0.772018          W   0.253165
boxscore-composite-v1.16  2026_05_SF_SEA           0.939039  0.700411          L  -1.000000
boxscore-composite-v1.17 2026_05_BAL_ATL           0.700461  0.636071          L  -1.000000
boxscore-composite-v1.17  2026_05_CHI_GB           0.490153  0.488236          L  -1.000000
boxscore-composite-v1.17 2026_05_CIN_MIA           0.260088  0.261754          W   0.289855
boxscore-composite-v1.17 2026_05_CLE_NYJ           0.536092  0.543821          W   0.740741
boxscore-composite-v1.17 2026_05_DEN_LAC           0.424978  0.413441          W   0.520833
boxscore-composite-v1.17 2026_05_DET_ARI           0.268344  0.337207          W   0.387597
boxscore-composite-v1.17 2026_05_HOU_TEN           0.251574  0.250796          W   0.281690
boxscore-composite-v1.17 2026_05_IND_PIT           0.542488  0.540172          W   0.675676
boxscore-composite-v1.17   2026_05_LV_NE           0.598425  0.611193          W   0.520833
boxscore-composite-v1.17  2026_05_MIN_NO           0.507626  0.494208          W   0.740741
boxscore-composite-v1.17 2026_05_NYG_WAS           0.588250  0.589476          P   0.000000
boxscore-composite-v1.17 2026_05_PHI_JAX           0.804659  0.777518          W   0.243902
boxscore-composite-v1.17  2026_05_SF_SEA           0.940683  0.700411          L  -1.000000
boxscore-composite-v1.17  2026_05_BUF_LA           0.661319  0.620637          L  -1.000000
boxscore-composite-v1.16  2026_05_BUF_LA           0.664820  0.620637          L  -1.000000
boxscore-composite-v1.18 2026_06_SEA_DEN           0.431610  0.431610          L  -1.000000
boxscore-composite-v1.16 2026_06_SEA_DEN           0.412161  0.431610          L  -1.000000
boxscore-composite-v1.18  2026_06_ARI_LA           0.814123  0.814123          L  -1.000000
boxscore-composite-v1.18 2026_06_BAL_CLE           0.435435  0.435435          L  -1.000000
boxscore-composite-v1.18  2026_06_BUF_LV           0.320416  0.320416          W   0.434783
boxscore-composite-v1.18 2026_06_CAR_PHI           0.392247  0.392247          W   0.602410
boxscore-composite-v1.18 2026_06_CHI_ATL           0.542147  0.542147          L  -1.000000
boxscore-composite-v1.18  2026_06_DAL_GB           0.522847  0.522847          W   0.847458
boxscore-composite-v1.18 2026_06_HOU_JAX           0.582992  0.582992          L  -1.000000
boxscore-composite-v1.18  2026_06_LAC_KC           0.756928  0.756928          W   0.219780
boxscore-composite-v1.18  2026_06_NO_NYG           0.448717  0.448717          W   0.909091
boxscore-composite-v1.18  2026_06_NYJ_NE           0.741555  0.741555          W   0.294118
boxscore-composite-v1.18  2026_06_PIT_TB           0.471129  0.471129          W   0.675676
boxscore-composite-v1.18 2026_06_TEN_IND           0.727969  0.727969          L  -1.000000
boxscore-composite-v1.16  2026_06_ARI_LA           0.814123  0.814123          L  -1.000000
boxscore-composite-v1.16 2026_06_BAL_CLE           0.435435  0.435435          L  -1.000000
boxscore-composite-v1.16  2026_06_BUF_LV           0.279990  0.320416          W   0.434783
boxscore-composite-v1.16 2026_06_CAR_PHI           0.360418  0.392247          W   0.602410
boxscore-composite-v1.16 2026_06_CHI_ATL           0.542147  0.542147          L  -1.000000
boxscore-composite-v1.16  2026_06_DAL_GB           0.544711  0.522847          W   0.847458
boxscore-composite-v1.16 2026_06_HOU_JAX           0.625817  0.582992          L  -1.000000
boxscore-composite-v1.16  2026_06_LAC_KC           0.756928  0.756928          W   0.219780
boxscore-composite-v1.16  2026_06_NO_NYG           0.448717  0.448717          W   0.909091
boxscore-composite-v1.16  2026_06_NYJ_NE           0.744276  0.741555          W   0.294118
boxscore-composite-v1.16  2026_06_PIT_TB           0.471129  0.471129          W   0.675676
boxscore-composite-v1.16 2026_06_TEN_IND           0.727969  0.727969          L  -1.000000
boxscore-composite-v1.18  2026_06_WAS_SF           0.798081  0.798081          W   0.212766
boxscore-composite-v1.16  2026_06_WAS_SF           0.823334  0.798081          W   0.212766
boxscore-composite-v1.18  2026_07_NE_CHI           0.590035  0.590035          W   0.645161
boxscore-composite-v1.16  2026_07_NE_CHI           0.617812  0.590035          W   0.645161
boxscore-composite-v1.18 2026_07_CLE_TEN           0.452202  0.452202          W   0.769231
boxscore-composite-v1.18 2026_07_DEN_ARI           0.417554  0.417554          W   0.434783
boxscore-composite-v1.18  2026_07_GB_DET           0.524899  0.524899          W   0.555556
boxscore-composite-v1.18 2026_07_IND_MIN           0.685576  0.685576          W   0.344828
boxscore-composite-v1.18  2026_07_KC_SEA           0.582310  0.582310          W   0.675676
boxscore-composite-v1.18   2026_07_LA_LV           0.436119  0.436119          W   0.571429
boxscore-composite-v1.18 2026_07_MIA_NYJ           0.617074  0.617074          L  -1.000000
boxscore-composite-v1.18 2026_07_NYG_HOU           0.768406  0.768406          L  -1.000000
boxscore-composite-v1.18  2026_07_PIT_NO           0.472369  0.472369          W   0.617284
boxscore-composite-v1.18  2026_07_SF_ATL           0.429264  0.429264          L  -1.000000
boxscore-composite-v1.18  2026_07_TB_CAR           0.557605  0.557605          L  -1.000000
boxscore-composite-v1.16 2026_07_CLE_TEN           0.432095  0.452202          W   0.769231
boxscore-composite-v1.16 2026_07_DEN_ARI           0.417554  0.417554          W   0.434783
boxscore-composite-v1.16  2026_07_GB_DET           0.524899  0.524899          W   0.555556
boxscore-composite-v1.16 2026_07_IND_MIN           0.685576  0.685576          W   0.344828
boxscore-composite-v1.16  2026_07_KC_SEA           0.622525  0.582310          W   0.675676
boxscore-composite-v1.16   2026_07_LA_LV           0.436119  0.436119          W   0.571429
boxscore-composite-v1.16 2026_07_MIA_NYJ           0.617074  0.617074          L  -1.000000
boxscore-composite-v1.16 2026_07_NYG_HOU           0.768406  0.768406          L  -1.000000
boxscore-composite-v1.16  2026_07_PIT_NO           0.472369  0.472369          W   0.617284
boxscore-composite-v1.16  2026_07_SF_ATL           0.429264  0.429264          L  -1.000000
boxscore-composite-v1.16  2026_07_TB_CAR           0.557605  0.557605          L  -1.000000
boxscore-composite-v1.18 2026_07_DAL_PHI           0.324386  0.324386          W   0.458716
boxscore-composite-v1.16 2026_07_DAL_PHI           0.257275  0.324386          W   0.458716
boxscore-composite-v1.18 2026_07_CIN_BAL           0.418454  0.418454          W   0.675676
boxscore-composite-v1.16 2026_07_CIN_BAL           0.381171  0.418454          W   0.675676
