"""
render.py — HTML dashboard generator for RayDar Data Center (PLAN.md step 6).

Adapted from reference/render.py (1782 lines). Reuses the dark hero, laser
beam, chain status bar, sub-layer cards with ratings/forecasts, expand
panels, and heat trail (Part A5/A6) — with fixes and deliberate scope cuts,
both stated explicitly here and in the commit message, not left as silent
omissions.

Fixed during the port (decision #6 — same anti-pattern as every other file
this session, just at the render layer this time):
  - company_rating()/rating_forecast(): reference did
    `(t_scored.get("fund_delta") or 0) * 100` — a None fund_delta (delta
    genuinely uncomputable) silently became 0, and company_rating() turned
    that into a real-looking "B" grade, indistinguishable from a ticker
    with a genuinely flat, known delta. Now: delta=None -> rating=None,
    rendered as a muted "—" badge, never a fabricated letter grade.
  - rating_forecast()'s elif chain had no guard for a missing rating — it
    would silently fall through to the `else: # D` branch, mislabeling
    missing data as a real D-rated failing company. Guarded explicitly now.
  - save_scores_history() assumed `result["best"]` is always a dict
    (checked via `"best" in result`, then `.get(...)`) — but 5a's design
    means `best` can be `None` (every ticker in a sub-layer insufficient).
    Fixed to check `result.get("best")` truthy, not just key presence.
  - Macro card values: reference did `macro_data.get("vix", 0)` — the same
    bug already fixed in fetch_macro()/score_engine.py this session (a
    `.get(key, default)` default is never used when the key is present
    with value `None`). Missing macro fields now show "—" instead of a
    fabricated 0 or crashing on `None > 30`.

Dropped, explicitly:
  - Next Nvidia Radar section — next_nvidia.py doesn't exist, no
    equivalent in Part B.
  - AI-generated analysis narrative / "One Action" pick / track record —
    analyze.py doesn't exist, no equivalent in this project's spec.
  - EARNINGS_WATCH / earnings-soon badges — reference hardcoded specific
    per-ticker earnings-month guesses with no real data source backing
    them. Fabricating dates would violate the core data-honesty rule
    (CLAUDE.md), so this feature is dropped rather than carried over with
    invented dates.
  - Email/Telegram delivery — no .env/secrets configured for this
    project, no deploy target yet (PLAN.md step 7). Delivery is HTML file
    + console print only.

Added (5b overlay, decision #1 — visually distinct from sub-layer scores,
never blended into them): capex direction strip + beneficiary-map display,
positioned above the sub-layer cards.
"""

import json
import logging
import datetime
from pathlib import Path

from config import SUB_LAYERS

log = logging.getLogger(__name__)

SCORES_HISTORY_FILE = "scores_history.json"
MAX_HISTORY_DAYS    = 30

CC = {
    "Red":    {"bg": "#FCEBEB", "border": "#E24B4A", "pill": "#E24B4A", "pft": "#FCEBEB", "lbl": "Hot",     "tc": "#791F1F"},
    "Orange": {"bg": "#FAEEDA", "border": "#EF9F27", "pill": "#EF9F27", "pft": "#FAEEDA", "lbl": "Emerging", "tc": "#633806"},
    "Green":  {"bg": "#EAF3DE", "border": "#639922", "pill": "#639922", "pft": "#EAF3DE", "lbl": "Neutral",  "tc": "#27500A"},
    "Blue":   {"bg": "#E6F1FB", "border": "#378ADD", "pill": "#378ADD", "pft": "#E6F1FB", "lbl": "Cooling",  "tc": "#0C447C"},
}

SUB_LAYER_SUBTITLES = {
    "cooling":    "liquid cooling",
    "networking": "switch silicon",
    "optical":    "800G → 1.6T",
    "compute":    "server integration",
    "colocation": "data center real estate",
}


def company_rating(delta: float | None, color: str, is_hype: bool) -> str | None:
    """
    A/B/C/D rating for individual companies. Returns None (not a
    fabricated letter) when delta is None — see module docstring.
    """
    if delta is None:
        return None
    if color in ("Red", "Orange") and delta > 20 and not is_hype:
        return "A"
    elif color in ("Red", "Orange", "Green") and delta > 0 and not is_hype:
        return "B"
    elif is_hype or delta < -5:
        return "C"
    elif delta < 0:
        return "C"
    else:
        return "B"


def rating_forecast(current_rating: str | None, delta: float | None, delta_band: str,
                    is_hype: bool, color: str) -> dict:
    """
    Forecast where rating is heading based on momentum signals. Explicit
    guard for a missing rating — reference's elif chain had none, so a
    missing rating would silently fall through to `else: # D`.
    """
    if current_rating is None:
        return {"direction": "—", "target": None, "label": "Insufficient data",
                "color": "#888780", "reason": "fund_delta could not be computed this run"}

    accelerating   = delta_band == "accelerating"
    decelerating   = delta_band == "decelerating"
    hot_layer      = color in ("Red", "Orange")
    real_hype_risk = is_hype and delta < 0

    if current_rating == "A":
        if decelerating and real_hype_risk:
            return {"direction": "↓", "target": "C", "label": "Warning — hype peaking",
                    "color": "#E24B4A", "reason": "Growth decelerating with hype risk"}
        elif decelerating:
            return {"direction": "↓", "target": "B", "label": "Watch for pullback",
                    "color": "#EF9F27", "reason": "Growth decelerating from peak"}
        else:
            return {"direction": "→", "target": "A", "label": "Holding strong",
                    "color": "#27500A", "reason": "Sustained acceleration"}
    elif current_rating == "B":
        if accelerating and hot_layer:
            return {"direction": "↑", "target": "A", "label": "Upgrade likely",
                    "color": "#27500A", "reason": "Accelerating into bottleneck layer"}
        elif real_hype_risk or (decelerating and delta < -10):
            return {"direction": "↓", "target": "C", "label": "Downgrade risk",
                    "color": "#E24B4A", "reason": "Growth slowing with hype or sharp delta drop"}
        elif decelerating:
            return {"direction": "↓", "target": "C", "label": "Watch closely",
                    "color": "#EF9F27", "reason": "Growth decelerating — monitor next quarter"}
        else:
            return {"direction": "→", "target": "B", "label": "Stable",
                    "color": "#378ADD", "reason": "Fundamentals holding steady"}
    elif current_rating == "C":
        if accelerating and not real_hype_risk:
            return {"direction": "↑", "target": "B", "label": "Recovery signal",
                    "color": "#EF9F27", "reason": "Momentum improving — watch for confirmation"}
        elif real_hype_risk and decelerating:
            return {"direction": "↓", "target": "D", "label": "Avoid",
                    "color": "#E24B4A", "reason": "Hype unwinding with deteriorating fundamentals"}
        else:
            return {"direction": "→", "target": "C", "label": "Still cautious",
                    "color": "#EF9F27", "reason": "No clear recovery signal yet"}
    else:  # D
        if accelerating:
            return {"direction": "↑", "target": "C", "label": "Early recovery",
                    "color": "#EF9F27", "reason": "Momentum turning — confirm next quarter"}
        return {"direction": "→", "target": "D", "label": "Avoid",
                "color": "#E24B4A", "reason": "No recovery signals yet"}


# ── History helpers ───────────────────────────────────────────────────────────

def load_scores_history() -> list:
    """
    Load scores history from disk. Handles: missing file -> []; current
    list format -> as-is; legacy dict format -> converted; corrupt file ->
    logged, []. Prevents scores_history.json from being silently wiped on
    format mismatch.
    """
    p = Path(SCORES_HISTORY_FILE)
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text())
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            log.warning("scores_history.json is in legacy dict format — converting to list.")
            converted = [{"date": k, "scores": v} for k, v in data.items()]
            return sorted(converted, key=lambda x: x.get("date", ""))
        log.warning(f"scores_history.json unexpected type {type(data)} — starting fresh")
        return []
    except Exception as e:
        log.warning(f"scores_history.json unreadable ({e}) — starting fresh")
        return []


def save_scores_history(scored_data: dict):
    """
    Writes scores_history.json — the write side main.py's 3-day color
    confirmation has been waiting on since 5a. No action_ticker/
    action_price params (dropped with the "One Action" feature).
    result.get("best") truthy-checked, not "best" in result — 5a's design
    means best can be explicitly None (every ticker insufficient).
    """
    history = load_scores_history()
    today   = datetime.datetime.now().strftime("%Y-%m-%d")
    history = [e for e in history if e.get("date") != today]
    history.append({
        "date": today,
        "time": datetime.datetime.now().strftime("%H:%M"),
        "scores": {
            layer_id: {
                "score": result["best"].get("score"),
                "color": result["best"].get("color"),
                "ratings": {
                    t.get("ticker"): company_rating(
                        t.get("fund_delta"),
                        t.get("color", "Green"),
                        t.get("is_hype", False),
                    )
                    for t in result.get("all_tickers", [])
                    if t.get("ticker")
                },
            }
            for layer_id, result in scored_data.items()
            if result.get("best")
        },
    })
    history = history[-MAX_HISTORY_DAYS:]
    Path(SCORES_HISTORY_FILE).write_text(json.dumps(history, indent=2))
    log.info(f"  Scores history saved ({len(history)} days)")


def get_yesterday_scores(scored_data: dict) -> dict:
    """Returns {layer_id: {score, color, ratings}} for the most recent previous run."""
    history = load_scores_history()
    today   = datetime.datetime.now().strftime("%Y-%m-%d")
    prev    = [e for e in history if e.get("date") != today]
    if not prev:
        return {}
    return prev[-1].get("scores", {})


# ── Ticker lookup ─────────────────────────────────────────────────────────────

def build_ticker_lookup(market_data: dict) -> dict:
    """market_data is {"sub_layers": {...}, "meta": {...}} per fetch_market.run_pipeline()."""
    lookup = {}
    for tickers in market_data.get("sub_layers", {}).values():
        for t in (tickers or []):
            if t and t.get("ticker"):
                lookup[t["ticker"]] = t
    return lookup


# ── JS data builders ──────────────────────────────────────────────────────────

