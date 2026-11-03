<<<<<<< HEAD
# care-transition-analytics
=======
# Care Transition Efficiency & Placement Outcome Analytics

Process-efficiency analytics for the UAC care pipeline: **CBP custody → HHS care → sponsor placement**.
Instead of only counting children in care, this project measures *how well the pipeline moves them*.

**Live dashboard:** `<paste your Streamlit URL here>`

## What's inside
| Path | Purpose |
|---|---|
| `app.py` | Streamlit dashboard (6 tabs: Overview, Pipeline Flow, Efficiency, Bottlenecks, Outcome Trends, Data & Method) |
| `src/pipeline_metrics.py` | Cleaning, KPIs, backlog / stagnation / sudden-drop detection (shared by app, notebook, paper) |
| `src/make_figures.py` | Regenerates paper figures and `reports/key_stats.json` |
| `notebooks/01_care_transition_analysis.ipynb` | Full EDA & methodology walkthrough (executed) |
| `reports/Research_Paper.docx` | Research paper (EDA, insights, recommendations) |
| `reports/Executive_Summary.docx` | One-page summary for government stakeholders |
| `data/Dataset.csv` | Source data (720 valid reporting days, 12 Jan 2023 – 21 Dec 2025) |
| `docs/` | Deployment guide, video scripts, report builder |

## KPIs
| KPI | Formula |
|---|---|
| Transfer Efficiency Ratio | transfers ÷ CBP custody |
| Discharge Effectiveness Index | discharges ÷ HHS care |
| Pipeline Throughput | exits ÷ entries (discharges ÷ intake) |
| Backlog Accumulation Rate | (entries − exits)/day ÷ (CBP + HHS load) |
| Outcome Stability Score | 100 × (1 − CV of discharges, rolling 28 reporting days) |

## Headline findings
- Transfer efficiency ≈ 76–78 % (2023–24) → ≈ 30 % by Q4 2025.
- Discharge effectiveness 3.3 %/day (2023) → 1.1 % (2025).
- Implied CBP dwell time ≈ 1.3 days → > 3 days in H2 2025; implied HHS residence ≈ 30 → 150–230 days.
- Four stagnation periods (3–8 weeks) in 2025; eight sudden discharge drops.
- Discharges vary by weekday (Tuesday weakest); transfers do not.
- Simple persistence beats gradient boosting, which fails across the early-2025 structural break.
- Data caveat: flows and stocks do not fully reconcile in 2023–24, and Fri/Sat are largely unreported.

## Run locally
```bash
pip install -r requirements.txt
streamlit run app.py
```
Reproduce analysis: `pip install matplotlib scipy scikit-learn seaborn jupyter` then `python src/make_figures.py` and open the notebook.

## Dashboard features
Date-range selection · ratio-metric toggles · rolling-window slider · visual threshold alerts · Sankey pipeline flow · bottleneck & stagnation detection · downloadable scorecards · optional CSV upload.
>>>>>>> 0ebf3ce (files added)
