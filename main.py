"""
main.py — Pipeline orchestration for RayDar Data Center (PLAN.md steps 5a/5b/6).

Scope: fetch + score (aggregation, 5a), the capex direction overlay (5b),
and render (step 6, render.py). run_full_pipeline() / --now runs all three.
analyze.py, next_nvidia.py, publish.py still don't exist (no AI narrative,
no radar, no auto-publish) — matching the "don't get ahead of the build
order" discipline used for score_engine.py (step 3). --now writes
index.html but doesn't deploy it; that's step 7.

Adapted from reference/main.py. Reuses market-cap weighting, bottleneck
leader boost, Red reality check, and 3-day color confirmation AS-IS in
design — with two adaptations:

1. Missing-data propagation (decision #6). A ticker whose ScoreEngine result
   is score=None ("insufficient data") is excluded from the sub-layer's
   market-cap-weighted average and from the bottleneck-leader-boost / Red-
   reality-check candidate pools — but never silently dropped without a
   trace: each sub-layer result carries tickers_scored/tickers_total and an
   `insufficient` list (ticker + reason). If EVERY ticker in a sub-layer
   comes back insufficient, the sub-layer's weighted_score/color is itself
   None/"insufficient data", never a fabricated Green or 0.

   Single-ticker sub-layers (Cooling = VRT, decision #2) need no special
   case — the market-cap-weighted average of one ticker at 100% of
   total_mcap already IS that ticker's own score.

2. Red reality check (decision #3): reference/main.py's version reads
   `t.get("rating", "C")` for the dominant companies' quality, but "rating"
   (A/B/C/D) is only ever assigned by render.py (step 6) — at the point
   this check runs, no ticker dict has a "rating" key yet. Defaulting to
   "C" would make the check ALWAYS fire and downgrade every multi-ticker
   Red sub-layer to Orange, unconditionally — a bug in the reference, not
   a selective check. Fixed here to skip (no verdict, color unchanged)
   until ratings actually exist, rather than reuse that default. This
   ALSO naturally covers single-ticker sub-layers (decision #3) via the
   existing len(top2) < 2 guard — no separate special-case needed there
   either.

   3-day color confirmation reads scores_history.json but doesn't write
   it — that's render.py's job (step 6). Until render.py exists, every
   run falls into "unconfirmed — building baseline". Expected, not a bug
   in this commit.
"""

import json
import logging
import argparse
import datetime

from render import day_label

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger(__name__)

# _confirmed_color() returns a plain-English note and the branch that set
# the colour. The dashboard shows the note on each sub-layer card and, while
# at least one card is in the "no_history" branch, a page-level line saying
# colours are the latest session's reading only (ledger R30/R36/R42), so the disclosure
# follows the data and disappears by itself once history is stored.
NO_HISTORY = "no_history"

# Rating quality map — used for Red reality check once render.py (step 6)
# starts assigning ratings. Kept here so the check is future-proofed rather
# than needing this reintroduced later.
RATING_QUALITY = {"A": 4, "B": 3, "C": 2, "D": 1}


# ── Score history helpers (read-only here — see module docstring) ─────────────
# History entries are dated by US market session (ledger R33b). Confirmation
# looks at the CONFIRM_WINDOW sessions before the current one, taken from the
# trading calendar (fetch_trading_sessions), not from whatever entries happen
# to be stored. A session in that window with no stored score is missing: it
# is left out and named in the note, never counted as 0 (decision #6, ledger
# R33d/R40). Sessions before the first stored entry aren't "missing" (history
# hadn't started), and sessions more than MAX_ENTRY_AGE_DAYS calendar days
# before the current one don't count at all.

CONFIRM_WINDOW     = 3
MAX_ENTRY_AGE_DAYS = 7


def _confirmation_window(layer_id: str, history: list, sessions: list,
                         current: datetime.date) -> tuple[list, list]:
    """
    Returns (stored, missing) for the CONFIRM_WINDOW sessions before
    `current`: stored is [(session, score, color)], oldest first; missing is
    [session] for window sessions with no score stored for this sub-layer.
    """
    cutoff  = current - datetime.timedelta(days=MAX_ENTRY_AGE_DAYS)
    window  = [s for s in sessions if cutoff <= s < current][-CONFIRM_WINDOW:]
    dates   = sorted(e.get("date") for e in history if e.get("date"))
    first   = datetime.date.fromisoformat(dates[0]) if dates else None
    by_date = {e.get("date"): e for e in history}
    stored, missing = [], []
    for s in window:
        layer = ((by_date.get(s.isoformat()) or {}).get("scores") or {}).get(layer_id) or {}
        if layer.get("score") is not None:
            stored.append((s, layer["score"], layer.get("color")))
        elif first is not None and s >= first:
            missing.append(s)
    return stored, missing


