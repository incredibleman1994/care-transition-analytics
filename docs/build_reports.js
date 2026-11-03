// Builds reports/Research_Paper.docx and reports/Executive_Summary.docx
// Usage: node docs/build_reports.js   (requires the `docx` npm package)
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, ImageRun, Table, TableRow, TableCell, HeadingLevel, AlignmentType,
  LevelFormat, LineRuleType, BorderStyle, WidthType, ShadingType, Footer, Header, PageNumber, PageBreak, TabStopType,
} = require("docx");

const ROOT = path.resolve(__dirname, "..");
const S = JSON.parse(fs.readFileSync(path.join(ROOT, "reports", "key_stats.json"), "utf8"));
const AUTHOR = "[Your Name]";
const PAGE = { width: 11906, height: 16838 };              // A4
const MARGIN = 1134;
const CW = PAGE.width - 2 * MARGIN;                        // content width in DXA = 9638
const NAVY = "1F3A5F", TEAL = "2A9D8F", GREY = "5B6573", LIGHT = "EEF2F7", RED = "C0392B";

// ------------------------------------------------------------------ helpers
const pct = (x, n = 1) => (100 * x).toFixed(n) + "%";
const run = (t, o = {}) => new TextRun({ text: t, font: "Calibri", size: 22, ...o });
function rich(text, base = {}) {            // **bold** inline markup
  return text.split(/(\*\*[^*]+\*\*)/g).filter(Boolean).map((s) =>
    s.startsWith("**") ? run(s.slice(2, -2), { bold: true, ...base }) : run(s, base));
}
const P = (text, o = {}) => new Paragraph({ children: rich(text), spacing: { after: 140, line: 300, lineRule: LineRuleType.AUTO }, alignment: AlignmentType.JUSTIFIED, ...o });
const H1 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun({ text: t, font: "Calibri", size: 32, bold: true, color: NAVY })], spacing: { before: 360, after: 160 }, border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: TEAL, space: 4 } } });
const H2 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun({ text: t, font: "Calibri", size: 26, bold: true, color: NAVY })], spacing: { before: 240, after: 100 } });
const B = (text, level = 0) => new Paragraph({ numbering: { reference: "bul", level }, children: rich(text), spacing: { after: 80, line: 290, lineRule: LineRuleType.AUTO } });
const N = (text) => new Paragraph({ numbering: { reference: "num", level: 0 }, children: rich(text), spacing: { after: 90, line: 290, lineRule: LineRuleType.AUTO } });
const gap = (n = 120) => new Paragraph({ children: [], spacing: { after: n } });

function pngSize(file) {
  const b = fs.readFileSync(file);
  return { w: b.readUInt32BE(16), h: b.readUInt32BE(20) };
}
function figure(file, caption, widthPx = 610) {
  const f = path.join(ROOT, "figures", file);
  const { w, h } = pngSize(f);
  return [
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 120, after: 60 }, keepNext: true,
      children: [new ImageRun({ type: "png", data: fs.readFileSync(f), transformation: { width: widthPx, height: Math.round((widthPx * h) / w) },
        altText: { title: caption, description: caption, name: file } })] }),
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 200 }, children: [run(caption, { italics: true, size: 19, color: GREY })] }),
  ];
}

const border = { style: BorderStyle.SINGLE, size: 4, color: "C9D1DC" };
const borders = { top: border, bottom: border, left: border, right: border };
function table(header, rows, widths, opts = {}) {
  const total = widths.reduce((a, b) => a + b, 0);
  const cell = (t, w, isH, align) => new TableCell({
    width: { size: w, type: WidthType.DXA }, borders,
    shading: isH ? { fill: NAVY, type: ShadingType.CLEAR, color: "auto" } : undefined,
    margins: { top: 70, bottom: 70, left: 100, right: 100 },
    children: [new Paragraph({ keepNext: true, alignment: align, children: [run(String(t), { size: opts.size || 19, bold: isH, color: isH ? "FFFFFF" : "222222" })] })],
  });
  return new Table({
    width: { size: total, type: WidthType.DXA }, columnWidths: widths,
    rows: [
      new TableRow({ tableHeader: true, children: header.map((h, i) => cell(h, widths[i], true, i === 0 ? AlignmentType.LEFT : AlignmentType.CENTER)) }),
      ...rows.map((r, ri) => new TableRow({ children: r.map((c, i) => {
        const tc = cell(c, widths[i], false, i === 0 ? AlignmentType.LEFT : AlignmentType.CENTER);
        return tc;
      }) })),
    ],
  });
}
function callout(title, text, color = TEAL) {
  const none = { style: BorderStyle.NONE, size: 0, color: "FFFFFF" };
  return new Table({
    width: { size: CW, type: WidthType.DXA }, columnWidths: [CW],
    rows: [new TableRow({ children: [new TableCell({
      width: { size: CW, type: WidthType.DXA },
      borders: { top: none, bottom: none, right: none, left: { style: BorderStyle.SINGLE, size: 24, color } },
      shading: { fill: LIGHT, type: ShadingType.CLEAR, color: "auto" }, margins: { top: 110, bottom: 110, left: 200, right: 160 },
      children: [new Paragraph({ spacing: { after: 60 }, children: [run(title, { bold: true, color })] }), new Paragraph({ spacing: { line: 290, lineRule: LineRuleType.AUTO }, children: rich(text, { size: 21 }) })],
    })] })],
  });
}

