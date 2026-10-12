# boxscore-composite-v1.17 retrospective ledger replay

Reconstructed predictions at each original snapshot moneyline. Original snapshots are unchanged. This is hindsight, not native forward evidence.

Snapshots: 16; unique games: 14. Repeated snapshots are not independent games.
Summary uses the earliest original snapshot per game, globally and within each original revision. Revision groups overlap and must not be pooled.
Ties push in returns and are excluded from binary scores. Pending games remain ungraded. Market baseline uses each snapshot moneyline.

                   group  games  pending  wins  losses  pushes  units  roi  roi_se  market_null_roi  favorite_units  favorite_roi  binary_games  log_loss  market_log_loss    brier  market_brier
        All unique games     14       13     0       1       0   -1.0 -1.0     NaN        -0.040264            -1.0          -1.0             1  1.661357         1.567153 0.656292      0.626253
boxscore-composite-v1.12      1        0     0       1       0   -1.0 -1.0     NaN        -0.040264            -1.0          -1.0             1  1.661357         1.567153 0.656292      0.626253
boxscore-composite-v1.13      1        0     0       1       0   -1.0 -1.0     NaN        -0.040000            -1.0          -1.0             1  1.704567         1.609438 0.669368      0.640000
boxscore-composite-v1.14      1        0     0       1       0   -1.0 -1.0     NaN        -0.040785            -1.0          -1.0             1  1.745958         1.651078 0.681487      0.653118
boxscore-composite-v1.16     13       13     0       0       0    0.0  NaN     NaN              NaN             0.0           NaN             0       NaN              NaN      NaN           NaN

       original_revision         game_id  original_model_wp  model_wp bet_result  bet_units
boxscore-composite-v1.12  2026_05_TB_DAL           0.644547  0.810119          L       -1.0
boxscore-composite-v1.13  2026_05_TB_DAL           0.632918  0.818149          L       -1.0
boxscore-composite-v1.14  2026_05_TB_DAL           0.619215  0.825522          L       -1.0
boxscore-composite-v1.16 2026_05_BAL_ATL           0.709701  0.700417                   NaN
boxscore-composite-v1.16  2026_05_CHI_GB           0.498569  0.500465                   NaN
boxscore-composite-v1.16 2026_05_CIN_MIA           0.257985  0.256287                   NaN
boxscore-composite-v1.16 2026_05_CLE_NYJ           0.543821  0.536092                   NaN
boxscore-composite-v1.16 2026_05_DEN_LAC           0.413441  0.424978                   NaN
boxscore-composite-v1.16 2026_05_DET_ARI           0.342853  0.274207                   NaN
boxscore-composite-v1.16 2026_05_HOU_TEN           0.242192  0.249231                   NaN
boxscore-composite-v1.16 2026_05_IND_PIT           0.540172  0.542488                   NaN
boxscore-composite-v1.16   2026_05_LV_NE           0.611193  0.598425                   NaN
boxscore-composite-v1.16  2026_05_MIN_NO           0.482003  0.495136                   NaN
boxscore-composite-v1.16 2026_05_NYG_WAS           0.576515  0.577747                   NaN
boxscore-composite-v1.16 2026_05_PHI_JAX           0.795347  0.799784                   NaN
boxscore-composite-v1.16  2026_05_SF_SEA           0.939039  0.940683                   NaN
