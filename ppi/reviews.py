"""Customer reviews: data model, fictional sample data, theme detection and summary metrics.

Reviews from every platform (Google, Yelp, Facebook, RepairPal, ...) are stored in one
table with a `platform` column, so adding a new source later only means mapping its
export or API response onto these columns:

    review_id, platform, posted_at, reviewer, rating (1-5), text,
    responded (bool), responded_at, response_text

Themes are detected from the review *text* with keyword rules (not stored with the
sample data), so the same logic works unchanged on real reviews.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd
import streamlit as st

PLATFORMS = ["Google", "Yelp", "Facebook", "RepairPal"]
NEGATIVE_MAX = 2      # 1-2 stars = negative
RESPONSE_SLA_HOURS = 48

# --- Theme rules ------------------------------------------------------------------
# theme: (kind, regex). Phrases are matched case-insensitively against the review text.
THEMES: dict[str, tuple[str, str]] = {
    # Compliments
    "Honest & trustworthy": ("compliment", r"\bhonest|\btrust(worthy|ed)?\b|integrity|never pushy|no pressure|didn'?t try to (up)?sell"),
    "Friendly, helpful staff": ("compliment", r"\bfriendly|courteous|\bhelpful|welcoming|went above and beyond|treated me"),
    "Clear communication": ("compliment", r"explained everything|kept me (updated|informed)|walked me through|sent (me )?photos|great communication|clear explanation"),
    "Quality workmanship": ("compliment", r"fixed (it )?right|runs (great|like new|perfect)|quality work|thorough|knowledgeable|found the problem|diagnosed it"),
    "Fast turnaround": ("compliment", r"same[- ]day|done (early|ahead|quickly)|\bquick\b|fast service|back on the road (fast|quickly)|on time"),
    "Fair pricing": ("compliment", r"fair pric|reasonabl[ey] priced|reasonable price|good value|price was fair|less than the dealer"),
    "Clean, comfortable shop": ("compliment", r"\bclean\b|spotless|waiting area|lounge|coffee"),
    # Complaints
    "High prices": ("complaint", r"(?<!not )(?<!never )expensive|overpriced|too much money|pricey|ripped off|cost more than|charged way"),
    "Slow service / delays": ("complaint", r"took (way )?too long|took forever|delay|days longer|still waiting|kept my car|longer than (promised|quoted)"),
    "Poor communication": ("complaint", r"never called|no one called|no updates?\b|didn'?t (call|update)|had to call (them|multiple|three)|calls? (were |was )?not returned|left in the dark"),
    "Repair not fixed": ("complaint", r"same problem|still (broken|not fixed|making)|came back on|not fixed|had to bring it back|didn'?t fix"),
    "Upselling pressure": ("complaint", r"(?<!never )pushy|upsell|pressured me|tried to sell me|unnecessary (work|repairs|services)"),
    "Billing surprises": ("complaint", r"surprise|hidden fee|extra charges?|invoice was higher|wasn'?t quoted|not what (I was|they) quoted"),
    "Scheduling & availability": ("complaint", r"couldn'?t get (an appointment|in)|appointment was (moved|cancel)|booked out|no availability|lost my appointment"),
}
_THEME_RX = {t: re.compile(rx, re.IGNORECASE) for t, (_, rx) in THEMES.items()}
COMPLIMENTS = [t for t, (k, _) in THEMES.items() if k == "compliment"]
COMPLAINTS = [t for t, (k, _) in THEMES.items() if k == "complaint"]


def detect_themes(text: str) -> list[str]:
    text = text or ""
    return [t for t, rx in _THEME_RX.items() if rx.search(text)]


# --- Fictional sample data -----------------------------------------------------------
_SENT = {
    "Honest & trustworthy": ["Finally found an honest shop.", "They were honest about what could wait.", "{staff} was never pushy and I trust them completely.",
                             "I trust these guys with all three of our cars.", "No pressure at all, just straight answers."],
    "Friendly, helpful staff": ["Everyone was friendly and helpful.", "{staff} went above and beyond for us.", "Super friendly front counter.",
                                "{staff} treated me like family."],
    "Clear communication": ["{staff} explained everything before doing any work.", "They kept me updated all day by text.",
                            "They sent photos of the worn parts, which I loved.", "{staff} walked me through every line on the estimate."],
    "Quality workmanship": ["My truck runs like new.", "They found the problem two other shops missed.", "Very thorough inspection.",
                            "Fixed it right the first time.", "Knowledgeable techs who clearly know what they're doing."],
    "Fast turnaround": ["Same-day service on my brakes.", "Car was done early.", "Quick oil change, in and out.", "Fast service even on a busy Saturday."],
    "Fair pricing": ["The price was fair.", "Reasonably priced and less than the dealer quoted.", "Good value for the quality of work."],
    "Clean, comfortable shop": ["Clean waiting area with good coffee.", "The shop is spotless and the lounge is comfortable."],
    "High prices": ["Way too expensive for an oil change.", "Overpriced compared to other shops.", "Felt a bit pricey.", "It cost more than I expected."],
    "Slow service / delays": ["Took way too long to get my car back.", "Repair took three days longer than promised.", "There was delay after delay on parts.",
                              "They kept my car over the weekend for a simple job."],
    "Poor communication": ["No one called me with an update.", "I had to call them multiple times to get an answer.", "Left in the dark about my car all day.",
                           "They never called when it was ready."],
    "Repair not fixed": ["Same problem two days later.", "The check engine light came back on the next week.", "Had to bring it back and it's still not fixed."],
    "Upselling pressure": ["{staff} was pushy about a bunch of extra services.", "Felt pressured me into unnecessary work.", "They tried to sell me a full brake job I didn't need."],
    "Billing surprises": ["The invoice was higher than the estimate.", "Surprise shop fee at pickup.", "Extra charges that weren't quoted."],
    "Scheduling & availability": ["Couldn't get an appointment for two weeks.", "My appointment was moved twice.", "They lost my appointment and I had to come back."],
}
_OPENERS = {5: ["Highly recommend!", "Best shop in town.", "Five stars.", "Great experience.", ""],
            4: ["Good experience overall.", "Solid shop.", "Pretty happy.", ""],
            3: ["Mixed feelings.", "It was okay.", ""],
            2: ["Disappointed.", "Not great.", ""],
            1: ["Avoid.", "Terrible experience.", "Very frustrated.", ""]}
_RESPONSES = {
    "pos": ["Thank you, {first}! We appreciate you trusting us with your vehicle.", "Thanks for the kind words, {first} — see you at your next service!",
            "We're glad we could help, {first}. Thanks for choosing Premier Performance!"],
    "neg": ["{first}, we're sorry to hear this. Please call and ask for the service manager so we can make it right.",
            "Thank you for the feedback, {first}. This isn't the experience we want for anyone — we've reached out directly to resolve it."],
}
_FIRST = ["Mike", "Sarah", "Jason", "Emily", "Carlos", "Megan", "Tony", "Brittany", "Kevin", "Amanda", "Derek", "Lauren", "Omar", "Rachel",
          "Greg", "Jessica", "Tyrone", "Hannah", "Victor", "Kim", "Paul", "Nicole", "Sean", "Diana", "Raj", "Monica"]
_LAST_INIT = list("ABCDEFGHJKLMNPRSTW")
_STAFF_POS = ["Rachel", "Rachel", "Tasha", "Brent", "Marcus", "Dana"]
_STAFF_NEG = ["Brent", "Brent", "Tasha"]

# platform: (share of reviews, rating weights 1..5, response rate)
_PLATFORM_PARAMS = {
    "Google": (0.56, [0.05, 0.03, 0.05, 0.15, 0.72], 0.86),
    "Yelp": (0.18, [0.12, 0.07, 0.09, 0.20, 0.52], 0.55),
    "Facebook": (0.16, [0.05, 0.03, 0.06, 0.14, 0.72], 0.64),
    "RepairPal": (0.10, [0.03, 0.02, 0.05, 0.18, 0.72], 0.80),
}


def generate(end: date | None = None, days: int = 400, seed: int = 11) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    end = end or date.today()
    start = end - timedelta(days=days)
    plats = list(_PLATFORM_PARAMS)
    shares = np.array([_PLATFORM_PARAMS[p][0] for p in plats])
    rows = []
    rid = 0
    d = start
    while d <= end:
        recent = (end - d).days <= 60  # planted story: a busy recent stretch hurts speed & communication
        lam = 1.05 * (1.1 if recent else 1.0)
        for _ in range(rng.poisson(lam)):
            rid += 1
            plat = plats[rng.choice(len(plats), p=shares)]
            _, weights, resp_rate = _PLATFORM_PARAMS[plat]
            w = np.array(weights, dtype=float)
            if recent:
                w = w * np.array([1.6, 1.5, 1.3, 1.0, 0.9])
            rating = int(rng.choice([1, 2, 3, 4, 5], p=w / w.sum()))

            pos_pool = COMPLIMENTS
            neg_pool = COMPLAINTS
            neg_w = np.array([3, 2.5, 2, 2, 1.5, 1.5, 1.2], dtype=float)  # High prices most common...
            if recent:
                neg_w[[1, 2]] *= 2.6  # ...but delays & communication spike recently
            pos_w = np.array([3, 2.5, 2, 2.2, 1.6, 1.4, 0.6])
            n_pos, n_neg = {5: (2, 0), 4: (2, int(rng.random() < 0.3)), 3: (1, 1), 2: (0, 2), 1: (0, 2)}[rating]
            if rating == 5 and rng.random() < 0.35:
                n_pos = 3
            pos = list(rng.choice(pos_pool, size=n_pos, replace=False, p=pos_w / pos_w.sum())) if n_pos else []
            neg = list(rng.choice(neg_pool, size=n_neg, replace=False, p=neg_w / neg_w.sum())) if n_neg else []

            parts = [str(rng.choice(_OPENERS[rating]))]
            for t in pos + neg:
                s = str(rng.choice(_SENT[t]))
                if "{staff}" in s:
                    s = s.format(staff=str(rng.choice(_STAFF_POS if t in COMPLIMENTS else _STAFF_NEG)))
                parts.append(s)
            text = " ".join(p for p in parts if p)

            posted = datetime(d.year, d.month, d.day, int(rng.integers(7, 22)), int(rng.integers(0, 60)))
            first = str(rng.choice(_FIRST))
            age_days = (end - d).days
            p_resp = resp_rate * (0.85 if rating <= NEGATIVE_MAX else 1.0) * (0.45 if age_days <= 2 else 1.0)
            responded = rng.random() < p_resp
            hours = float(rng.gamma(1.6, 22 if rating > NEGATIVE_MAX else 30)) if responded else None
            responded_at = posted + timedelta(hours=hours) if responded else None
            if responded_at and responded_at.date() > end:
                responded, responded_at = False, None
            rows.append({
                "review_id": f"R{rid:05d}", "platform": plat, "posted_at": pd.Timestamp(posted),
                "reviewer": f"{first} {rng.choice(_LAST_INIT)}.", "rating": rating, "text": text,
                "responded": bool(responded), "responded_at": pd.Timestamp(responded_at) if responded_at else pd.NaT,
                "response_text": str(rng.choice(_RESPONSES["neg" if rating <= 3 else "pos"])).format(first=first) if responded else None,
            })
        d += timedelta(days=1)
    return pd.DataFrame(rows)


@st.cache_data(show_spinner="Loading reviews…")
def load(end: date) -> pd.DataFrame:
    return enrich(generate(end=end))


def enrich(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["posted_date"] = df["posted_at"].dt.normalize()
    df["themes"] = df["text"].map(detect_themes)
    df["compliments"] = df["themes"].map(lambda ts: [t for t in ts if t in COMPLIMENTS])
    df["complaints"] = df["themes"].map(lambda ts: [t for t in ts if t in COMPLAINTS])
    df["is_negative"] = df["rating"] <= NEGATIVE_MAX
    df["response_hours"] = (df["responded_at"] - df["posted_at"]).dt.total_seconds() / 3600
    return df


# --- Metrics ---------------------------------------------------------------------

def in_period(df: pd.DataFrame, start: date, end: date) -> pd.DataFrame:
    return df[df["posted_date"].between(pd.Timestamp(start), pd.Timestamp(end))]


def summary(df: pd.DataFrame) -> dict[str, float]:
    n = len(df)
    nan = float("nan")
    return {
        "count": float(n),
        "avg_rating": df["rating"].mean() if n else nan,
        "pct_5": (df["rating"] == 5).mean() if n else nan,
        "pct_positive": (df["rating"] >= 4).mean() if n else nan,
        "negatives": float(df["is_negative"].sum()),
        "response_rate": df["responded"].mean() if n else nan,
        "median_response_hours": df["response_hours"].median() if df["responded"].any() else nan,
        "negative_response_rate": df.loc[df["is_negative"], "responded"].mean() if df["is_negative"].any() else nan,
    }


def theme_table(df: pd.DataFrame, prev: pd.DataFrame, kind: str) -> pd.DataFrame:
    """Mentions per theme with share of reviews, avg rating of mentioning reviews, and change vs prior period."""
    col = "compliments" if kind == "compliment" else "complaints"
    names = COMPLIMENTS if kind == "compliment" else COMPLAINTS

    def counts(frame):
        ex = frame[[col, "rating"]].explode(col).dropna(subset=[col])
        return ex.groupby(col).agg(mentions=("rating", "size"), avg_rating=("rating", "mean"))

    cur, old = counts(df).reindex(names), counts(prev).reindex(names)
    out = pd.DataFrame({"theme": names, "mentions": cur["mentions"].fillna(0).to_numpy(),
                        "avg_rating": cur["avg_rating"].to_numpy(), "prev_mentions": old["mentions"].fillna(0).to_numpy()})
    out["share"] = out["mentions"] / max(len(df), 1)
    out["prev_share"] = out["prev_mentions"] / max(len(prev), 1)
    out["change_pts"] = out["share"] - out["prev_share"]
    return out.sort_values("mentions", ascending=False).reset_index(drop=True)


def staff_mentions(df: pd.DataFrame, names: list[str]) -> pd.DataFrame:
    rows = []
    for n in names:
        m = df[df["text"].str.contains(rf"\b{re.escape(n)}\b", case=False, regex=True)]
        if len(m):
            rows.append({"name": n, "mentions": len(m), "avg_rating": m["rating"].mean(), "negative": int(m["is_negative"].sum())})
    return pd.DataFrame(rows, columns=["name", "mentions", "avg_rating", "negative"]).sort_values("mentions", ascending=False)


def alerts(df: pd.DataFrame, now: pd.Timestamp) -> pd.DataFrame:
    """Unanswered reviews of 3 stars or fewer, most urgent first (all dates — an open alert never expires)."""
    a = df[(df["rating"] <= 3) & ~df["responded"]].copy()
    a["age_hours"] = (now - a["posted_at"]).dt.total_seconds() / 3600
    a["severity"] = np.select([(a["rating"] <= NEGATIVE_MAX) & (a["age_hours"] > RESPONSE_SLA_HOURS), a["rating"] <= NEGATIVE_MAX],
                              ["critical", "serious"], "warning")
    order = {"critical": 0, "serious": 1, "warning": 2}
    return a.sort_values(["severity", "posted_at"], key=lambda s: s.map(order) if s.name == "severity" else s, ascending=[True, False])