def _confirmed_color(
    today_score: float,
    today_color: str,
    layer_id: str,
    top_fund_delta: float | None,
    history: list,
    sessions: list,
    current: datetime.date,
) -> tuple[str, str, str]:
    """
    3-day color confirmation system — rules unchanged from reference. A color
    change requires confirmation across multiple daily runs to prevent
    single-day data noise from flipping the dashboard signal.

    INSTANT RED   — today_score > 80, OR top_fund_delta > 0.60
    CONFIRMED RED — today > 65 AND 2+ of last 3 days also > 55
    CONFIRMED ORANGE — today >= 45 AND 2+ of last 3 days also >= 40
    CONFIRMED BLUE — today < 25 AND 2+ of last 3 days also < 30
    HOLDING — keep the recent dominant colour if today's score is within
              its band (for Green the band check always passes: gap 0)
    DEFAULT — Green if 25 <= score < 45, else today's colour

    Returns (colour, note, branch). The note is the plain-English text the
    dashboard shows on the card (R36 wording, with R42's change: scores
    belong to the last completed session, so "latest", not "today's").
    Confirmed notes say "N of the last 3 sessions" when all three are
    stored, and "N of M available recent sessions" otherwise (R42 asks
    for it whenever a session is missing; it's also used in the first days
    of a history, when fewer than 3 are stored, so the note never implies a
    session was checked that wasn't). branch is one of: no_history,
    instant, confirmed, holding, not_sustained.

    A missing session in the window is named at the end of every note that
    depends on history (all but instant Red), e.g. "(no reading for Mon
    Oct 5)" (ledger R40).
    """
    stored, missing = _confirmation_window(layer_id, history, sessions, current)
    recent = [score for _, score, _ in stored]
    k = len(recent)
    gap = f"no reading for {', '.join(day_label(s) for s in missing)}" if missing else ""
    if missing:
        log.info(f"  {layer_id}: {gap} — left out of confirmation, not counted as 0")

    if k < 2:
        log.debug(f"  {layer_id}: {today_color} unconfirmed — only {k} history days")
        stored_txt = f"{k} of 2 earlier sessions stored" + (f"; {gap}" if gap else "")
        return today_color, f"Latest session only — not yet confirmed ({stored_txt})", NO_HISTORY

    suffix = f" ({gap})" if gap else ""
    span   = "of the last 3 sessions" if k == CONFIRM_WINDOW else f"of {k} available recent sessions"

    if today_score > 80:
        log.info(f"  {layer_id}: instant Red — extreme score {today_score:.1f} > 80")
        return "Red", f"Red without waiting: score {today_score:.1f} is above 80", "instant"

    if top_fund_delta and top_fund_delta > 0.60:
        log.info(f"  {layer_id}: instant Red — fund_delta {top_fund_delta:.2f} > 0.60")
        return "Red", "Red without waiting: revenue growth at one of its companies is accelerating sharply", "instant"

    days_above_55  = sum(1 for s in recent if s > 55)
    days_above_40  = sum(1 for s in recent if s >= 40)
    days_below_30  = sum(1 for s in recent if s < 30)

    if today_score > 65 and days_above_55 >= 2:
        return "Red", f"Red, confirmed: {days_above_55} {span} also above 55{suffix}", "confirmed"

    if today_score >= 45 and days_above_40 >= 2:
        return "Orange", f"Orange, confirmed: {days_above_40} {span} also at or above 40{suffix}", "confirmed"

    if today_score < 25 and days_below_30 >= 2:
        return "Blue", f"Blue, confirmed: {days_below_30} {span} also below 30{suffix}", "confirmed"

    # Same window as the scores above: a missing session adds no colour.
    prev_colors = [color for _, _, color in stored if color]

    if prev_colors:
        from collections import Counter
        dominant = Counter(prev_colors).most_common(1)[0][0]
        threshold_gap = {
            "Red":    today_score - 65,
            "Orange": today_score - 45,
            "Green":  0,
            "Blue":   25 - today_score,
        }.get(dominant, 0)

        if -10 <= threshold_gap <= 5:
            log.info(f"  {layer_id}: holding {dominant} (borderline score {today_score:.1f}, "
                     f"prev dominant={dominant})")
            if dominant == "Green":
                note = f"Kept Green: latest score {today_score:.1f} isn't confirmed yet, and recent sessions were mostly Green"
            else:
                note = (f"Kept {dominant}: latest score {today_score:.1f} is near the line, "
                        f"and recent sessions were mostly {dominant}")
            return dominant, note + suffix, "holding"

    shown = "Green" if 25 <= today_score < 45 else today_color
    log.info(f"  {layer_id}: {today_color} -> {shown} (unconfirmed, fallback)")
    return shown, f"Shown as {shown}: latest score {today_score:.1f} hasn't held over recent sessions{suffix}", "not_sustained"


