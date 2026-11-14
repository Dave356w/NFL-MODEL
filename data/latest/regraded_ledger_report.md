# boxscore-composite-v1.24 retrospective ledger replay

Reconstructed predictions at each original snapshot moneyline. Original snapshots are unchanged. This is hindsight, not native forward evidence.

Snapshots: 158; unique games: 84. Repeated snapshots are not independent games.
Summary uses the earliest original snapshot per game, globally and within each original revision. Revision groups overlap and must not be pooled.
Ties push in returns and are excluded from binary scores. Pending games remain ungraded. Market baseline uses each snapshot moneyline.

                   group  games  pending  wins  losses  pushes     units       roi   roi_se  market_null_roi  favorite_units  favorite_roi  binary_games  log_loss  market_log_loss    brier  market_brier
        All unique games     84       11    50      22       1  1.965569  0.026926 0.081918        -0.040942        4.514278      0.062698            72  0.610084         0.600641 0.209258      0.204410
boxscore-composite-v1.12      1        0     0       1       0 -1.000000 -1.000000      NaN        -0.040264       -1.000000     -1.000000             1  1.573241         1.567153 0.628259      0.626253
boxscore-composite-v1.13      1        0     0       1       0 -1.000000 -1.000000      NaN        -0.040000       -1.000000     -1.000000             1  1.615592         1.609438 0.641965      0.640000
boxscore-composite-v1.14      1        0     0       1       0 -1.000000 -1.000000      NaN        -0.040785       -1.000000     -1.000000             1  1.657296         1.651078 0.655041      0.653118
boxscore-composite-v1.16     73        1    50      21       1  2.970961  0.041263 0.081797        -0.040961        5.519670      0.077742            71  0.596243         0.586712 0.203207      0.198301
boxscore-composite-v1.17     14        0     9       4       1  0.401868  0.028705 0.188371        -0.040787        0.401868      0.028705            13  0.617719         0.574300 0.215195      0.194824
boxscore-composite-v1.18     42        0    27      15       0 -1.269387 -0.030224 0.115655        -0.041048        1.279323      0.031203            42  0.643787         0.645515 0.224279      0.224255
boxscore-composite-v1.21     12        0    11       1       0  3.401299  0.283442 0.127535        -0.040811        3.401299      0.283442            12  0.432219         0.416427 0.129110      0.121994
boxscore-composite-v1.22      3        1     1       1       0 -0.494949 -0.247475 0.752525        -0.040555       -0.494949     -0.247475             2  0.673955         0.640042 0.240578      0.224681
boxscore-composite-v1.24     11       11     0       0       0  0.000000       NaN      NaN              NaN        0.000000           NaN             0       NaN              NaN      NaN           NaN

       original_revision         game_id  original_model_wp  model_wp bet_result  bet_units
