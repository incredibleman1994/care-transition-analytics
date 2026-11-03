"""Generate the static figures and key statistics used in the research paper.

Usage:  python src/make_figures.py
Outputs: figures/*.png  and  reports/key_stats.json
"""
import json
import sys
import warnings
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.model_selection import TimeSeriesSplit

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from pipeline_metrics import (  # noqa: E402
    add_metrics, data_quality_report, imbalance_periods, kpi_summary, load_data,
    monthly_summary, stagnation_periods, sudden_drops,
)

FIG = ROOT / "figures"
FIG.mkdir(exist_ok=True)
(ROOT / "reports").mkdir(exist_ok=True)

CBP, HHS, OUT, WARN, BAD, GOOD, GREY = "#E07A5F", "#3D5A80", "#2A9D8F", "#F2A541", "#C0392B", "#2A9D8F", "#8D99AE"
plt.rcParams.update({
    "figure.dpi": 150, "savefig.dpi": 200, "font.size": 9.5, "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.alpha": 0.25, "axes.titleweight": "bold", "axes.titlesize": 11,
})
fmt = mdates.DateFormatter("%b %y")

df = load_data(ROOT / "data" / "Dataset.csv")
d = add_metrics(df, window=7)
d["year"] = d["date"].dt.year
S = {}  # stats store

# ------------------------------------------------------------------ data quality
S["quality"] = {k: (str(v) if not isinstance(v, (int, float, dict)) else v) for k, v in data_quality_report(df).items()}
raw_rows = len(pd.read_csv(ROOT / "data" / "Dataset.csv"))
S["quality"]["raw_rows"] = raw_rows
S["quality"]["blank_rows_dropped"] = raw_rows - len(df)

c = d[d["gap_days"] == 1].copy()
c["dhhs"] = d["hhs_load"].diff()
c["dcbp"] = d["cbp_load"].diff()
recon = {}
for y, g in c.groupby("year"):
    recon[int(y)] = {"hhs_corr": round(g["dhhs"].corr(g["hhs_net"]), 2), "cbp_corr": round(g["dcbp"].corr(g["cbp_net"]), 2), "n": int(len(g))}
S["reconciliation"] = recon
S["intake_vs_transfer_total"] = {"intake": int(d.intake.sum()), "transfers": int(d.transfers.sum()), "discharges": int(d.discharges.sum())}

# ------------------------------------------------------------------ fig 1 load
fig, ax = plt.subplots(2, 1, figsize=(9, 5.2), sharex=True)
ax[0].plot(d.date, d.hhs_load, color=HHS, lw=1.8)
ax[0].set_title("Children in HHS care"); ax[0].set_ylabel("Children")
ax[1].plot(d.date, d.cbp_load, color=CBP, lw=1.3)
ax[1].set_title("Children in CBP custody"); ax[1].set_ylabel("Children")
ax[1].xaxis.set_major_formatter(fmt)
fig.tight_layout(); fig.savefig(FIG / "fig01_care_load.png"); plt.close(fig)

# ------------------------------------------------------------------ fig 2 monthly flows
m = monthly_summary(d)
fig, ax = plt.subplots(figsize=(9, 3.8))
w = 7
x = mdates.date2num(m.month)
ax.bar(x - w, m.intake / m.reported_days, w, color=CBP, label="Apprehended (intake)")
ax.bar(x, m.transfers / m.reported_days, w, color=HHS, label="Transferred to HHS")
ax.bar(x + w, m.avg_daily_discharges, w, color=OUT, label="Discharged to sponsors")
ax.xaxis_date(); ax.xaxis.set_major_formatter(fmt)
ax.set_ylabel("Children per reporting day"); ax.set_title("Average daily stage movements by month")
ax.set_ylim(0, ax.get_ylim()[1] * 1.18)
ax.legend(frameon=False, ncol=3, loc="upper right")
fig.tight_layout(); fig.savefig(FIG / "fig02_monthly_flows.png"); plt.close(fig)

# ------------------------------------------------------------------ fig 3 efficiency
fig, ax = plt.subplots(2, 1, figsize=(9, 5.4), sharex=True)
ax[0].plot(d.date, d.transfer_eff, color=CBP, alpha=0.18, lw=0.8)
ax[0].plot(d.date, d.transfer_eff_roll, color=CBP, lw=2)
ax[0].set_ylim(0, 1.5); ax[0].set_title("Transfer Efficiency Ratio (transfers ÷ CBP custody), 7-day rolling"); ax[0].yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0%}"))
ax[1].plot(d.date, d.discharge_eff, color=OUT, alpha=0.18, lw=0.8)
ax[1].plot(d.date, d.discharge_eff_roll, color=OUT, lw=2)
ax[1].set_title("Discharge Effectiveness Index (discharges ÷ HHS care), 7-day rolling"); ax[1].yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.1%}"))
ax[1].xaxis.set_major_formatter(fmt)
fig.tight_layout(); fig.savefig(FIG / "fig03_efficiency.png"); plt.close(fig)