const styles = {
  default: { document: { run: { font: "Calibri", size: 22 } } },
  paragraphStyles: [
    { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true, run: { size: 32, bold: true, font: "Calibri" }, paragraph: { spacing: { before: 360, after: 160 }, outlineLevel: 0 } },
    { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true, run: { size: 26, bold: true, font: "Calibri" }, paragraph: { spacing: { before: 240, after: 100 }, outlineLevel: 1 } },
  ],
};
const numbering = {
  config: [
    { reference: "bul", levels: [
      { level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 540, hanging: 270 } } } },
      { level: 1, format: LevelFormat.BULLET, text: "–", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 1000, hanging: 270 } } } } ] },
    { reference: "num", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 540, hanging: 340 } } } }] },
  ],
};
const pageProps = { page: { size: PAGE, margin: { top: MARGIN, bottom: MARGIN, left: MARGIN, right: MARGIN } } };
const footer = (label) => new Footer({ children: [new Paragraph({
  tabStops: [{ type: TabStopType.RIGHT, position: CW }],
  children: [run(label, { size: 17, color: GREY }), new TextRun({ children: ["\tPage ", PageNumber.CURRENT], font: "Calibri", size: 17, color: GREY })] })] });

// ------------------------------------------------------------------ numbers
const K = S.kpi_by_year, Q = S.quarterly_throughput, KQ = S.kpi_by_quarter, W = S.weekday, R = S.regime, REC = S.reconciliation;
const fmtDate = (s) => new Date(s + "T00:00:00").toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });

// ====================================================================== RESEARCH PAPER
const paper = [];
paper.push(
  gap(1400),
  new Paragraph({ alignment: AlignmentType.LEFT, spacing: { after: 120 }, children: [run("RESEARCH PAPER", { size: 22, bold: true, color: TEAL, characterSpacing: 60 })] }),
  new Paragraph({ spacing: { after: 160, line: 260, lineRule: LineRuleType.AUTO }, children: [run("Care Transition Efficiency & Placement Outcome Analytics", { size: 56, bold: true, color: NAVY })] }),
  new Paragraph({ spacing: { after: 400 }, children: [run("A process-efficiency analysis of the CBP → HHS → sponsor pipeline for unaccompanied children, January 2023 – December 2025", { size: 28, color: GREY })] }),
  new Paragraph({ border: { top: { style: BorderStyle.SINGLE, size: 8, color: TEAL, space: 8 } }, spacing: { after: 60 }, children: [run("Author: ", { bold: true }), run(AUTHOR)] }),
  new Paragraph({ spacing: { after: 60 }, children: [run("Domain: ", { bold: true }), run("Data Science · Child-welfare process analytics")] }),
  new Paragraph({ spacing: { after: 60 }, children: [run("Data: ", { bold: true }), run(`${S.quality.reported_days} reporting days, ${fmtDate(S.quality.start)} – ${fmtDate(S.quality.end)}`)] }),
  new Paragraph({ spacing: { after: 60 }, children: [run("Deliverables: ", { bold: true }), run("research paper · Streamlit dashboard · executive summary · analysis notebook")] }),
  new Paragraph({ children: [new PageBreak()] }),
);

// Abstract
paper.push(
  H1("Abstract"),
  P(`The Unaccompanied Children (UAC) Program is a multi-stage pipeline: children are apprehended and held in U.S. Customs and Border Protection (CBP) custody, transferred to the Department of Health and Human Services (HHS) for care and case management, and finally discharged to vetted sponsors. Aggregate head-counts are monitored closely, but **process-efficiency metrics are largely absent**, so bottlenecks stay hidden. This paper reframes the daily UAC dataset (${S.quality.reported_days} reporting days, 2023–2025) from a capacity-monitoring lens to a process-efficiency lens. We model the system as a flow pipeline, derive five KPIs (Transfer Efficiency Ratio, Discharge Effectiveness Index, Pipeline Throughput, Backlog Accumulation Rate, Outcome Stability Score), and test for backlogs, delays, weekday effects and instability.`),
  P(`**Key results.** Through 2023–24 roughly three-quarters of children in CBP custody were transferred per reporting day (${pct(K[2023].transfer_eff)} in 2023, ${pct(K[2024].transfer_eff)} in 2024) and about 3% of the HHS population was discharged per day. In early 2025 the system underwent a structural break: transfer efficiency fell to ${pct(R.post_ter, 0)} and discharge effectiveness to ${pct(R.post_dei, 2)} (both p < 0.001). Implied dwell time in CBP custody, stable at ≈1.3 days until Q1 2025, rose to ≈${KQ["2025Q3"].implied_cbp_days.toFixed(1)}–${KQ["2025Q4"].implied_cbp_days.toFixed(1)} days in H2 2025, past the 72-hour transfer benchmark, while implied time in HHS care rose from ≈30 to 150–230 days. Four prolonged stagnation periods and eight sudden discharge drops were detected. Discharges differ significantly by weekday (Tuesday weakest) while transfer speed does not. A forecasting benchmark shows that simple persistence beats gradient boosting, which fails across the structural break. We also document a stock–flow reconciliation gap in 2023–24 that limits how literally flow totals can be read. A Streamlit dashboard operationalises all metrics with date filters, ratio toggles and visual threshold alerts.`),
  P("**Keywords:** care transitions, unaccompanied children, pipeline analytics, process efficiency, backlog detection, child welfare, Streamlit.", { alignment: AlignmentType.LEFT }),
);