def _chain_js_data(scored_data: dict, market_data: dict, yesterday: dict) -> str:
    """
    Build the LAYERS JS array. A sub-layer with best=None (every ticker
    insufficient, 5a) gets an explicit insufficient-data entry — never
    silently skipped or defaulted to a fake score (decision #6).
    """
    ticker_lookup = build_ticker_lookup(market_data)
    yesterday_ratings = {}
    for layer_scores in yesterday.values():
        for ticker, rating in layer_scores.get("ratings", {}).items():
            yesterday_ratings[ticker] = rating
    layers = []

    for layer_id, layer_result in scored_data.items():
        best = layer_result.get("best")
        n1 = SUB_LAYERS.get(layer_id, {}).get("name", layer_id.capitalize())
        n2 = SUB_LAYER_SUBTITLES.get(layer_id, "")

        if not best:
            layers.append({
                "id": layer_id, "n1": n1, "n2": n2,
                "score": None, "color": None, "insufficient": True,
                "tickers_scored": layer_result.get("tickers_scored", 0),
                "tickers_total":  layer_result.get("tickers_total", 0),
                "insufficient_reasons": layer_result.get("insufficient", []),
                "tickers": [], "news_vel": None, "momentum_label": "",
                "delta_score": None, "prev_color": "", "color_changed": False,
                "divergence": False, "divergence_msg": "",
            })
            continue

        color      = best.get("color", "Green")
        score      = round(best.get("score", 0), 1)
        all_scores = layer_result.get("all_tickers", [])

        prev       = yesterday.get(layer_id, {})
        prev_score = prev.get("score")
        prev_color = prev.get("color", "")
        if prev_score is not None:
            delta_score   = round(score - prev_score, 1)
            color_changed = color != prev_color
        else:
            delta_score   = None
            color_changed = False

        news_vals = [ts.get("news_velocity") for ts in all_scores if ts.get("news_velocity") is not None]
        news_vel  = news_vals[0] if news_vals else None

        fund_delta = best.get("fund_delta")

        tickers_out = []
        for t_scored in all_scores[:4]:
            sym   = t_scored.get("ticker", "")
            raw   = ticker_lookup.get(sym, {})
            t_fd  = t_scored.get("fund_delta")
            raw_delta = t_fd * 100 if t_fd is not None else None
            if raw_delta is None:
                delta_band = "unknown"
            elif raw_delta > 5:
                delta_band = "accelerating"
            elif raw_delta < -5:
                delta_band = "decelerating"
            else:
                delta_band = "stable"
            hist_raw  = raw.get("price_history", [])
            sparkline = [round(p, 2) for p in hist_raw[-30:]] if hist_raw else []
            t_color   = t_scored.get("color", "Green")
            t_hype    = t_scored.get("is_hype", False)
            t_rating  = company_rating(t_fd, t_color, t_hype)
            t_prev_rating  = yesterday_ratings.get(sym, "")
            rating_changed = bool(t_prev_rating) and bool(t_rating) and t_prev_rating != t_rating
            ret30    = t_scored.get("price_30d_return")
            price    = t_scored.get("price") if t_scored.get("price") is not None else raw.get("price")
            rev_q    = raw.get("revenue_quarterly")
            w52h     = raw.get("week52_high")
            tickers_out.append({
                "sym":          sym or "?",
                "name":         t_scored.get("name") or raw.get("name") or sym or "?",
                "price":        price,
                "ret30":        round(ret30 * 100, 1) if ret30 is not None else None,
                "delta_band":   delta_band,
                "hype":         t_hype,
                "color":        t_color,
                "sparkline":    sparkline,
                "rating":       t_rating,
                "prev_rating":  t_prev_rating,
                "rating_up":    rating_changed and t_rating is not None and t_prev_rating in ("A","B","C","D") and ord(t_rating) < ord(t_prev_rating),
                "rating_down":  rating_changed and t_rating is not None and t_prev_rating in ("A","B","C","D") and ord(t_rating) > ord(t_prev_rating),
                "forecast":     rating_forecast(t_rating, t_fd, delta_band, t_hype, t_color),
                "run_rate":     round(rev_q * 4 / 1e9, 1) if rev_q else None,
                "pct_of_high":  round((price / w52h) * 100) if price and w52h else None,
                "week52_high":  w52h,
                "week52_low":   raw.get("week52_low"),
                "data_missing": t_scored.get("data_missing", []),
            })

        if fund_delta is not None:
            momentum_band  = "strong" if abs(fund_delta * 100) > 20 else "moderate" if abs(fund_delta * 100) > 5 else "mild"
            momentum_label = f"{'+' if fund_delta >= 0 else '-'}{momentum_band}"
        else:
            momentum_label = "unknown"

        divergence     = False
        divergence_msg = ""
        if fund_delta is not None and news_vel is not None:
            if news_vel >= 4 and fund_delta < -0.05:
                divergence     = True
                divergence_msg = ("News narrative is active but revenue growth is decelerating. "
                                   "The market story is running ahead of reported financials.")
            elif news_vel >= 5 and fund_delta < 0.03 and color == "Green":
                divergence     = True
                divergence_msg = ("News activity detected but fundamental acceleration is weak. "
                                   "Watch for confirmation in next results before positioning.")
            elif news_vel == 0 and color == "Green" and fund_delta < 0:
                divergence     = True
                divergence_msg = ("Revenue growth is decelerating with no supporting news signal. "
                                   "Fundamentals are weakening — monitor for further deterioration.")

        layers.append({
            "id": layer_id, "n1": n1, "n2": n2,
            "score": score, "color": color, "insufficient": False,
            "tickers_scored": layer_result.get("tickers_scored"),
            "tickers_total":  layer_result.get("tickers_total"),
            "news_vel": news_vel, "momentum_label": momentum_label,
            "delta_score": delta_score, "prev_color": prev_color, "color_changed": color_changed,
            "tickers": tickers_out,
            "divergence": divergence, "divergence_msg": divergence_msg,
        })

    return json.dumps(layers)


def _history_js_data(history: list, scored_data: dict) -> str:
    layer_ids = list(scored_data.keys())
    date_map  = {e["date"]: e.get("scores", {}) for e in history}
    today     = datetime.datetime.now().date()
    days_out  = []
    for i in range(89, -1, -1):
        d     = today - datetime.timedelta(days=i)
        d_str = d.strftime("%Y-%m-%d")
        day_data = {"date": d_str, "label": d.strftime("%b %d"), "short": d.strftime("%d"), "layers": {}}
        scores = date_map.get(d_str, {})
        for lid in layer_ids:
            day_data["layers"][lid] = scores[lid].get("color", "none") if lid in scores else "none"
        days_out.append(day_data)
    return json.dumps({"layer_ids": layer_ids, "days": days_out})


def _capex_js_data(capex_data: dict) -> str:
    """Passthrough of main.py's stage_capex() output — already shaped correctly."""
    default = {"direction": None, "magnitude_pct": None, "reporting": "0/0",
               "insufficient": [], "beneficiary_map": {}}
    return json.dumps(capex_data or default)


# ── Company context (static profile text, not dynamic data — see D3) ──────────

COMPANY_CONTEXT = {
    "VRT":   "Vertiv makes liquid cooling systems for dense GPU clusters. As GPU power density rises, air cooling fails — Vertiv's moment is now.",
    "ANET":  "Arista Networks makes the high-speed ethernet switches connecting GPU clusters, central to the Ultra Ethernet Consortium's AI networking push.",
    "CSCO":  "Cisco provides networking backbone for enterprise AI deployments, pivoting its silicon and software strategy around data center switching.",
    "CIEN":  "Ciena makes optical networking equipment — the bandwidth pipes connecting AI data centers across distances, critical for multi-site clusters.",
    "LITE":  "Lumentum makes optical components and transceivers for the 800G/1.6T bandwidth transition inside and between data centers.",
    "COHR":  "Coherent supplies optical and photonic components — transceivers, lasers, and materials used in AI data center interconnects.",
    "GLW":   "Corning makes the fiber optic cable and glass infrastructure that data center interconnects and long-haul AI networking run on.",
    "SMCI":  "Super Micro Computer builds AI-optimized server racks, fastest to market with liquid-cooled GPU servers.",
    "DELL":  "Dell Technologies builds AI server infrastructure at hyperscaler and enterprise scale, a major GPU server integrator.",
    "HPE":   "Hewlett Packard Enterprise builds AI servers and networking gear, expanding its AI infrastructure and services portfolio.",
    "EQIX":  "Equinix operates 260+ data centers globally. AI workloads need colocation space close to fiber interconnects — Equinix's core offering.",
    "DLR":   "Digital Realty operates hyperscale and colocation data center capacity globally, a direct beneficiary of AI-driven facility demand.",
    "MSFT":  "Microsoft's Azure AI services and Copilot are the monetization vehicle for one of the largest AI capex programs in history.",
    "GOOGL": "Google runs Gemini models on Google Cloud and designs its own TPU AI chips — vertically integrated from silicon to application.",
    "AMZN":  "AWS is the largest cloud provider; Amazon Bedrock offers multi-model AI access, alongside custom Trainium/Inferentia chips.",
    "META":  "Meta open-sources LLaMA models and is running one of the largest AI infrastructure capex programs of any hyperscaler.",
}


# ── Master HTML builder ───────────────────────────────────────────────────────

def generate_dashboard(scored_data: dict, macro_data: dict, market_data: dict = None,
                       capex_data: dict = None) -> str:
    if market_data is None:
        market_data = {"sub_layers": {}, "meta": {}}
    if capex_data is None:
        capex_data = {"direction": None, "magnitude_pct": None, "reporting": "0/0",
                       "insufficient": [], "beneficiary_map": {}}

    save_scores_history(scored_data)

    yesterday    = get_yesterday_scores(scored_data)
    full_history = load_scores_history()
    now          = datetime.datetime.now()
    date_str     = now.strftime("%A, %B %d %Y")
    time_str     = now.strftime("%H:%M")
    datetime_str = f"{date_str} · {time_str}"
    fetch_note   = f"Fetched {time_str} · Quarterly financials may be up to 90 days old"

    vix          = macro_data.get("vix")
    yield_ch     = macro_data.get("yield_10y_change")
    nasdaq_raw   = macro_data.get("nasdaq_vs_spx_20d")
    nasdaq_r     = nasdaq_raw * 100 if nasdaq_raw is not None else None

    if vix is None and yield_ch is None and nasdaq_r is None:
        reg_lbl = "Market regime: Unknown (macro data unavailable)"
    elif (vix is not None and vix > 30) or (yield_ch is not None and yield_ch > 100):
        reg_lbl = "Market regime: Risk-Off"
    elif (vix is not None and vix > 20) or (yield_ch is not None and yield_ch > 50):
        reg_lbl = "Market regime: Neutral"
    else:
        reg_lbl = "Market regime: Risk-On"

    vix_disp    = f"{vix:.1f}" if vix is not None else "—"
    vix_note    = ("Low fear" if (vix is not None and vix < 20) else "Elevated" if vix is not None else "No data")
    vix_col     = "#C0DD97" if (vix is not None and vix < 20) else ("#FAC775" if vix is not None else "#888780")

    yield_disp  = f"{yield_ch:+.1f}" if yield_ch is not None else "—"
    yield_note  = ("falling" if (yield_ch is not None and yield_ch < 0) else "rising" if yield_ch is not None else "no data")
    yield_col   = "#C0DD97" if (yield_ch is not None and yield_ch < 0) else ("#FAC775" if yield_ch is not None else "#888780")

    nasdaq_disp = f"{nasdaq_r:+.1f}%" if nasdaq_r is not None else "—"
    nasdaq_note = ("Tech leading" if (nasdaq_r is not None and nasdaq_r > 0) else "Tech lagging" if nasdaq_r is not None else "No data")
    nasdaq_col  = "#C0DD97" if (nasdaq_r is not None and nasdaq_r > 0) else ("#FAC775" if nasdaq_r is not None else "#888780")

    total_tickers = sum(len(v) for v in market_data.get("sub_layers", {}).values())

    layers_js  = _chain_js_data(scored_data, market_data, yesterday)
    history_js = _history_js_data(full_history, scored_data)
    capex_js   = _capex_js_data(capex_data)
    has_yesterday = "true" if yesterday else "false"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>RayDar Data Center — bottleneck intelligence · {datetime_str}</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
      background:#0E1628;color:#1A1A1A;min-height:100vh;padding:0 0 32px}}
