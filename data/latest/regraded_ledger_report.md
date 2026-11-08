# boxscore-composite-v1.21 retrospective ledger replay

Reconstructed predictions at each original snapshot moneyline. Original snapshots are unchanged. This is hindsight, not native forward evidence.

Snapshots: 142; unique games: 72. Repeated snapshots are not independent games.
Summary uses the earliest original snapshot per game, globally and within each original revision. Revision groups overlap and must not be pooled.
Ties push in returns and are excluded from binary scores. Pending games remain ungraded. Market baseline uses each snapshot moneyline.

                   group  games  pending  wins  losses  pushes     units       roi   roi_se  market_null_roi  favorite_units  favorite_roi  binary_games  log_loss  market_log_loss    brier  market_brier
        All unique games     72       14    37      20       1 -1.707530 -0.029440 0.096020        -0.040978        0.841179      0.014758            57  0.645709         0.637192 0.225596      0.220971
boxscore-composite-v1.12      1        0     0       1       0 -1.000000 -1.000000      NaN        -0.040264       -1.000000     -1.000000             1  1.573301         1.567153 0.628279      0.626253
boxscore-composite-v1.13      1        0     0       1       0 -1.000000 -1.000000      NaN        -0.040000       -1.000000     -1.000000             1  1.615652         1.609438 0.641984      0.640000
boxscore-composite-v1.14      1        0     0       1       0 -1.000000 -1.000000      NaN        -0.040785       -1.000000     -1.000000             1  1.657356         1.651078 0.655060      0.653118
boxscore-composite-v1.16     71       14    37      19       1 -0.702138 -0.012318 0.096175        -0.040995        1.846571      0.032974            56  0.629226         0.620671 0.218430      0.213760
boxscore-composite-v1.17     14        0     9       4       1  0.401868  0.028705 0.188371        -0.040787        0.401868      0.028705            13  0.617739         0.574300 0.215205      0.194824
boxscore-composite-v1.18     42        0    27      15       0 -1.269387 -0.030224 0.115655        -0.041048        1.279323      0.031203            42  0.643780         0.645515 0.224277      0.224255
boxscore-composite-v1.21     12       11     1       0       0  0.186916  0.186916      NaN        -0.040785        0.186916      0.186916             1  0.201779         0.212999 0.033388      0.036804

       original_revision         game_id  original_model_wp  model_wp bet_result  bet_units