// 1 Introduction
paper.push(
  H1("1. Introduction and Background"),
  P("The UAC Program operates as a multi-stage care and reunification pipeline, not merely a healthcare system. The stages are: (1) apprehension and CBP custody; (2) transfer to HHS care; (3) medical screening, sheltering and case management; and (4) discharge and reunification with a vetted sponsor. For children, time in each stage matters: delays prolong time in congregate settings and postpone reunification. From a policy and humanitarian perspective, the **speed, continuity and reliability** of this pipeline are as critical as bed capacity."),
  P("Official reporting emphasises stock measures, such as how many children are in CBP custody or HHS care on a given day. Stock measures cannot distinguish a busy-but-healthy system from a congested one: 2,500 children in care could mean rapid turnover or a long, stagnant wait. Flow-based, process-oriented measures can."),
  H2("1.1 Problem statement"),
  P("While aggregate counts are monitored, process-efficiency metrics are largely absent. This project addresses four unanswered questions:"),
  B("How efficiently are children transferred from CBP to HHS?"),
  B("Are discharges keeping pace with inflows?"),
  B("When and where do care backlogs accumulate?"),
  B("Are placement outcomes improving or deteriorating over time?"),
  H2("1.2 Objectives"),
  P("**Primary:** (i) measure the efficiency of CBP → HHS transitions; (ii) evaluate discharge and sponsor-placement outcomes; (iii) identify delays and process bottlenecks. **Secondary:** support faster reunification, improve case-management workflows and inform policy-level process reforms."),
);

// 2 Data
paper.push(
  H1("2. Data"),
  H2("2.1 Description"),
  P("The dataset contains one row per reporting date with five measures, listed below. Three are flows (daily movements between stages) and two are stocks (children present at a point in time)."),
  table(["Column", "Type", "Meaning"], [
    ["Children apprehended and placed in CBP custody", "Flow", "Daily intake into the pipeline"],
    ["Children in CBP custody", "Stock", "Active CBP care load"],
    ["Children transferred out of CBP custody", "Flow", "Daily flow into the HHS system"],
    ["Children in HHS care", "Stock", "Active HHS care load"],
    ["Children discharged from HHS care", "Flow", "Daily successful sponsor placements"],
  ], [4200, 1200, 4238]),
  gap(),
  H2("2.2 Cleaning"),
  P(`The raw file has ${S.quality.raw_rows.toLocaleString()} rows, of which **${S.quality.blank_rows_dropped} are entirely blank** and were removed, leaving ${S.quality.reported_days}. The HHS-care column was stored as text with thousands separators (e.g. "2,340") and was converted to numeric; dates were parsed from text and re-sorted chronologically (the file is newest-first); column names were shortened and the footnote asterisk removed. No duplicate dates and no missing values remain after cleaning.`),
  H2("2.3 Data-quality findings that shape the analysis"),
  B(`**Incomplete calendar.** The ${S.quality.reported_days} reporting days cover only ${S.quality.coverage_pct}% of the ${S.quality.calendar_days.toLocaleString()} calendar days in the span. Reports exist for Monday–Thursday and Sunday; Friday has only ${S.quality.weekday_counts.Friday} rows and Saturday none. A Sunday row therefore follows a 3-day gap. All rates in this paper are expressed **per reporting day**.`),
  B(`**Stock and flow data do not fully reconcile.** If the pipeline model were exact, the daily change in HHS care would equal transfers minus discharges. On consecutive-day pairs the correlation between the two is only ${REC[2023].hhs_corr} in 2023, improves to ${REC[2024].hhs_corr} in 2024, and reaches ${REC[2025].hhs_corr} in 2025 (Figure 1). In 2023 the HHS stock grew faster than reported net flows imply, which suggests children entered HHS care through routes not captured in the reported CBP transfers, or that some transfers went unreported.`),
  B(`**Intake is narrower than transfers.** Across the period, ${S.intake_vs_transfer_total.transfers.toLocaleString()} children are reported transferred out of CBP custody but only ${S.intake_vs_transfer_total.intake.toLocaleString()} apprehended and placed in custody (a ${((S.intake_vs_transfer_total.transfers / S.intake_vs_transfer_total.intake - 1) * 100).toFixed(0)}% difference). The "apprehended" definition is evidently narrower than total CBP intake.`),
  B("**Structural break.** Volumes collapse in early 2025 (Section 5.1), so pooled averages across the whole period mix two very different regimes."),
  ...figure("fig09_reconciliation.png", "Figure 1. Flow vs stock reconciliation on consecutive-day pairs. Points on the dashed line would indicate perfect agreement."),
  callout("Implication", "Ratio metrics are valid as **process indicators** and for comparing periods, but flow totals should not be treated as exact stock changes. The analysis therefore reports flow-based and stock-based backlog views side by side, and highlights where they agree."),
);