# ------------------------------------------------------------------ fig 4 throughput by stage (quarterly)
d["q"] = d.date.dt.to_period("Q")
q = d.groupby("q").agg(i=("intake", "sum"), t=("transfers", "sum"), o=("discharges", "sum"))
q["s1"], q["s2"], q["e2e"] = q.t / q.i, q.o / q.t, q.o / q.i
fig, ax = plt.subplots(figsize=(9, 3.6))
xs = np.arange(len(q))
ax.plot(xs, q.s1, marker="o", color=CBP, label="Stage 1: transfers ÷ intake")
ax.plot(xs, q.s2, marker="o", color=HHS, label="Stage 2: discharges ÷ transfers")
ax.plot(xs, q.e2e, marker="o", color=OUT, lw=2.4, label="End-to-end: discharges ÷ intake")
ax.axhline(1, color=GREY, ls="--", lw=1)
ax.set_xticks(xs); ax.set_xticklabels([str(p) for p in q.index], rotation=45)
ax.set_title("Quarterly pipeline throughput (1.0 = balance)"); ax.legend(frameon=False, fontsize=8)
fig.tight_layout(); fig.savefig(FIG / "fig04_throughput_stages.png"); plt.close(fig)
S["quarterly_throughput"] = {str(k): {"s1": round(v.s1, 2), "s2": round(v.s2, 2), "e2e": round(v.e2e, 2)} for k, v in q.iterrows()}

# ------------------------------------------------------------------ fig 5 backlog
stag = stagnation_periods(d)
imb = imbalance_periods(d)
fig, ax = plt.subplots(2, 1, figsize=(9, 5.4), sharex=True)
net = d.sys_net.rolling(7, min_periods=3).mean()
ax[0].fill_between(d.date, net.clip(lower=0), color=BAD, step="mid", label="building")
ax[0].fill_between(d.date, net.clip(upper=0), color=GOOD, step="mid", label="draining")
ax[0].set_title("Flow view: entries − exits (7-day mean, children/day)")
ch = d.total_load_change_per_day.rolling(7, min_periods=3).mean()
ax[1].fill_between(d.date, ch.clip(lower=0), color=BAD, step="mid")
ax[1].fill_between(d.date, ch.clip(upper=0), color=GOOD, step="mid")
ax[1].set_title("Stock view: observed change in CBP + HHS load (7-day mean, children/day)")
for _, r in stag.iterrows():
    for a in ax:
        a.axvspan(r.start, r.end, color=WARN, alpha=0.3, lw=0)
ax[0].legend(frameon=False, loc="lower left"); ax[1].xaxis.set_major_formatter(fmt)
fig.text(0.99, 0.005, "Amber bands = stagnation periods", ha="right", fontsize=8, color="#996515")
fig.tight_layout(); fig.savefig(FIG / "fig05_backlog.png"); plt.close(fig)

# ------------------------------------------------------------------ fig 6 weekday
order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Sunday"]
wk = d[d.weekday.isin(order)].groupby("weekday").agg(
    n=("date", "size"), tr=("transfers", "mean"), dis=("discharges", "mean"), ter=("transfer_eff", "mean"), dei=("discharge_eff", "mean"),
).reindex(order)
fig, ax = plt.subplots(1, 3, figsize=(10, 3.2))
for a, col, ttl, clr, f in (
    (ax[0], "tr", "Avg transfers / day", HHS, "{:.0f}"),
    (ax[1], "dis", "Avg discharges / day", OUT, "{:.0f}"),
    (ax[2], "dei", "Avg discharge effectiveness", WARN, "{:.2%}"),
):
    bars = a.bar([o[:3] for o in order], wk[col], color=clr)
    a.set_title(ttl, fontsize=10)
    if col == "dei":
        a.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.1%}"))
    for b, v in zip(bars, wk[col]):
        a.text(b.get_x() + b.get_width() / 2, b.get_height(), f.format(v), ha="center", va="bottom", fontsize=8)
