# Validation: W% band mean/median MOV

- Focused mean/median module suite: **15 passed**. Fixtures cover signed margins
  including losses and ties, even-sample medians, matching group membership,
  negative mean/median retention, weighted monotone pooling, boundaries/endpoints,
  missing inputs, duplicate and invalid rows, prior-season cutoffs, forecast
  invariance to scored-season labels, paired week resampling, ATS skip/push
  precedence, and protected output paths.
- Five artifacts reproduce byte-for-byte in a separate process: per-game
  forecasts, current counterfactuals, fitted rules, results and provenance.
- Independently recomputed every prior band count, signed mean and median;
  checked weighted PAVA against SciPy; recomputed all five arms on all 895
  games, primary/current/pooled point errors, ATS grades and unit returns.
- Every fit's final training season is earlier than its scored season.
- Every frozen input, module and protocol source hash matches provenance.
- `python sync_notebook.py`: already in sync.
- `python validate_data_files.py`: **43 files OK**.
- Production model, moneylines, fixed bands, notebook, workflows and original
  `data/` records have no changes. `git diff --check` passes.

The full model was not rebuilt from raw NFL feature inputs; this test reuses
frozen forecasts. Source-vintage, historical-design-exposure and actual ATS
quote timestamp limitations remain. Research results are not native forward
records or verified executable-price returns.

Final full repository run: **732 passed, 1 existing xfailed**, 281.48 seconds.
Two pre-existing pandas concatenation warnings originate in `build_site.py`.