// 3 Method
paper.push(
  H1("3. Methodology"),
  H2("3.1 Care-pipeline model"),
  P("The system is represented as a three-stage flow pipeline: **Apprehension → CBP custody → HHS care → Sponsor placement**. Two stocks (CBP load, HHS load) are fed and drained by three flows (intake, transfers, discharges). Daily movements between stages are tracked, and net flows are defined for each stage:"),
  B("CBP net flow = intake − transfers (positive: CBP queue building)"),
  B("HHS net flow = transfers − discharges (positive: HHS queue building)"),
  B("System net flow = intake − discharges (positive: whole pipeline filling)"),
  H2("3.2 Key performance indicators"),
  table(["KPI", "Formula", "Interpretation"], [
    ["Transfer Efficiency Ratio (TER)", "Transfers ÷ CBP custody", "Share of the CBP population moved to HHS per reporting day; higher is faster"],
    ["Discharge Effectiveness Index (DEI)", "Discharges ÷ HHS care", "Share of the HHS population placed with sponsors per reporting day"],
    ["Pipeline Throughput", "Total exits ÷ total entries (discharges ÷ intake)", ">1 = system draining; <1 = filling"],
    ["Backlog Accumulation Rate", "(Entries − exits) per day ÷ (CBP + HHS load)", "Positive = backlog building; severity of delay"],
    ["Outcome Stability Score", "100 × (1 − coefficient of variation of daily discharges over a rolling 28 reporting days)", "100 = perfectly steady placements; low = erratic"],
  ], [2500, 3500, 3638]),
  gap(),
  P("Daily ratios are noisy, so rolling versions use a **ratio of sums** over a 7-reporting-day window (configurable in the dashboard) rather than a mean of daily ratios. Two supplementary indicators estimate delay using Little's law (average time in a stage ≈ stock ÷ outflow rate): **implied days in CBP custody** (CBP load ÷ mean transfers) and **implied days in HHS care** (HHS load ÷ mean discharges). Little's law is exact only for steady-state systems, so these are used as indicators of direction and magnitude, not precise lengths of stay."),
  H2("3.3 Backlog, stagnation and instability detection"),
  B("**Sustained imbalance:** at least 10 consecutive reporting days in which the rolling mean of (intake − discharges) is positive."),
  B("**Stagnation:** at least 14 consecutive reporting days in which HHS load changes by less than 5% over 14 days **and** the rolling DEI is below 1.5%. The second condition separates genuine stagnation (children stay put) from healthy equilibrium (large inflows balanced by large outflows)."),
  B("**Sudden drops:** the 7-day average of discharges falls at least 30% below the preceding 7-day average (base of at least 10 per day); consecutive flags are merged into one event."),
  H2("3.4 Statistical testing and forecasting"),
  P("Differences between regimes and weekdays are tested with non-parametric tests (Mann–Whitney U for two groups, Kruskal–Wallis for several) because the distributions are skewed. To test whether the pipeline is predictable enough for modelling to add value, discharges five reporting days ahead are forecast with gradient boosting and two naive baselines (last value and 7-day mean), using 5-fold rolling-origin cross-validation and weighted absolute percentage error (WAPE = Σ|error| ÷ Σ actual)."),
);

