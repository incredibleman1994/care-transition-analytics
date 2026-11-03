"""
Care Transition Efficiency & Placement Outcome Analytics - Streamlit dashboard

Run locally:   streamlit run app.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

sys.path.insert(0, str(Path(__file__).parent / "src"))
from pipeline_metrics import (  # noqa: E402
    add_metrics,
    data_quality_report,
    imbalance_periods,
    kpi_summary,
    load_data,
    monthly_summary,
    stagnation_periods,
    sudden_drops,
)

DATA_PATH = Path(__file__).parent / "data" / "Dataset.csv"

st.set_page_config(page_title="Care Transition Analytics", page_icon="🧭", layout="wide")

# ---------------------------------------------------------------- palette
C_CBP, C_HHS, C_OUT, C_WARN, C_BAD, C_GOOD = "#E07A5F", "#3D5A80", "#2A9D8F", "#F2A541", "#C0392B", "#2A9D8F"
PLOT = dict(template="plotly_white", margin=dict(l=10, r=10, t=50, b=10), legend=dict(orientation="h", y=-0.15))


# ---------------------------------------------------------------- data
@st.cache_data(show_spinner=False)
def get_raw(file_bytes: bytes | None):
    if file_bytes:
        import io

        return load_data(io.BytesIO(file_bytes))
    return load_data(DATA_PATH)


def pct(x, nd=1):
    return "n/a" if x is None or x != x else f"{100 * x:.{nd}f}%"


# ---------------------------------------------------------------- sidebar
st.sidebar.title("🧭 Controls")
upload = st.sidebar.file_uploader("Optional: upload your own CSV (same columns)", type="csv")
try:
    raw = get_raw(upload.getvalue() if upload else None)
except Exception as e:  # noqa: BLE001
    st.error(f"Could not read the dataset: {e}")
    st.stop()

dmin, dmax = raw["date"].min().date(), raw["date"].max().date()
rng = st.sidebar.date_input("Date range", value=(dmin, dmax), min_value=dmin, max_value=dmax)
if isinstance(rng, tuple) and len(rng) == 2:
    start, end = rng
else:
    start, end = dmin, dmax

window = st.sidebar.slider("Rolling window (reporting days)", 3, 28, 7, help="Smooths day-to-day noise in ratio metrics.")

st.sidebar.subheader("Ratio metrics to display")
show_ter = st.sidebar.toggle("Transfer Efficiency Ratio", True)
show_dei = st.sidebar.toggle("Discharge Effectiveness Index", True)
show_thr = st.sidebar.toggle("Pipeline Throughput", True)
show_daily = st.sidebar.toggle("Show raw daily values (faint)", False)

st.sidebar.subheader("⚠️ Alert thresholds")
th_ter = st.sidebar.slider("Min Transfer Efficiency (daily %)", 0, 100, 50, help="Alert if rolling TER falls below this.") / 100
th_dei = st.sidebar.slider("Min Discharge Effectiveness (daily %)", 0.0, 5.0, 1.5, 0.1,
                           help="Share of HHS population discharged per reporting day.") / 100
th_thr = st.sidebar.slider("Min Pipeline Throughput (×)", 0.0, 3.0, 1.0, 0.05,
                           help="Exits ÷ entries. Below 1.0 means the system is filling up.")
th_stab = st.sidebar.slider("Min Outcome Stability Score", 0, 100, 60)
drop_pct = st.sidebar.slider("Sudden-drop trigger (% fall in discharges week-on-week)", 10, 70, 30)

# ---------------------------------------------------------------- compute
full = add_metrics(raw, window=window)
mask = (full["date"].dt.date >= start) & (full["date"].dt.date <= end)
d = full.loc[mask].reset_index(drop=True)
if len(d) < 5:
    st.warning("Please select a wider date range (at least 5 reporting days).")
    st.stop()

k = kpi_summary(d)
# previous period of equal length (for deltas)
span = (pd.Timestamp(end) - pd.Timestamp(start)).days + 1
prev = full[(full["date"] >= pd.Timestamp(start) - pd.Timedelta(days=span)) & (full["date"] < pd.Timestamp(start))]
kp = kpi_summary(prev) if len(prev) >= 5 else {}


def delta(key, scale=100, suffix=" pp"):
    if not kp or kp.get(key) is None or kp[key] != kp[key]:
        return None
    return f"{scale * (k[key] - kp[key]):+.1f}{suffix}"


# ---------------------------------------------------------------- header
st.title("Care Transition Efficiency & Placement Outcome Analytics")
st.caption(
    f"UAC care pipeline: CBP custody → HHS care → sponsor placement · "
    f"{start:%d %b %Y} – {end:%d %b %Y} · {len(d):,} reporting days"
)

tabs = st.tabs(["📊 Overview", "🔀 Pipeline Flow", "⚙️ Efficiency Panels", "🚧 Bottlenecks", "📈 Outcome Trends", "ℹ️ Data & Method"])

# ================================================================ OVERVIEW
with tabs[0]:
    c = st.columns(5)
    c[0].metric("Transfer Efficiency", pct(k["transfer_eff"]), delta("transfer_eff"),
                help="Transfers ÷ CBP custody (average per reporting day).")
    c[1].metric("Discharge Effectiveness", pct(k["discharge_eff"], 2), delta("discharge_eff", suffix=" pp"),
                help="Discharges ÷ HHS care (average per reporting day).")
    c[2].metric("Pipeline Throughput", f"{k['throughput']:.2f}×",
                None if not kp else f"{k['throughput'] - kp['throughput']:+.2f}×",
                help="Total exits (discharges) ÷ total entries (apprehensions).")
    c[3].metric("Backlog Accumulation", f"{100 * k['backlog_rate']:+.2f}%/day",
                None if not kp else f"{100 * (k['backlog_rate'] - kp['backlog_rate']):+.2f} pp", delta_color="inverse",
                help="(Entries − exits) per day as % of CBP+HHS load. Positive = queue building.")
    c[4].metric("Outcome Stability", f"{k['stability']:.0f}/100",
                None if not kp else f"{k['stability'] - kp['stability']:+.0f}",
                help="100 × (1 − coefficient of variation of discharges, rolling 28 reporting days).")

    st.markdown("##### 🚦 Alert status (latest rolling values in selected range)")
    last = d.iloc[-1]
    alerts = [
        ("Transfer Efficiency", last["transfer_eff_roll"], th_ter, pct(last["transfer_eff_roll"]), pct(th_ter, 0), "<"),
        ("Discharge Effectiveness", last["discharge_eff_roll"], th_dei, pct(last["discharge_eff_roll"], 2), pct(th_dei, 1), "<"),
        ("Pipeline Throughput", last["throughput_roll"], th_thr, f"{last['throughput_roll']:.2f}×", f"{th_thr:.2f}×", "<"),
        ("Outcome Stability", last["stability_score"], th_stab, f"{last['stability_score']:.0f}", f"{th_stab}", "<"),
    ]
    ac = st.columns(4)
    for col, (name, val, thr, vs, ts, _) in zip(ac, alerts):
        breach = (val != val) or val < thr
        col.markdown(
            f"""<div style="border-left:6px solid {C_BAD if breach else C_GOOD};padding:8px 12px;background:#f7f7f9;border-radius:4px">
            <b>{'🔴' if breach else '🟢'} {name}</b><br>
            <span style="font-size:1.3rem">{vs}</span><br>
            <span style="color:#666;font-size:.8rem">threshold {ts} · {'BREACH' if breach else 'OK'}</span></div>""",
            unsafe_allow_html=True,
        )

    st.markdown("&nbsp;")
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Scatter(x=d["date"], y=d["hhs_load"], name="Children in HHS care", line=dict(color=C_HHS, width=2.5)), secondary_y=False)
    fig.add_trace(go.Scatter(x=d["date"], y=d["cbp_load"], name="Children in CBP custody", line=dict(color=C_CBP, width=2)), secondary_y=True)
    fig.update_yaxes(title_text="HHS care load", secondary_y=False)
    fig.update_yaxes(title_text="CBP custody load", secondary_y=True)
    fig.update_layout(title="Care load by stage", **PLOT)
    st.plotly_chart(fig, width="stretch")

    n_breach = sum(1 for a in alerts if (a[1] != a[1]) or a[1] < a[2])
    st.info(
        f"**Reading this range:** on average {pct(k['transfer_eff'], 0)} of children in CBP custody were transferred each reporting day, "
        f"and {pct(k['discharge_eff'], 2)} of the HHS population was placed with sponsors. "
        f"Implied average time in CBP custody is ≈ **{k['implied_cbp_days']:.1f} days** and in HHS care ≈ **{k['implied_hhs_days']:.0f} days** (Little's-law estimates). "
        f"{n_breach} of 4 alert thresholds are currently breached."
    )

# ================================================================ PIPELINE FLOW
with tabs[1]:
    st.subheader("Care pipeline flow")
    tot_in, tot_tr, tot_out = k["total_intake"], k["total_transfers"], k["total_discharges"]
    sankey = go.Figure(go.Sankey(
        arrangement="snap",
        node=dict(
            label=["Apprehended into CBP", "CBP custody", "Transferred to HHS", "HHS care", "Discharged to sponsors"],
            color=[C_CBP, C_CBP, C_HHS, C_HHS, C_OUT], pad=25, thickness=22,
        ),
        link=dict(
            source=[0, 1, 2, 3], target=[1, 2, 3, 4],
            value=[tot_in, tot_tr, tot_tr, tot_out],
            color=["rgba(224,122,95,.35)", "rgba(224,122,95,.35)", "rgba(61,90,128,.35)", "rgba(42,157,143,.35)"],
        ),
    ))
    sankey.update_layout(title=f"Cumulative movements in range (intake {tot_in:,} → transfers {tot_tr:,} → discharges {tot_out:,})",
                         height=380, margin=dict(l=10, r=10, t=50, b=10))
    st.plotly_chart(sankey, width="stretch")

    s1 = tot_tr / tot_in if tot_in else np.nan
    s2 = tot_out / tot_tr if tot_tr else np.nan
    a, b, c3 = st.columns(3)
    a.metric("Stage 1 conversion (transfers ÷ intake)", f"{s1:.2f}×")
    b.metric("Stage 2 conversion (discharges ÷ transfers)", f"{s2:.2f}×")
    c3.metric("End-to-end (discharges ÷ intake)", f"{k['throughput']:.2f}×")
    st.caption("Values above 1.0× mean a stage is releasing more children than arrived in the period (it is draining its stock). "
               "Values persistently below 1.0× mean the stage is accumulating children.")

    agg = st.radio("Time aggregation", ["Weekly", "Monthly"], horizontal=True)
    rule = "W" if agg == "Weekly" else "MS"
    f = d.set_index("date")[["intake", "transfers", "discharges"]].resample(rule).sum()
    fig = go.Figure()
    fig.add_bar(x=f.index, y=f["intake"], name="Apprehended (CBP intake)", marker_color=C_CBP)
    fig.add_bar(x=f.index, y=f["transfers"], name="Transferred to HHS", marker_color=C_HHS)
    fig.add_bar(x=f.index, y=f["discharges"], name="Discharged to sponsors", marker_color=C_OUT)
    fig.update_layout(barmode="group", title=f"{agg} stage movements", **PLOT)
    st.plotly_chart(fig, width="stretch")

# ================================================================ EFFICIENCY
with tabs[2]:
    st.subheader("Transfer & discharge efficiency")
    if not (show_ter or show_dei or show_thr):
        st.info("Turn on at least one ratio metric in the sidebar.")

    if show_ter:
        fig = go.Figure()
        if show_daily:
            fig.add_scatter(x=d["date"], y=d["transfer_eff"], name="Daily", line=dict(color="rgba(224,122,95,.25)", width=1))
        fig.add_scatter(x=d["date"], y=d["transfer_eff_roll"], name=f"{window}-day rolling", line=dict(color=C_CBP, width=2.5))
        fig.add_hline(y=th_ter, line_dash="dash", line_color=C_BAD, annotation_text="alert threshold")
        low = d[d["transfer_eff_roll"] < th_ter]
        fig.add_scatter(x=low["date"], y=low["transfer_eff_roll"], mode="markers", name="Below threshold", marker=dict(color=C_BAD, size=5))
        fig.update_layout(title="Transfer Efficiency Ratio (transfers ÷ CBP custody)", yaxis_tickformat=".0%", **PLOT)
        st.plotly_chart(fig, width="stretch")

    if show_dei:
        fig = go.Figure()
        if show_daily:
            fig.add_scatter(x=d["date"], y=d["discharge_eff"], name="Daily", line=dict(color="rgba(42,157,143,.25)", width=1))
        fig.add_scatter(x=d["date"], y=d["discharge_eff_roll"], name=f"{window}-day rolling", line=dict(color=C_OUT, width=2.5))
        fig.add_hline(y=th_dei, line_dash="dash", line_color=C_BAD, annotation_text="alert threshold")
        low = d[d["discharge_eff_roll"] < th_dei]
        fig.add_scatter(x=low["date"], y=low["discharge_eff_roll"], mode="markers", name="Below threshold", marker=dict(color=C_BAD, size=5))
        fig.update_layout(title="Discharge Effectiveness Index (discharges ÷ HHS care)", yaxis_tickformat=".1%", **PLOT)
        st.plotly_chart(fig, width="stretch")

    if show_thr:
        fig = go.Figure()
        if show_daily:
            fig.add_scatter(x=d["date"], y=d["throughput"].clip(upper=6), name="Daily (capped at 6×)", line=dict(color="rgba(61,90,128,.25)", width=1))
        fig.add_scatter(x=d["date"], y=d["throughput_roll"].clip(upper=6), name=f"{window}-day rolling", line=dict(color=C_HHS, width=2.5))
        fig.add_hline(y=1.0, line_dash="dot", line_color="#888", annotation_text="balance (1.0×)")
        fig.add_hline(y=th_thr, line_dash="dash", line_color=C_BAD, annotation_text="alert threshold")
        fig.update_layout(title="Pipeline Throughput (exits ÷ entries, capped at 6× for readability)", **PLOT)
        st.plotly_chart(fig, width="stretch")

    st.markdown("##### Weekday vs Sunday transition speed")
    w = d.groupby("weekday").agg(
        reporting_days=("date", "size"), transfers=("transfers", "mean"), discharges=("discharges", "mean"),
        transfer_eff=("transfer_eff", "mean"), discharge_eff=("discharge_eff", "mean"),
    ).reindex(["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Sunday"]).dropna()
    fig = make_subplots(rows=1, cols=2, subplot_titles=("Avg transfers per reporting day", "Avg discharges per reporting day"))
    fig.add_bar(x=w.index, y=w["transfers"], marker_color=C_HHS, name="Transfers", row=1, col=1)
    fig.add_bar(x=w.index, y=w["discharges"], marker_color=C_OUT, name="Discharges", row=1, col=2)
    fig.update_layout(showlegend=False, template="plotly_white", margin=dict(l=10, r=10, t=50, b=10))
    st.plotly_chart(fig, width="stretch")
    st.caption("⚠️ The source reports Mon–Thu and Sunday only (Friday has just 2 rows, Saturday none). A Sunday row follows a 3-day gap, so it likely "
               "reflects weekend activity. Treat the weekday/weekend comparison as indicative, not a measure of staffing.")
    st.dataframe(
        w.assign(transfer_eff=(100 * w["transfer_eff"]).round(1), discharge_eff=(100 * w["discharge_eff"]).round(2)).round(1)
         .rename(columns={"transfer_eff": "transfer_eff_%", "discharge_eff": "discharge_eff_%"}),
        width="stretch",
    )

# ================================================================ BOTTLENECKS
with tabs[3]:
    st.subheader("Bottleneck & backlog detection")
    imb = imbalance_periods(d, window=window)
    stag = stagnation_periods(d, max_dei=th_dei)

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.08,
                        subplot_titles=("Net flow into the system: entries − exits (7-day mean)", "Observed change in total care load per day (stock-based)"))
    net = d["sys_net"].rolling(window, min_periods=3).mean()
    fig.add_bar(x=d["date"], y=net.clip(lower=0), marker_color=C_BAD, name="Backlog building", row=1, col=1)
    fig.add_bar(x=d["date"], y=net.clip(upper=0), marker_color=C_GOOD, name="Backlog draining", row=1, col=1)
    ch = d["total_load_change_per_day"].rolling(window, min_periods=3).mean()
    fig.add_bar(x=d["date"], y=ch.clip(lower=0), marker_color=C_BAD, showlegend=False, row=2, col=1)
    fig.add_bar(x=d["date"], y=ch.clip(upper=0), marker_color=C_GOOD, showlegend=False, row=2, col=1)
    for _, r in stag.iterrows():
        fig.add_vrect(x0=r["start"], x1=r["end"], fillcolor=C_WARN, opacity=0.25, line_width=0)
    fig.update_layout(barmode="relative", height=520, title="Where backlogs accumulate (amber bands = stagnation periods)", **PLOT)
    st.plotly_chart(fig, width="stretch")
    st.caption("Top panel uses reported flows; bottom panel uses reported stock levels. In 2023–24 the two do not reconcile well "
               "(see Data & Method), so both are shown. Agreement between them is stronger evidence of a real backlog.")

    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_scatter(x=d["date"], y=d["implied_hhs_days"], name="Implied days in HHS care", line=dict(color=C_HHS, width=2.5))
    fig.add_scatter(x=d["date"], y=d["hhs_load"], name="HHS care load", line=dict(color="#aaa", width=1.5, dash="dot"), secondary_y=True)
    fig.update_yaxes(title_text="Days", secondary_y=False)
    fig.update_yaxes(title_text="Children", secondary_y=True)
    fig.update_layout(title="Delay severity: implied time in HHS care (HHS load ÷ 28-day mean discharges)", **PLOT)
    st.plotly_chart(fig, width="stretch")

    fig = go.Figure()
    fig.add_scatter(x=d["date"], y=d["implied_cbp_days"].clip(upper=10), name="Implied days in CBP custody", line=dict(color=C_CBP, width=2.5))
    fig.add_hline(y=3, line_dash="dash", line_color=C_BAD, annotation_text="72-hour transfer benchmark (3 days)")
    fig.update_layout(title="Delay severity: implied time in CBP custody (CBP load ÷ 14-day mean transfers, capped at 10 days)",
                      yaxis_title="Days", **PLOT)
    st.plotly_chart(fig, width="stretch")
    st.caption("Little's-law approximation (stock ÷ outflow rate); indicative only. The statutory benchmark is that unaccompanied children "
               "should generally be transferred to HHS within 72 hours.")

    a, b = st.columns(2)
    with a:
        st.markdown("**Sustained imbalance periods** (entries > exits for ≥ 10 reporting days)")
        if imb.empty:
            st.success("None in this range.")
        else:
            st.dataframe(imb.assign(start=imb.start.dt.date, end=imb.end.dt.date), hide_index=True, width="stretch")
    with b:
        st.markdown("**Stagnation periods** (flat HHS load + discharge effectiveness below threshold, ≥ 14 reporting days)")
        if stag.empty:
            st.success("None in this range.")
        else:
            st.dataframe(stag.assign(start=stag.start.dt.date, end=stag.end.dt.date), hide_index=True, width="stretch")

# ================================================================ OUTCOMES
with tabs[4]:
    st.subheader("Placement outcome trends")
    m = monthly_summary(d)
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_bar(x=m["month"], y=m["avg_daily_discharges"], name="Avg discharges / reporting day", marker_color=C_OUT)
    fig.add_scatter(x=m["month"], y=100 * m["discharge_eff"], name="Discharge effectiveness (%)", line=dict(color=C_HHS, width=2.5), secondary_y=True)
    fig.update_yaxes(title_text="Discharges per day", secondary_y=False)
    fig.update_yaxes(title_text="% of HHS population / day", secondary_y=True)
    fig.update_layout(title="Month-over-month placement performance", **PLOT)
    st.plotly_chart(fig, width="stretch")

    a, b = st.columns(2)
    with a:
        fig = go.Figure()
        fig.add_scatter(x=d["date"], y=d["stability_score"], line=dict(color=C_HHS, width=2.5), name="Stability")
        fig.add_hline(y=th_stab, line_dash="dash", line_color=C_BAD, annotation_text="alert threshold")
        fig.update_layout(title="Outcome Stability Score (rolling 28 reporting days)", yaxis_range=[0, 100], **PLOT)
        st.plotly_chart(fig, width="stretch")
    with b:
        mm = m.dropna(subset=["discharge_mom_pct"])
        fig = go.Figure(go.Bar(x=mm["month"], y=mm["discharge_mom_pct"],
                               marker_color=[C_GOOD if v >= 0 else C_BAD for v in mm["discharge_mom_pct"]]))
        fig.update_layout(title="Month-over-month change in daily discharges (%)", **PLOT)
        st.plotly_chart(fig, width="stretch")

    st.markdown("**Sudden drops in discharge performance**")
    sd = sudden_drops(d, drop_pct=drop_pct / 100)
    if sd.empty:
        st.success(f"No week-on-week drops of {drop_pct}% or more in this range.")
    else:
        st.dataframe(
            sd.assign(date=sd.date.dt.date).rename(columns={"prev_avg": "previous 7-day avg", "current_avg": "latest 7-day avg", "change_pct": "change %"}),
            hide_index=True, width="stretch",
        )

    st.markdown("**Monthly scorecard**")
    show = m.assign(
        transfer_eff=(100 * m["transfer_eff"]).round(1), discharge_eff=(100 * m["discharge_eff"]).round(2),
        month=m["month"].dt.strftime("%b %Y"),
    )[["month", "intake", "transfers", "discharges", "avg_hhs_load", "transfer_eff", "discharge_eff", "throughput", "stability"]].round(1)
    st.dataframe(show, hide_index=True, width="stretch")
    st.download_button("⬇️ Download monthly scorecard (CSV)", show.to_csv(index=False), "monthly_scorecard.csv", "text/csv")

# ================================================================ DATA & METHOD
with tabs[5]:
    q = data_quality_report(raw)
    st.subheader("Data quality")
    a, b, c = st.columns(3)
    a.metric("Reporting days", f"{q['reported_days']:,}", f"{q['coverage_pct']}% of calendar days")
    b.metric("Unreported calendar days", f"{q['unreported_days']:,}")
    c.metric("Longest reporting gap", f"{q['longest_gap_days']} days")
    st.markdown(
        """