def _layer_color_from_score(score: float, top_delta: float | None) -> tuple[str, str]:
    """Derive sub-layer color from the market-cap weighted composite score."""
    if top_delta is not None and top_delta < 0:
        return "Blue", f"Cooling — dominant ticker decelerating ({top_delta*100:.1f}%)"
    if score > 65:
        return "Red", "Confirmed bottleneck — weighted sub-layer score"
    elif score >= 45:
        return "Orange", "Emerging — acceleration building across sub-layer"
    elif score < 25:
        return "Blue", "Cooling"
    else:
        return "Green", "Neutral — healthy growth, no constraint pressure"


def _red_reality_check(
    layer_scores: list,
    market_data_tickers: list,
    color: str,
) -> tuple[str, str]:
    """
    A sub-layer cannot be Red if its two largest companies by market cap are
    both rated C or D. See module docstring: skipped (no verdict, color
    unchanged) until render.py (step 6) actually assigns "rating" — reusing
    reference/main.py's t.get("rating", "C") default here would make this
    ALWAYS fire, a bug in the reference, not the intended selective check.
    """
    if color != "Red":
        return color, ""

    mcap_lookup = {}
    for t in (market_data_tickers or []):
        if t and t.get("ticker"):
            mcap_lookup[t["ticker"]] = t.get("market_cap") or 0

    sorted_by_mcap = sorted(
        layer_scores,
        key=lambda x: mcap_lookup.get(x.get("ticker", ""), 0),
        reverse=True
    )

    top2 = sorted_by_mcap[:2]
    if len(top2) < 2:
        # Not enough scored tickers to check — covers single-ticker
        # sub-layers (decision #3) AND any sub-layer that degenerated to
        # 1 scored ticker this run because the other(s) were insufficient.
        return color, ""

    if any(t.get("rating") is None for t in top2):
        # Ratings aren't available yet (render.py, step 6) — no verdict
        # possible, so don't downgrade based on an assumed default.
        return color, ""

    top2_ratings = [t["rating"] for t in top2]
    top2_tickers = [t.get("ticker", "?") for t in top2]
    top2_quality = [RATING_QUALITY.get(r, 2) for r in top2_ratings]

    if all(q <= 2 for q in top2_quality):
        reason = (
            f"Downgraded Red->Orange: dominant companies "
            f"{top2_tickers[0]}({top2_ratings[0]}) and "
            f"{top2_tickers[1]}({top2_ratings[1]}) not confirming bottleneck"
        )
        log.info(f"  Red reality check fired: {reason}")
        return "Orange", reason

    return color, ""


# ── Pipeline stages ─────────────────────────────────────────────────────────