// 4 Results
paper.push(
  H1("4. Results"),
  H2("4.1 Pipeline overview and the early-2025 structural break"),
  P(`HHS care peaked at ${S.peak.hhs_max.toLocaleString()} children on ${fmtDate(S.peak.hhs_max_date)} and CBP custody at ${S.peak.cbp_max} on ${fmtDate(S.peak.cbp_max_date)}. From January 2025 both stocks fell sharply within roughly two months, with HHS care dropping from about 6,400 to about 2,100 and then holding in a narrow 2,000–2,500 band for the rest of the year (low point: ${S.peak.hhs_min.toLocaleString()} on ${fmtDate(S.peak.hhs_min_date)}). Daily flows fell by an order of magnitude: discharges averaged ${R.pre_discharges_per_day} per reporting day before February 2025 and ${R.post_discharges_per_day} after April 2025.`),
  ...figure("fig01_care_load.png", "Figure 2. Children in HHS care and in CBP custody, Jan 2023 – Dec 2025."),
  ...figure("fig02_monthly_flows.png", "Figure 3. Average daily stage movements by month."),
  H2("4.2 How efficiently are children transferred from CBP to HHS?"),
  P(`Transfer efficiency was high and steady through 2023–24 (${pct(K[2023].transfer_eff)} in 2023, ${pct(K[2024].transfer_eff)} in 2024): on a typical reporting day about three of every four children in CBP custody were transferred. After the break it fell to a mean of ${pct(R.post_ter, 0)} (before: ${pct(R.pre_ter, 0)}; Mann–Whitney p < 0.001), reaching ${pct(KQ["2025Q4"].transfer_eff, 0)} in Q4 2025. The 2025 annual figure of ${pct(K[2025].transfer_eff)} blends the high-efficiency first weeks with the low-efficiency remainder.`),
  P("The decline has a clear operational meaning. Implied time in CBP custody was stable at about 1.3 days from 2023 to Q1 2025 (Table 1) and then rose to 2.4 days in Q2 and **3.2–3.4 days in H2 2025**. Under the 72-hour benchmark for transferring unaccompanied children to HHS, a mean dwell time above three days implies that many children were held beyond that benchmark, although the estimate is indicative because volumes are very low in this period (≈30 children in custody)."),
  ...figure("fig03_efficiency.png", "Figure 4. Rolling 7-day Transfer Efficiency Ratio (top) and Discharge Effectiveness Index (bottom); faint lines show daily values."),
  H2("4.3 Are discharges keeping pace with inflows?"),
  P("Taken as a whole, yes: total discharges (124,853) exceed total apprehensions (67,337) and total transfers (92,641), so the end-to-end throughput ratio is 1.85×. But aggregate throughput hides stage-level and period-level shortfalls. Figure 5 splits throughput by stage and quarter. Stage 1 (transfers ÷ intake) stays between 1.2× and 1.5× throughout, so CBP was never the cumulative bottleneck. Stage 2 (discharges ÷ transfers) falls **below 1.0 in Q2, Q3 and Q4 2024 (0.90, 0.95, 0.84)** and again in Q4 2025 (0.96): in those quarters HHS discharged fewer children than it received, so its caseload grew."),
  ...figure("fig04_throughput_stages.png", "Figure 5. Quarterly throughput by stage. Values below 1.0 (dashed line) indicate that a stage is accumulating children."),
  P("Placement effectiveness shows a longer-term decline that is easy to miss in head-counts:"),
  table(["Year", "Transfer eff.", "Discharge eff.", "Throughput", "Avg HHS load", "Implied days in HHS", "Stability"], [
    ...[2023, 2024, 2025].map((y) => [String(y), pct(K[y].transfer_eff), pct(K[y].discharge_eff, 2), K[y].throughput.toFixed(2) + "×", Math.round(K[y].avg_hhs_load).toLocaleString(), K[y].implied_hhs_days.toFixed(0), K[y].stability.toFixed(0)]),
  ], [900, 1400, 1500, 1300, 1500, 1700, 1338], { size: 18 }),
  new Paragraph({ spacing: { before: 60, after: 160 }, children: [run("Table 1. Annual KPI scorecard (per reporting day). Throughput > 1 means the system drained stock.", { italics: true, size: 19, color: GREY })] }),
  P(`Discharge effectiveness fell from ${pct(K[2023].discharge_eff, 2)} per day in 2023 to ${pct(K[2024].discharge_eff, 2)} in 2024 and ${pct(K[2025].discharge_eff, 2)} in 2025 (quarterly low: ${pct(KQ["2025Q4"].discharge_eff, 2)}). Implied time in HHS care lengthened from ≈29 days in Q1 2023 to ≈39 days by Q4 2024 and then to **149–234 days in Q3–Q4 2025** (Figure 6). The size of the 2025 change makes the direction unambiguous even allowing for the approximations in Little's law. The data cannot, however, explain *why*: reduced intake leaves a residual HHS population that is more likely to be long-stay cases, and sponsor-vetting practices or policy changes may also play a role. Establishing cause requires case-level data.`),
  ...figure("fig08_dwell_times.png", "Figure 6. Implied time in CBP custody (left; dashed line is the 72-hour benchmark) and in HHS care (right)."),
  H2("4.4 When and where do backlogs accumulate?"),
  P(`Sustained flow-based imbalance (entries exceeding exits for at least 10 reporting days) is rare: two episodes, ${fmtDate(S.imbalance[0].start)}–${fmtDate(S.imbalance[0].end)} (excess of ${S.imbalance[0].excess} children, CBP custody peaking at ${S.imbalance[0].peak_cbp}) and ${fmtDate(S.imbalance[1].start)}–${fmtDate(S.imbalance[1].end)} (excess of ${S.imbalance[1].excess}). The flow view therefore suggests the system was draining almost continuously. The **stock view tells a different story** in 2023–24: total care load rose repeatedly (Figure 7, lower panel). This is the reconciliation gap of Section 2.3 in action, and it means that backlogs in 2023–24 cannot be reliably located from reported flows alone. In 2025 the two views agree, and both show a quiet, slow-moving system.`),
  ...figure("fig05_backlog.png", "Figure 7. Flow-based (top) and stock-based (bottom) backlog views. Amber bands mark stagnation periods."),
  P("The more important 2025 phenomenon is **stagnation** rather than overflow. Four prolonged windows were detected in which HHS load was flat and discharges had nearly stopped:"),
  table(["Period", "Reporting days", "Avg HHS load", "Discharges / day", "Discharge eff."],
    S.stagnation.map((s) => [`${fmtDate(s.start)} – ${fmtDate(s.end)}`, s.days, s.hhs.toLocaleString(), s.dis, s.dei_pct + "%"]), [3400, 1500, 1600, 1600, 1538], { size: 18 }),
  new Paragraph({ spacing: { before: 60, after: 160 }, children: [run("Table 2. Detected stagnation periods (2025).", { italics: true, size: 19, color: GREY })] }),
  P(`The longest window (${fmtDate(S.stagnation[3].start)} – ${fmtDate(S.stagnation[3].end)}, ${S.stagnation[3].days} reporting days) holds ${S.stagnation[3].hhs.toLocaleString()} children with about ${Math.round(S.stagnation[3].dis)} discharges per day, a rate at which the standing population turns over only very slowly. This is the clearest hidden bottleneck revealed by process analytics: capacity is not the constraint, but throughput is.`),
  H2("4.5 Weekday versus weekend transition speed"),
  P(`Transfer volumes are essentially identical on Sundays and Monday–Thursday (${W.sunday_vs_weekday_transfers.sunday} vs ${W.sunday_vs_weekday_transfers.weekday} per day, p = ${W.sunday_vs_weekday_transfers.mannwhitney_p.toFixed(2)}), so there is no evidence of a weekend slow-down in CBP → HHS transfers. Discharges, however, vary significantly by day (Kruskal–Wallis p < 0.001): **Tuesday is weakest (${W.table.Tuesday.discharges} per day) and Thursday and Sunday strongest (${W.table.Thursday.discharges} and ${W.table.Sunday.discharges})**. Sunday discharges exceed Monday–Thursday by about ${Math.round((W.sunday_vs_weekday_discharges.sunday / W.sunday_vs_weekday_discharges.weekday - 1) * 100)}% (p = ${W.sunday_vs_weekday_discharges.mannwhitney_p.toFixed(3)}). Because Sunday rows follow a 3-day reporting gap, they may include catch-up activity, so this should be validated with complete Friday and Saturday data before any staffing change is made.`),
  ...figure("fig06_weekday.png", "Figure 8. Average transfers, discharges and discharge effectiveness by reporting weekday.", 600),
  H2("4.6 Are placement outcomes improving or deteriorating?"),
  P(`Month-over-month, daily discharges swing widely: the largest falls were −29% (June 2023) and −60% and −77% (February and March 2025), with partial recoveries in May–June 2025 (+29%, +45%). Outcome stability tells the same story compactly: the score held at about 77 out of 100 in both 2023 and 2024, collapsed to a minimum of about 6 in April 2025 (when the 28-day window spanned the transition) and averaged ${K[2025].stability.toFixed(0)} across 2025, still hovering around the 60-point alert line at year-end. Eight sudden week-on-week drops of 30% or more were detected (April 2024; January, February and March 2025; July, September, October and November 2025). The five events with a prior base below 30 discharges per day (March 2025 and July–November 2025) should be read cautiously, because when daily discharges are around 10, a handful of cases shifts the percentage.`),
  ...figure("fig07_stability_drops.png", "Figure 9. Discharges per reporting day with detected sudden drops (top) and Outcome Stability Score (bottom)."),
  P("**Overall, placement outcomes deteriorated on every efficiency measure**: they were stable but gradually softening through 2023–24, fell sharply in early 2025, and remain far below earlier levels at the end of the series."),
  H2("4.7 Is the pipeline predictable enough for forecasting?"),
  P(`Gradient boosting matches the naive baselines in the three stable folds (WAPE ≈ ${pct(S.forecast.gbm.folds[0], 0)}–${pct(S.forecast.gbm.folds[2], 0)}) but fails badly in the fold containing the structural break (WAPE ${pct(S.forecast.gbm.folds[3], 0)}), because tree-based models cannot extrapolate to a regime they have never seen. Averaged over folds, the best method is simply the **last observed value (WAPE ${pct(S.forecast.naive_last.mean_wape, 1)})**, ahead of the 7-day mean (${pct(S.forecast.naive_mean7.mean_wape, 1)}) and gradient boosting (${pct(S.forecast.gbm.mean_wape, 1)}). This is a useful negative result: short-term discharge volume is best monitored through persistence-based indicators with change-detection alerts, as in the dashboard, rather than a black-box forecaster that can fail silently when conditions change.`),
  ...figure("fig10_forecast_benchmark.png", "Figure 10. Five-reporting-day-ahead discharge forecast error under rolling-origin cross-validation.", 470),
);