**Known data characteristics (read before drawing conclusions)**
- The raw CSV contains ~450 blank rows; these are dropped. 720 valid reporting days remain (12 Jan 2023 – 21 Dec 2025).
- Reporting follows Mon–Thu + Sunday; Fridays (2 rows) and Saturdays (0 rows) are essentially absent.
- **Flows and stocks do not fully reconcile in 2023–24** (e.g. daily change in HHS load vs transfers − discharges correlate 0.46 in 2023, 0.80 in 2024, 0.98 in 2025). Intake is also systematically lower than transfers, suggesting *apprehensions* is a narrower definition than CBP *entries*. Ratios are therefore reported as **indicators**, and stock-based and flow-based views are shown side by side.
- Late 2025 volumes are very small (≈ 10 discharges/day), so ratios there are noisy; use a wider rolling window.
        """
    )
    st.subheader("Metric definitions")
    st.markdown(
        """
| Metric | Formula |
|---|---|
| **Transfer Efficiency Ratio** | Transfers ÷ CBP custody |
| **Discharge Effectiveness Index** | Discharges ÷ HHS care |
| **Pipeline Throughput** | Total exits (discharges) ÷ total entries (apprehensions) |
| **Backlog Accumulation Rate** | (Entries − exits) per day ÷ (CBP + HHS load); positive = queue building |
| **Outcome Stability Score** | 100 × (1 − coefficient of variation of daily discharges over rolling 28 reporting days) |
| **Implied time in HHS** | HHS load ÷ mean daily discharges (Little's law approximation) |
        """
    )
    with st.expander("Preview cleaned data"):
        cols = ["date", "intake", "cbp_load", "transfers", "hhs_load", "discharges", "transfer_eff", "discharge_eff", "throughput"]
        st.dataframe(d[cols].round({c: 3 for c in cols if c != "date"}), width="stretch", hide_index=True)
        st.download_button("⬇️ Download filtered data (CSV)", d[cols].to_csv(index=False), "filtered_pipeline_data.csv", "text/csv")
