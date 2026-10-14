# Premier Performance Intelligence

A private business intelligence dashboard for an independent automotive repair shop: profitability, technician
productivity, advisor performance and operations in one place. Built with Python, Streamlit and Plotly.

It ships with **fictional sample data** (a believable shop, about 13 months of history, with problems planted on purpose)
so every report works right away. Once you import, the financial pages use your data. The Reputation & Reviews
page stays on fictional sample reviews until review platforms are connected. When you're ready, import CSV exports from Tekmetric on the **Data Import** page.

> **Private by design.** The app runs only on your computer (`localhost`). Nothing is published, and imported shop
> data stays in `data/imported/`, which Git ignores.

---

## Preview it on your computer

You need **Python 3.10 or newer**. Check with `python3 --version` (on Windows, `python --version`).
If you don't have it, install it from [python.org](https://www.python.org/downloads/). On Windows, tick
**"Add Python to PATH"** during setup.

```bash
# 1. Get the code (or download the ZIP from GitHub and unzip it)
git clone https://github.com/tdukes92/premier-performance-intelligence.git
cd premier-performance-intelligence
git checkout claude/premier-performance-dashboard-9zijuv   # until this branch is merged

# 2. Create a private Python environment for the project (one time)
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# 3. Install the libraries (one time)
pip install -r requirements.txt

# 4. Start the dashboard
streamlit run app.py
```

Your browser opens to **http://localhost:8501**. If it doesn't, paste that address into your browser.
To stop it, press **Ctrl + C** in the terminal. Next time, you only need steps 2's `activate` line and step 4.

**What's a virtual environment (`.venv`)?** It's a folder that holds this project's own copy of its libraries, so
they don't clash with anything else on your computer. "Activating" it just tells your terminal to use that folder.

---

## What's inside

| Page | What it answers |
|---|---|
| **Executive Overview** | Sales, gross profit, car count, ARO, effective labor rate and parts margin leakage, each compared to the prior period, plus generated "key insights". |
| **Parts Profitability** | Parts GP by category, cost tier and vendor. The **Margin Leakage Exception Report** lists every part sold at $0, below cost or below your pricing matrix, with the dollars lost. You can export it to CSV. The matrix and rules can be edited. |
| **Technician Profitability** | Efficiency, productivity and proficiency; billed vs. worked vs. available hours; labor sales vs. pay cost; comebacks; a drill-down for each tech. |
| **Service Advisors** | ARO, close rate, hours per RO, discounting, parts leakage and gross profit for each advisor. |
| **RO Profitability** | GP % distribution, RO size vs. margin, profit by job type and per billed hour, a low-profit RO review list, and an RO inspector with a profit waterfall. |
| **Operational Insights** | Arrival heatmap, cycle time, aging work-in-progress, declined-work follow-up list, comebacks, and vehicle make and age mix. |
| **Reputation & Reviews** | Google, Yelp, Facebook and RepairPal reviews in one place: star ratings per platform, review volume over time, response status, negative-review alerts, a generated executive summary of the top complaints and compliments, and a filterable review feed. *(Fictional sample reviews for now.)* |
| **Data Import** | Upload CSVs, match columns automatically, validate, preview and save. You can also download templates. |

Every page has a **📘 explainer** at the bottom that defines its metrics in plain English. The sidebar filters
(period, advisor, customer type) apply to every page.

## Importing your Tekmetric data

The dashboard uses four tables. Only **Repair Orders** is required. Each additional table turns on more views:

1. **Repair Orders**: one row per posted RO with sales and cost totals.
2. **Jobs & Labor Lines**: one row per job (approved *and* declined) with technician and hours.
3. **Parts Lines**: one row per part with quantity, cost and retail price.
4. **Technician Timecards**: one row per tech per day with hours clocked in, pay type and rate.

On **Data Import**, choose the table, upload the CSV, and check the column matches. The app guesses them from
header names, and you can fix any that are wrong. Then review the validation results and click **Save**. The
sidebar's **Data source** switch lets you flip between your data and the sample data at any time.

## Project layout

```
app.py                 Entry point: page setup, navigation, sidebar filters
views/                 One file per dashboard page
ppi/theme.py           Colors, typography, chart styling (change the look here)
ppi/schema.py          The four tables' columns and header synonyms used for auto-matching
ppi/sample_data.py     Fictional sample data generator
ppi/data.py            Loading, cleaning, filtering
ppi/metrics.py         KPI and scorecard calculations
ppi/pricing.py         Parts matrix and margin-leakage logic
ppi/importer.py        CSV mapping and validation
ppi/reviews.py         Review data model, sample reviews, theme detection rules
.streamlit/config.toml Dark theme; server bound to localhost only
data/imported/         Your imported CSVs (git-ignored, never committed)
```
