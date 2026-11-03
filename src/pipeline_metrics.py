"""
Core data-cleaning and metric logic for the
Care Transition Efficiency & Placement Outcome Analytics project.

Pipeline modelled:  Apprehension -> CBP custody -> HHS care -> Sponsor placement
"""
from __future__ import annotations

import numpy as np
import pandas as pd

COLUMN_MAP = {
    "Date": "date",
    "Children apprehended and placed in CBP custody*": "intake",
    "Children in CBP custody": "cbp_load",
    "Children transferred out of CBP custody": "transfers",
    "Children in HHS Care": "hhs_load",
    "Children discharged from HHS Care": "discharges",
}
FLOW_COLS = ["intake", "transfers", "discharges"]
STOCK_COLS = ["cbp_load", "hhs_load"]


# ----------------------------------------------------------------------------
# 1. Loading & cleaning
# ----------------------------------------------------------------------------
def load_data(path_or_buffer) -> pd.DataFrame:
    """Read the raw CSV and return a tidy, chronologically sorted frame.

    Cleaning steps
    - drop fully empty trailing rows (the raw file contains ~450 blank rows)
    - strip the '*' footnote marker from headers and rename to short names
    - remove thousands separators ("2,340") from the HHS column and cast to numeric
    - parse dates, sort ascending, drop duplicate dates
    """
    raw = pd.read_csv(path_or_buffer)
    raw = raw.dropna(how="all").copy()
    raw.columns = [c.strip() for c in raw.columns]
    raw = raw.rename(columns=COLUMN_MAP)

    missing = set(COLUMN_MAP.values()) - set(raw.columns)
    if missing:
        raise ValueError(f"Dataset is missing expected columns: {sorted(missing)}")

    for c in STOCK_COLS + FLOW_COLS:
        raw[c] = pd.to_numeric(raw[c].astype(str).str.replace(",", "", regex=False), errors="coerce")

    raw["date"] = pd.to_datetime(raw["date"], errors="coerce")
    raw = raw.dropna(subset=["date"] + STOCK_COLS + FLOW_COLS)
    raw = raw.drop_duplicates("date").sort_values("date").reset_index(drop=True)
    return raw


def data_quality_report(df: pd.DataFrame) -> dict:
    """Summarise coverage and known reporting quirks."""
    full = pd.date_range(df["date"].min(), df["date"].max())
    gaps = df["date"].diff().dt.days
    return {
        "rows": int(len(df)),
        "start": df["date"].min().date(),
        "end": df["date"].max().date(),
        "calendar_days": int(len(full)),
        "reported_days": int(len(df)),
        "unreported_days": int(len(full) - len(df)),
        "coverage_pct": round(100 * len(df) / len(full), 1),
        "weekday_counts": df["date"].dt.day_name().value_counts().to_dict(),
        "longest_gap_days": int(gaps.max()),
    }


