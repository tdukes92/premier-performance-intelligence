"""CSV import: apply a column mapping, coerce types, and validate before saving."""

from __future__ import annotations

import pandas as pd

from .data import coerce
from .schema import Dataset


def apply_mapping(raw: pd.DataFrame, dataset: Dataset, mapping: dict[str, str | None]) -> pd.DataFrame:
    out = pd.DataFrame(index=raw.index)
    for col in dataset.columns:
        src = mapping.get(col.name)
        if src:
            out[col.name] = raw[src]
    return coerce(out, dataset)


def validate(raw: pd.DataFrame, dataset: Dataset, mapping: dict[str, str | None], df: pd.DataFrame) -> list[tuple[str, str]]:
    """Return (level, message) pairs. level: 'error' blocks saving; 'warning'/'info' do not."""
    issues: list[tuple[str, str]] = []
    missing = [c for c in dataset.required if not mapping.get(c)]
    if missing:
        issues.append(("error", "Required column(s) not mapped: " + ", ".join(f"`{m}`" for m in missing)))
        return issues
    if df.empty:
        issues.append(("error", "The file has no data rows."))
        return issues

    for col in dataset.columns:
        src = mapping.get(col.name)
        if not src:
            continue
        raw_filled = raw[src].notna() & raw[src].astype(str).str.strip().ne("")
        if col.dtype == "date":
            bad = int((raw_filled & df[col.name].isna()).sum())
            if bad:
                issues.append(("warning", f"`{col.name}`: {bad:,} value(s) couldn't be read as dates and will be blank."))
        elif col.dtype == "float":
            parsed = pd.to_numeric(raw[src].astype(str).str.replace(r"[\$,\s]", "", regex=True).str.replace(r"^\((.*)\)$", r"-\1", regex=True), errors="coerce")
            bad = int((raw_filled & parsed.isna()).sum())
            if bad:
                issues.append(("warning", f"`{col.name}`: {bad:,} value(s) aren't numbers and will be treated as 0."))
        if col.required:
            empty = int((~raw_filled).sum())
            if empty:
                issues.append(("warning", f"`{col.name}` is blank on {empty:,} row(s)."))

    if dataset.key == "repair_orders":
        dups = int(df["ro_number"].duplicated().sum())
        if dups:
            issues.append(("warning", f"{dups:,} duplicate RO number(s). Each RO should appear once — check the export isn't line-level."))
        if not mapping.get("labor_cost") or not mapping.get("parts_cost"):
            issues.append(("warning", "Labor and/or parts cost not mapped — gross profit will be overstated for those ROs."))
        if not mapping.get("closed_at"):
            issues.append(("warning", "No posted/closed date mapped — every RO will be treated as still open."))
    if dataset.key == "parts":
        neg = int(((df["unit_cost"] < 0) | (df["quantity"] < 0)).sum())
        if neg:
            issues.append(("info", f"{neg:,} line(s) have negative cost or quantity (returns/cores?)."))
        under = int((df["unit_price"] < df["unit_cost"]).sum())
        if under:
            issues.append(("info", f"{under:,} line(s) are priced below cost — they'll appear on the leakage report."))
    if dataset.key == "jobs" and not mapping.get("technician"):
        issues.append(("warning", "No technician column mapped — technician views will be empty."))

    issues.append(("info", f"{len(df):,} rows ready to import."))
    return issues