def stage_fetch() -> tuple[dict, dict]:
    """
    Returns (market_data, macro_data). market_data is
    {"sub_layers": {...}, "meta": {...}} per fetch_market.run_pipeline().
    On a total fetch failure, returns an empty/all-missing shape — never
    fabricated defaults (decision #6; replaces reference/main.py's
    hardcoded MACRO_DEFAULTS = {"vix": 20.0, ...} fallback).

    The trading-session calendar is fetched first and outside that
    catch-all: if it fails, the run fails (ledger R40), because the history
    is dated by session and confirmation needs to know which sessions to
    expect. meta["session"] is the last completed session (ISO date), and
    meta["sessions"] the calendar it came from.
    """
    log.info("[1/2] Fetching market data...")
    from fetch_market import fetch_trading_sessions, SchemaError
    sessions = fetch_trading_sessions()
    session_meta = {"session": sessions[-1].isoformat(),
                    "sessions": [s.isoformat() for s in sessions]}
    log.info(f"  Session: {session_meta['session']} (last completed US session)")
    try:
        from fetch_market import run_pipeline, fetch_macro
        market_data = run_pipeline()
        macro_data  = fetch_macro()
        market_data.setdefault("meta", {}).update(session_meta)
        log.info(f"  Fetched {len(market_data.get('sub_layers', {}))} sub-layers, "
                 f"macro: VIX={macro_data.get('vix')}")
        return market_data, macro_data
    except SchemaError:
        raise           # a data-format change fails the run (ledger R44)
    except Exception as e:
        log.error(f"  Fetch failed: {e} — no data this run")
        empty_macro = {
            "vix": None, "yield_10y_change": None, "nasdaq_vs_spx_20d": None,
            "data_missing": ["vix", "yield_10y_change", "nasdaq_vs_spx_20d"],
        }
        return {"sub_layers": {}, "meta": {"generic_feed_failures": [], **session_meta}}, empty_macro


def stage_score(market_data: dict, macro_data: dict) -> dict:
    """
    Score every ticker, then build a market-cap weighted sub-layer score.
    A ticker with score=None ("insufficient data") is excluded from the
    aggregate — but surfaced via tickers_scored/tickers_total/insufficient,
    never silently dropped (decision #6).
    """
    log.info("[2/2] Calculating scores...")
    from score_engine import ScoreEngine
    from render import load_scores_history
    engine  = ScoreEngine(macro_data)
    results = {}

    meta     = market_data.get("meta", {})
    sessions = [datetime.date.fromisoformat(s) for s in meta["sessions"]]
    current  = datetime.date.fromisoformat(meta["session"])
    history  = load_scores_history()

    sub_layers = market_data.get("sub_layers", {})
    for layer_id, tickers_data in sub_layers.items():
        if not tickers_data:
            log.warning(f"  {layer_id}: no ticker data — skipping")
            continue

        layer_scores = []
        insufficient = []
        for ticker_data in tickers_data:
            ticker = ticker_data.get("ticker", "?")
            try:
                result = engine.process_sector(layer_id, ticker_data)
            except Exception as e:
                log.warning(f"  {layer_id}/{ticker}: unexpected scoring error — {e}")
                insufficient.append({"ticker": ticker, "reason": f"scoring error: {e}"})
                continue

            if result.get("score") is None:
                insufficient.append({"ticker": ticker, "reason": result.get("status", "insufficient data")})
                continue

            result["ticker"]           = ticker
            result["name"]             = ticker_data.get("name", "")
            result["price"]            = ticker_data.get("price")
            result["price_30d_return"] = ticker_data.get("price_30d_return")
            result["vol_spike"]        = ticker_data.get("vol_spike")
            result["news_velocity"]    = ticker_data.get("news_velocity")
            result["market_cap"]       = ticker_data.get("market_cap")
            layer_scores.append(result)

        if not layer_scores:
            log.warning(f"  {layer_id}: all {len(tickers_data)} ticker(s) insufficient data — sub-layer unscored")
            results[layer_id] = {
                "best":           None,
                "all_tickers":    [],
                "layer_id":       layer_id,
                "weighted_score": None,
                "layer_color":    None,
                "layer_status":   "Insufficient data — no scoreable tickers this run",
                "tickers_scored": 0,
                "tickers_total":  len(tickers_data),
                "insufficient":   insufficient,
            }
            continue

        # ── Market-cap weighted sub-layer score ─────────────────────────────
        # Degenerates correctly to N=1 for single-ticker sub-layers
        # (decision #2) — no special-casing needed.
        total_mcap = sum((t.get("market_cap") or 0) for t in layer_scores)

        if total_mcap > 0:
            weighted_score = sum(
                t["score"] * ((t.get("market_cap") or 0) / total_mcap)
                for t in layer_scores
            )
        else:
            weighted_score = sum(t["score"] for t in layer_scores) / len(layer_scores)

        weighted_score = round(min(100, max(0, weighted_score)), 2)

        # ── Bottleneck leader boost ──────────────────────────────────────────
        # Only candidates with a computable fund_delta — a None delta must
        # not be silently ranked as 0 (decision #6): that could hide a real
        # leader, or fabricate one from a ticker whose delta simply wasn't
        # computable this run.
        delta_candidates = [t for t in layer_scores if t.get("fund_delta") is not None]
        if delta_candidates:
            best_by_delta  = max(delta_candidates, key=lambda x: x["fund_delta"])
            top_fund_delta = best_by_delta["fund_delta"]
        else:
            best_by_delta  = None
            top_fund_delta = None

        if top_fund_delta is not None and top_fund_delta > 0.40 and weighted_score < 45:
            old_score = weighted_score
            weighted_score = max(weighted_score, 45.0)
            log.info(f"  Bottleneck leader boost: {best_by_delta.get('ticker','?')} "
                     f"delta={top_fund_delta:.2f} -> floor 45 (was {old_score:.1f})")

        weighted_score = round(min(100, max(0, weighted_score)), 2)

        # ── Determine sub-layer color ────────────────────────────────────────
        best_ticker = max(layer_scores, key=lambda x: x["score"])
        layer_color, layer_status = _layer_color_from_score(weighted_score, top_fund_delta)

        # ── Red reality check ────────────────────────────────────────────────
        layer_color, reality_status = _red_reality_check(layer_scores, tickers_data, layer_color)
        if reality_status:
            layer_status = reality_status

        # ── 3-day color confirmation ─────────────────────────────────────────
        layer_color, confirm_note, confirm_branch = _confirmed_color(
            weighted_score, layer_color, layer_id, top_fund_delta,
            history, sessions, current,
        )
        if confirm_note:
            layer_status = confirm_note

        best = dict(best_ticker)
        best["color"]  = layer_color
        best["score"]  = weighted_score
        best["status"] = layer_status

        results[layer_id] = {
            "best":           best,
            "all_tickers":    layer_scores,
            "layer_id":       layer_id,
            "weighted_score": weighted_score,
            "layer_color":    layer_color,
            "layer_status":   layer_status,
            "confirm_note":   confirm_note,
            "history_insufficient": confirm_branch == NO_HISTORY,
            "tickers_scored": len(layer_scores),
            "tickers_total":  len(tickers_data),
            "insufficient":   insufficient,
        }

        log.info(
            f"  {layer_id}: weighted={weighted_score:.1f} color={layer_color} "
            f"({len(layer_scores)}/{len(tickers_data)} tickers scored, "
            f"best={best_ticker['ticker']} score={best_ticker['score']:.1f})"
        )

    return results