fig.tight_layout(); fig.savefig(FIG / "fig06_weekday.png"); plt.close(fig)
grp = [d.loc[d.weekday == o, "discharges"].values for o in order]
kw = stats.kruskal(*grp)
sun = d.loc[d.weekday == "Sunday"]
wkd = d.loc[d.weekday.isin(["Monday", "Tuesday", "Wednesday", "Thursday"])]
mw = stats.mannwhitneyu(sun.discharges, wkd.discharges)
mw_tr = stats.mannwhitneyu(sun.transfers, wkd.transfers)
S["weekday"] = {
    "table": {k: {"n": int(v.n), "transfers": round(v.tr, 1), "discharges": round(v.dis, 1), "ter": round(v.ter, 3), "dei": round(v.dei, 4)} for k, v in wk.iterrows()},
    "kruskal_discharges_p": float(kw.pvalue),
    "sunday_vs_weekday_discharges": {"sunday": round(sun.discharges.mean(), 1), "weekday": round(wkd.discharges.mean(), 1), "mannwhitney_p": float(mw.pvalue)},
    "sunday_vs_weekday_transfers": {"sunday": round(sun.transfers.mean(), 1), "weekday": round(wkd.transfers.mean(), 1), "mannwhitney_p": float(mw_tr.pvalue)},
}

# ------------------------------------------------------------------ fig 7 stability & drops
drops = sudden_drops(d)
fig, ax = plt.subplots(2, 1, figsize=(9, 5.2), sharex=True)
ax[0].plot(d.date, d.discharges.rolling(7).mean(), color=OUT, lw=1.8)
roll7 = d.set_index("date").discharges.rolling(7).mean()
ax[0].scatter(drops.date, roll7.loc[drops.date].values, color=BAD, zorder=5, s=36, label="sudden drop (≥30% w/w)")
ax[0].set_title("Discharges per reporting day (7-day mean)"); ax[0].legend(frameon=False)
ax[1].plot(d.date, d.stability_score, color=HHS, lw=1.8); ax[1].axhline(60, color=BAD, ls="--", lw=1)
ax[1].set_ylim(0, 100); ax[1].set_title("Outcome Stability Score (rolling 28 reporting days; dashed = 60 alert)")
ax[1].xaxis.set_major_formatter(fmt)
fig.tight_layout(); fig.savefig(FIG / "fig07_stability_drops.png"); plt.close(fig)
S["sudden_drops"] = [{"date": str(r.date.date()), "prev": r.prev_avg, "now": r.current_avg, "chg": r.change_pct} for r in drops.itertuples()]
S["stagnation"] = [{"start": str(r.start.date()), "end": str(r.end.date()), "days": int(r.reported_days), "hhs": int(r.avg_hhs_load), "dis": r.avg_daily_discharges, "dei_pct": r.avg_discharge_eff_pct} for r in stag.itertuples()]
S["imbalance"] = [{"start": str(r.start.date()), "end": str(r.end.date()), "days": int(r.reported_days), "excess": int(r.excess_entries), "peak_cbp": int(r.peak_cbp_load)} for r in imb.itertuples()]

# ------------------------------------------------------------------ fig 8 dwell times
fig, ax = plt.subplots(1, 2, figsize=(10, 3.4))
ax[0].plot(d.date, d.implied_cbp_days.clip(upper=10), color=CBP, lw=1.8)
ax[0].axhline(3, color=BAD, ls="--", lw=1); ax[0].text(d.date.iloc[5], 3.15, "72-hour benchmark", color=BAD, fontsize=8)
ax[0].set_title("Implied days in CBP custody"); ax[0].xaxis.set_major_formatter(fmt)
ax[1].plot(d.date, d.implied_hhs_days.clip(upper=400), color=HHS, lw=1.8)
ax[1].set_title("Implied days in HHS care"); ax[1].xaxis.set_major_formatter(fmt)
for a in ax:
    a.tick_params(axis="x", labelrotation=45)
fig.tight_layout(); fig.savefig(FIG / "fig08_dwell_times.png"); plt.close(fig)

# ------------------------------------------------------------------ fig 9 reconciliation
fig, ax = plt.subplots(1, 3, figsize=(10, 3.3), sharex=False, sharey=False)
for a, (y, g) in zip(ax, c.groupby("year")):
    a.scatter(g.hhs_net, g.dhhs, s=9, color=HHS, alpha=0.6)
    lim = [min(g.hhs_net.min(), g.dhhs.min()), max(g.hhs_net.max(), g.dhhs.max())]
    a.plot(lim, lim, color=BAD, ls="--", lw=1)
    a.set_title(f"{y}  (r = {recon[int(y)]['hhs_corr']})", fontsize=10)
    a.set_xlabel("transfers − discharges"); a.set_ylabel("Δ HHS load")
fig.suptitle("Flow vs stock reconciliation, consecutive-day pairs (dashed = perfect agreement)", fontsize=10, fontweight="bold")
fig.tight_layout(); fig.savefig(FIG / "fig09_reconciliation.png"); plt.close(fig)

# ------------------------------------------------------------------ KPI by year & overall
S["kpi_by_year"] = {}
for y, g in d.groupby("year"):
    S["kpi_by_year"][int(y)] = {k: (round(float(v), 4) if isinstance(v, (float, np.floating)) else int(v)) for k, v in kpi_summary(g).items()}
