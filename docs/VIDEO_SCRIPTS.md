# Video Scripts

## A. Project Explanation Video (≈ 5–6 min)
**0:00 Intro (20s)** – "Hi, I'm <name>. My project is Care Transition Efficiency & Placement Outcome Analytics. It measures how efficiently children move through the UAC pipeline: CBP custody, then HHS care, then sponsor placement."

**0:20 Problem (40s)** – Counts of children in care are monitored, but process efficiency isn't. I wanted to answer: how fast are transfers, do discharges keep pace, where do backlogs form, and are outcomes improving?

**1:00 Data & cleaning (45s)** – 1,170 rows, 450 blank. Fixed thousands separators, parsed dates, sorted. Found only 67 % calendar coverage (Fri/Sat missing) and that flows don't fully reconcile with stocks in 2023–24, so I treat ratios as indicators.

**1:45 Method (60s)** – Pipeline model; five KPIs (Transfer Efficiency, Discharge Effectiveness, Throughput, Backlog Accumulation, Stability); rolling 7-day ratios; detection of imbalance, stagnation and sudden drops; Little's-law dwell-time estimates.

**2:45 Findings (75s)** – Transfer efficiency ~76–78 % → ~30 %; discharge effectiveness 3.3 % → 1.1 %; CBP dwell > 3 days in H2 2025; HHS residence ~30 → 150–230 days; four stagnation periods; Tuesday weakest; ML forecast didn't beat a naive baseline.

**4:00 Dashboard demo (90s)** – Show each tab; change the date range; toggle metrics; move alert sliders and show a tile turning red; show Sankey and stagnation bands.

**5:30 Recommendations & close (30s)** – Adopt process KPIs, audit H2-2025 CBP timing, review long-stay cases, fix data reporting. Thank you.

## B. Internship Experience & Feedback Video (≈ 3–4 min) – personalise this
1. Who you are, the internship, duration, team/mentor.
2. What you worked on (this project) and the tools: Python, pandas, Plotly, Streamlit, Jupyter, GitHub.
3. Biggest challenges (e.g. messy data, reconciliation gaps, deploying the app) and how you solved them.
4. Skills learned: data cleaning, KPI design, storytelling for non-technical stakeholders, dashboarding, deployment.
5. Feedback: what worked well, what could improve (mentor access, dataset documentation, timelines).
6. Future goals and thanks.