// 5 Dashboard
paper.push(
  H1("5. Streamlit Dashboard"),
  P("All metrics are operationalised in an interactive Streamlit application that shares its calculation code with this paper and the analysis notebook, so the numbers always agree. The dashboard has six tabs:"),
  table(["Module", "Content"], [
    ["Overview", "Five KPI cards with change vs the previous period of equal length; four traffic-light alert tiles; HHS and CBP load chart; plain-language reading of the selected range"],
    ["Pipeline Flow", "Sankey diagram of cumulative movements (apprehended → CBP → HHS → sponsors); stage-conversion ratios; weekly or monthly stage movements"],
    ["Efficiency Panels", "Rolling Transfer Efficiency, Discharge Effectiveness and Throughput charts with threshold lines and breach markers; weekday vs Sunday comparison"],
    ["Bottlenecks", "Flow- and stock-based backlog charts with stagnation bands; implied CBP and HHS dwell times; tables of imbalance and stagnation periods"],
    ["Outcome Trends", "Month-over-month placement performance; stability score; sudden-drop detector; downloadable monthly scorecard"],
    ["Data & Method", "Data-quality summary, known caveats, metric definitions, cleaned-data preview and download"],
  ], [2200, 7438]),
  gap(),
  P("**User controls:** a date-range selector; toggles to show or hide each ratio metric and raw daily values; a rolling-window slider (3–28 days); and adjustable visual alert thresholds for transfer efficiency, discharge effectiveness, throughput, stability and the sudden-drop trigger. An optional upload accepts a CSV with the same columns so the tool can be reused on new data."),
);