.hero{{background:linear-gradient(135deg,#08081A 0%,#0C1A3A 30%,#1A0830 60%,#0A0818 100%);
       padding:22px 24px 20px;position:relative;overflow:hidden}}
.hero-laser{{position:absolute;top:0;left:0;right:0;height:3px;
             background:linear-gradient(90deg,transparent 0%,transparent 10%,#534AB7 28%,#85B7EB 45%,#ffffff 50%,#85B7EB 55%,#534AB7 72%,transparent 90%,transparent 100%);
             opacity:0.9}}
.hero-glow{{position:absolute;top:0;left:10%;right:10%;height:40px;
            background:radial-gradient(ellipse at 50% 0%,rgba(133,183,235,0.45) 0%,rgba(83,74,183,0.2) 40%,transparent 75%)}}
.hero-accent{{position:absolute;bottom:-40px;right:-40px;width:200px;height:200px;
              background:radial-gradient(circle,rgba(60,52,137,0.15) 0%,transparent 70%)}}
.hero-top{{display:flex;justify-content:space-between;align-items:center;
           margin-bottom:14px;position:relative;flex-wrap:wrap;gap:8px}}
.hero-title{{font-size:22px;color:#fff;line-height:1.2;letter-spacing:-0.3px}}
.hero-sub{{font-size:11px;color:#8A9AB8;margin-top:3px}}
.hero-sibling-link{{font-size:12px;font-weight:600;color:#fff;text-decoration:none;
                    border:1px solid rgba(175,169,236,0.5);padding:4px 10px;border-radius:10px;
                    background:#3C3489;
                    box-shadow:0 0 8px rgba(133,183,235,0.35);
                    display:inline-flex;align-items:center;gap:4px;
                    transition:background .15s,box-shadow .15s}}
.hero-sibling-link:hover{{background:#4a3fb0;box-shadow:0 0 14px rgba(133,183,235,0.6)}}
.reg-pill{{font-size:11px;font-weight:500;padding:5px 14px;border-radius:20px;
           border:1px solid rgba(255,255,255,.3);color:#fff;
           background:rgba(255,255,255,.15);cursor:pointer;position:relative}}
.reg-pill:hover .reg-tooltip,.reg-pill:focus .reg-tooltip{{display:block}}
.reg-tooltip{{display:none;position:absolute;top:calc(100% + 8px);right:0;
              background:#1A1A1A;color:#F8F8F7;font-size:10px;line-height:1.6;
              padding:10px 12px;border-radius:6px;width:260px;z-index:200;
              font-weight:400;box-shadow:0 4px 16px rgba(0,0,0,.4);text-align:left}}
.reg-tooltip::before{{content:"";position:absolute;bottom:100%;right:16px;
                      border:5px solid transparent;border-bottom-color:#1A1A1A}}
.reg-tooltip b{{color:#97C459}}
.hm-grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:6px;position:relative}}
.hm-card{{background:rgba(255,255,255,.07);border:0.5px solid rgba(133,183,235,0.2);
          border-radius:8px;padding:5px 12px 6px}}
.hm-lbl{{font-size:9px;color:#85B7EB;margin-bottom:1px;letter-spacing:.06em;font-weight:500}}
.hm-val{{font-size:14px;font-weight:500;color:#fff;line-height:1.1}}
.hm-note{{font-size:9px;margin-top:1px;line-height:1.1}}
.body{{padding:16px 16px 0;margin-top:0;position:relative;
       background:linear-gradient(180deg,#0E1628 0%,#101C32 40%,#13182A 75%,#0F1420 100%);
       min-height:100vh}}
.card{{background:white;border:0.5px solid #E0DFDC;border-radius:12px;
       padding:16px;margin-bottom:12px}}
.card-label{{font-size:10px;font-weight:500;color:#888780;
             letter-spacing:.05em;margin-bottom:12px}}
.fetch-note{{font-size:10px;color:#B4B2A9;margin-top:4px}}
.layer{{flex:1;min-width:120px;width:148px;border:1.5px solid;border-radius:10px;
        padding:11px 10px;cursor:pointer;transition:transform .1s,box-shadow .1s}}
.layer:hover{{transform:translateY(-2px)}}
.chain-arrow{{display:flex;align-items:center;padding:20px 3px 0;flex-shrink:0}}
.layer.insufficient{{border-style:dashed}}
.lyr-pill{{font-size:9px;font-weight:500;padding:2px 8px;border-radius:10px;
           display:inline-block;margin-bottom:6px}}
.lyr-name{{font-size:11px;font-weight:500;color:#1A1A1A;margin-bottom:2px;line-height:1.3}}
.lyr-score{{font-size:28px;font-weight:500;line-height:1;margin:5px 0 2px}}
.lyr-delta{{font-size:10px;margin-bottom:4px;display:flex;align-items:center;gap:4px}}
.lyr-bar{{height:3px;border-radius:2px;background:rgba(0,0,0,.08);margin-bottom:8px}}
.lyr-fill{{height:3px;border-radius:2px}}
.lyr-meta{{font-size:10px;color:#888780;margin-bottom:8px}}
.lyr-tickers{{border-top:1px solid rgba(0,0,0,.06);padding-top:7px;
              display:flex;flex-direction:column;gap:4px}}
.lyr-tk{{display:flex;justify-content:space-between;font-size:10px;font-weight:500}}
.expand{{border:0.5px solid #E0DFDC;border-radius:10px;padding:14px;
         margin-top:10px;background:#F8F8F7;display:none}}
.expand.open{{display:block}}
.ex-hdr{{display:flex;justify-content:space-between;align-items:center;margin-bottom:10px}}
.ex-title{{font-size:13px;font-weight:500;color:#1A1A1A}}
.ex-btn{{font-size:11px;padding:4px 10px;border:0.5px solid #E0DFDC;
         border-radius:6px;background:white;cursor:pointer;color:#1A1A1A}}
.ex-grid{{display:grid;grid-template-columns:repeat(2,1fr);gap:8px}}
.ex-tk{{background:white;border:0.5px solid #E0DFDC;border-radius:8px;padding:10px}}
.ex-sym{{font-size:13px;font-weight:500;color:#1A1A1A}}
.ex-name{{font-size:10px;color:#888780;margin:2px 0 6px}}
.ex-row{{display:flex;justify-content:space-between;font-size:10px;margin-bottom:2px}}
.ex-lbl{{color:#888780}}
.heat-grid{{display:grid;grid-template-columns:56px repeat(7,1fr);
            gap:3px;align-items:center;margin-top:14px}}
.heat-lbl{{font-size:10px;color:#888780;text-align:right;padding-right:8px}}
.hbtn{{font-size:12px;font-weight:500;padding:5px 14px;border:none;border-radius:5px;
       background:transparent;color:#378ADD;cursor:pointer;transition:all .15s}}
.hbtn:hover{{background:white;color:#0C447C}}
.active-hbtn{{background:white!important;color:#0C447C!important;font-weight:600!important;
              box-shadow:0 1px 4px rgba(12,68,124,.2)}}
.heat-day{{font-size:9px;color:#B4B2A9;text-align:center}}
.heat-cell{{height:18px;border-radius:3px}}
.meth-trigger{{display:flex;justify-content:space-between;align-items:center;
               cursor:pointer;padding:14px 16px;background:#E6F1FB;
               border:2px solid #378ADD;border-radius:10px;margin-bottom:4px;
               transition:background .15s;box-shadow:0 2px 6px rgba(55,138,221,.15)}}
.meth-trigger:hover{{background:#D4E8F7}}
.meth-body{{display:none;background:white;border:0.5px solid #E0DFDC;
            border-radius:10px;padding:14px;margin-bottom:12px}}
.meth-body.open{{display:block}}
.mc{{padding:8px 10px;border-radius:7px;border:0.5px solid;margin-bottom:6px}}
.mc-name{{font-size:11px;font-weight:500;margin-bottom:3px}}
.mc-desc{{font-size:10px;line-height:1.5}}
.sigs{{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-bottom:12px}}
.sig{{border:0.5px solid #E0DFDC;border-radius:8px;padding:10px}}
.sig-icon{{width:22px;height:22px;border-radius:5px;display:flex;align-items:center;
           justify-content:center;font-size:12px;margin-bottom:6px}}
.sig-name{{font-size:11px;font-weight:500;color:#1A1A1A;margin-bottom:4px}}
.sig-items{{font-size:10px;color:#5F5E5A;line-height:1.7}}
.override{{background:#F8F8F7;border-left:2px solid #B4B2A9;border-radius:0 6px 6px 0;
           padding:8px 10px;font-size:10px;color:#5F5E5A;line-height:1.6;margin-bottom:12px}}
.ip-note{{font-size:10px;color:#B4B2A9;text-align:center;line-height:1.6}}
.div-flag{{display:inline-flex;align-items:center;gap:4px;background:#FFF3CD;
           border:0.5px solid #EF9F27;border-radius:4px;padding:2px 6px;
           font-size:9px;font-weight:500;color:#633806;cursor:pointer;
           margin-top:4px;position:relative}}
.div-flag:hover .div-tooltip,.div-flag:focus .div-tooltip{{display:block}}
.div-tooltip{{display:none;position:absolute;bottom:calc(100% + 6px);left:0;
              background:#1A1A1A;color:#F8F8F7;font-size:10px;line-height:1.5;
              padding:8px 10px;border-radius:6px;width:220px;z-index:100;
              font-weight:400;box-shadow:0 4px 12px rgba(0,0,0,.3)}}
.div-tooltip::after{{content:"";position:absolute;top:100%;left:12px;
                     border:5px solid transparent;border-top-color:#1A1A1A}}
.rating-A{{background:#EAF3DE;color:#27500A;border:0.5px solid #639922;font-weight:600}}
.rating-B{{background:#E6F1FB;color:#0C447C;border:0.5px solid #378ADD;font-weight:600}}
.rating-C{{background:#FAEEDA;color:#633806;border:0.5px solid #EF9F27;font-weight:600}}
.rating-D{{background:#FCEBEB;color:#791F1F;border:0.5px solid #E24B4A;font-weight:600}}
.rating-na{{background:#F1EFE8;color:#888780;border:0.5px solid #B4B2A9;font-weight:500}}
.rating-badge{{font-size:10px;padding:1px 6px;border-radius:4px;display:inline-block}}
.ticker-band{{background:#05050F;border-top:0.5px solid rgba(83,74,183,0.35);border-bottom:none;
              overflow:hidden;padding:5px 0;position:relative;z-index:10}}
.ticker-scroll{{display:flex;white-space:nowrap;animation:ticker-move 28s linear infinite}}
.ticker-scroll:hover{{animation-play-state:paused}}
.t-item{{display:inline-flex;align-items:center;gap:6px;padding:0 18px;
         font-size:11px;color:#85B7EB;border-right:0.5px solid #1A3A5C;flex-shrink:0}}
.t-sym{{color:white;font-weight:500}}
.t-up{{color:#97C459}}.t-dn{{color:#E24B4A}}.t-neu{{color:#888780}}
@keyframes ticker-move{{0%{{transform:translateX(0)}}100%{{transform:translateX(-50%)}}}}
.signal-bars{{display:flex;align-items:flex-end;justify-content:center;
              gap:3px;height:28px;margin-top:12px}}
.sbar{{width:4px;border-radius:2px;animation:sbar-pulse 1.4s ease-in-out infinite}}
@keyframes sbar-pulse{{0%,100%{{opacity:.2;transform:scaleY(.35)}}50%{{opacity:1;transform:scaleY(1)}}}}
.footer{{font-size:12px;color:#8A9AB8;text-align:center;margin-top:16px;
         padding:20px 16px;border-top:1px solid rgba(255,255,255,0.06);
         background:#080812;border-radius:8px;line-height:2.0}}
.footer-cobhc{{font-size:12px;color:#C8D4E8;font-weight:500;margin-top:6px;
              letter-spacing:.02em}}
.footer-cobhc span{{color:#E24B4A;font-style:italic}}
.footer-family a{{color:#85B7EB;text-decoration:none}}
.footer-family a:hover{{text-decoration:underline}}
.pdf-btn{{display:inline-flex;align-items:center;gap:6px;background:rgba(255,255,255,.15);
          border:1px solid rgba(255,255,255,.3);color:#fff;font-size:11px;font-weight:500;
          padding:5px 14px;border-radius:20px;cursor:pointer;transition:background .15s}}
.pdf-btn:hover{{background:rgba(255,255,255,.25)}}
.capex-strip{{background:linear-gradient(135deg,#1A1830,#0F1A2E);border:1px solid rgba(175,169,236,0.35);
             border-radius:10px;padding:14px 16px;margin-bottom:12px;color:#E8E6DF}}
.capex-strip.insufficient{{opacity:0.75;border-style:dashed}}
.ecosystem-banner{{display:flex;align-items:center;justify-content:center;gap:8px;
                   font-size:13px;font-weight:600;color:#fff;text-decoration:none;
                   padding:10px 16px;border-radius:8px;margin-bottom:12px;
                   background:linear-gradient(135deg,#0C1A3A,#3C3489);
                   box-shadow:0 0 0 1px rgba(133,183,235,0.35),0 0 10px rgba(83,74,183,0.4);
                   transition:box-shadow .15s;text-align:center;flex-wrap:wrap}}
.ecosystem-banner:hover{{box-shadow:0 0 0 1px rgba(133,183,235,0.7),0 0 16px rgba(83,74,183,0.7)}}
.capex-lbl{{font-size:10px;font-weight:500;color:#AFA9EC;letter-spacing:.06em;margin-bottom:6px}}
.capex-dir{{font-size:18px;font-weight:500;display:flex;align-items:center;gap:8px;margin-bottom:4px;flex-wrap:wrap}}
.capex-meta{{font-size:11px;color:#8A9AB8;margin-bottom:10px}}
.capex-chips{{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:8px}}
.capex-chip{{background:rgba(255,255,255,.06);border:0.5px solid rgba(175,169,236,0.3);
            border-radius:8px;padding:6px 10px;font-size:10px;color:#C8D4E8}}
.capex-chip b{{color:#fff}}
.capex-caveat{{font-size:9px;color:#6A7A9A;line-height:1.5}}
@media print{{
  .pdf-btn,.meth-trigger,.meth-body,.expand{{display:none!important}}
  .hero{{-webkit-print-color-adjust:exact;print-color-adjust:exact}}
  .card{{break-inside:avoid;page-break-inside:avoid}}
  body{{padding:0}}
  .layer{{min-width:100px}}
}}
@media(max-width:768px){{
  .hero{{padding:14px 12px 16px}}
  .hero-title{{font-size:15px}}
  .hero-title span:first-child{{font-size:22px!important}}
  .hero-sub{{font-size:10px}}
  .hm-grid{{grid-template-columns:1fr 1fr;gap:5px}}
  .hm-val{{font-size:13px}}
  .hm-lbl,.hm-note{{font-size:9px}}
  .body{{padding:8px 8px 0;margin-top:0}}
  .card{{padding:10px 8px;border-radius:8px;margin-bottom:8px}}
  .card-label{{font-size:9px;margin-bottom:6px}}
  .layer{{min-width:120px;max-width:150px;padding:8px 7px}}
  .lyr-score{{font-size:20px}}
  .lyr-name{{font-size:9px}}
  .lyr-pill{{font-size:8px;padding:1px 5px}}
  .lyr-meta{{font-size:9px}}
  .lyr-tk{{font-size:9px}}
  .heat-grid{{grid-template-columns:40px repeat(7,1fr);gap:2px;margin-top:10px}}
  .heat-lbl{{font-size:9px;padding-right:4px}}
  .heat-day{{font-size:8px}}
  .heat-cell{{height:13px}}
  .meth-trigger{{padding:8px 10px}}
  .sigs{{grid-template-columns:1fr}}
  #bottleneck-strip{{font-size:10px;padding:5px 8px;gap:5px}}
  .footer{{font-size:9px}}
  .pdf-btn{{font-size:9px;padding:3px 8px}}
  .reg-pill{{font-size:9px;padding:3px 8px}}
  .ex-grid{{grid-template-columns:1fr 1fr}}
  .hero-top{{gap:6px}}
  #hero-chain-status{{flex-wrap:wrap}}
  #hero-chain-status > div{{min-width:calc(33.3% - 1px);flex:none}}

  /* Swipeable sub-layer row (mobile only; desktop #chain is untouched).
     Peek-width cards (80vw) are the primary swipe cue since mobile
     browsers hide scrollbars; scroll-snap makes each swipe land cleanly
     on a card. #chain .layer's specificity (id+class) overrides the
     bare .layer rule above without needing !important. */
  #chain{{display:flex;overflow-x:auto;scroll-snap-type:x mandatory;
         -webkit-overflow-scrolling:touch;gap:10px;
         margin:0 -8px;padding:2px 8px 6px;scroll-padding-left:8px}}
  #chain .layer{{flex:0 0 80vw;max-width:80vw;min-width:0;scroll-snap-align:start}}
  .chain-arrow{{display:none}} /* doesn't fit naturally at 80vw card width */
  .chain-fade{{position:absolute;top:0;right:0;bottom:6px;width:32px;
              background:linear-gradient(90deg,rgba(14,22,40,0) 0%,#101C32 100%);
              pointer-events:none;opacity:1;transition:opacity .15s}}
  .chain-fade.hidden{{opacity:0}}
}}
@media(min-width:769px){{
  .chain-fade{{display:none}} /* desktop: row never overflows, no fade needed */
}}
@media(max-width:380px){{
  .hm-grid{{grid-template-columns:1fr 1fr}}
  .layer{{min-width:110px}}
  #hero-chain-status > div{{min-width:calc(50% - 1px)}}
}}
</style>
</head>
<body>

<div class="hero">
  <div class="hero-laser"></div>
  <div class="hero-glow"></div>
  <div class="hero-accent"></div>
  <div class="hero-top">
    <div>
      <div class="hero-title" style="display:flex;align-items:center;gap:8px;flex-wrap:wrap">
        <span style="font-size:30px;font-weight:500;letter-spacing:-1px">Ray<span style="color:#85B7EB;font-weight:300">Dar</span></span>
        <span style="font-size:11px;font-weight:600;color:#0A0818;background:#85B7EB;padding:2px 8px;border-radius:10px;letter-spacing:.04em">DATA CENTER</span>
        <a href="https://miikawir-ops.github.io/AI_valuechain/" class="hero-sibling-link">← RayDar AI value chain</a>
        <span style="width:5px;height:5px;border-radius:50%;background:#E24B4A;flex-shrink:0;display:inline-block;margin-top:6px"></span>
        <span style="font-size:14px;font-weight:400;background:linear-gradient(90deg,#85B7EB,#AFA9EC,#85B7EB);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;letter-spacing:0.08em;opacity:0.95">AI data center infrastructure intelligence</span>
      </div>
      <div class="hero-sub">{datetime_str}</div>
    </div>
    <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap">
      <button class="pdf-btn" onclick="window.print()">↓ PDF</button>
      <div class="reg-pill" tabindex="0">{reg_lbl}
        <div class="reg-tooltip">
          <b>What is Market Regime?</b><br><br>
          A systemic filter applied to all sub-layer scores.<br><br>
          <b>Risk-On</b> — VIX low, yields stable, tech leading. Full signal strength.<br>
          <b>Neutral</b> — Some uncertainty. Scores dampened.<br>
          <b>Risk-Off</b> — High fear, rising yields, tech selling off.<br><br>
          Signals: VIX · 10Y yield change · NASDAQ vs S&amp;P 500
        </div>
      </div>
    </div>
  </div>
  <div class="hm-grid" style="margin-bottom:12px">
    <div class="hm-card">
      <div class="hm-lbl">VIX</div>
      <div class="hm-val">{vix_disp}</div>
      <div class="hm-note" style="color:{vix_col}">{vix_note}</div>
    </div>
    <div class="hm-card">
      <div class="hm-lbl">10Y YIELD CHANGE</div>
      <div class="hm-val">{yield_disp}</div>
      <div class="hm-note" style="color:{yield_col}">bps · {yield_note}</div>
    </div>
    <div class="hm-card">
      <div class="hm-lbl">NASDAQ VS S&amp;P</div>
      <div class="hm-val">{nasdaq_disp}</div>
      <div class="hm-note" style="color:{nasdaq_col}">{nasdaq_note}</div>
    </div>
    <div class="hm-card">
      <div class="hm-lbl">SUB-LAYERS SCORED</div>
      <div class="hm-val">{len(scored_data)}</div>
      <div class="hm-note" style="color:#85B7EB">{total_tickers} tickers</div>
    </div>
  </div>
  <div id="hero-chain-status" style="position:relative;display:flex;gap:1px;background:rgba(255,255,255,0.04);border-radius:8px;overflow:hidden;margin-top:12px"></div>
</div>

<div class="ticker-band">
  <div class="ticker-scroll" id="top-ticker"></div>
</div>
<div class="body">

<div class="capex-strip" id="capex-strip"></div>

<a href="ecosystem.html" class="ecosystem-banner">🗺️ Explore the Data Center Ecosystem — who the players are and how they connect →</a>

<div class="card">
  <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;margin-bottom:10px">
    <div style="font-size:12px;font-weight:500;color:#C8D4E8;letter-spacing:0.02em;margin-bottom:0">Data center infrastructure — signal scores</div>
    <div style="display:flex;gap:12px;font-size:10px;color:#8A9AB8;align-items:center;flex-wrap:wrap">
      <span><span style="display:inline-block;width:7px;height:7px;border-radius:50%;background:#E24B4A;margin-right:4px"></span>Hot / bottleneck</span>
      <span><span style="display:inline-block;width:7px;height:7px;border-radius:50%;background:#EF9F27;margin-right:4px"></span>Emerging</span>
      <span><span style="display:inline-block;width:7px;height:7px;border-radius:50%;background:#639922;margin-right:4px"></span>Neutral / healthy</span>
      <span><span style="display:inline-block;width:7px;height:7px;border-radius:50%;background:#378ADD;margin-right:4px"></span>Cooling</span>
    </div>
  </div>
  <div class="fetch-note" style="margin-bottom:8px;color:#6A7A9A">{fetch_note}</div>
  <div style="display:flex;justify-content:space-between;align-items:center;gap:8px;margin-bottom:6px;flex-wrap:wrap">
    <div id="bottleneck-strip" style="display:flex;align-items:center;gap:8px;padding:8px 12px;
         border-radius:6px;background:#F8F8F7;border:0.5px solid #E0DFDC;
         font-size:11px;color:#5F5E5A;flex-wrap:wrap;flex:1"></div>
    <button onclick="toggleAbout()" style="font-size:12px;font-weight:500;
            padding:8px 16px;border:1.5px solid #378ADD;border-radius:6px;
            background:#E6F1FB;color:#0C447C;cursor:pointer;white-space:nowrap;
            flex-shrink:0;display:flex;align-items:center;gap:6px"
            id="about-btn">ℹ️ About this dashboard</button>
  </div>
  <div id="about-section" style="display:none;background:#F8F8F7;border:0.5px solid #E0DFDC;
       border-radius:8px;padding:14px;margin-bottom:10px;font-size:12px;color:#5F5E5A;line-height:1.7">
    <div style="font-size:13px;font-weight:500;color:#1A1A1A;margin-bottom:10px">About this dashboard</div>
    <p style="margin-bottom:8px">A signal dashboard tracking the data center infrastructure buildout — cooling, networking, optical, compute assembly, and colocation — identifying which part of the buildout is currently the most constrained.</p>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:10px">
      <div style="background:white;border-radius:6px;padding:8px 10px;border:0.5px solid #E0DFDC">
        <div style="font-size:11px;font-weight:500;color:#1A1A1A;margin-bottom:4px">🔴 Hot / Bottleneck</div>
        <div style="font-size:11px">Current dominant constraint. Supply cannot meet demand.</div>
      </div>
      <div style="background:white;border-radius:6px;padding:8px 10px;border:0.5px solid #E0DFDC">
        <div style="font-size:11px;font-weight:500;color:#1A1A1A;margin-bottom:4px">🟠 Emerging</div>
        <div style="font-size:11px">Building momentum toward a bottleneck, or price ahead of fundamentals.</div>
      </div>
      <div style="background:white;border-radius:6px;padding:8px 10px;border:0.5px solid #E0DFDC">
        <div style="font-size:11px;font-weight:500;color:#1A1A1A;margin-bottom:4px">🟢 Neutral / Healthy</div>
        <div style="font-size:11px">Stable. No constraint pressure.</div>
      </div>
      <div style="background:white;border-radius:6px;padding:8px 10px;border:0.5px solid #E0DFDC">
        <div style="font-size:11px;font-weight:500;color:#1A1A1A;margin-bottom:4px">🔵 Cooling</div>
        <div style="font-size:11px">Previously hot, constraint easing.</div>
      </div>
    </div>
    <div style="font-size:11px;font-weight:500;color:#1A1A1A;margin-bottom:6px">Data sources</div>
    <p style="margin-bottom:2px">Stock prices &amp; fundamentals, capex data — Yahoo Finance · News signals — Reuters, Yahoo Finance, MarketWatch, CNBC</p>
    <p style="margin-top:8px;font-size:10px;color:#B4B2A9">Quarterly financials may be up to 90 days old · Not financial advice · Always do your own research</p>
  </div>
  <div id="chain-wrap" style="position:relative">
    <div style="display:flex;align-items:stretch;gap:0" id="chain"></div>
    <div id="chain-fade" class="chain-fade"></div>
  </div>
  <div id="expand-area"></div>
  <div style="margin-top:14px">
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px">
      <div style="display:flex;align-items:center;gap:10px">
        <div style="display:flex;gap:3px;background:#E6F1FB;border-radius:8px;padding:4px;border:1.5px solid #378ADD">
          <button onclick="setHeatDays(7)"  id="hbtn-7"  class="hbtn active-hbtn">7d</button>
          <button onclick="setHeatDays(30)" id="hbtn-30" class="hbtn">30d</button>
          <button onclick="setHeatDays(90)" id="hbtn-90" class="hbtn">90d</button>
        </div>
        <div style="font-size:10px;font-weight:500;color:#888780" id="heat-label">Signal heat trail</div>
      </div>
    </div>
    <div class="heat-grid" id="heat"></div>
  </div>
</div>

<div class="meth-trigger" onclick="toggleMeth()">
  <div style="display:flex;align-items:center;gap:8px">
    <span style="font-size:12px;font-weight:500;color:#1A1A1A">How to read this dashboard</span>
    <span style="font-size:10px;padding:1px 7px;border:0.5px solid #E0DFDC;border-radius:8px;color:#888780">methodology</span>
  </div>
  <span style="font-size:11px;color:#B4B2A9" id="marrow">▾</span>
</div>
<div class="meth-body" id="meth-body">
  <div style="font-size:11px;font-weight:500;color:#1A1A1A;margin-bottom:8px">What the colors mean</div>
  <div class="mc" style="background:#FCEBEB;border-color:#E24B4A">
    <div class="mc-name" style="color:#791F1F">Red — current bottleneck</div>
    <div class="mc-desc" style="color:#A32D2D">All three signal categories agree. This sub-layer is the dominant constraint right now.</div>
  </div>
  <div class="mc" style="background:#FAEEDA;border-color:#EF9F27">
    <div class="mc-name" style="color:#633806">Orange — emerging or hype warning</div>
    <div class="mc-desc" style="color:#854F0B">Building momentum toward a bottleneck, or price action is outrunning the fundamentals.</div>
  </div>
  <div class="mc" style="background:#EAF3DE;border-color:#639922">
    <div class="mc-name" style="color:#27500A">Green — neutral / healthy</div>
    <div class="mc-desc" style="color:#3B6D11">Stable activity, no constraint pressure.</div>
  </div>
  <div class="mc" style="background:#E6F1FB;border-color:#378ADD">
    <div class="mc-name" style="color:#0C447C">Blue — cooling</div>
    <div class="mc-desc" style="color:#185FA5">Previously hot sub-layer, constraint easing.</div>
  </div>
  <div style="background:#F8F8F7;border-left:2px solid #378ADD;border-radius:0 6px 6px 0;
              padding:8px 10px;font-size:10px;color:#5F5E5A;line-height:1.6;margin-top:4px">
    <strong>Note on Cooling:</strong> this sub-layer is currently a single ticker (VRT). Its score is
    that company's own score directly — market-cap weighting degenerates correctly to N=1, and the
    Red reality check (which needs 2+ companies) does not apply here.
  </div>
  <div style="background:#F8F8F7;border-left:2px solid #AFA9EC;border-radius:0 6px 6px 0;
              padding:8px 10px;font-size:10px;color:#5F5E5A;line-height:1.6;margin-top:6px">
    <strong>Note on the capex strip above:</strong> hyperscaler capex direction is a display overlay
    only — it does not feed into any sub-layer's score or weighting.
  </div>
  <div style="font-size:11px;font-weight:500;color:#1A1A1A;margin:12px 0 8px">Three signal categories</div>
  <div class="sigs">
    <div class="sig">
      <div class="sig-icon" style="background:#EAF3DE">F</div>
      <div class="sig-name">Fundamentals</div>
      <div class="sig-items">Revenue growth acceleration<br>Gross margin expansion<br>Pricing power trend</div>
    </div>
    <div class="sig">
      <div class="sig-icon" style="background:#FCEBEB">C</div>
      <div class="sig-name">Constraint signal</div>
      <div class="sig-items">News narrative velocity<br>Capital expenditure trends<br>Supply/demand pressure</div>
    </div>
    <div class="sig">
      <div class="sig-icon" style="background:#E6F1FB">S</div>
      <div class="sig-name">Smart money</div>
      <div class="sig-items">Volume-price confirmation<br>Analyst upgrade clusters<br>Short interest direction</div>
    </div>
  </div>
  <div class="override"><strong>Fundamental override:</strong> if revenue growth is decelerating, a sub-layer cannot be Red regardless of price momentum.</div>
  <div class="ip-note">Signal weights and exact scoring logic are proprietary.<br>This summary describes methodology categories only. Not financial advice.</div>
</div>

</div>

<div class="footer">
  <div><strong>RayDar Data Center</strong> · {datetime_str}</div>
  <div style="font-size:11px;color:#888780;margin-top:2px">
    Not financial advice · Always do your own research · Data may be up to 90 days old
  </div>
  <div class="footer-family" style="margin-top:6px">
    <a href="https://miikawir-ops.github.io/AI_valuechain/" target="_blank" rel="noopener">Part of the RayDar family</a> — AI value chain intelligence, one layer at a time.
  </div>
  <div class="footer-cobhc">
    ⚔️ Built in Espoo, Finland · <span>Are You Dead Yet?</span> — the market will tell you 🤘
  </div>
  <div class="signal-bars" id="signal-bars"></div>
</div>

<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.js"></script>
<script>
const LAYERS       = {layers_js};
const HISTORY      = {history_js};
const CAPEX        = {capex_js};
const HAS_YESTERDAY= {has_yesterday};

const CC = {{
  Red:    {{bg:"#FCEBEB",border:"#E24B4A",pill:"#E24B4A",pft:"#FCEBEB",lbl:"Hot"}},
  Orange: {{bg:"#FAEEDA",border:"#EF9F27",pill:"#EF9F27",pft:"#FAEEDA",lbl:"Emerging"}},
  Green:  {{bg:"#EAF3DE",border:"#639922",pill:"#639922",pft:"#EAF3DE",lbl:"Neutral"}},
  Blue:   {{bg:"#E6F1FB",border:"#378ADD",pill:"#378ADD",pft:"#E6F1FB",lbl:"Cooling"}},
}};

let active = null;

function fmt(v, decimals=1) {{
  return (v >= 0 ? "+" : "") + v.toFixed(decimals);
}}

function deltaArrow(d) {{
  if (d === null || d === undefined) return "";
  const col   = d > 0 ? "#27500A" : d < 0 ? "#A32D2D" : "#888780";
  const arrow = d > 0 ? "▲" : d < 0 ? "▼" : "—";
  return `<span style="color:${{col}};font-size:10px">${{arrow}} ${{Math.abs(d).toFixed(1)}}</span>`;
}}

function colorChangeBadge(l) {{
  if (!HAS_YESTERDAY || !l.color_changed || !l.prev_color) return "";
  const prev = CC[l.prev_color] || CC.Green;
  return `<span style="font-size:9px;padding:1px 5px;border-radius:4px;
                        background:${{prev.bg}};color:${{prev.pill}};
                        border:0.5px solid ${{prev.pill}};margin-left:4px">was ${{prev.lbl}}</span>`;
}}

const COMPANY_CONTEXT = {json.dumps(COMPANY_CONTEXT)};

function getCompanyContext(sym, layerId) {{
  return COMPANY_CONTEXT[sym] || `${{sym}} is a key player in the ${{layerId}} sub-layer.`;
}}

const sparkCharts = {{}};

function toggleTickerDetail(id) {{
  const el = document.getElementById(id);
  if (!el) return;
  const open = el.style.display === "none";
  document.querySelectorAll('[id^="tk-detail-"]').forEach(d => d.style.display = "none");
  Object.keys(sparkCharts).forEach(k => {{ try {{ sparkCharts[k].destroy(); }} catch(e) {{}} delete sparkCharts[k]; }});
  el.style.display = open ? "block" : "none";
  if (!open) return;

  const sym = id.replace(/^tk-detail-[^-]+-/, "");
  LAYERS.forEach(l => (l.tickers||[]).forEach(t => {{
    if (t.sym !== sym || !t.sparkline || t.sparkline.length < 5) return;
    const data  = t.sparkline;
    const mn    = Math.min(...data);
    const mx    = Math.max(...data);
    const range = mx - mn;
    const canvasWrap = document.getElementById("spark-wrap-" + sym);
    if (range < 1) {{
      if (canvasWrap) canvasWrap.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:100%;font-size:11px;color:#B4B2A9;font-style:italic">Fetching 6-month history...</div>';
      return;
    }}
    const pad   = range * 0.12;
    const col   = (t.ret30 == null || t.ret30 >= 0) ? "#27500A" : "#A32D2D";
    const bgCol = col === "#27500A" ? "rgba(39,80,10,0.07)" : "rgba(163,45,45,0.07)";
    const today = new Date();
    const step  = Math.max(1, Math.floor(180 / data.length));
    const labels = data.map((_, i) => {{
      const d = new Date(today);
      d.setDate(d.getDate() - (data.length - 1 - i) * step);
      return d.toLocaleDateString("en", {{month:"short", day:"numeric"}});
    }});
    if (canvasWrap) canvasWrap.innerHTML = '<canvas id="spark-' + sym + '" style="width:100%;height:100%"></canvas>';
    setTimeout(() => {{
      const canvas = document.getElementById("spark-" + sym);
      if (!canvas) return;
      sparkCharts["spark-" + sym] = new Chart(canvas, {{
        type: "line",
        data: {{ labels, datasets: [{{ data, borderColor: col, borderWidth: 2, pointRadius: 0,
                 pointHoverRadius: 3, fill: true, backgroundColor: bgCol, tension: 0.35 }}] }},
        options: {{
          responsive: true, maintainAspectRatio: false,
          interaction: {{ mode:"index", intersect:false }},
          plugins: {{ legend:{{display:false}}, tooltip:{{ callbacks:{{
            label: c => "$" + c.parsed.y.toFixed(2), title: c => c[0].label }} }} }},
          scales: {{
            x: {{ display:true, ticks:{{maxTicksLimit:5,font:{{size:9}},color:"#888780",maxRotation:0}},
                  grid:{{display:false}}, border:{{display:false}} }},
            y: {{ display:true, min:mn-pad, max:mx+pad,
                  ticks:{{maxTicksLimit:4,font:{{size:9}},color:"#888780",callback:v=>"$"+Math.round(v)}},
                  grid:{{color:"rgba(0,0,0,0.04)"}}, border:{{display:false}} }}
          }},
          animation: {{ duration:500 }}
        }}
      }});
    }}, 80);
  }}));
}}

function toggleAbout() {{
  const sec = document.getElementById("about-section");
  const btn = document.getElementById("about-btn");
  const open = sec.style.display === "none";
  sec.style.display = open ? "block" : "none";
  btn.innerHTML = open ? "✕ Close" : "ℹ️ About this dashboard";
}}

function buildBottleneckStrip() {{
  const strip = document.getElementById("bottleneck-strip");
  if (!strip) return;
  const scored = LAYERS.filter(l => !l.insufficient);
  if (scored.length === 0) {{ strip.innerHTML = `<span style="color:#888780">No sub-layers scored this run.</span>`; return; }}
  const sorted    = [...scored].sort((a,b) => b.score - a.score);
  const hotLayers = sorted.filter(l => l.color === "Red");
  const emerging  = sorted.find(l => l.color === "Orange");
  const easing    = sorted.find(l => l.color === "Blue");
  const ease      = easing || sorted[sorted.length-1];

  let html = "";
  if (hotLayers.length > 0) {{
    html += `<span style="color:#888780">Bottleneck${{hotLayers.length > 1 ? "s" : ""}}:</span>`;
    hotLayers.forEach((l, i) => {{
      html += `<strong style="color:#E24B4A">${{l.n1}}</strong>`;
      if (i < hotLayers.length - 1) html += `<span style="color:#E24B4A;margin:0 2px">+</span>`;
    }});
  }}
  if (emerging) {{
    html += `<span style="color:#B4B2A9;margin:0 4px">→</span>`;
    html += `<span style="color:#888780">Emerging:</span>`;
    html += `<strong style="color:#EF9F27">${{emerging.n1}}</strong>`;
  }}
  html += `<span style="color:#B4B2A9;margin:0 4px">→</span>`;
  html += `<span style="color:#888780">Easing:</span>`;
  html += `<strong style="color:${{(CC[ease.color]||CC.Green).border}}">${{ease.n1}}</strong>`;
  const insuffCount = LAYERS.length - scored.length;
  if (insuffCount > 0) html += `<span style="color:#B4B2A9;margin-left:6px">(${{insuffCount}} insufficient data)</span>`;
  strip.innerHTML = html;
}}

// Reusable mobile swipe-row pattern (see .chain-arrow/.chain-fade/#chain-wrap
// in the <style> block for the CSS half) — horizontally scroll-snapping row
// with a peek-width next card and an edge fade that hides once scrolled to
// the end. Self-contained: only touches #chain/#chain-fade by id, so the
// parent AI_valuechain dashboard's own layer row can reuse it as-is.
function updateChainFade() {{
  const chain = document.getElementById("chain");
  const fade = document.getElementById("chain-fade");
  if (!chain || !fade) return;
  const atEnd = chain.scrollLeft + chain.clientWidth >= chain.scrollWidth - 4;
  fade.classList.toggle("hidden", atEnd);
}}

function buildChain() {{
  const wrap = document.getElementById("chain");
  wrap.innerHTML = "";
  LAYERS.forEach((l, idx) => {{
    const div = document.createElement("div");
    div.className = "layer" + (l.insufficient ? " insufficient" : "");

    if (l.insufficient) {{
      div.style.cssText = `background:#F1EFE8;border-color:#B4B2A9;`;
      div.innerHTML = `
        <div class="lyr-pill" style="background:#B4B2A9;color:#fff">No data</div>
        <div class="lyr-name" style="margin-top:6px">${{l.n1}}<br><span style="color:#888780;font-weight:400">${{l.n2}}</span></div>
        <div style="font-size:11px;color:#5F5E5A;margin-top:10px;line-height:1.5">
          ${{l.tickers_scored}}/${{l.tickers_total}} tickers scored this run
        </div>`;
      div.onclick = () => {{ active = active === l.id ? null : l.id; buildChain(); buildExpand(); }};
      wrap.appendChild(div);
      if (idx < LAYERS.length - 1) {{
        const arrow = document.createElement("div");
        arrow.className = "chain-arrow";
        arrow.innerHTML = `<svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M3 8h10M9 4l4 4-4 4" stroke="#B4B2A9" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
        wrap.appendChild(arrow);
      }}
      return;
    }}

    const c   = CC[l.color] || CC.Green;
    const pct = Math.min(100, Math.round(l.score));
    const top3 = l.tickers.slice(0, 3);
    const tkHtml = top3.map(t => {{
      const col   = t.ret30 != null ? (t.ret30 >= 0 ? "#27500A" : "#A32D2D") : "#888780";
      const db    = t.delta_band === "accelerating" ? "▲" : t.delta_band === "decelerating" ? "▼" : t.delta_band === "unknown" ? "?" : "—";
      const dc    = t.delta_band === "accelerating" ? "#27500A" : t.delta_band === "decelerating" ? "#A32D2D" : "#888780";
      const retTxt = t.ret30 != null ? fmt(t.ret30) + "%" : "—";
      return `<div class="lyr-tk">
        <span>${{t.sym}} <span style="color:${{dc}};font-size:9px">${{db}}</span></span>
        <span style="color:${{col}}">${{retTxt}}</span>
      </div>`;
    }}).join("");

    const div_ = div;
    div_.style.cssText = `background:${{c.bg}};border-color:${{c.border}};${{active===l.id?"box-shadow:0 0 0 2px "+c.border:""}}`;
    div_.innerHTML = `
      <div style="display:flex;align-items:center;flex-wrap:wrap;gap:3px;margin-bottom:6px">
        <span class="lyr-pill" style="background:${{c.pill}};color:${{c.pft}}">${{c.lbl}}</span>
        ${{colorChangeBadge(l)}}
      </div>
      <div class="lyr-name">${{l.n1}}<br><span style="color:#888780;font-weight:400">${{l.n2}}</span></div>
      <div class="lyr-score" style="color:${{c.border}}">${{l.score.toFixed(0)}}</div>
      <div class="lyr-delta">
        ${{HAS_YESTERDAY && l.delta_score !== null
          ? deltaArrow(l.delta_score) + "<span style='font-size:10px;color:#888780;margin-left:2px'>vs yesterday</span>"
          : "<span style='font-size:10px;color:#B4B2A9'>first run</span>"}}
      </div>
      <div class="lyr-bar"><div class="lyr-fill" style="width:${{pct}}%;background:${{c.border}}"></div></div>
      <div class="lyr-meta">News ${{l.news_vel != null ? l.news_vel : "—"}} hits · Momentum ${{l.momentum_label}}</div>
      <div style="display:flex;gap:3px;margin-bottom:4px;flex-wrap:wrap">
        ${{top3.map(t => {{
          const rc = t.rating || "na";
          const rTxt = t.rating || "—";
          const rTitle = t.rating ? `${{t.sym}}: ${{t.rating==='A'?'Accelerating':t.rating==='B'?'Stable':t.rating==='C'?'Caution':'Deteriorating'}}` : `${{t.sym}}: insufficient data`;
          return `<span class="rating-badge rating-${{rc}}" style="font-size:9px;padding:1px 4px" title="${{rTitle}}">${{t.sym}} ${{rTxt}}</span>`;
        }}).join("")}}
      </div>
      ${{l.divergence ? `<div class="div-flag" tabindex="0">⚡ Narrative ahead of fundamentals
        <div class="div-tooltip">${{l.divergence_msg}}</div></div>` : ""}}
      <div class="lyr-tickers">${{tkHtml}}</div>`;
    div_.onclick = () => {{ active = active === l.id ? null : l.id; buildChain(); buildExpand(); }};
    wrap.appendChild(div_);

    if (idx < LAYERS.length - 1) {{
      const arrow = document.createElement("div");
      arrow.className = "chain-arrow";
      arrow.innerHTML = `<svg width="16" height="16" viewBox="0 0 16 16" fill="none">
        <path d="M3 8h10M9 4l4 4-4 4" stroke="#B4B2A9" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
      </svg>`;
      wrap.appendChild(arrow);
    }}
  }});
  buildBottleneckStrip();
  updateChainFade();
}}

function buildExpand() {{
  const area = document.getElementById("expand-area");
  if (!active) {{ area.innerHTML = ""; return; }}
  const l = LAYERS.find(x => x.id === active);
  if (!l) {{ area.innerHTML = ""; return; }}

  if (l.insufficient) {{
    const reasons = (l.insufficient_reasons||[]).map(r => `<div style="margin-top:4px">• ${{r.ticker}}: ${{r.reason}}</div>`).join("");
    area.innerHTML = `<div class="expand open" style="border-color:#B4B2A9;background:#F8F8F7">
      <div class="ex-title" style="margin-bottom:6px">${{l.n1}} — Insufficient data</div>
      <div style="font-size:11px;color:#5F5E5A;line-height:1.6">
        ${{l.tickers_scored}}/${{l.tickers_total}} tickers scored this run. No sub-layer score can be
        computed until at least one ticker has usable data.${{reasons}}
      </div>
    </div>`;
    return;
  }}

  const c = CC[l.color] || CC.Green;

  const cards = l.tickers.map(t => {{
    const rc      = t.ret30 != null ? (t.ret30 >= 0 ? "#27500A" : "#A32D2D") : "#888780";
    const retTxt  = t.ret30 != null ? fmt(t.ret30) + "%" : "—";
    const hyp     = t.hype ? `<span style="font-size:9px;background:#FAEEDA;color:#854F0B;padding:1px 5px;border-radius:4px;margin-left:4px">hype</span>` : "";
    const tIcon   = t.delta_band === "accelerating" ? "▲" : t.delta_band === "decelerating" ? "▼" : t.delta_band === "unknown" ? "?" : "—";
    const tCol    = t.delta_band === "accelerating" ? "#27500A" : t.delta_band === "decelerating" ? "#A32D2D" : "#888780";
    const cardId  = `tk-detail-${{l.id}}-${{t.sym}}`;
    const rCls    = t.rating || "na";
    const rTxt    = t.rating || "—";
    const priceTxt = t.price != null ? "$" + t.price.toLocaleString() : "—";
    const missing = (t.data_missing && t.data_missing.length)
      ? `<div style="font-size:9px;color:#B4B2A9;margin-top:6px">Data gaps this run: ${{t.data_missing.join(", ")}}</div>` : "";
    const deepDive = `Give me a focused investment deep dive on ${{t.sym}} (${{t.name}}) in the context of the AI data center buildout. Cover: 1) What role does ${{t.sym}} play? 2) Latest revenue trend — accelerating or decelerating? 3) Gross margin trend. 4) The strongest bull case in one paragraph. 5) The main risk. 6) Compared to peers in the ${{l.n1}} sub-layer, is ${{t.sym}} gaining or losing ground?`;

    return `<div class="ex-tk" style="cursor:pointer" onclick="toggleTickerDetail('${{cardId}}')">
      <div style="display:flex;align-items:center;justify-content:space-between">
        <div style="display:flex;align-items:center;gap:6px">
          <div class="ex-sym">${{t.sym}}</div>
          <span class="rating-badge rating-${{rCls}}"
                title="${{t.rating_up ? 'Upgraded from '+t.prev_rating : t.rating_down ? 'Downgraded from '+t.prev_rating : (t.rating ? 'Rating: '+t.rating : 'Insufficient data')}}"
          >${{rTxt}}</span>
          ${{t.rating_up ? `<span style="font-size:10px;color:#27500A;font-weight:600">↑ was ${{t.prev_rating}}</span>` : ""}}
          ${{t.rating_down ? `<span style="font-size:10px;color:#A32D2D;font-weight:600">↓ was ${{t.prev_rating}}</span>` : ""}}
          ${{hyp}}
        </div>
        <span style="font-size:9px;color:#B4B2A9">tap for insight ↓</span>
      </div>
      <div class="ex-name">${{t.name}}</div>
      ${{t.run_rate ? `<div style="font-size:10px;font-weight:600;color:#27500A;margin:3px 0;
          padding:2px 6px;background:#EAF3DE;border-radius:4px;display:inline-block">
        Run rate $${{t.run_rate}}B/yr</div>` : ""}}
      <div class="ex-row"><span class="ex-lbl">Price</span><span>${{priceTxt}}</span></div>
      <div class="ex-row"><span class="ex-lbl">30d return</span><span style="color:${{rc}}">${{retTxt}}</span></div>
      <div class="ex-row"><span class="ex-lbl">Trend</span><span style="color:${{tCol}}">${{tIcon}} ${{t.delta_band}}</span></div>
      <div style="margin-top:6px;padding:5px 8px;border-radius:5px;
                  background:#F8F8F7;border-left:2px solid ${{t.forecast.color}}">
        <span style="font-size:10px;font-weight:500;color:${{t.forecast.color}}">
          ${{t.forecast.direction}} ${{rTxt}}${{t.forecast.target ? " → " + t.forecast.target : ""}}
        </span>
        <span style="font-size:10px;color:#888780;margin-left:6px">${{t.forecast.label}}</span>
      </div>
      ${{missing}}
      <div id="${{cardId}}" style="display:none;margin-top:10px;padding-top:10px;
           border-top:0.5px solid #E0DFDC" onclick="event.stopPropagation()">
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-bottom:10px">
          ${{t.run_rate ? `<div style="background:#EAF3DE;border-radius:6px;padding:8px 10px;border:0.5px solid #639922">
            <div style="font-size:9px;color:#27500A;font-weight:500;margin-bottom:2px">REVENUE RUN RATE</div>
            <div style="font-size:16px;font-weight:500;color:#27500A">$${{t.run_rate}}B</div>
            <div style="font-size:9px;color:#3B6D11">annualized · latest quarter ×4</div>
          </div>` : ""}}
          ${{t.pct_of_high ? `<div style="background:#F8F8F7;border-radius:6px;padding:8px 10px;border:0.5px solid #E0DFDC">
            <div style="font-size:9px;color:#888780;font-weight:500;margin-bottom:2px">52W POSITION</div>
            <div style="font-size:16px;font-weight:500;color:#1A1A1A">${{t.pct_of_high}}%</div>
            <div style="font-size:9px;color:#888780">of 52-week high (${{t.week52_high != null ? "$"+t.week52_high.toFixed(0) : "—"}})</div>
            <div style="margin-top:4px;height:4px;background:#E0DFDC;border-radius:2px">
              <div style="height:4px;border-radius:2px;background:${{t.pct_of_high>80?'#E24B4A':t.pct_of_high>50?'#EF9F27':'#639922'}};width:${{t.pct_of_high}}%"></div>
            </div>
          </div>` : ""}}
        </div>
        <div style="font-size:10px;color:#888780;margin-bottom:4px;font-weight:500">6-month price trend</div>
        <div id="spark-wrap-${{t.sym}}" style="position:relative;width:100%;height:120px;margin-bottom:8px;background:#F8F8F7;border-radius:4px">
          <canvas id="spark-${{t.sym}}" style="width:100%;height:100%" role="img" aria-label="${{t.sym}} 6-month price chart"></canvas>
        </div>
        <div style="font-size:10px;color:#888780;margin-bottom:4px;font-weight:500">Strategic role</div>
        <div style="font-size:10px;color:#5F5E5A;line-height:1.6;margin-bottom:8px">${{getCompanyContext(t.sym, l.id)}}</div>
        <button onclick="sendPrompt('${{deepDive}}')"
                style="width:100%;padding:7px;border:1px solid #378ADD;border-radius:6px;
                       background:#E6F1FB;color:#0C447C;font-size:11px;font-weight:500;cursor:pointer">
          🔍 Deep dive with Claude ↗
        </button>
      </div>
    </div>`;
  }}).join("");

  area.innerHTML = `<div class="expand open" style="border-color:${{c.border}}">
    <div class="ex-hdr">
      <div class="ex-title">${{l.n1}} ${{l.n2}} — ${{c.lbl}} · score ${{l.score.toFixed(1)}}</div>
      <button class="ex-btn" onclick="sendPrompt('Deep dive on the ${{l.n1}} sub-layer of the data center buildout today. Which company is best positioned and what would make this sub-layer turn Red?')">Deep dive ↗</button>
    </div>
    <div class="ex-grid">${{cards}}</div>
  </div>`;
}}

function colorFromName(c) {{
  return {{Red:"#E24B4A",Orange:"#EF9F27",Green:"#97C459",Blue:"#B5D4F4"}}[c] || "#E8E6DF";
}}

let currentHeatDays = 7;

function setHeatDays(days) {{
  currentHeatDays = days;
  [7,30,90].forEach(d => {{
    const btn = document.getElementById("hbtn-"+d);
    if (btn) btn.className = "hbtn" + (d===days ? " active-hbtn" : "");
  }});
  const lbl = document.getElementById("heat-label");
  if (lbl) lbl.textContent = `Signal heat trail · last ${{days}} days`;
  buildHeat();
}}

function buildHeat() {{
  const g = document.getElementById("heat");
  if (!g) return;
  g.innerHTML = "";
  const days    = currentHeatDays;
  const slice   = HISTORY.days.slice(HISTORY.days.length - days);
  const cellMin = days<=7?"32px":days<=30?"12px":"6px";
  g.style.gridTemplateColumns = `56px repeat(${{days}}, minmax(${{cellMin}},1fr))`;

  g.appendChild(document.createElement("div"));
  const showEvery = days<=7?1:days<=30?5:15;
  slice.forEach((day,i) => {{
    const d = document.createElement("div");
    d.className = "heat-day";
    d.style.fontSize = days>30?"7px":"9px";
    d.textContent = i%showEvery===0 ? day.short : "";
    g.appendChild(d);
  }});

  const displaySlice = days === 7
    ? slice.filter(day => HISTORY.layer_ids.some(lid => day.layers[lid] && day.layers[lid] !== "none"))
    : slice;

  if (days === 7 && displaySlice.length !== slice.length) {{
    g.style.gridTemplateColumns = `56px repeat(${{displaySlice.length}}, minmax(32px,1fr))`;
    g.innerHTML = "";
    g.appendChild(document.createElement("div"));
    displaySlice.forEach((day,i) => {{
      const d = document.createElement("div");
      d.className = "heat-day";
      d.style.fontSize = "9px";
      d.textContent = day.short;
      g.appendChild(d);
    }});
  }}

  LAYERS.forEach((l) => {{
    const lbl = document.createElement("div");
    lbl.className = "heat-lbl";
    lbl.textContent = l.n1;
    g.appendChild(lbl);
    displaySlice.forEach((day) => {{
      const cell = document.createElement("div");
      cell.className = "heat-cell";
      cell.style.height = days>30?"13px":"18px";
      const realColor = day.layers[l.id];
      let displayColor;
      if (realColor && realColor !== "none") {{
        displayColor = colorFromName(realColor);
        cell.title = `${{l.n1}} · ${{day.label}} · ${{realColor}}`;
      }} else {{
        displayColor = days === 7 ? colorFromName(l.color) : "#EDEAE0";
        cell.style.opacity = days === 7 ? "0.4" : "1";
        cell.title = `${{l.n1}} · ${{day.label}} · ${{days===7?"estimated":"no data yet"}}`;
      }}
      cell.style.background = displayColor;
      g.appendChild(cell);
    }});
  }});
}}

function buildTopTicker(layers) {{
  const el = document.getElementById("top-ticker");
  if (!el) return;
  const STATUS = {{Red:"Hot",Orange:"Emerging",Green:"Neutral",Blue:"Cooling"}};
  const ICONS  = {{cooling:"❄️",networking:"🔌",optical:"💡",compute:"🖥️",colocation:"🏢"}};
  const items = [];
  layers.forEach(l => {{
    if (l.insufficient) return;
    l.tickers.slice(0,3).forEach(t => {{
      if (t.ret30 == null) return;
      const dir = t.ret30 > 1 ? "up" : t.ret30 < -1 ? "dn" : "neu";
      items.push(`<span class="t-item">
        <span class="t-sym">${{t.sym}}</span>
        <span>${{ICONS[l.id]||""}} ${{l.n1}} · ${{STATUS[l.color]||"Neutral"}}</span>
        <span class="t-${{dir}}">${{t.ret30>=0?"+":""}}${{t.ret30.toFixed(1)}}%</span>
      </span>`);
    }});
  }});
  if (items.length === 0) {{ el.innerHTML = ""; return; }}
  el.innerHTML = [...items,...items].join("");
}}

function buildSignalBars() {{
  const wrap = document.getElementById("signal-bars");
  if (!wrap) return;
  const heights = [8,14,22,28,24,18,10,14,20,28,22,16,8,12,20,26,28,18,10,8];
  const colors  = ["#378ADD","#378ADD","#534AB7","#534AB7","#E24B4A","#E24B4A",
                   "#534AB7","#534AB7","#378ADD","#378ADD","#534AB7","#E24B4A",
                   "#E24B4A","#534AB7","#378ADD","#378ADD","#534AB7","#534AB7","#E24B4A","#378ADD"];
  wrap.innerHTML = heights.map((h,i) =>
    `<div class="sbar" style="height:${{h}}px;background:${{colors[i]}};animation-delay:${{(i*0.07).toFixed(2)}}s"></div>`
  ).join("");
}}

function toggleMeth() {{
  const b = document.getElementById("meth-body");
  const a = document.getElementById("marrow");
  const open = b.classList.toggle("open");
  a.textContent = open ? "▴" : "▾";
}}

function sendPrompt(text) {{
  window.open('https://claude.ai/new?q=' + encodeURIComponent(text), '_blank');
}}

function buildCapexStrip() {{
  const el = document.getElementById("capex-strip");
  if (!el || !CAPEX) return;
  if (!CAPEX.direction) {{
    el.classList.add("insufficient");
    el.innerHTML = `
      <div class="capex-lbl">HYPERSCALER CAPEX DIRECTION</div>
      <div class="capex-dir" style="color:#8A9AB8">— Insufficient data</div>
      <div class="capex-meta">${{CAPEX.reporting || "0/4"}} hyperscalers reporting this run</div>`;
    return;
  }}
  const arrow = CAPEX.direction === "accelerating" ? "▲" : CAPEX.direction === "decelerating" ? "▼" : "→";
  const col   = CAPEX.direction === "accelerating" ? "#97C459" : CAPEX.direction === "decelerating" ? "#E8898A" : "#85B7EB";
  const pct   = (CAPEX.magnitude_pct * 100).toFixed(1);
  const dirLbl = CAPEX.direction.charAt(0).toUpperCase() + CAPEX.direction.slice(1);
  const chips = Object.values(CAPEX.beneficiary_map || {{}}).map(cat =>
    `<div class="capex-chip"><b>${{cat.description}}</b> → ${{cat.sub_layers.join(", ")}}</div>`
  ).join("");
  const insuffNote = (CAPEX.insufficient && CAPEX.insufficient.length)
    ? " · " + CAPEX.insufficient.map(i=>i.ticker).join(", ") + " insufficient data" : "";
  el.innerHTML = `
    <div class="capex-lbl">HYPERSCALER CAPEX DIRECTION</div>
    <div class="capex-dir" style="color:${{col}}">${{arrow}} ${{dirLbl}}
      <span style="font-size:13px;color:#C8D4E8;font-weight:400">${{pct}}% avg YoY</span></div>
    <div class="capex-meta">${{CAPEX.reporting}} hyperscalers reporting${{insuffNote}}</div>
    <div class="capex-chips">${{chips}}</div>
    <div class="capex-caveat">Context, not a per-category breakdown — capex data isn't differentiated by spend category. All beneficiary categories shown reflect where AI capex generally flows, not this run's specific allocation.</div>`;
}}

function buildHeroStatus() {{
  const el = document.getElementById("hero-chain-status");
  if (!el || !LAYERS.length) return;
  const HCOLOR = {{
    Red:    {{label:"BOTTLENECK", val:"#E24B4A", bg:"rgba(226,75,74,0.12)",   border:"rgba(226,75,74,0.5)"}},
    Orange: {{label:"EMERGING",   val:"#EF9F27", bg:"rgba(239,159,39,0.10)",  border:"rgba(239,159,39,0.4)"}},
    Green:  {{label:"NEUTRAL",    val:"#639922", bg:"rgba(8,8,26,0.5)",        border:"rgba(255,255,255,0.04)"}},
    Blue:   {{label:"EASING",     val:"#378ADD", bg:"rgba(55,138,221,0.10)",  border:"rgba(55,138,221,0.3)"}},
  }};
  const order = {{Red:0, Orange:1, Blue:2, Green:3}};
  const sorted = [...LAYERS].sort((a,b) => {{
    if (a.insufficient && b.insufficient) return 0;
    if (a.insufficient) return 1;
    if (b.insufficient) return -1;
    return (order[a.color] ?? 3) - (order[b.color] ?? 3);
  }});
  el.innerHTML = sorted.map(l => {{
    if (l.insufficient) {{
      return `<div style="flex:1;padding:7px 10px;background:rgba(180,178,169,0.1);border-right:0.5px solid rgba(255,255,255,0.06);">
        <div style="font-size:8px;color:#B4B2A9;font-weight:600;letter-spacing:.08em;margin-bottom:1px">NO DATA</div>
        <div style="font-size:11px;font-weight:500;color:#fff;margin-bottom:1px">${{l.n1}}</div>
        <div style="font-size:16px;font-weight:500;color:#8A9AB8;line-height:1">—</div>
      </div>`;
    }}
    const c = HCOLOR[l.color] || HCOLOR.Green;
    return `<div style="flex:1;padding:7px 10px;background:${{c.bg}};border-right:0.5px solid rgba(255,255,255,0.06);">
      <div style="font-size:8px;color:${{c.val}};font-weight:600;letter-spacing:.08em;margin-bottom:1px">${{c.label}}</div>
      <div style="font-size:11px;font-weight:500;color:#fff;margin-bottom:1px">${{l.n1}}</div>
      <div style="font-size:16px;font-weight:500;color:${{c.val}};line-height:1">${{l.score.toFixed(0)}}</div>
    </div>`;
  }}).join("");
}}

buildChain(); buildExpand(); buildHeat(); buildHeroStatus();
buildTopTicker(LAYERS); buildSignalBars(); buildCapexStrip();
document.getElementById("chain").addEventListener("scroll", updateChainFade, {{passive:true}});
window.addEventListener("resize", updateChainFade);
</script>
</body>
</html>"""

    path = Path("index.html")
    path.write_text(html, encoding="utf-8")
    log.info(f"  Dashboard saved: {path.absolute()}")
    return str(path.absolute())


# ── Delivery ──────────────────────────────────────────────────────────────────

def deliver(html_path: str):
    """
    HTML file + console print only. No email/Telegram — no .env/secrets
    configured for this project, no deploy target yet (PLAN.md step 7).
    """
    print("\n" + "="*60)
    print("  RAYDAR DATA CENTER — DASHBOARD GENERATED")
    print("="*60)
    print(f"\nDashboard: {html_path}")
    print("Open this file in your browser.\n")
