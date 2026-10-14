"""Canonical data model.

Every page in the dashboard reads these four tables. Sample data is generated
in exactly this shape, and CSV imports are mapped onto it, so the dashboard
works the same either way.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Column:
    name: str
    dtype: str  # "str" | "date" | "float" | "bool"
    required: bool
    help: str
    synonyms: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class Dataset:
    key: str
    label: str
    description: str
    columns: tuple[Column, ...]

    @property
    def required(self) -> list[str]:
        return [c.name for c in self.columns if c.required]

    def col(self, name: str) -> Column:
        return next(c for c in self.columns if c.name == name)


REPAIR_ORDERS = Dataset(
    key="repair_orders",
    label="Repair Orders",
    description="One row per repair order (RO) with its sales and cost totals. Usually the RO / sales "
    "summary report in your shop management system.",
    columns=(
        Column("ro_number", "str", True, "Unique RO / invoice number", ("ro", "ro #", "ro no", "ro num", "repair order", "repair order number", "repair order #", "invoice", "invoice #", "invoice number")),
        Column("opened_at", "date", True, "Date/time the RO was created", ("created", "created date", "created at", "date created", "opened", "open date", "date opened")),
        Column("closed_at", "date", False, "Date the RO was posted / closed (blank = still in progress)", ("posted", "posted date", "posted at", "date posted", "closed", "closed date", "date closed", "completed date", "invoice date")),
        Column("advisor", "str", True, "Service advisor / writer on the RO", ("service advisor", "service writer", "writer", "advisor name", "sa")),
        Column("customer_type", "str", False, "Retail, Fleet, etc.", ("customer type", "type", "account type", "label")),
        Column("customer_name", "str", False, "Customer name", ("customer", "customer name", "name")),
        Column("vehicle_make", "str", False, "Vehicle make", ("make", "vehicle make")),
        Column("vehicle_year", "float", False, "Vehicle model year", ("year", "vehicle year", "model year")),
        Column("mileage", "float", False, "Odometer at check-in", ("odometer", "miles", "mileage in", "miles in")),
        Column("labor_sale", "float", True, "Labor sales $", ("labor", "labor sales", "labor total", "total labor", "labor sold")),
        Column("parts_sale", "float", True, "Parts sales $", ("parts", "parts sales", "parts total", "total parts", "parts sold")),
        Column("sublet_sale", "float", False, "Sublet sales $", ("sublet", "sublet sales", "sublet total")),
        Column("fees", "float", False, "Shop supplies / fees $", ("fee", "fees total", "shop supplies", "shop fees", "supplies")),
        Column("discount", "float", False, "Discounts given $ (positive number)", ("discounts", "discount total", "total discount")),
        Column("labor_cost", "float", False, "Technician labor cost $", ("labor cost", "cost of labor", "tech cost", "labor cogs")),
        Column("parts_cost", "float", False, "Parts cost $", ("parts cost", "cost of parts", "parts cogs")),
        Column("sublet_cost", "float", False, "Sublet cost $", ("sublet cost", "cost of sublet")),
        Column("waiter", "bool", False, "True if the customer waited on site", ("waiter", "waiting", "wait")),
        Column("is_comeback", "bool", False, "True if this RO is a comeback / redo", ("comeback", "redo", "warranty comeback")),
    ),
)

JOBS = Dataset(
    key="jobs",
    label="Jobs & Labor Lines",
    description="One row per job (concern) on each RO, recommended or authorized. Drives technician "
    "productivity and advisor close rates.",
    columns=(
        Column("ro_number", "str", True, "RO number the job belongs to", REPAIR_ORDERS.col("ro_number").synonyms),
        Column("job_id", "str", False, "Unique job id (generated if missing)", ("job", "job #", "job number", "line id")),
        Column("job_name", "str", True, "Job description", ("job", "job name", "description", "job description", "concern", "service")),
        Column("category", "str", False, "Job category (Brakes, Maintenance...)", ("job category", "service category", "type", "labor category")),
        Column("technician", "str", False, "Technician assigned", ("tech", "technician name", "assigned tech", "mechanic")),
        Column("authorized", "bool", True, "Was the job approved by the customer?", ("approved", "status", "authorized?", "sold", "is authorized")),
        Column("hours_billed", "float", False, "Labor hours billed / flagged", ("billed hours", "labor hours", "hours", "flagged hours", "sold hours")),
        Column("hours_worked", "float", False, "Actual clocked hours on the job", ("actual hours", "clocked hours", "worked hours", "time on job")),
        Column("labor_sale", "float", False, "Labor $ on the job", ("labor", "labor total", "labor sales")),
        Column("job_total", "float", True, "Total quoted $ (labor + parts) for the job", ("total", "job total", "amount", "quoted", "estimate")),
    ),
)

PARTS = Dataset(
    key="parts",
    label="Parts Lines",
    description="One row per part sold. Drives the parts profitability views and the margin leakage report.",
    columns=(
        Column("ro_number", "str", True, "RO number the part was sold on", REPAIR_ORDERS.col("ro_number").synonyms),
        Column("job_id", "str", False, "Job id the part belongs to", ("job", "job #", "job number")),
        Column("part_number", "str", False, "Part number", ("part #", "part no", "pn", "sku", "part num")),
        Column("description", "str", True, "Part description", ("part", "part name", "part description", "name", "desc")),
        Column("category", "str", False, "Part category (Brakes, Tires, Fluids...)", ("part category", "type", "part type")),
        Column("vendor", "str", False, "Supplier", ("supplier", "vendor name", "brand", "source")),
        Column("quantity", "float", True, "Quantity sold", ("qty", "quantity sold", "units")),
        Column("unit_cost", "float", True, "Cost per unit $", ("cost", "unit cost", "cost each", "each cost")),
        Column("unit_price", "float", True, "Retail price per unit $", ("price", "retail", "unit price", "sell price", "price each", "retail each")),
    ),
)

TIMECARDS = Dataset(
    key="timecards",
    label="Technician Timecards",
    description="One row per technician per day with hours available (clocked in for the day) and pay "
    "plan. Drives productivity and technician profitability.",
    columns=(
        Column("technician", "str", True, "Technician name", ("tech", "technician name", "employee", "name")),
        Column("date", "date", True, "Work date", ("work date", "day", "shift date")),
        Column("hours_available", "float", True, "Hours clocked in / available that day", ("hours", "clocked hours", "attendance hours", "hours present", "shift hours")),
        Column("pay_type", "str", False, "Flat Rate or Hourly", ("pay plan", "pay type", "compensation")),
        Column("pay_rate", "float", False, "$ per hour (flagged or clocked)", ("rate", "hourly rate", "flat rate", "pay rate")),
    ),
)

DATASETS: dict[str, Dataset] = {d.key: d for d in (REPAIR_ORDERS, JOBS, PARTS, TIMECARDS)}


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def guess_mapping(dataset: Dataset, headers: list[str]) -> dict[str, str | None]:
    """Best-effort match of CSV headers to canonical columns (exact name first, then synonyms)."""
    normalized = {_norm(h): h for h in headers}
    mapping: dict[str, str | None] = {}
    used: set[str] = set()
    for col in dataset.columns:
        candidates = [col.name, col.name.replace("_", " "), *col.synonyms]
        match = None
        for cand in candidates:
            h = normalized.get(_norm(cand))
            if h is not None and h not in used:
                match = h
                break
        mapping[col.name] = match
        if match:
            used.add(match)
    return mapping
