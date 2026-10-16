"""Create the compact PDF report from completed, verified experiment outputs."""
import json
from pathlib import Path
import sys
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.utils import ImageReader
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'research/joint_market_residual_results'
WIDTH = 516
NAVY = colors.HexColor('#102b46')
BLUE = colors.HexColor('#2563eb')
TEAL = colors.HexColor('#0f766e')
GRAY = colors.HexColor('#475569')


def load(name):
    return json.loads((DATA / name).read_text())


styles = getSampleStyleSheet()
styles.add(ParagraphStyle(name='ReportTitle', fontName='Helvetica-Bold', fontSize=24, leading=28, textColor=NAVY, spaceAfter=12))
styles.add(ParagraphStyle(name='ReportH', fontName='Helvetica-Bold', fontSize=13, leading=17, textColor=NAVY, spaceBefore=12, spaceAfter=7))
styles.add(ParagraphStyle(name='ReportBody', fontName='Helvetica', fontSize=9.2, leading=13, textColor=NAVY, spaceAfter=8))
styles.add(ParagraphStyle(name='ReportNote', fontName='Helvetica', fontSize=8, leading=11, textColor=GRAY, spaceAfter=7))
styles.add(ParagraphStyle(name='ReportCell', fontName='Helvetica', fontSize=7.5, leading=10, textColor=NAVY))
styles.add(ParagraphStyle(name='ReportCellHead', fontName='Helvetica-Bold', fontSize=7.5, leading=10, textColor=colors.white))


def p(text, style='ReportBody'):
    return Paragraph(text, styles[style])


def h(text):
    return p(text, 'ReportH')


def tab(headers, rows, widths):
    content = [[p(escape(str(x)), 'ReportCellHead') for x in headers]]
    content += [[p(escape(str(x)), 'ReportCell') for x in row] for row in rows]
    table = Table(content, colWidths=widths, repeatRows=1, hAlign='LEFT')
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), NAVY), ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 7), ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6), ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#eef4f8'), colors.white]),
        ('LINEBELOW', (0, 0), (-1, 0), .6, NAVY),
    ]))
    return table


def arm_name(arm):
    return arm.replace('smooth__', 'Smooth / ').replace('empirical__', 'Empirical / ').replace(
        'A_market', 'A market').replace('B_residual', 'B means').replace('C_absolute', 'C absolute').replace('C_squared', 'C squared')


def interval_text(v, digits=4):
    return f'[{v[0]:+.{digits}f}, {v[1]:+.{digits}f}]'


def picture(filename, width=WIDTH):
    path = DATA / filename
    w, hh = ImageReader(str(path)).getSize()
    return Image(str(path), width=width, height=width * hh / w, hAlign='LEFT')


def footer(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor('#d7e1e9'))
    canvas.line(48, 752, 564, 752)
    canvas.setFont('Helvetica', 8)
    canvas.setFillColor(GRAY)
    canvas.drawString(48, 763, 'NFL MODEL  /  DISTRIBUTION RESEARCH')
    canvas.drawRightString(564, 763, 'OCTOBER 16, 2026')
    canvas.drawString(48, 28, 'Historical development - unknown market quote timestamps')
    canvas.drawRightString(564, 28, f'{doc.page}')
    canvas.restoreState()