boxscore-composite-v1.12  2026_05_TB_DAL           0.644547  0.792640          L  -1.000000
boxscore-composite-v1.13  2026_05_TB_DAL           0.632918  0.801239          L  -1.000000
boxscore-composite-v1.14  2026_05_TB_DAL           0.619215  0.809358          L  -1.000000
boxscore-composite-v1.16 2026_05_BAL_ATL           0.709701  0.637766          L  -1.000000
boxscore-composite-v1.16  2026_05_CHI_GB           0.498569  0.466500          L  -1.000000
boxscore-composite-v1.16 2026_05_CIN_MIA           0.257985  0.251720          W   0.281690
boxscore-composite-v1.16 2026_05_CLE_NYJ           0.543821  0.535164          W   0.740741
boxscore-composite-v1.16 2026_05_DEN_LAC           0.413441  0.401776          W   0.520833
boxscore-composite-v1.16 2026_05_DET_ARI           0.342853  0.311766          W   0.400000
boxscore-composite-v1.16 2026_05_HOU_TEN           0.242192  0.252074          W   0.277778
boxscore-composite-v1.16 2026_05_IND_PIT           0.540172  0.542845          W   0.675676
boxscore-composite-v1.16   2026_05_LV_NE           0.611193  0.626398          W   0.520833
boxscore-composite-v1.16  2026_05_MIN_NO           0.482003  0.460531          W   0.704225
boxscore-composite-v1.16 2026_05_NYG_WAS           0.576515  0.593252          P   0.000000
boxscore-composite-v1.16 2026_05_PHI_JAX           0.795347  0.766628          W   0.253165
boxscore-composite-v1.16  2026_05_SF_SEA           0.939039  0.692442          L  -1.000000
boxscore-composite-v1.17 2026_05_BAL_ATL           0.700461  0.637766          L  -1.000000
boxscore-composite-v1.17  2026_05_CHI_GB           0.490153  0.456227          L  -1.000000
boxscore-composite-v1.17 2026_05_CIN_MIA           0.260088  0.255429          W   0.289855
boxscore-composite-v1.17 2026_05_CLE_NYJ           0.536092  0.535164          W   0.740741
boxscore-composite-v1.17 2026_05_DEN_LAC           0.424978  0.401776          W   0.520833
boxscore-composite-v1.17 2026_05_DET_ARI           0.268344  0.306394          W   0.387597
boxscore-composite-v1.17 2026_05_HOU_TEN           0.251574  0.255127          W   0.281690
boxscore-composite-v1.17 2026_05_IND_PIT           0.542488  0.542845          W   0.675676
boxscore-composite-v1.17   2026_05_LV_NE           0.598425  0.626398          W   0.520833
boxscore-composite-v1.17  2026_05_MIN_NO           0.507626  0.472688          W   0.740741
boxscore-composite-v1.17 2026_05_NYG_WAS           0.588250  0.606050          P   0.000000
boxscore-composite-v1.17 2026_05_PHI_JAX           0.804659  0.772219          W   0.243902
boxscore-composite-v1.17  2026_05_SF_SEA           0.940683  0.692442          L  -1.000000
boxscore-composite-v1.17  2026_05_BUF_LA           0.661319  0.624623          L  -1.000000
boxscore-composite-v1.16  2026_05_BUF_LA           0.664820  0.624623          L  -1.000000
boxscore-composite-v1.18 2026_06_SEA_DEN           0.431610  0.458737          L  -1.000000
boxscore-composite-v1.16 2026_06_SEA_DEN           0.412161  0.458737          L  -1.000000
boxscore-composite-v1.18  2026_06_ARI_LA           0.814123  0.853160          L  -1.000000
boxscore-composite-v1.18 2026_06_BAL_CLE           0.435435  0.426236          L  -1.000000
boxscore-composite-v1.18  2026_06_BUF_LV           0.320416  0.320833          W   0.434783
boxscore-composite-v1.18 2026_06_CAR_PHI           0.392247  0.391455          W   0.602410
boxscore-composite-v1.18 2026_06_CHI_ATL           0.542147  0.506363          L  -1.000000
boxscore-composite-v1.18  2026_06_DAL_GB           0.522847  0.533806          W   0.847458
boxscore-composite-v1.18 2026_06_HOU_JAX           0.582992  0.582532          L  -1.000000
boxscore-composite-v1.18  2026_06_LAC_KC           0.756928  0.767797          W   0.219780
boxscore-composite-v1.18  2026_06_NO_NYG           0.448717  0.475424          W   0.909091
boxscore-composite-v1.18  2026_06_NYJ_NE           0.741555  0.743928          W   0.294118
boxscore-composite-v1.18  2026_06_PIT_TB           0.471129  0.445311          W   0.675676
boxscore-composite-v1.18 2026_06_TEN_IND           0.727969  0.742520          L  -1.000000
boxscore-composite-v1.16  2026_06_ARI_LA           0.814123  0.853160          L  -1.000000
boxscore-composite-v1.16 2026_06_BAL_CLE           0.435435  0.426236          L  -1.000000
boxscore-composite-v1.16  2026_06_BUF_LV           0.279990  0.320833          W   0.434783
boxscore-composite-v1.16 2026_06_CAR_PHI           0.360418  0.391455          W   0.602410
boxscore-composite-v1.16 2026_06_CHI_ATL           0.542147  0.506363          L  -1.000000
boxscore-composite-v1.16  2026_06_DAL_GB           0.544711  0.533806          W   0.847458
boxscore-composite-v1.16 2026_06_HOU_JAX           0.625817  0.582532          L  -1.000000
boxscore-composite-v1.16  2026_06_LAC_KC           0.756928  0.767797          W   0.219780
boxscore-composite-v1.16  2026_06_NO_NYG           0.448717  0.475424          W   0.909091
boxscore-composite-v1.16  2026_06_NYJ_NE           0.744276  0.743928          W   0.294118
boxscore-composite-v1.16  2026_06_PIT_TB           0.471129  0.445311          W   0.675676
boxscore-composite-v1.16 2026_06_TEN_IND           0.727969  0.742520          L  -1.000000
boxscore-composite-v1.18  2026_06_WAS_SF           0.798081  0.795601          W   0.212766
boxscore-composite-v1.16  2026_06_WAS_SF           0.823334  0.795601          W   0.212766
boxscore-composite-v1.18  2026_07_NE_CHI           0.590035  0.541388          W   0.645161
boxscore-composite-v1.16  2026_07_NE_CHI           0.617812  0.541388          W   0.645161
boxscore-composite-v1.18 2026_07_CLE_TEN           0.452202  0.476858          W   0.769231
boxscore-composite-v1.18 2026_07_DEN_ARI           0.417554  0.434916          W   0.434783
boxscore-composite-v1.18  2026_07_GB_DET           0.524899  0.569702          W   0.555556
boxscore-composite-v1.18 2026_07_IND_MIN           0.685576  0.650790          W   0.344828
boxscore-composite-v1.18  2026_07_KC_SEA           0.582310  0.573726          W   0.675676
boxscore-composite-v1.18   2026_07_LA_LV           0.436119  0.384460          W   0.571429
boxscore-composite-v1.18 2026_07_MIA_NYJ           0.617074  0.605044          L  -1.000000
boxscore-composite-v1.18 2026_07_NYG_HOU           0.768406  0.743670          L  -1.000000
boxscore-composite-v1.18  2026_07_PIT_NO           0.472369  0.435129          W   0.617284
boxscore-composite-v1.18  2026_07_SF_ATL           0.429264  0.435898          L  -1.000000
boxscore-composite-v1.18  2026_07_TB_CAR           0.557605  0.535004          L  -1.000000
boxscore-composite-v1.16 2026_07_CLE_TEN           0.432095  0.476858          W   0.769231
boxscore-composite-v1.16 2026_07_DEN_ARI           0.417554  0.434916          W   0.434783
boxscore-composite-v1.16  2026_07_GB_DET           0.524899  0.569702          W   0.555556
boxscore-composite-v1.16 2026_07_IND_MIN           0.685576  0.650790          W   0.344828
boxscore-composite-v1.16  2026_07_KC_SEA           0.622525  0.573726          W   0.675676
boxscore-composite-v1.16   2026_07_LA_LV           0.436119  0.384460          W   0.571429
boxscore-composite-v1.16 2026_07_MIA_NYJ           0.617074  0.605044          L  -1.000000
boxscore-composite-v1.16 2026_07_NYG_HOU           0.768406  0.743670          L  -1.000000
boxscore-composite-v1.16  2026_07_PIT_NO           0.472369  0.435129          W   0.617284
boxscore-composite-v1.16  2026_07_SF_ATL           0.429264  0.435898          L  -1.000000
boxscore-composite-v1.16  2026_07_TB_CAR           0.557605  0.535004          L  -1.000000
boxscore-composite-v1.18 2026_07_DAL_PHI           0.324386  0.327778          W   0.458716
boxscore-composite-v1.16 2026_07_DAL_PHI           0.257275  0.327778          W   0.458716
boxscore-composite-v1.18 2026_07_CIN_BAL           0.418454  0.417319          W   0.675676
boxscore-composite-v1.16 2026_07_CIN_BAL           0.381171  0.417319          W   0.675676
boxscore-composite-v1.18  2026_08_CAR_GB           0.613204  0.614487          W   0.520833
boxscore-composite-v1.16  2026_08_CAR_GB           0.613204  0.614487          W   0.520833
boxscore-composite-v1.18 2026_08_ARI_DAL           0.717609  0.691773          L  -1.000000
boxscore-composite-v1.18  2026_08_ATL_TB           0.548686  0.554244          W   0.740741
boxscore-composite-v1.18 2026_08_BAL_BUF           0.607288  0.605523          W   0.588235
boxscore-composite-v1.18 2026_08_CLE_PIT           0.604358  0.626202          W   0.520833
boxscore-composite-v1.18 2026_08_IND_JAX           0.802934  0.800809          W   0.200000
boxscore-composite-v1.18  2026_08_KC_DEN           0.470735  0.470340          L  -1.000000
boxscore-composite-v1.18  2026_08_LAC_LA           0.641690  0.689210          W   0.359712
boxscore-composite-v1.18  2026_08_LV_NYJ           0.499998  0.503192          L  -1.000000
boxscore-composite-v1.18 2026_08_MIN_DET           0.461144  0.491520          L  -1.000000
boxscore-composite-v1.18  2026_08_NE_MIA           0.385631  0.262135          W   0.307692
boxscore-composite-v1.18 2026_08_PHI_WAS           0.693244  0.691846          W   0.400000
boxscore-composite-v1.18 2026_08_TEN_CIN           0.842440  0.842191          W   0.148148
boxscore-composite-v1.16 2026_08_ARI_DAL           0.717609  0.691773          L  -1.000000
boxscore-composite-v1.16  2026_08_ATL_TB           0.548686  0.554244          W   0.740741
boxscore-composite-v1.16 2026_08_BAL_BUF           0.621299  0.605523          W   0.588235
boxscore-composite-v1.16 2026_08_CLE_PIT           0.604358  0.626202          W   0.520833
boxscore-composite-v1.16 2026_08_IND_JAX           0.814344  0.800809          W   0.200000
boxscore-composite-v1.16  2026_08_KC_DEN           0.423596  0.470340          L  -1.000000
boxscore-composite-v1.16  2026_08_LAC_LA           0.641690  0.689210          W   0.359712
boxscore-composite-v1.16  2026_08_LV_NYJ           0.499998  0.503192          L  -1.000000
boxscore-composite-v1.16 2026_08_MIN_DET           0.461144  0.491520          L  -1.000000
boxscore-composite-v1.16  2026_08_NE_MIA           0.385631  0.262135          W   0.307692
boxscore-composite-v1.16 2026_08_PHI_WAS           0.723517  0.691846          W   0.400000
boxscore-composite-v1.16 2026_08_TEN_CIN           0.862389  0.842191          W   0.148148
boxscore-composite-v1.18 2026_08_CHI_SEA           0.610058  0.605839          L  -1.000000
boxscore-composite-v1.16 2026_08_CHI_SEA           0.650658  0.605839          L  -1.000000
boxscore-composite-v1.21 2026_09_JAX_BAL           0.182724  0.182724          W   0.186916
boxscore-composite-v1.16 2026_09_JAX_BAL           0.156113  0.186447          W   0.192308
boxscore-composite-v1.21 2026_09_ARI_SEA           0.773003  0.773003                   NaN
boxscore-composite-v1.21  2026_09_CLE_NO           0.610561  0.610561                   NaN
boxscore-composite-v1.21 2026_09_DEN_CAR           0.463328  0.463328                   NaN
boxscore-composite-v1.21 2026_09_DET_MIA           0.285540  0.285540                   NaN
boxscore-composite-v1.21   2026_09_GB_NE           0.547136  0.547136                   NaN
boxscore-composite-v1.21 2026_09_HOU_LAC           0.384924  0.384924                   NaN
boxscore-composite-v1.21   2026_09_LV_SF           0.797646  0.797646                   NaN
boxscore-composite-v1.21 2026_09_NYG_PHI           0.403581  0.403581                   NaN
boxscore-composite-v1.21  2026_09_NYJ_KC           0.788355  0.788355                   NaN
boxscore-composite-v1.21  2026_09_TB_CHI           0.669476  0.669476                   NaN
boxscore-composite-v1.16 2026_09_ARI_SEA           0.810878  0.773003                   NaN
boxscore-composite-v1.16 2026_09_CIN_ATL           0.396567  0.401357                   NaN
boxscore-composite-v1.16  2026_09_CLE_NO           0.639766  0.609070                   NaN
boxscore-composite-v1.16 2026_09_DAL_IND           0.345575  0.347757                   NaN
boxscore-composite-v1.16 2026_09_DEN_CAR           0.481752  0.463328                   NaN
boxscore-composite-v1.16 2026_09_DET_MIA           0.334414  0.285540                   NaN
boxscore-composite-v1.16   2026_09_GB_NE           0.538736  0.547136                   NaN
boxscore-composite-v1.16  2026_09_LA_WAS           0.290132  0.330024                   NaN
boxscore-composite-v1.16   2026_09_LV_SF           0.804203  0.797646                   NaN
boxscore-composite-v1.16 2026_09_NYG_PHI           0.343261  0.403581                   NaN
boxscore-composite-v1.16  2026_09_NYJ_KC           0.781526  0.788355                   NaN
boxscore-composite-v1.16  2026_09_TB_CHI           0.682476  0.669476                   NaN
boxscore-composite-v1.21 2026_09_BUF_MIN           0.459494  0.459494                   NaN
boxscore-composite-v1.16 2026_09_BUF_MIN           0.444987  0.459494                   NaN
boxscore-composite-v1.16 2026_09_HOU_LAC           0.391889  0.384924                   NaN
