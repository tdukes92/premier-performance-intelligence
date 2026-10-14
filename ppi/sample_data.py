"""Fictional sample data for a single-location independent repair shop.

All names, customers, and numbers are invented. The generator deliberately
plants realistic problems (a discount-heavy advisor, parts sold under the
pricing matrix, a tech with low efficiency) so every report has something
worth finding.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

import zlib
from bisect import bisect_right

import numpy as np
import pandas as pd

from .pricing import DEFAULT_MATRIX, TIRE_TARGET_MARGIN

SEED = 42
LABOR_RATE = 165.0
FLEET_LABOR_RATE = 145.0

TECHS = {
    # name: (level, pay_type, pay_rate, efficiency, comeback_rate)
    "Marcus Reyes": ("A", "Flat Rate", 44.0, 1.28, 0.012),
    "Dana Whitfield": ("A", "Flat Rate", 42.0, 1.16, 0.010),
    "Luis Ortega": ("B", "Flat Rate", 35.0, 1.06, 0.018),
    "Jordan Pike": ("B", "Flat Rate", 33.0, 0.81, 0.042),
    "Kevin Tran": ("C", "Hourly", 28.0, 0.97, 0.020),
    "Sam Holloway": ("L", "Hourly", 21.0, 1.12, 0.015),
}

ADVISORS = {
    # name: (share of ROs, close_rate, discount_prob, override_prob, upsell_bias)
    "Rachel Kim": (0.40, 0.64, 0.05, 0.020, 1.10),
    "Brent Collins": (0.35, 0.55, 0.19, 0.095, 1.00),
    "Tasha Morgan": (0.25, 0.43, 0.08, 0.045, 0.85),
}

MAKES = ["Toyota", "Ford", "Honda", "Chevrolet", "Nissan", "Subaru", "Jeep", "Hyundai", "BMW", "Ram", "Kia", "Mercedes-Benz"]
MAKE_W = [17, 14, 12, 11, 7, 7, 6, 6, 5, 5, 5, 5]

VENDORS = {
    "default": ["Summit Parts Supply", "Keystone Auto Parts", "Apex Distribution", "Dealer OE"],
    "Tires": ["Metro Tire Wholesale", "Summit Parts Supply"],
}

# category: (weight, hours (lo, hi), tech levels, parts [(desc, part category, cost lo, cost hi, qty lo, qty hi)])
JOB_TYPES = {
    "Maintenance": (36, (0.5, 1.0), "LC", [
        ("Synthetic Oil 5W-30 (qt)", "Fluids & Filters", 3.5, 6.0, 5, 8),
        ("Oil Filter", "Fluids & Filters", 4.0, 14.0, 1, 1),
        ("Engine Air Filter", "Fluids & Filters", 9.0, 28.0, 1, 1),
        ("Cabin Air Filter", "Fluids & Filters", 8.0, 32.0, 1, 1),
        ("Wiper Blade", "Accessories", 7.0, 18.0, 2, 2),
    ]),
    "Brakes": (16, (1.4, 2.8), "CBA", [
        ("Ceramic Brake Pad Set", "Brakes", 32.0, 95.0, 1, 2),
        ("Brake Rotor", "Brakes", 38.0, 160.0, 2, 2),
        ("Brake Hardware Kit", "Brakes", 8.0, 22.0, 1, 2),
        ("Brake Fluid DOT 3/4", "Fluids & Filters", 6.0, 14.0, 1, 2),
        ("Brake Caliper (Reman)", "Brakes", 45.0, 140.0, 1, 2),
    ]),
    "Tires": (7, (0.8, 1.4), "LC", [
        ("All-Season Tire", "Tires", 80.0, 210.0, 2, 4),
        ("TPMS Service Kit", "Tires", 4.0, 9.0, 2, 4),
        ("Valve Stem", "Tires", 1.0, 4.0, 2, 4),
    ]),
    "Alignment": (7, (1.0, 1.3), "CB", []),
    "Diagnostics": (12, (1.0, 2.2), "BA", [
        ("Engine Oxygen Sensor", "Engine", 38.0, 120.0, 1, 1),
        ("Ignition Coil", "Engine", 32.0, 95.0, 1, 2),
    ]),
    "Suspension & Steering": (6, (2.0, 4.5), "BA", [
        ("Strut Assembly", "Suspension", 85.0, 260.0, 2, 2),
        ("Control Arm w/ Ball Joint", "Suspension", 55.0, 190.0, 1, 2),
        ("Outer Tie Rod End", "Suspension", 22.0, 70.0, 1, 2),
        ("Sway Bar Link", "Suspension", 14.0, 45.0, 2, 2),
    ]),
    "Electrical": (5, (1.0, 3.5), "A", [
        ("Battery Group 35", "Electrical", 110.0, 210.0, 1, 1),
        ("Alternator (Reman)", "Electrical", 150.0, 380.0, 1, 1),
        ("Starter (Reman)", "Electrical", 120.0, 320.0, 1, 1),
    ]),
    "Engine Repair": (3, (3.5, 9.5), "A", [
        ("Timing Belt Kit w/ Water Pump", "Engine", 160.0, 420.0, 1, 1),
        ("Valve Cover Gasket Set", "Engine", 28.0, 85.0, 1, 1),
        ("Spark Plug Iridium", "Engine", 8.0, 22.0, 4, 8),
        ("Engine Mount", "Engine", 45.0, 180.0, 1, 2),
    ]),
    "HVAC": (3, (1.5, 3.8), "BA", [
        ("A/C Compressor", "HVAC", 260.0, 640.0, 1, 1),
        ("Refrigerant R-1234yf (lb)", "HVAC", 38.0, 70.0, 1, 2),
        ("Blower Motor", "HVAC", 60.0, 180.0, 1, 1),
    ]),
    "Cooling System": (3, (1.5, 3.2), "BA", [
        ("Radiator", "Cooling", 120.0, 330.0, 1, 1),
        ("Thermostat w/ Housing", "Cooling", 22.0, 75.0, 1, 1),
        ("Coolant 50/50 (gal)", "Fluids & Filters", 9.0, 16.0, 1, 3),
        ("Upper Radiator Hose", "Cooling", 14.0, 48.0, 1, 1),
    ]),
    "Fluid Services": (5, (0.6, 1.4), "LC", [
        ("ATF Synthetic (qt)", "Fluids & Filters", 6.0, 11.0, 4, 10),
        ("Fuel System Cleaner", "Fluids & Filters", 8.0, 16.0, 1, 1),
        ("Power Steering Fluid", "Fluids & Filters", 5.0, 10.0, 1, 2),
    ]),
    "Drivetrain": (2, (2.0, 7.5), "A", [
        ("CV Axle Assembly", "Drivetrain", 70.0, 210.0, 1, 2),
        ("Wheel Bearing Hub Assy", "Drivetrain", 65.0, 230.0, 1, 2),
        ("Differential Fluid (qt)", "Fluids & Filters", 9.0, 18.0, 2, 3),
    ]),
}
JOB_NAMES = {
    "Maintenance": ["Full Synthetic Oil Service", "Maintenance Service A", "Maintenance Service B", "Filter Replacement"],
    "Brakes": ["Front Brake Pads & Rotors", "Rear Brake Pads & Rotors", "Brake Caliper Replacement", "Brake Fluid Flush"],
    "Tires": ["Replace Tires", "Mount & Balance", "Tire Rotation & TPMS"],
    "Alignment": ["4-Wheel Alignment"],
    "Diagnostics": ["Check Engine Light Diagnosis", "Drivability Diagnosis", "Noise Diagnosis"],
    "Suspension & Steering": ["Replace Front Struts", "Control Arm Replacement", "Tie Rod Replacement"],
    "Electrical": ["Battery Replacement", "Alternator Replacement", "Starter Replacement", "Electrical Diagnosis"],
    "Engine Repair": ["Timing Belt Service", "Valve Cover Gasket", "Spark Plug Replacement", "Engine Mount Replacement"],
    "HVAC": ["A/C Performance Service", "A/C Compressor Replacement", "Blower Motor Replacement"],
    "Cooling System": ["Radiator Replacement", "Thermostat Replacement", "Coolant Flush"],
    "Fluid Services": ["Transmission Fluid Service", "Fuel System Service", "Power Steering Flush"],
    "Drivetrain": ["CV Axle Replacement", "Wheel Bearing Replacement", "Differential Service"],
}

FIRST = ["James", "Maria", "Robert", "Linda", "Michael", "Patricia", "David", "Jennifer", "Chris", "Elizabeth",
         "Daniel", "Susan", "Matthew", "Karen", "Anthony", "Nancy", "Mark", "Lisa", "Steven", "Ashley", "Andre", "Priya"]
LAST = ["Smith", "Johnson", "Brown", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez",
        "Wilson", "Anderson", "Thomas", "Moore", "Jackson", "Lee", "Thompson", "White", "Harris", "Clark", "Patel", "Nguyen"]
FLEETS = ["Bluegrass Plumbing Co.", "Ridgeline Landscaping", "Metro Courier Fleet", "Summit HVAC Services", "City Electric LLC"]


_BOUNDS = DEFAULT_MATRIX["cost_from"].tolist()
_MARGINS = DEFAULT_MATRIX["target_margin"].tolist()


def _matrix_price(cost: float, category: str) -> float:
    """Fast scalar version of pricing.matrix_price for the generator loop."""
    if category == "Tires":
        return cost / (1 - TIRE_TARGET_MARGIN)
    return cost / (1 - _MARGINS[max(0, bisect_right(_BOUNDS, cost) - 1)])


def _season(d: date) -> float:
    # Busier in late spring/summer, softer around the holidays.
    return 1.0 + 0.12 * np.sin((d.timetuple().tm_yday - 80) / 365 * 2 * np.pi) - (0.15 if d.month == 12 and d.day > 20 else 0)


def generate(end: date | None = None, days: int = 400, seed: int = SEED) -> dict[str, pd.DataFrame]:
    rng = np.random.default_rng(seed)
    end = end or date.today()
    start = end - timedelta(days=days)
    tech_names = list(TECHS)
    adv_names = list(ADVISORS)
    adv_share = np.array([ADVISORS[a][0] for a in adv_names])
    job_cats = list(JOB_TYPES)
    job_w = np.array([JOB_TYPES[c][0] for c in job_cats], dtype=float)
    job_w /= job_w.sum()

    ros, jobs, parts, timecards = [], [], [], []
    ro_seq = 41000

    d = start
    while d <= end:
        weekday = d.weekday()
        if weekday == 6:  # closed Sundays
            d += timedelta(days=1)
            continue
        progress = (d - start).days / days
        base = 15.5 if weekday < 5 else 6.5
        n_ros = rng.poisson(base * _season(d) * (0.93 + 0.12 * progress))

        load: dict[str, float] = {}
        # Timecards for the day.
        for t in tech_names:
            if weekday == 5 and t not in ("Kevin Tran", "Sam Holloway", "Luis Ortega"):
                continue
            if rng.random() < 0.035:  # PTO / sick
                continue
            hrs = rng.normal(8.6, 0.35) if weekday < 5 else rng.normal(5.0, 0.3)
            lvl, ptype, rate, _, _ = TECHS[t]
            load[t] = 0.0
            timecards.append({"technician": t, "date": pd.Timestamp(d), "hours_available": round(hrs, 2),
                              "pay_type": ptype, "pay_rate": rate})

        for _ in range(n_ros):
            ro_seq += 1
            ro_number = str(ro_seq)
            advisor = adv_names[rng.choice(len(adv_names), p=adv_share)]
            _, close_rate, disc_p, override_p, upsell = ADVISORS[advisor]
            fleet = rng.random() < 0.13
            hour = int(rng.choice([7, 8, 9, 10, 11, 12, 13, 14, 15, 16], p=[.17, .2, .14, .1, .08, .07, .07, .07, .06, .04]))
            opened = datetime(d.year, d.month, d.day, hour, int(rng.integers(0, 60)))
            make = MAKES[rng.choice(len(MAKES), p=np.array(MAKE_W) / sum(MAKE_W))]
            year = int(np.clip(rng.normal(2016, 4.5), 2003, 2026))
            mileage = int(np.clip(rng.normal((2027 - year) * 12500, 15000), 3000, 260000))
            waiter = rng.random() < 0.28
            customer = rng.choice(FLEETS) if fleet else f"{rng.choice(FIRST)} {rng.choice(LAST)}"

            # Comeback: a redo of earlier work, no charge to the customer.
            is_comeback = False
            comeback_tech = None
            if rng.random() < 0.022:
                weights = np.array([TECHS[t][4] for t in tech_names])
                comeback_tech = tech_names[rng.choice(len(tech_names), p=weights / weights.sum())]
                is_comeback = True

            n_primary = 1 + int(rng.random() < 0.18)
            n_recommended = int(rng.poisson(1.05 * upsell))
            if is_comeback:
                n_primary, n_recommended = 1, 0
            ro_jobs = []
            for j in range(n_primary + n_recommended):
                cat = job_cats[rng.choice(len(job_cats), p=job_w)]
                primary = j < n_primary
                authorized = True if primary else rng.random() < close_rate * (1.08 if fleet else 1.0)
                ro_jobs.append((cat, primary, authorized))

            labor_rate = FLEET_LABOR_RATE if fleet else LABOR_RATE
            ro_labor = ro_parts = ro_labor_cost = ro_parts_cost = 0.0
            for j, (cat, primary, authorized) in enumerate(ro_jobs):
                job_id = f"{ro_number}-{j + 1}"
                weight, (hlo, hhi), levels, catalog = JOB_TYPES[cat]
                billed = round(float(rng.uniform(hlo, hhi)) * 10) / 10
                eligible = [t for t in load if TECHS[t][0] in levels] or [t for t in load] or tech_names
                # Dispatch to the least-loaded eligible tech today (with some randomness).
                tech = comeback_tech if is_comeback else min(eligible, key=lambda t: load[t] + rng.uniform(0, 2.5))
                lvl, ptype, rate, eff, _ = TECHS[tech]
                worked = round(max(0.2, billed / eff * rng.normal(1.0, 0.12)), 2)
                if authorized:
                    load[tech] = load.get(tech, 0.0) + worked
                labor = 0.0 if is_comeback else round(billed * labor_rate, 2)

                part_rows = []
                if catalog:
                    k = int(rng.integers(1, min(3, len(catalog)) + 1))
                    if cat == "Alignment":
                        k = 0
                    for idx in rng.choice(len(catalog), size=k, replace=False):
                        desc, pcat, clo, chi, qlo, qhi = catalog[idx]
                        cost = round(float(rng.uniform(clo, chi)), 2)
                        qty = int(rng.integers(qlo, qhi + 1))
                        target = _matrix_price(cost, pcat)
                        price = target * rng.normal(1.0, 0.015)
                        roll = rng.random()
                        if is_comeback:
                            price = 0.0
                        elif roll < override_p:
                            price = target * rng.uniform(0.62, 0.93)  # manual price override
                        elif roll < override_p + 0.004:
                            price = cost * rng.uniform(0.75, 0.99)  # sold below cost
                        elif roll < override_p + 0.0065:
                            price = 0.0  # forgot to charge
                        if fleet and price > 0:
                            price *= 0.94  # fleet parts discount
                        part_rows.append({
                            "ro_number": ro_number, "job_id": job_id,
                            "part_number": f"{pcat[:2].upper()}-{zlib.crc32(desc.encode()) % 90000 + 10000}",
                            "description": desc, "category": pcat,
                            "vendor": rng.choice(VENDORS["Tires" if pcat == "Tires" else "default"]),
                            "quantity": qty, "unit_cost": cost, "unit_price": round(price, 2),
                        })
                parts_total = sum(p["unit_price"] * p["quantity"] for p in part_rows)
                job_total = labor + (parts_total if authorized else sum(
                    _matrix_price(p["unit_cost"], p["category"]) * p["quantity"] for p in part_rows))
                jobs.append({
                    "ro_number": ro_number, "job_id": job_id, "job_name": rng.choice(JOB_NAMES[cat]), "category": cat,
                    "technician": tech if authorized else None, "authorized": bool(authorized),
                    "hours_billed": billed if authorized else 0.0, "hours_worked": worked if authorized else 0.0,
                    "labor_sale": labor if authorized else 0.0, "job_total": round(job_total, 2),
                })
                if authorized:
                    parts.extend(part_rows)
                    ro_labor += labor
                    ro_parts += parts_total
                    ro_labor_cost += (billed if ptype == "Flat Rate" else worked) * rate
                    ro_parts_cost += sum(p["unit_cost"] * p["quantity"] for p in part_rows)

            sublet = sublet_cost = 0.0
            if not is_comeback and rng.random() < 0.04:
                sublet = round(float(rng.uniform(140, 650)), 2)
                sublet_cost = round(sublet * rng.uniform(0.68, 0.8), 2)
            fees = 0.0 if is_comeback else round(min(35.0, ro_labor * 0.05), 2)
            discount = 0.0
            if not is_comeback and rng.random() < disc_p:
                discount = round(ro_labor * rng.uniform(0.05, 0.18) + (25 if rng.random() < 0.3 else 0), 2)

            # Close-out timing: quick services same day, bigger repairs take longer.
            big = sum(JOB_TYPES[c][1][1] for c, _, a in ro_jobs if a)
            days_open = 0 if big < 2 or waiter else int(rng.choice([0, 1, 1, 2, 2, 3, 4, 6]))
            closed = opened + timedelta(days=days_open, hours=float(rng.uniform(1.5, 7.0)))
            if closed.date() > end or (closed.date() == end and rng.random() < 0.5):
                closed = None

            ros.append({
                "ro_number": ro_number, "opened_at": pd.Timestamp(opened),
                "closed_at": pd.Timestamp(closed) if closed else pd.NaT,
                "advisor": advisor, "customer_type": "Fleet" if fleet else "Retail", "customer_name": customer,
                "vehicle_make": make, "vehicle_year": year, "mileage": mileage, "waiter": waiter,
                "labor_sale": round(ro_labor, 2), "parts_sale": round(ro_parts, 2), "sublet_sale": sublet,
                "fees": fees, "discount": discount, "labor_cost": round(ro_labor_cost, 2),
                "parts_cost": round(ro_parts_cost, 2), "sublet_cost": sublet_cost, "is_comeback": is_comeback,
            })
        d += timedelta(days=1)

    return {
        "repair_orders": pd.DataFrame(ros),
        "jobs": pd.DataFrame(jobs),
        "parts": pd.DataFrame(parts),
        "timecards": pd.DataFrame(timecards),
    }