def stage_capex() -> dict:
    """
    Capex direction overlay (PLAN.md step 5b, decision #1: display overlay
    only — never fed into ScoreEngine or its weights, independent of
    stage_score()).

    Aggregation rule: average capex_yoy_pct across only the REPORTING
    hyperscalers (excluding any with data_missing), then classify that
    average against CAPEX_YOY_ACCELERATING_PCT/DECELERATING_PCT. Chosen
    over a majority-vote-of-labels approach because individual hyperscalers
    can vary by 30+ points while all being genuinely "accelerating" (the 4b
    real spread was 76.7-109.6%) — a single averaged magnitude is more
    informative than collapsing that to a vote, and matches decision #4's
    "show magnitude, not just the label" principle.

    Partial-reporting rule (config.CAPEX_MIN_REPORTING = 2): fewer than 2 of
    4 hyperscalers reporting means direction/magnitude_pct are None
    ("insufficient data") rather than computed from a 1-company sample
    mislabeled as an aggregate. Honest caveat (see config.py comment): this
    only really justifies ">=2", not "2 rather than 3" — 3 (majority-of-4)
    would be a legitimate, more conservative alternative given GOOGL's
    documented fragility, but that tradeoff wasn't actually weighed when 2
    was picked. Untested against real data as of 2026-09-18 (every run so
    far has been 4/4) — documented so the rule exists before the branch is
    ever exercised, not discovered later.

    "reporting" (e.g. "3/4") and "insufficient" (ticker + reason) are
    always present, even at 4/4 — decision #4's "don't drop an
    insufficient-data ticker from the aggregate silently" rule.
    """
    from fetch_market import fetch_capex_trend
    from config import CAPEX_YOY_ACCELERATING_PCT, CAPEX_YOY_DECELERATING_PCT, \
        CAPEX_MIN_REPORTING, CAPEX_BENEFICIARY_MAP, CAPEX_TICKERS

    capex = fetch_capex_trend()
    reporting = [c for c in capex if not c["data_missing"]]
    insufficient = [
        {"ticker": c["ticker"], "reason": f"missing: {c['data_missing']}"}
        for c in capex if c["data_missing"]
    ]

    if len(reporting) < CAPEX_MIN_REPORTING:
        log.warning(f"  Capex: only {len(reporting)}/{len(capex)} hyperscalers reporting "
                    f"(minimum {CAPEX_MIN_REPORTING}) — direction insufficient data")
        return {
            "direction":       None,
            "magnitude_pct":   None,
            "reporting":       f"{len(reporting)}/{len(capex)}",
            "insufficient":    insufficient,
            "beneficiary_map": CAPEX_BENEFICIARY_MAP,
        }

    magnitude_pct = round(sum(c["capex_yoy_pct"] for c in reporting) / len(reporting), 4)

    if magnitude_pct > CAPEX_YOY_ACCELERATING_PCT:
        direction = "accelerating"
    elif magnitude_pct < CAPEX_YOY_DECELERATING_PCT:
        direction = "decelerating"
    else:
        direction = "stable"

    log.info(f"  Capex: {direction} ({magnitude_pct*100:.1f}% avg YoY, "
             f"{len(reporting)}/{len(capex)} hyperscalers reporting)")

    return {
        "direction":       direction,
        "magnitude_pct":   magnitude_pct,
        "reporting":       f"{len(reporting)}/{len(capex)}",
        "insufficient":    insufficient,
        "beneficiary_map": CAPEX_BENEFICIARY_MAP,
    }