S["kpi_overall"] = {k: (round(float(v), 4) if isinstance(v, (float, np.floating)) else int(v)) for k, v in kpi_summary(d).items()}
S["kpi_by_quarter"] = {str(k): {kk: round(float(vv), 3) for kk, vv in kpi_summary(g).items() if kk in ("transfer_eff", "discharge_eff", "throughput", "stability", "implied_cbp_days", "implied_hhs_days")} for k, g in d.groupby("q")}
mm = m.copy(); mm["month"] = mm.month.dt.strftime("%Y-%m")
S["monthly"] = mm.round(4).set_index("month").to_dict("index")

# regime comparison (Jan-2025 break)
pre, post = d[d.date < "2025-02-01"], d[d.date >= "2025-04-01"]
S["regime"] = {
    "pre_n": int(len(pre)), "post_n": int(len(post)),
    "pre_discharges_per_day": round(pre.discharges.mean(), 1), "post_discharges_per_day": round(post.discharges.mean(), 1),
    "pre_dei": round(pre.discharge_eff.mean(), 4), "post_dei": round(post.discharge_eff.mean(), 4),
    "pre_ter": round(pre.transfer_eff.mean(), 3), "post_ter": round(post.transfer_eff.mean(), 3),
    "ter_mannwhitney_p": float(stats.mannwhitneyu(pre.transfer_eff, post.transfer_eff).pvalue),
    "dei_mannwhitney_p": float(stats.mannwhitneyu(pre.discharge_eff, post.discharge_eff).pvalue),
}
S["peak"] = {"hhs_max": int(d.hhs_load.max()), "hhs_max_date": str(d.loc[d.hhs_load.idxmax(), "date"].date()),
             "cbp_max": int(d.cbp_load.max()), "cbp_max_date": str(d.loc[d.cbp_load.idxmax(), "date"].date()),
             "hhs_min": int(d.hhs_load.min()), "hhs_min_date": str(d.loc[d.hhs_load.idxmin(), "date"].date())}

# ------------------------------------------------------------------ forecasting benchmark
H = 5  # reporting days ahead (~1 week)
X = pd.DataFrame({
    "dis_l1": d.discharges, "dis_m7": d.discharges.rolling(7).mean(), "dis_m14": d.discharges.rolling(14).mean(),
    "tr_m7": d.transfers.rolling(7).mean(), "in_m7": d.intake.rolling(7).mean(), "hhs": d.hhs_load, "cbp": d.cbp_load,
    "dow": d.date.dt.dayofweek, "hhs_chg7": d.hhs_load.diff(7),
})
y = d.discharges.shift(-H)
ok = X.notna().all(axis=1) & y.notna()
X, y = X[ok].reset_index(drop=True), y[ok].reset_index(drop=True)
wape = lambda a, p: float(np.abs(a - p).sum() / max(a.sum(), 1))
res = {"naive_last": [], "naive_mean7": [], "gbm": []}
for tr, te in TimeSeriesSplit(n_splits=5).split(X):
    res["naive_last"].append(wape(y[te], X.dis_l1[te]))
    res["naive_mean7"].append(wape(y[te], X.dis_m7[te]))
    mdl = GradientBoostingRegressor(n_estimators=200, max_depth=3, learning_rate=0.05, random_state=0).fit(X.iloc[tr], y[tr])
    res["gbm"].append(wape(y[te], mdl.predict(X.iloc[te])))
S["forecast"] = {k: {"folds": [round(v, 3) for v in vs], "mean_wape": round(float(np.mean(vs)), 3)} for k, vs in res.items()}
fig, ax = plt.subplots(figsize=(6.5, 3.2))
names = ["Last value", "7-day mean", "Gradient boosting"]
vals = [S["forecast"][k]["mean_wape"] for k in ("naive_last", "naive_mean7", "gbm")]
bars = ax.bar(names, vals, color=[GREY, HHS, WARN])
for b, v in zip(bars, vals):
    ax.text(b.get_x() + b.get_width() / 2, v, f"{v:.1%}", ha="center", va="bottom")
ax.set_ylabel("WAPE (lower is better)"); ax.set_title("5-reporting-day-ahead discharge forecast, 5-fold rolling origin")
ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0%}"))
fig.tight_layout(); fig.savefig(FIG / "fig10_forecast_benchmark.png"); plt.close(fig)

with open(ROOT / "reports" / "key_stats.json", "w") as f:
    # NaN is not valid JSON -> store as null
    json.dump(json.loads(json.dumps(S, default=str).replace("NaN", "null")), f, indent=2)
print(json.dumps({k: S[k] for k in ("quality", "reconciliation", "weekday", "regime", "peak", "forecast", "sudden_drops", "stagnation", "imbalance", "kpi_by_year", "quarterly_throughput")}, indent=1, default=str))