def create_pdf(path):
    summaries = load('summary.json')
    primary = {r['arm']: r for r in summaries if r['basis'] == 'primary_2023_25'}
    diagnostic = {r['arm']: r for r in summaries if r['basis'] == 'diagnostic_2026'}
    earlier = {r['arm']: r for r in summaries if r['basis'] == 'earlier_2017_22'}
    arms = [shape + '__' + info for shape in ('smooth', 'empirical') for info in ('A_market', 'B_residual', 'C_absolute', 'C_squared')]
    returns = {r['arm']: r for r in load('moneyline_returns.json') if r['basis'] == 'primary_2023_25'}
    annual = {(r['arm'], r['season']): r for r in load('annual_summary.json')}
    annual_roi = {(r['arm'], int(r['basis'].split('_')[1])): r for r in load('annual_moneyline_returns.json')}
    pairs = [r for r in load('paired_comparisons.json') if r['basis'] == 'primary_2023_25' and r['family'] == 'primary' and r['metric'] == 'joint_nll']
    shape_gain = next(r for r in load('paired_comparisons.json') if r['basis'] == 'primary_2023_25' and r['family'] == 'shape' and r['arm'] == 'empirical__A_market' and r['metric'] == 'joint_nll')
    market = load('moneyline_baseline.json')
    verification = load('verification.json')
    story = []
    story += [p('Market context explains more<br/>than recent market errors', 'ReportTitle'),
              p('<b>Eight fixed variants | 816 main-test games | 2023-2025</b>'),
              p('The proposed four-game residual features did <b>not demonstrate incremental forecast skill</b> beyond current spread and total in these implementations. Every added-feature variant had worse pooled joint-score log loss than its matching market-only baseline. None of six primary gains cleared the adjusted uncertainty interval.'),
              p('The empirical market-only distribution best predicted exact score pairs. The smooth market-only distribution had the best broad MOV, total and team-point CRPS. The no-vig moneyline had a better winner log-loss point estimate than all eight variants.'),
              h('Returns and probability quality'),
              tab(['Variant', 'Joint-score NLL', 'Winner log loss', 'Flat 1u units', 'ROI'], [
                  [arm_name(a), f"{primary[a]['joint_nll']:.5f}", f"{primary[a]['win_ll']:.6f}", f"{returns[a]['units']:+.2f}", f"{100*returns[a]['roi']:+.2f}%"] for a in arms],
                  [170, 92, 92, 83, 79]), Spacer(1, 8),
              p(f"Market-favorite control: <b>+0.18u / +0.02% ROI</b> on the same 812 priced games. Always-underdog control: -89.82u / -11.06%. Quote-implied negative-hold null: about -4.10%. Moneyline winner baseline: log loss {market['win_ll']:.6f}, Brier {market['win_brier']:.6f}, n={market['n']}.", 'ReportNote'),
              p('All variants have negative pooled moneyline returns. The best new return, empirical A, is -0.91u (-0.11% +/- 2.47 percentage points SE). Its paired ROI difference versus always favorite is -0.13 pp, 95% interval [-1.12, +0.89] pp.', 'ReportNote'),
              h('What was tested'),
              p('<b>A:</b> current market total and spread. <b>B:</b> A plus scored and points-allowed residual EWMAs for each team. <b>C absolute / squared:</b> B means plus recent error-magnitude histories for uncertainty. Each information set has a smooth joint-score distribution and an 85/15 smooth-empirical mixture.'),
              p('These are exposed historical development results, not native forward forecasts. A confidence interval spanning zero leaves the effect unresolved. No model was selected or tuned by moneyline ROI.', 'ReportNote'), PageBreak()]
    story += [p('Do residual histories add information?', 'ReportTitle'),
              p('Positive gain means the residual variant assigns more probability to the realized home-away score pair. Each contrast uses the same 816 games and the same distribution family.'),
              picture('joint_gain_intervals.png'), Spacer(1, 8),
              tab(['Added information', 'NLL gain vs A', 'Adjusted interval'], [
                  [arm_name(r['arm']), f"{r['gain']:+.6f}", interval_text(r['joint_nll_six_contrast_ci'], 6)] for r in pairs], [205, 110, 201]),
              Spacer(1, 9),
              p('Paired whole-week bootstrap, stratified within season; 10,000 draws. Each interval has nominal 99.1667% coverage, targeting 95% family coverage across the six primary contrasts. These intervals condition on this fixed experiment and do not erase earlier research-selection exposure.', 'ReportNote'),
              p('<b>One clear adverse result:</b> empirical C absolute is worse than empirical A after the six-comparison adjustment. The other five incremental effects remain unresolved, with negative point estimates.'),
              h('Shape helps exact scores, not every target'),
              p(f"Adding the empirical mixture to market-only A improves joint-score NLL by <b>{shape_gain['gain']:.5f}</b>, descriptive 95% interval {interval_text(shape_gain['ci95'], 5)}. But it slightly worsens MOV CRPS (7.1129 vs 7.1019), total CRPS (7.2408 vs 7.2396), and team CRPS (5.1112 vs 5.1061). Better exact-score structure is not a demonstrated betting edge."), PageBreak()]
    story += [p('Season consistency', 'ReportTitle'),
              p('Weekly coefficients use only earlier games; all feature definitions, penalties, decay rules and empirical weights stay fixed. No season chooses its own best retrospective arm.'),
              h('Joint-score log loss and moneyline ROI by season'),
              tab(['Variant', '2023 NLL', '2024 NLL', '2025 NLL', '2023 ROI', '2024 ROI', '2025 ROI'], [
                  [arm_name(a)] + [f"{annual[a, y]['joint_nll']:.4f}" for y in (2023, 2024, 2025)] +
                  [f"{100*annual_roi[a, y]['roi']:+.2f}%" for y in (2023, 2024, 2025)] for a in arms],
                  [150, 61, 61, 61, 61, 61, 61]), Spacer(1, 8),
              p('816 primary distribution games; 272 each season. Winner scores exclude one tie. The common 812-bet sample excludes four market pick\'ems. Seasonal ROI is descriptive and can vary sharply with a few near-even games.', 'ReportNote'),
              h('2026 weeks 1-5: separate diagnostic, 79 games'),
              tab(['Variant', 'Joint NLL', 'MOV CRPS', 'Total CRPS', 'Winner LL'], [
                  [arm_name(a), f"{diagnostic[a]['joint_nll']:.4f}", f"{diagnostic[a]['margin_crps']:.4f}",
                   f"{diagnostic[a]['total_crps']:.4f}", f"{diagnostic[a]['win_ll']:.5f}"] for a in arms],
                  [186, 83, 82, 83, 82]), Spacer(1, 8),
              p('This diagnostic uses the completed games in the committed snapshot, not all games available as of the report date. It is not pooled with 2023-2025 and is too small to qualify a new model.', 'ReportNote'),
              h('Earlier context'),
              p('The package also contains 1,567 prior-week forecasts per variant for 2017-2022. Those are supplementary exposed development history. Every year and every fixed arm appears in the machine-readable summaries and full Markdown report.'), PageBreak()]
    story += [p('Calibration and usable outputs', 'ReportTitle'),
              p('Every forecast starts with one joint home-away score distribution. All win/loss/tie, team points, totals and MOV probabilities are derived from it, so their arithmetic is internally consistent.'),
              tab(['Variant', 'MOV 90% coverage', 'Total 90% coverage', 'Mean tie probability'], [
                  [arm_name(a), f"{100*primary[a]['margin_coverage90']:.2f}%", f"{100*primary[a]['total_coverage90']:.2f}%", f"{100*primary[a]['mean_tie_probability']:.2f}%"] for a in arms],
                  [198, 106, 106, 106]), Spacer(1, 8),
              p('<b>Material limitation:</b> one of 816 primary games tied (0.12%). Raw average tie forecasts are 2.50-2.87%, far too high. They are unsuitable for operational win/loss/tie use. Winner log loss and Brier in this report condition on a non-tie; they do not validate unconditional tie calibration.'),
              picture('interval_calibration.png', 495),
              p('Discrete intervals include endpoint mass, so nominal coverage need not be exact. Width matters alongside coverage. The smooth model\'s market-only 90% MOV interval averages 40.6 points wide; the total interval averages 41.6. The full report includes 50/80/90% coverage, widths, exact marginal NLL, CRPS, MAE/RMSE and reliability bins.', 'ReportNote'),
              p('No tie correction was fitted after seeing these results. The fixed variants remain available exactly as tested, allowing a separate, clearly labeled tie-aware experiment later.', 'ReportNote'), PageBreak()]
    story += [p('Method, verification and reproduction', 'ReportTitle'),
              h('Forecast construction'),
              p('Use the repo\'s committed regular-season schedule and total-line files, beginning in 2013. Positive spread means home favored. Derived market locations are (total + spread)/2 for home and (total - spread)/2 for away; they are not assumed expected means or actual sportsbook team-total quotes.'),
              p('EWMA span=4 means alpha=.4, zero initialization, older games retained, and 50% offseason retention. Update all histories after the entire week. Fit ridge mean corrections weekly with normalized penalty .1, training-only scales, a six-season window and two-season training half-life.'),
              p('Uncertainty is fit from earlier prequential mean-error cross-products. No covariance warm-up fallback remains in reported 2017-2026 games. C variants add absolute or squared residual histories. Score support is integer 0-80 for each team; all observed outcomes are inside the cap. Empirical mixture uses earlier actual score pairs only.'),
              h('Checks and evidence limits'),
              p(f"All <b>{len(verification)} integrity checks</b> pass: prior-week fit and history cutoffs, identical game sets, PMF normalization and row ordering, coherent means and event probabilities, and no reported covariance fallback. Focused tests include changing a whole week\'s outcomes without changing its forecasts. Full repository test results are recorded in VALIDATION.md in the bundle."),
              p('The Gaussian lattice approximates cell probabilities; rare impossible football score pairs are not removed. Scores include overtime. Empirical neighbors can be sparse. Covariance safeguards exist but did not activate in the primary sample. This test covers the stated fixed models, not every possible market-residual model.'),
              p('Historical line/price capture timestamps are unknown. They cannot substantiate an executable-price claim. No separately traded team-total prices are available. Whole-week intervals condition on the fixed designs and do not include all earlier research choices.'),
              h('Files and reproduction'),
              p('<b>REPORT.md:</b> complete tables and interpretation. <b>predictions.csv.gz:</b> 19,696 scored arm-game rows. <b>marginal_probabilities.npz:</b> all home, away, total and MOV PMFs, with game IDs and supports. <b>example_joint_probabilities.npz:</b> illustrative full joint PMFs. Frozen inputs, features, history/fit cutoffs, coefficients, hashes, calibration and return summaries are included.'),
              p('Run from the extracted experiment folder:<br/><font name="Courier" size="8">OPENBLAS_NUM_THREADS=1 python research/joint_market_residuals.py<br/>OPENBLAS_NUM_THREADS=1 python research/joint_market_residuals_report.py</font>'),
              p('Requirements: numpy, pandas, matplotlib; pytest for tests; reportlab to recreate this PDF. The rerun uses the frozen pack and makes no network requests.', 'ReportNote'),
              h('Decision'),
              p('<b>Keep market-only scoring distributions as the research benchmark. These tests do not justify adding the four-game residual features or claiming a betting edge. Resolve the raw tie calibration before using unconditional game-outcome probabilities.</b>'),
              p('Base repository: Dave356w/NFL-MODEL, e93b936b9de03bab8e97a6b7ae71fb6d3a224fa7. Protocol fixed in local commit 00033e7 before this experiment generated forecasts. Production forecasts, ledger and deployed site were not changed.', 'ReportNote')]
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(path), pagesize=(612, 792), leftMargin=48, rightMargin=48,
                            topMargin=52, bottomMargin=46, title='NFL market residual variants - historical test',
                            author='NFL Model Research')
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    print(path)


if __name__ == '__main__':
    create_pdf(sys.argv[1] if len(sys.argv) > 1 else ROOT.parent / 'output/pdf/NFL_Market_Residual_Variants_Report.pdf')