def stage_render(market_data: dict, macro_data: dict, scored_data: dict, capex_data: dict) -> str:
    """
    Writes index.html at repo root (GitHub Pages bare-URL requirement,
    CLAUDE.md) and prints the console summary. analyze.py's AI narrative
    and next_nvidia.py's radar aren't part of this pipeline (see
    render.py's module docstring) — this is fetch -> score -> capex ->
    render only.
    """
    log.info("[3/3] Rendering dashboard...")
    from render import generate_dashboard, deliver
    html_path = generate_dashboard(scored_data, macro_data, market_data, capex_data)
    deliver(html_path)
    return html_path


def run_full_pipeline():
    market_data, macro_data = stage_fetch()
    scored_data = stage_score(market_data, macro_data)
    capex_data  = stage_capex()
    stage_render(market_data, macro_data, scored_data, capex_data)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="RayDar Data Center — pipeline (steps 5a/5b/6: fetch + score, capex overlay, render)"
    )
    parser.add_argument("--score", action="store_true",
                        help="Fetch + score only.")
    parser.add_argument("--capex", action="store_true",
                        help="Capex direction overlay only (5b) — aggregate direction + beneficiary map.")
    parser.add_argument("--now", action="store_true",
                        help="Full pipeline: fetch -> score -> capex -> render index.html.")
    args = parser.parse_args()

    if args.now:
        run_full_pipeline()
    elif args.capex:
        print(json.dumps(stage_capex(), indent=2))
    elif args.score:
        market_data, macro_data = stage_fetch()
        scored_data = stage_score(market_data, macro_data)
        print(json.dumps(
            {k: {
                "weighted_score": v.get("weighted_score"),
                "color":          v.get("layer_color"),
                "status":         v.get("layer_status"),
                "tickers_scored": v.get("tickers_scored"),
                "tickers_total":  v.get("tickers_total"),
                "best_ticker":    v["best"]["ticker"] if v.get("best") else None,
                "best_score":     v["best"]["score"] if v.get("best") else None,
                "insufficient":   v.get("insufficient", []),
             }
             for k, v in scored_data.items()
            }, indent=2))
    else:
        print("Available: --score (fetch+score), --capex (5b capex overlay), "
              "--now (full pipeline: fetch -> score -> capex -> render).\n"
              "analyze.py/publish.py (PLAN.md step 7 deploy plumbing) don't exist yet — "
              "--now writes index.html but doesn't auto-publish.")
