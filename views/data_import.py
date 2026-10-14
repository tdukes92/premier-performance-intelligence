import io

import pandas as pd
import streamlit as st

from ppi import data as data_mod
from ppi import importer, sample_data
from ppi.components import card, learn, page_header, section
from ppi.schema import DATASETS, guess_mapping
from ppi.state import ctx

c = ctx()
page_header("Data Import", "Bring in CSV exports from Tekmetric (or any shop system) to replace the sample data.", c.period_label, c.all.source)

st.markdown("""
<div class="ppi-learn"><b>How importing works.</b> The dashboard runs on four tables: <b>Repair Orders</b>, <b>Jobs</b>,
<b>Parts lines</b> and <b>Technician timecards</b>. Upload a CSV for each, match its columns to the fields below
(most are matched automatically), check the validation results, then save. Imported files are stored only on this
computer in <code>data/imported/</code> and are never committed to Git. Only Repair Orders is needed to start —
add the others to light up the parts, technician and close-rate views.</div>
""", unsafe_allow_html=True)

# --- Status -----------------------------------------------------------------------
section("Import status")
imported = set(data_mod.imported_keys())
cols = st.columns(4, gap="small")
for col, (key, ds) in zip(cols, DATASETS.items()):
    with col:
        path = data_mod.IMPORT_DIR / f"{key}.csv"
        if key in imported:
            n = sum(1 for _ in open(path, encoding="utf-8")) - 1
            status = f'<div class="delta" style="color:#0ca30c">✓ Imported · {n:,} rows</div>'
        else:
            status = '<div class="delta" style="color:#7d8594">○ Not imported — using sample</div>'
        st.markdown(f'<div class="ppi-kpi"><div class="label">{ds.label}</div>'
                    f'<div class="foot" style="margin-top:6px">{ds.description}</div>{status}</div>', unsafe_allow_html=True)

if imported:
    st.caption("Switch between your imported data and the sample data with **Data source** in the sidebar.")

# --- Import wizard ------------------------------------------------------------------
section("Import a file")
with card(None, key="wizard"):
    key = st.radio("1 · What are you importing?", list(DATASETS), format_func=lambda k: DATASETS[k].label, horizontal=True)
    ds = DATASETS[key]

    tcol1, tcol2 = st.columns([3, 1])
    tcol1.caption(f"**{ds.label}** — {ds.description} Required fields are marked ★.")
    tmpl = sample_data.generate(days=3, seed=7)[key].head(25)
    tcol2.download_button("Download template CSV", tmpl.to_csv(index=False).encode(), file_name=f"template_{key}.csv",
                          mime="text/csv", width="stretch")

    up = st.file_uploader("2 · Upload CSV", type=["csv"], key=f"upload_{key}")
    if up is not None:
        try:
            raw = pd.read_csv(io.BytesIO(up.getvalue()), dtype=str, keep_default_na=False, na_values=[""], encoding_errors="replace")
        except Exception as e:  # noqa: BLE001 - show any parse problem to the user
            st.error(f"Couldn't read that file as CSV: {e}")
            st.stop()
        raw.columns = [str(h).strip() for h in raw.columns]
        st.caption(f"Read **{len(raw):,} rows** and **{len(raw.columns)} columns** from `{up.name}`.")

        st.markdown("**3 · Match columns**")
        st.caption("We guessed matches from the column names. Fix any that are wrong; leave optional fields as “— not in file —”.")
        guess = guess_mapping(ds, list(raw.columns))
        options = ["— not in file —", *raw.columns]
        mapping: dict[str, str | None] = {}
        grid = st.columns(3, gap="medium")
        for i, col in enumerate(ds.columns):
            g = guess.get(col.name)
            choice = grid[i % 3].selectbox(
                f"{'★ ' if col.required else ''}{col.name}", options, index=options.index(g) if g in options else 0,
                help=col.help, key=f"map_{key}_{col.name}",
            )
            mapping[col.name] = None if choice == options[0] else choice

        df = importer.apply_mapping(raw, ds, mapping)
        issues = importer.validate(raw, ds, mapping, df)
        st.markdown("**4 · Validate & preview**")
        for level, msg in issues:
            {"error": st.error, "warning": st.warning, "info": st.info}[level](msg)
        if not any(level == "error" for level, _ in issues):
            st.dataframe(df.head(50), width="stretch", hide_index=True)
            replace = key in imported
            if st.button(f"5 · {'Replace' if replace else 'Save'} {ds.label} ({len(df):,} rows)", type="primary"):
                path = data_mod.save_import(key, df)
                st.session_state["_force_source"] = "Imported data"
                st.success(f"Saved to `{path.relative_to(data_mod.ROOT)}`. The dashboard now uses your imported data.")
                st.rerun()

# --- Manage -------------------------------------------------------------------------
if imported:
    section("Manage imported data")
    with card(None, key="manage"):
        mc = st.columns(len(imported) + 1)
        for i, k in enumerate(sorted(imported)):
            if mc[i].button(f"Remove {DATASETS[k].label}", key=f"del_{k}", width="stretch"):
                data_mod.delete_import(k)
                st.rerun()

# --- Guidance -----------------------------------------------------------------------
section("Getting data out of Tekmetric")
learn("Which reports to export (step-by-step)", """
Report names and columns change between Tekmetric versions and depend on your account, so treat this as a guide —
the column-matching step above handles different header names.<br><br>
<b>1. Repair Orders</b> — use an RO / sales summary or end-of-day report filtered to <i>posted</i> ROs for your date
range, exported to CSV. You want one row per RO with RO number, created and posted dates, service writer, labor,
parts, sublet, fees, discount and — importantly — <b>labor cost and parts cost</b>.<br>
<b>2. Jobs</b> — a job- or labor-detail report with one row per job: RO number, job name, technician, authorized
(approved/declined), labor hours and job total. Including <i>declined</i> jobs enables close-rate tracking.<br>
<b>3. Parts</b> — a parts-sold or parts-detail report with one row per part line: RO number, description, quantity,
cost and retail price. Category and vendor are optional but make the breakdowns richer.<br>
<b>4. Technician timecards</b> — a payroll / time-clock export with one row per tech per day and hours clocked in.
Add pay type (Flat Rate or Hourly) and pay rate as columns if your export doesn't have them.<br><br>
<b>Tip:</b> export the same date range for all four so the numbers tie out. Re-importing a dataset replaces the
previous file for that dataset.
""")
learn("Is my data private?", """
Yes. This app runs entirely on your computer (<code>localhost</code>). Uploaded files are processed in memory and
saved to the <code>data/imported/</code> folder on your machine. That folder is listed in <code>.gitignore</code>,
so real shop data is never pushed to GitHub. Delete it anytime with the Remove buttons above.
""")