boxscore-composite-v1.12  2026_05_TB_DAL           0.644547  0.792628          L  -1.000000
boxscore-composite-v1.13  2026_05_TB_DAL           0.632918  0.801227          L  -1.000000
boxscore-composite-v1.14  2026_05_TB_DAL           0.619215  0.809346          L  -1.000000
boxscore-composite-v1.16 2026_05_BAL_ATL           0.709701  0.637712          L  -1.000000
boxscore-composite-v1.16  2026_05_CHI_GB           0.498569  0.466494          L  -1.000000
boxscore-composite-v1.16 2026_05_CIN_MIA           0.257985  0.251723          W   0.281690
boxscore-composite-v1.16 2026_05_CLE_NYJ           0.543821  0.535145          W   0.740741
boxscore-composite-v1.16 2026_05_DEN_LAC           0.413441  0.401758          W   0.520833
boxscore-composite-v1.16 2026_05_DET_ARI           0.342853  0.311766          W   0.400000
boxscore-composite-v1.16 2026_05_HOU_TEN           0.242192  0.252081          W   0.277778
boxscore-composite-v1.16 2026_05_IND_PIT           0.540172  0.542872          W   0.675676
boxscore-composite-v1.16   2026_05_LV_NE           0.611193  0.626432          W   0.520833
boxscore-composite-v1.16  2026_05_MIN_NO           0.482003  0.460508          W   0.704225
boxscore-composite-v1.16 2026_05_NYG_WAS           0.576515  0.593261          P   0.000000
boxscore-composite-v1.16 2026_05_PHI_JAX           0.795347  0.766631          W   0.253165
boxscore-composite-v1.16  2026_05_SF_SEA           0.939039  0.692443          L  -1.000000
boxscore-composite-v1.17 2026_05_BAL_ATL           0.700461  0.637712          L  -1.000000
boxscore-composite-v1.17  2026_05_CHI_GB           0.490153  0.456222          L  -1.000000
boxscore-composite-v1.17 2026_05_CIN_MIA           0.260088  0.255432          W   0.289855
boxscore-composite-v1.17 2026_05_CLE_NYJ           0.536092  0.535145          W   0.740741
boxscore-composite-v1.17 2026_05_DEN_LAC           0.424978  0.401758          W   0.520833
boxscore-composite-v1.17 2026_05_DET_ARI           0.268344  0.306394          W   0.387597
boxscore-composite-v1.17 2026_05_HOU_TEN           0.251574  0.255134          W   0.281690
boxscore-composite-v1.17 2026_05_IND_PIT           0.542488  0.542872          W   0.675676
boxscore-composite-v1.17   2026_05_LV_NE           0.598425  0.626432          W   0.520833
boxscore-composite-v1.17  2026_05_MIN_NO           0.507626  0.472666          W   0.740741
boxscore-composite-v1.17 2026_05_NYG_WAS           0.588250  0.606059          P   0.000000
boxscore-composite-v1.17 2026_05_PHI_JAX           0.804659  0.772222          W   0.243902
boxscore-composite-v1.17  2026_05_SF_SEA           0.940683  0.692443          L  -1.000000
boxscore-composite-v1.17  2026_05_BUF_LA           0.661319  0.624624          L  -1.000000
boxscore-composite-v1.16  2026_05_BUF_LA           0.664820  0.624624          L  -1.000000
boxscore-composite-v1.18 2026_06_SEA_DEN           0.431610  0.458749          L  -1.000000
boxscore-composite-v1.16 2026_06_SEA_DEN           0.412161  0.458749          L  -1.000000
boxscore-composite-v1.18  2026_06_ARI_LA           0.814123  0.853160          L  -1.000000
boxscore-composite-v1.18 2026_06_BAL_CLE           0.435435  0.426069          L  -1.000000
boxscore-composite-v1.18  2026_06_BUF_LV           0.320416  0.320826          W   0.434783
boxscore-composite-v1.18 2026_06_CAR_PHI           0.392247  0.391467          W   0.602410
boxscore-composite-v1.18 2026_06_CHI_ATL           0.542147  0.506285          L  -1.000000
boxscore-composite-v1.18  2026_06_DAL_GB           0.522847  0.533805          W   0.847458
boxscore-composite-v1.18 2026_06_HOU_JAX           0.582992  0.582535          L  -1.000000
boxscore-composite-v1.18  2026_06_LAC_KC           0.756928  0.767786          W   0.219780
boxscore-composite-v1.18  2026_06_NO_NYG           0.448717  0.475438          W   0.909091
boxscore-composite-v1.18  2026_06_NYJ_NE           0.741555  0.743933          W   0.294118
boxscore-composite-v1.18  2026_06_PIT_TB           0.471129  0.445354          W   0.675676
boxscore-composite-v1.18 2026_06_TEN_IND           0.727969  0.742517          L  -1.000000
boxscore-composite-v1.16  2026_06_ARI_LA           0.814123  0.853160          L  -1.000000
boxscore-composite-v1.16 2026_06_BAL_CLE           0.435435  0.426069          L  -1.000000
boxscore-composite-v1.16  2026_06_BUF_LV           0.279990  0.320826          W   0.434783
boxscore-composite-v1.16 2026_06_CAR_PHI           0.360418  0.391467          W   0.602410
boxscore-composite-v1.16 2026_06_CHI_ATL           0.542147  0.506285          L  -1.000000
boxscore-composite-v1.16  2026_06_DAL_GB           0.544711  0.533805          W   0.847458
boxscore-composite-v1.16 2026_06_HOU_JAX           0.625817  0.582535          L  -1.000000
boxscore-composite-v1.16  2026_06_LAC_KC           0.756928  0.767786          W   0.219780
boxscore-composite-v1.16  2026_06_NO_NYG           0.448717  0.475438          W   0.909091
boxscore-composite-v1.16  2026_06_NYJ_NE           0.744276  0.743933          W   0.294118
boxscore-composite-v1.16  2026_06_PIT_TB           0.471129  0.445354          W   0.675676
boxscore-composite-v1.16 2026_06_TEN_IND           0.727969  0.742517          L  -1.000000
boxscore-composite-v1.18  2026_06_WAS_SF           0.798081  0.795597          W   0.212766
boxscore-composite-v1.16  2026_06_WAS_SF           0.823334  0.795597          W   0.212766
boxscore-composite-v1.18  2026_07_NE_CHI           0.590035  0.541365          W   0.645161
boxscore-composite-v1.16  2026_07_NE_CHI           0.617812  0.541365          W   0.645161
boxscore-composite-v1.18 2026_07_CLE_TEN           0.452202  0.476859          W   0.769231
boxscore-composite-v1.18 2026_07_DEN_ARI           0.417554  0.434908          W   0.434783
boxscore-composite-v1.18  2026_07_GB_DET           0.524899  0.569718          W   0.555556
boxscore-composite-v1.18 2026_07_IND_MIN           0.685576  0.650820          W   0.344828
boxscore-composite-v1.18  2026_07_KC_SEA           0.582310  0.573731          W   0.675676
boxscore-composite-v1.18   2026_07_LA_LV           0.436119  0.384451          W   0.571429
boxscore-composite-v1.18 2026_07_MIA_NYJ           0.617074  0.605007          L  -1.000000
boxscore-composite-v1.18 2026_07_NYG_HOU           0.768406  0.743699          L  -1.000000
boxscore-composite-v1.18  2026_07_PIT_NO           0.472369  0.435125          W   0.617284
boxscore-composite-v1.18  2026_07_SF_ATL           0.429264  0.435880          L  -1.000000
boxscore-composite-v1.18  2026_07_TB_CAR           0.557605  0.534993          L  -1.000000
boxscore-composite-v1.16 2026_07_CLE_TEN           0.432095  0.476859          W   0.769231
boxscore-composite-v1.16 2026_07_DEN_ARI           0.417554  0.434908          W   0.434783
boxscore-composite-v1.16  2026_07_GB_DET           0.524899  0.569718          W   0.555556
boxscore-composite-v1.16 2026_07_IND_MIN           0.685576  0.650820          W   0.344828
boxscore-composite-v1.16  2026_07_KC_SEA           0.622525  0.573731          W   0.675676
boxscore-composite-v1.16   2026_07_LA_LV           0.436119  0.384451          W   0.571429
boxscore-composite-v1.16 2026_07_MIA_NYJ           0.617074  0.605007          L  -1.000000
boxscore-composite-v1.16 2026_07_NYG_HOU           0.768406  0.743699          L  -1.000000
boxscore-composite-v1.16  2026_07_PIT_NO           0.472369  0.435125          W   0.617284
boxscore-composite-v1.16  2026_07_SF_ATL           0.429264  0.435880          L  -1.000000
boxscore-composite-v1.16  2026_07_TB_CAR           0.557605  0.534993          L  -1.000000
boxscore-composite-v1.18 2026_07_DAL_PHI           0.324386  0.327792          W   0.458716
boxscore-composite-v1.16 2026_07_DAL_PHI           0.257275  0.327792          W   0.458716
boxscore-composite-v1.18 2026_07_CIN_BAL           0.418454  0.417350          W   0.675676
boxscore-composite-v1.16 2026_07_CIN_BAL           0.381171  0.417350          W   0.675676
boxscore-composite-v1.18  2026_08_CAR_GB           0.613204  0.614491          W   0.520833
boxscore-composite-v1.16  2026_08_CAR_GB           0.613204  0.614491          W   0.520833
boxscore-composite-v1.18 2026_08_ARI_DAL           0.717609  0.691770          L  -1.000000
boxscore-composite-v1.18  2026_08_ATL_TB           0.548686  0.554242          W   0.740741
boxscore-composite-v1.18 2026_08_BAL_BUF           0.607288  0.605540          W   0.588235
boxscore-composite-v1.18 2026_08_CLE_PIT           0.604358  0.626227          W   0.520833
boxscore-composite-v1.18 2026_08_IND_JAX           0.802934  0.800811          W   0.200000
boxscore-composite-v1.18  2026_08_KC_DEN           0.470735  0.470345          L  -1.000000
boxscore-composite-v1.18  2026_08_LAC_LA           0.641690  0.689222          W   0.359712
boxscore-composite-v1.18  2026_08_LV_NYJ           0.499998  0.503174          L  -1.000000
boxscore-composite-v1.18 2026_08_MIN_DET           0.461144  0.491515          L  -1.000000
boxscore-composite-v1.18  2026_08_NE_MIA           0.385631  0.262135          W   0.307692
boxscore-composite-v1.18 2026_08_PHI_WAS           0.693244  0.691839          W   0.400000
boxscore-composite-v1.18 2026_08_TEN_CIN           0.842440  0.842189          W   0.148148
boxscore-composite-v1.16 2026_08_ARI_DAL           0.717609  0.691770          L  -1.000000
boxscore-composite-v1.16  2026_08_ATL_TB           0.548686  0.554242          W   0.740741
boxscore-composite-v1.16 2026_08_BAL_BUF           0.621299  0.605540          W   0.588235
boxscore-composite-v1.16 2026_08_CLE_PIT           0.604358  0.626227          W   0.520833
boxscore-composite-v1.16 2026_08_IND_JAX           0.814344  0.800811          W   0.200000
boxscore-composite-v1.16  2026_08_KC_DEN           0.423596  0.470345          L  -1.000000
boxscore-composite-v1.16  2026_08_LAC_LA           0.641690  0.689222          W   0.359712
boxscore-composite-v1.16  2026_08_LV_NYJ           0.499998  0.503174          L  -1.000000
boxscore-composite-v1.16 2026_08_MIN_DET           0.461144  0.491515          L  -1.000000
boxscore-composite-v1.16  2026_08_NE_MIA           0.385631  0.262135          W   0.307692
boxscore-composite-v1.16 2026_08_PHI_WAS           0.723517  0.691839          W   0.400000
boxscore-composite-v1.16 2026_08_TEN_CIN           0.862389  0.842189          W   0.148148
boxscore-composite-v1.18 2026_08_CHI_SEA           0.610058  0.605845          L  -1.000000
boxscore-composite-v1.16 2026_08_CHI_SEA           0.650658  0.605845          L  -1.000000
boxscore-composite-v1.21 2026_09_JAX_BAL           0.182724  0.182742          W   0.186916
boxscore-composite-v1.16 2026_09_JAX_BAL           0.156113  0.186465          W   0.192308
boxscore-composite-v1.21 2026_09_ARI_SEA           0.773003  0.773026          W   0.212766
boxscore-composite-v1.21  2026_09_CLE_NO           0.610561  0.610550          W   0.588235
boxscore-composite-v1.21 2026_09_DEN_CAR           0.463328  0.463323          W   0.645161
boxscore-composite-v1.21 2026_09_DET_MIA           0.285540  0.285538          W   0.344828
boxscore-composite-v1.21   2026_09_GB_NE           0.547136  0.547137          L  -1.000000
boxscore-composite-v1.21 2026_09_HOU_LAC           0.384924  0.384924          W   0.420168
boxscore-composite-v1.21   2026_09_LV_SF           0.797646  0.797647          W   0.206186
boxscore-composite-v1.21 2026_09_NYG_PHI           0.403581  0.403596          W   0.645161
boxscore-composite-v1.21  2026_09_NYJ_KC           0.788355  0.788377          W   0.212766
boxscore-composite-v1.21  2026_09_TB_CHI           0.669476  0.669475          W   0.350877
boxscore-composite-v1.16 2026_09_ARI_SEA           0.810878  0.773026          W   0.212766
boxscore-composite-v1.16 2026_09_CIN_ATL           0.396567  0.401359          W   0.555556
boxscore-composite-v1.16  2026_09_CLE_NO           0.639766  0.609066          W   0.588235
boxscore-composite-v1.16 2026_09_DAL_IND           0.345575  0.347752          W   0.444444
boxscore-composite-v1.16 2026_09_DEN_CAR           0.481752  0.463323          W   0.645161
boxscore-composite-v1.16 2026_09_DET_MIA           0.334414  0.285538          W   0.344828
boxscore-composite-v1.16   2026_09_GB_NE           0.538736  0.547137          L  -1.000000
boxscore-composite-v1.16  2026_09_LA_WAS           0.290132  0.330024          W   0.458716
boxscore-composite-v1.16   2026_09_LV_SF           0.804203  0.797647          W   0.206186
boxscore-composite-v1.16 2026_09_NYG_PHI           0.343261  0.403596          W   0.645161
boxscore-composite-v1.16  2026_09_NYJ_KC           0.781526  0.788377          W   0.212766
boxscore-composite-v1.16  2026_09_TB_CHI           0.682476  0.669475          W   0.350877
boxscore-composite-v1.21 2026_09_BUF_MIN           0.459494  0.459500          W   0.588235
boxscore-composite-v1.16 2026_09_BUF_MIN           0.444987  0.459500          W   0.588235
boxscore-composite-v1.16 2026_09_HOU_LAC           0.391889  0.384924          W   0.420168
boxscore-composite-v1.22 2026_09_BUF_MIN           0.424779  0.424784          W   0.505051
boxscore-composite-v1.22 2026_10_WAS_NYG           0.548400  0.548374          L  -1.000000
boxscore-composite-v1.16 2026_10_WAS_NYG           0.549846  0.536249          L  -1.000000
boxscore-composite-v1.16  2026_10_NE_DET           0.533908  0.546285                   NaN
boxscore-composite-v1.22  2026_10_NE_DET           0.557352  0.557367                   NaN
boxscore-composite-v1.24 2026_10_BUF_NYJ           0.214737  0.214737                   NaN
boxscore-composite-v1.24  2026_10_CAR_NO           0.512090  0.512090                   NaN
boxscore-composite-v1.24 2026_10_HOU_CLE           0.354031  0.354031                   NaN
boxscore-composite-v1.24 2026_10_JAX_TEN           0.151011  0.151011                   NaN
boxscore-composite-v1.24  2026_10_KC_ATL           0.405508  0.405508                   NaN
boxscore-composite-v1.24  2026_10_LA_ARI           0.190435  0.190435                   NaN
boxscore-composite-v1.24 2026_10_MIA_IND           0.618580  0.618580                   NaN
boxscore-composite-v1.24  2026_10_MIN_GB           0.515058  0.515058                   NaN
boxscore-composite-v1.24  2026_10_NE_DET           0.546285  0.546285                   NaN
boxscore-composite-v1.24 2026_10_PIT_CIN           0.627452  0.627452                   NaN
boxscore-composite-v1.24  2026_10_SEA_LV           0.273960  0.273960                   NaN
