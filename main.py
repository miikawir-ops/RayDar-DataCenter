"""
main.py — Pipeline orchestration for RayDar Data Center (PLAN.md step 5a).

Scope of this file right now: fetch + score only (aggregation). analyze.py,
render.py, next_nvidia.py, publish.py don't exist yet (PLAN.md steps 6-7) —
this deliberately doesn't wire up a full run_full_pipeline()/scheduler
against files that aren't built, matching the same "don't get ahead of the
build order" discipline used for score_engine.py (step 3) and capex (5b).

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
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger(__name__)

SCORES_HISTORY_FILE = "scores_history.json"

# Rating quality map — used for Red reality check once render.py (step 6)
# starts assigning ratings. Kept here so the check is future-proofed rather
# than needing this reintroduced later.
RATING_QUALITY = {"A": 4, "B": 3, "C": 2, "D": 1}


# ── Score history helpers (read-only here — see module docstring) ─────────────

def _load_recent_layer_scores(layer_id: str, days: int = 3) -> list[float]:
    """
    Load the last N days of weighted scores for a specific sub-layer from
    scores_history.json. Used for color confirmation. Returns list of
    scores, most recent last. Empty list if no history.
    """
    p = Path(SCORES_HISTORY_FILE)
    if not p.exists():
        return []
    try:
        history = json.loads(p.read_text())
        if not isinstance(history, list):
            return []
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        prev_days = [e for e in history if e.get("date") != today]
        recent = prev_days[-days:]
        return [
            e.get("scores", {}).get(layer_id, {}).get("score", 0)
            for e in recent
        ]
    except Exception:
        return []


def _confirmed_color(
    today_score: float,
    today_color: str,
    layer_id: str,
    top_fund_delta: float | None,
) -> tuple[str, str]:
    """
    3-day color confirmation system — unchanged from reference. A color
    change requires confirmation across multiple daily runs to prevent
    single-day data noise from flipping the dashboard signal.

    INSTANT RED   — today_score > 80, OR top_fund_delta > 0.60
    CONFIRMED RED — today > 65 AND 2+ of last 3 days also > 55
    CONFIRMED ORANGE — today >= 45 AND 2+ of last 3 days also >= 40
    CONFIRMED BLUE — today < 25 AND 2+ of last 3 days also < 30
    DEFAULT GREEN — if today's signal can't be confirmed by history
    """
    recent = _load_recent_layer_scores(layer_id, days=3)

    if len(recent) < 2:
        note = "unconfirmed (insufficient history — building baseline)"
        log.debug(f"  {layer_id}: {today_color} unconfirmed — only {len(recent)} history days")
        return today_color, note

    if today_score > 80:
        log.info(f"  {layer_id}: instant Red — extreme score {today_score:.1f} > 80")
        return "Red", f"Instant Red — extreme score {today_score:.1f}"

    if top_fund_delta and top_fund_delta > 0.60:
        log.info(f"  {layer_id}: instant Red — fund_delta {top_fund_delta:.2f} > 0.60")
        return "Red", f"Instant Red — strong fundamental acceleration delta={top_fund_delta:.2f}"

    days_above_55  = sum(1 for s in recent if s > 55)
    days_above_40  = sum(1 for s in recent if s >= 40)
    days_below_30  = sum(1 for s in recent if s < 30)

    if today_score > 65 and days_above_55 >= 2:
        return "Red", f"Confirmed Red — {days_above_55}/3 recent days above 55"

    if today_score >= 45 and days_above_40 >= 2:
        return "Orange", f"Confirmed Orange — {days_above_40}/3 recent days above 40"

    if today_score < 25 and days_below_30 >= 2:
        return "Blue", f"Confirmed Blue — {days_below_30}/3 recent days below 30"

    prev_colors = []
    try:
        p = Path(SCORES_HISTORY_FILE)
        if p.exists():
            history = json.loads(p.read_text())
            today_str = datetime.datetime.now().strftime("%Y-%m-%d")
            prev = [e for e in history if e.get("date") != today_str]
            prev_colors = [
                e.get("scores", {}).get(layer_id, {}).get("color", "")
                for e in prev[-3:]
                if e.get("scores", {}).get(layer_id, {}).get("color")
            ]
    except Exception:
        prev_colors = []

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
            return dominant, f"Holding {dominant} — borderline score, prev 3d dominant"

    note = f"Unconfirmed — score {today_score:.1f} not sustained in history"
    log.info(f"  {layer_id}: {today_color} -> Green (unconfirmed, fallback)")
    if 25 <= today_score < 45:
        return "Green", note
    return today_color, note


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
    """
    log.info("[1/2] Fetching market data...")
    try:
        from fetch_market import run_pipeline, fetch_macro
        market_data = run_pipeline()
        macro_data  = fetch_macro()
        log.info(f"  Fetched {len(market_data.get('sub_layers', {}))} sub-layers, "
                 f"macro: VIX={macro_data.get('vix')}")
        return market_data, macro_data
    except Exception as e:
        log.error(f"  Fetch failed: {e} — no data this run")
        empty_macro = {
            "vix": None, "yield_10y_change": None, "nasdaq_vs_spx_20d": None,
            "data_missing": ["vix", "yield_10y_change", "nasdaq_vs_spx_20d"],
        }
        return {"sub_layers": {}, "meta": {"generic_feed_failures": []}}, empty_macro


def stage_score(market_data: dict, macro_data: dict) -> dict:
    """
    Score every ticker, then build a market-cap weighted sub-layer score.
    A ticker with score=None ("insufficient data") is excluded from the
    aggregate — but surfaced via tickers_scored/tickers_total/insufficient,
    never silently dropped (decision #6).
    """
    log.info("[2/2] Calculating scores...")
    from score_engine import ScoreEngine
    engine  = ScoreEngine(macro_data)
    results = {}

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
        layer_color, confirm_note = _confirmed_color(
            weighted_score, layer_color, layer_id, top_fund_delta
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


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="RayDar Data Center — pipeline (step 5a: fetch + score only)"
    )
    parser.add_argument("--score", action="store_true",
                        help="Fetch + score. Only mode available — "
                             "analyze/render/deploy (PLAN.md steps 6-7) aren't built yet.")
    args = parser.parse_args()

    if not args.score:
        print("Only --score is available right now — analyze.py/render.py/publish.py "
              "(PLAN.md steps 6-7) don't exist yet.\nRun: python main.py --score")
    else:
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