// 6 Recommendations
paper.push(
  H1("6. Recommendations"),
  N("**Adopt process KPIs alongside head-counts.** Report Transfer Efficiency, Discharge Effectiveness, stage throughput and implied dwell times on a rolling basis. They reveal stagnation that stock counts cannot (for instance, 2,300 children in care is routine at one turnover rate and alarming at another)."),
  N("**Set alert thresholds and review them routinely.** Suggested starting thresholds, tunable in the dashboard: rolling transfer efficiency below 50%; discharge effectiveness below 1.5% per day; stage-2 throughput below 1.0 for a full quarter; outcome stability below 60; implied CBP dwell time above 3 days."),
  N("**Investigate the H2-2025 CBP dwell time.** Implied time in CBP custody exceeded the 72-hour benchmark in Q3 and Q4 2025 and was rising at the end of the series. Case-level timestamps should be audited to confirm whether this reflects genuine delays or low-volume noise."),
  N("**Launch a long-stay case review for HHS.** Stagnation windows of 14–37 reporting days at 10–17 discharges per day suggest a residual population that is not moving. A structured review of sponsor-vetting, case-management and legal-process steps for children with long lengths of stay could accelerate reunification."),
  N("**Examine weekday scheduling.** Tuesday discharges run about one-third below Thursday and Sunday. If confirmed with complete Friday and Saturday data, shifting sponsor-release and case-closure activities to smooth the weekly rhythm would raise average throughput at no cost in capacity."),
  N("**Fix the data at source.** Publish daily counts for all seven days; reconcile flows with stocks (document every route into and out of each stage); align the definition of \"apprehended\" with total CBP intake; and provide case-level entry, transfer and discharge dates so true lengths of stay can replace Little's-law estimates."),
  N("**Pair monitoring with change detection, not forecasting.** Because simple persistence outperforms machine-learning forecasts across a structural break, invest in alerts and drift monitoring rather than complex predictive models until data are richer."),
);

// 7 Limitations & conclusion
paper.push(
  H1("7. Limitations"),
  B("**Aggregate data.** Without case-level records, dwell times are Little's-law approximations and cannot be linked to child characteristics, sponsor categories or geography."),
  B("**Reporting calendar.** Only 67% of calendar days are covered; Friday and Saturday are essentially missing, which limits weekday analysis and may bias per-reporting-day rates."),
  B("**Flow–stock inconsistencies** in 2023–24 (Section 2.3) reduce confidence in backlog localisation for those years."),
  B("**Low-volume noise** in late 2025: ratios based on 10 discharges per day are volatile, and the sudden-drop detector is correspondingly sensitive."),
  B("**Descriptive, not causal.** The analysis identifies when and where efficiency changed, not why. Policy, enforcement, legal and seasonal drivers are outside the data."),
  H1("8. Conclusion"),
  P("Viewed as a process rather than a capacity problem, the UAC pipeline shows a clear and consequential pattern. It ran steadily through 2023–24, with about 76–78% of children in CBP custody transferred each reporting day and about 3% of the HHS population placed daily. It then underwent a structural change in early 2025 after which transfers slowed, discharge effectiveness fell by more than 80%, implied dwell times lengthened sharply in both CBP custody and HHS care, and outcome stability fell and only partially recovered. The dominant late-2025 risk is not overcrowding but **stagnation**: a smaller population moving through the system far more slowly. The process-efficiency framework, KPIs and dashboard developed here make this visible, give stakeholders concrete thresholds to monitor, and point to specific data and workflow improvements that could speed reunification."),
  H1("References"),
  P("U.S. Department of Health and Human Services. Office of Refugee Resettlement, Unaccompanied Children Program. https://www.acf.hhs.gov/orr", { alignment: AlignmentType.LEFT }),
  P("U.S. Department of Health and Human Services. https://www.hhs.gov/", { alignment: AlignmentType.LEFT }),
  P("William Wilberforce Trafficking Victims Protection Reauthorization Act of 2008, Pub. L. No. 110-457 (provisions on the transfer of unaccompanied children to HHS custody).", { alignment: AlignmentType.LEFT }),
  P("Little, J. D. C. (1961). A proof for the queuing formula: L = λW. Operations Research, 9(3), 383–387.", { alignment: AlignmentType.LEFT }),
  P("Project dataset: Dataset.csv (daily UAC program counts, 12 Jan 2023 – 21 Dec 2025), supplied with the project brief.", { alignment: AlignmentType.LEFT }),
);

const paperDoc = new Document({
  creator: AUTHOR, title: "Care Transition Efficiency & Placement Outcome Analytics", styles, numbering,
  sections: [{ properties: pageProps, footers: { default: footer("Care Transition Efficiency & Placement Outcome Analytics · Research Paper") }, children: paper }],
});