# ----------------------------------------------------------------------------
# 2. Derived metrics
# ----------------------------------------------------------------------------
def add_metrics(df: pd.DataFrame, window: int = 7) -> pd.DataFrame:
    """Add daily and rolling efficiency metrics.

    Daily ratios (as defined in the project brief)
      transfer_eff   = transfers  / CBP custody
      discharge_eff  = discharges / HHS care
      throughput     = total exits / total entries  (discharges / intake)

    Rolling versions use sums over `window` reporting days, which is far more
    stable than a single noisy day (ratio of sums, not mean of ratios).

    Backlog metrics
      cbp_net   = intake    - transfers     (>0 -> CBP queue building)
      hhs_net   = transfers - discharges    (>0 -> HHS queue building)
      sys_net   = intake    - discharges    (>0 -> whole pipeline building)
      backlog_rate = rolling sys_net as % of rolling (CBP + HHS) load
    """
    d = df.copy()
    mp = max(3, window // 2)
    d["total_load"] = d["cbp_load"] + d["hhs_load"]

    # --- daily ratios ---
    d["transfer_eff"] = d["transfers"] / d["cbp_load"].replace(0, np.nan)
    d["discharge_eff"] = d["discharges"] / d["hhs_load"].replace(0, np.nan)
    d["throughput"] = d["discharges"] / d["intake"].replace(0, np.nan)

    # --- net flows ---
    d["cbp_net"] = d["intake"] - d["transfers"]
    d["hhs_net"] = d["transfers"] - d["discharges"]
    d["sys_net"] = d["intake"] - d["discharges"]

    # --- rolling (ratio of sums) ---
    r = d[FLOW_COLS].rolling(window, min_periods=mp).sum()
    cbp_mean = d["cbp_load"].rolling(window, min_periods=mp).mean()
    hhs_mean = d["hhs_load"].rolling(window, min_periods=mp).mean()
    d["transfer_eff_roll"] = r["transfers"] / cbp_mean.replace(0, np.nan) / window
    d["discharge_eff_roll"] = r["discharges"] / hhs_mean.replace(0, np.nan) / window
    d["throughput_roll"] = r["discharges"] / r["intake"].replace(0, np.nan)
    d["stage1_ratio_roll"] = r["transfers"] / r["intake"].replace(0, np.nan)      # CBP exits / entries
    d["stage2_ratio_roll"] = r["discharges"] / r["transfers"].replace(0, np.nan)  # HHS exits / entries

    sys_net_roll = d["sys_net"].rolling(window, min_periods=mp).mean()
    d["backlog_rate"] = sys_net_roll / (cbp_mean + hhs_mean).replace(0, np.nan)  # per reporting day

    # --- stock-based view (robust to flow/stock reporting mismatches) ---
    gap_days = d["date"].diff().dt.days.fillna(1).clip(lower=1)
    d["gap_days"] = gap_days
    d["total_load_change_per_day"] = d["total_load"].diff() / gap_days
    d["hhs_load_change_per_day"] = d["hhs_load"].diff() / gap_days
    d["stock_backlog_rate"] = (
        d["total_load_change_per_day"].rolling(window, min_periods=mp).mean() / d["total_load"].replace(0, np.nan)
    )

    # --- outcome stability: 1 - coefficient of variation of daily discharges ---
    roll_mean = d["discharges"].rolling(28, min_periods=14).mean()
    roll_std = d["discharges"].rolling(28, min_periods=14).std()
    cv = roll_std / roll_mean.replace(0, np.nan)
    d["discharge_cv"] = cv
    d["stability_score"] = (100 * (1 - cv.clip(0, 1))).round(1)

    # --- implied residence time in HHS (Little's law, approx.) ---
    mean_dis = d["discharges"].rolling(window * 4, min_periods=window).mean()
    d["implied_hhs_days"] = d["hhs_load"] / mean_dis.replace(0, np.nan)
    mean_tr = d["transfers"].rolling(window * 2, min_periods=window).mean()
    d["implied_cbp_days"] = d["cbp_load"].rolling(window * 2, min_periods=window).mean() / mean_tr.replace(0, np.nan)

    # --- calendar helpers ---
    d["weekday"] = d["date"].dt.day_name()
    d["day_type"] = np.where(d["date"].dt.dayofweek == 6, "Sunday (weekend report)", "Weekday (Mon-Thu)")
    d["month"] = d["date"].dt.to_period("M").dt.to_timestamp()
    return d


# ----------------------------------------------------------------------------
# 3. Event / period detection
# ----------------------------------------------------------------------------
def _runs(mask: pd.Series, dates: pd.Series, min_len: int) -> pd.DataFrame:
    """Turn a boolean mask into a table of consecutive True runs (>= min_len rows)."""
    mask = mask.fillna(False).astype(bool).reset_index(drop=True)
    dates = dates.reset_index(drop=True)
    grp = (mask != mask.shift()).cumsum()
    out = []
    for _, idx in mask.groupby(grp).groups.items():
        idx = list(idx)
        if not mask.loc[idx[0]]:
            continue
        if len(idx) >= min_len:
            out.append({"start": dates.loc[idx[0]], "end": dates.loc[idx[-1]], "reported_days": len(idx)})
    return pd.DataFrame(out, columns=["start", "end", "reported_days"])


def imbalance_periods(d: pd.DataFrame, min_len: int = 10, window: int = 7) -> pd.DataFrame:
    """Sustained periods where entries outpaced exits (rolling sys_net > 0)."""
    net = d["sys_net"].rolling(window, min_periods=3).mean()
    runs = _runs(net > 0, d["date"], min_len)
    if runs.empty:
        return runs.assign(excess_entries=[], peak_cbp_load=[])
    runs["excess_entries"] = [
        int(d.loc[(d.date >= s) & (d.date <= e), "sys_net"].sum()) for s, e in zip(runs.start, runs.end)
    ]
    runs["peak_cbp_load"] = [
        int(d.loc[(d.date >= s) & (d.date <= e), "cbp_load"].max()) for s, e in zip(runs.start, runs.end)
    ]
    return runs


def stagnation_periods(
    d: pd.DataFrame, min_len: int = 14, tol: float = 0.05, window: int = 14, max_dei: float = 0.015
) -> pd.DataFrame:
    """Prolonged stagnation: HHS load is flat AND almost nobody is being discharged.

    A reporting day is 'stagnant' when
      (a) the absolute `window`-day change in HHS load is below `tol` (5 %), and
      (b) the rolling discharge effectiveness is below `max_dei` (1.5 % of the
          HHS population discharged per reporting day).
    Condition (b) separates genuine stagnation (children stay put) from healthy
    equilibrium (large inflows balanced by large outflows).
    """
    chg = (d["hhs_load"].diff(window).abs() / d["hhs_load"].shift(window)).fillna(1)
    roll_dei = d["discharge_eff_roll"] if "discharge_eff_roll" in d else d["discharge_eff"].rolling(7).mean()
    mask = (chg < tol) & (roll_dei < max_dei)
    runs = _runs(mask, d["date"], min_len)
    if not runs.empty:
        runs["avg_hhs_load"] = [
            int(d.loc[(d.date >= s) & (d.date <= e), "hhs_load"].mean()) for s, e in zip(runs.start, runs.end)
        ]
        runs["avg_daily_discharges"] = [
            round(d.loc[(d.date >= s) & (d.date <= e), "discharges"].mean(), 1) for s, e in zip(runs.start, runs.end)
        ]
        runs["avg_discharge_eff_pct"] = [
            round(100 * d.loc[(d.date >= s) & (d.date <= e), "discharge_eff"].mean(), 2) for s, e in zip(runs.start, runs.end)
        ]
    return runs


def sudden_drops(d: pd.DataFrame, window: int = 7, drop_pct: float = 0.30, min_base: int = 10) -> pd.DataFrame:
    """Sudden drops in discharge performance.

    Flags dates where the `window`-day average discharge level is at least
    `drop_pct` below the average of the previous `window` days.
    """
    cur = d["discharges"].rolling(window).mean()
    prev = cur.shift(window)
    chg = (cur - prev) / prev.replace(0, np.nan)
    flag = (chg <= -drop_pct) & (prev >= min_base)
    out = d.loc[flag, ["date"]].copy()
    out["prev_avg"] = prev[flag].round(1)
    out["current_avg"] = cur[flag].round(1)
    out["change_pct"] = (100 * chg[flag]).round(1)
    # collapse consecutive flags into one event (keep the first in each cluster)
    if not out.empty:
        out = out[out["date"].diff().dt.days.fillna(99) > window]
    return out.reset_index(drop=True)


# ----------------------------------------------------------------------------
# 4. KPI summary
# ----------------------------------------------------------------------------
def kpi_summary(d: pd.DataFrame) -> dict:
    """Headline KPIs for a (filtered) slice of the data."""
    if d.empty:
        return {}
    tot_in, tot_tr, tot_out = d["intake"].sum(), d["transfers"].sum(), d["discharges"].sum()
    mean_cbp, mean_hhs = d["cbp_load"].mean(), d["hhs_load"].mean()
    n = len(d)
    if "stability_score" in d and d["stability_score"].notna().any():
        stability = float(d["stability_score"].mean())
    else:
        cv = d["discharges"].std() / d["discharges"].mean() if d["discharges"].mean() else np.nan
        stability = float(100 * (1 - min(cv, 1))) if cv == cv else np.nan
    return {
        "transfer_eff": tot_tr / (mean_cbp * n) if mean_cbp else np.nan,
        "discharge_eff": tot_out / (mean_hhs * n) if mean_hhs else np.nan,
        "throughput": tot_out / tot_in if tot_in else np.nan,
        "backlog_rate": (tot_in - tot_out) / n / (mean_cbp + mean_hhs) if (mean_cbp + mean_hhs) else np.nan,
        "stability": stability,
        "total_intake": int(tot_in),
        "total_transfers": int(tot_tr),
        "total_discharges": int(tot_out),
        "avg_cbp_load": mean_cbp,
        "avg_hhs_load": mean_hhs,
        "implied_hhs_days": mean_hhs / (tot_out / n) if tot_out else np.nan,
        "implied_cbp_days": mean_cbp / (tot_tr / n) if tot_tr else np.nan,
    }


def monthly_summary(d: pd.DataFrame) -> pd.DataFrame:
    """Month-over-month totals and efficiency."""
    g = d.groupby("month")
    m = pd.DataFrame({
        "intake": g["intake"].sum(),
        "transfers": g["transfers"].sum(),
        "discharges": g["discharges"].sum(),
        "avg_cbp_load": g["cbp_load"].mean(),
        "avg_hhs_load": g["hhs_load"].mean(),
        "reported_days": g.size(),
    })
    m["transfer_eff"] = m["transfers"] / (m["avg_cbp_load"] * m["reported_days"])
    m["discharge_eff"] = m["discharges"] / (m["avg_hhs_load"] * m["reported_days"])
    m["throughput"] = m["discharges"] / m["intake"].replace(0, np.nan)
    m["avg_daily_discharges"] = m["discharges"] / m["reported_days"]
    m["discharge_mom_pct"] = 100 * m["avg_daily_discharges"].pct_change()
    m["stability"] = 100 * (1 - (g["discharges"].std() / g["discharges"].mean()).clip(0, 1))
    return m.reset_index()