// ====================================================================== EXECUTIVE SUMMARY
const BX = (text) => new Paragraph({ numbering: { reference: "bul", level: 0 }, children: rich(text), spacing: { after: 50, line: 262, lineRule: LineRuleType.AUTO } });
const NX = (text) => new Paragraph({ numbering: { reference: "num", level: 0 }, children: rich(text), spacing: { after: 50, line: 262, lineRule: LineRuleType.AUTO } });
const ex = [];
const kpiCard = (label, value, sub, w) => new TableCell({
  width: { size: w, type: WidthType.DXA },
  borders: { top: { style: BorderStyle.SINGLE, size: 18, color: TEAL }, bottom: border, left: border, right: border },
  shading: { fill: LIGHT, type: ShadingType.CLEAR, color: "auto" }, margins: { top: 90, bottom: 90, left: 110, right: 110 },
  children: [
    new Paragraph({ spacing: { after: 20 }, children: [run(label, { size: 16, color: GREY, bold: true })] }),
    new Paragraph({ spacing: { after: 20 }, children: [run(value, { size: 28, bold: true, color: NAVY })] }),
    new Paragraph({ children: [run(sub, { size: 16, color: GREY })] }),
  ],
});
const cw5 = [1928, 1928, 1928, 1927, 1927];
ex.push(
  new Paragraph({ spacing: { after: 60 }, children: [run("EXECUTIVE SUMMARY", { size: 20, bold: true, color: TEAL, characterSpacing: 60 })] }),
  new Paragraph({ spacing: { after: 80, line: 250, lineRule: LineRuleType.AUTO }, children: [run("Care Transition Efficiency & Placement Outcome Analytics", { size: 40, bold: true, color: NAVY })] }),
  new Paragraph({ spacing: { after: 200 }, border: { bottom: { style: BorderStyle.SINGLE, size: 8, color: TEAL, space: 6 } }, children: [run(`For government stakeholders · UAC care pipeline, ${fmtDate(S.quality.start)} – ${fmtDate(S.quality.end)} · Prepared by ${AUTHOR}`, { size: 20, color: GREY })] }),
  new Paragraph({ spacing: { after: 100 }, children: [run("The bottom line", { bold: true, size: 26, color: NAVY })] }),
  P(`Head-counts show how many children are in care, not how well the pipeline moves them. Daily flows between CBP custody, HHS care and sponsor placement show that **the system ran steadily through 2023–24 but, since early 2025, has been moving far more slowly**. The main risk in late 2025 is not overcrowding but **stagnation**: about 2,300 children in HHS care with only about 10 discharges a day, and implied time in CBP custody above the 72-hour transfer benchmark.`),
  new Table({ width: { size: CW, type: WidthType.DXA }, columnWidths: cw5, rows: [new TableRow({ children: [
    kpiCard("TRANSFER EFFICIENCY", pct(K[2024].transfer_eff, 0) + " → " + pct(KQ["2025Q4"].transfer_eff, 0), "2024 avg → Q4 2025", cw5[0]),
    kpiCard("DISCHARGE EFF. / DAY", pct(K[2024].discharge_eff, 1) + " → " + pct(KQ["2025Q4"].discharge_eff, 1), "2024 → Q4 2025", cw5[1]),
    kpiCard("DAYS IN CBP (IMPLIED)", "1.3 → " + KQ["2025Q4"].implied_cbp_days.toFixed(1), "pre-2025 → Q4 2025", cw5[2]),
    kpiCard("DAYS IN HHS (IMPLIED)", "≈30 → " + Math.round(KQ["2025Q4"].implied_hhs_days), "2023 → Q4 2025", cw5[3]),
    kpiCard("OUTCOME STABILITY", "77 → " + Math.round(K[2025].stability), "2023–24 → 2025 (of 100)", cw5[4]),
  ] })] }),
  gap(80),
  new Paragraph({ spacing: { after: 100 }, children: [run("What we found", { bold: true, size: 26, color: NAVY })] }),
  BX("**Transfers (CBP → HHS) slowed after a steady two years.** About three of four children in CBP custody were transferred per reporting day in 2023–24; by Q4 2025, fewer than one in three. Implied CBP dwell time rose from about 1.3 to over 3 days in H2 2025."),
  BX("**Placements (HHS → sponsors) deteriorated.** Daily discharge effectiveness fell from 3.3% (2023) to 2.9% (2024) to 1.1% (2025). Four stagnation periods of 3–8 weeks (about 2,000–2,500 children, 10–17 discharges a day) were detected."),
  BX("**Discharges kept pace with inflows overall (1.85×), but not everywhere.** HHS discharged fewer children than it received in Q2–Q4 2024 and Q4 2025, so its caseload grew in those quarters."),
  BX("**Outcomes are less stable.** Stability held near 77/100 for two years, fell to about 6 in April 2025 and still sits near the 60-point alert line. Eight sudden week-on-week drops were flagged."),
  BX("**A weekly pattern exists.** Tuesday discharges run about one-third below Thursday and Sunday; transfers show no weekend slow-down."),
  gap(40),
  new Paragraph({ spacing: { after: 100 }, children: [run("What we recommend", { bold: true, size: 26, color: NAVY })] }),
  NX("**Adopt process KPIs** (transfer efficiency, discharge effectiveness, stage throughput, dwell times) and review them monthly alongside head-counts."),
  NX("**Audit CBP transfer timing for H2 2025** against the 72-hour benchmark using case-level timestamps."),
  NX("**Review long-stay HHS cases** to unblock sponsor vetting, legal and case-management steps that are holding discharges at about 10 a day."),
  NX("**Check weekday scheduling**, since smoothing the Tuesday dip could lift discharges without adding capacity, once confirmed with complete weekend data."),
  NX("**Improve the data:** report all seven days, reconcile flows with stock counts, and add case-level dates."),
  gap(40),
  callout("Caveats leaders should know", "The source covers about two-thirds of calendar days (Fri/Sat largely absent) and flows do not fully reconcile with stock counts in 2023–24, so ratios are indicators of change, not exact values. It shows **when and where** efficiency changed, not **why**.", RED),
);
const exDoc = new Document({
  creator: AUTHOR, title: "Executive Summary – Care Transition Efficiency", styles, numbering,
  sections: [{ properties: { page: { size: PAGE, margin: { top: 560, bottom: 600, left: MARGIN, right: MARGIN } } },
    footers: { default: footer("Executive Summary · Care Transition Efficiency & Placement Outcome Analytics") }, children: ex }],
});

(async () => {
  fs.writeFileSync(path.join(ROOT, "reports", "Research_Paper.docx"), await Packer.toBuffer(paperDoc));
  fs.writeFileSync(path.join(ROOT, "reports", "Executive_Summary.docx"), await Packer.toBuffer(exDoc));
  console.log("written");
})();
