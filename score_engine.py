"""
score_engine.py — Composite scoring engine for RayDar Data Center sub-layers.

BOTTLENECK-FOCUSED MODEL v3.1, adapted from reference/score_engine.py (PLAN.md
step 3) per decision #6's None-handling contract — see "Missing-data handling"
below for what changed and why.

Core thesis: Revenue acceleration is the primary bottleneck signal. When AI
demand exceeds supply in a sub-layer, revenue explodes first — margins and
analyst coverage follow 1-2 quarters later.

Scoring weights:
  65% Revenue Acceleration   ← primary bottleneck detector
  20% Constraint Signal      ← sub-layer supply pressure (news + capex_div)
  15% Smart Money            ← earliest leading indicator (positions before earnings)

Color thresholds:
  Red    > 65  — confirmed structural bottleneck
  Orange  45-65 — emerging constraint / acceleration building
  Green   25-45 — healthy growth, no constraint pressure
  Blue    < 25  — cooling or decelerating

Macro multiplier: Risk-On 1.0 / Neutral 0.85 / Risk-Off 0.65

Missing-data handling (decision #6 — this is the reason step 3 isn't a pure
copy of reference/score_engine.py, per spec D3's "reuse the design, not a bug
found empirically" rule):

  The reference's `_get(data, key, default=X)` helper silently substituted a
  hardcoded neutral value for any missing field and kept computing a full
  score, only noting the field name in a human-readable status string. A
  `None` (now a meaningful "this fetch failed" signal, not just "absent")
  would flow through arithmetic as if it were a real 0.0/1.0/50.0 — exactly
  the anti-pattern decision #6 exists to stop. It also crashed on a macro
  dict containing an explicit `None` (`.get("vix", 20.0)` returns `None`,
  not the default, when the key IS present with value `None` — `fetch_macro()`
  does this now).

  Replaced with three tiers:
    Field-level  — a missing input excludes that sub-component from its stage
                   and renormalizes the stage's remaining sub-component
                   weights. Never substitutes a fixed neutral number.
    Stage-level  — if a whole stage (acceleration/constraints/smart_money)
                   has zero usable input, it's dropped from the composite and
                   the top-level 65/20/15 weights renormalize across the
                   stages that DO have data.
    Ticker-level — only when acceleration (65% weight, "the primary
                   bottleneck detector") has zero usable input at all
                   (growth_curr, growth_prev, AND gm_delta all None) does the
                   whole score become `None` ("insufficient data") rather
                   than a number built from the remaining 35%. news_velocity
                   alone does NOT trigger this — at its actual weight (20%
                   constraints x 60% news = 12% of the composite), nuking the
                   whole score over it would flag "insufficient data" far too
                   often for what's really a minor gap.

  Every result also carries `stages_used` (which of the 3 top-level stages
  had usable input) and `reduced_input` (True if ANY field was excluded
  anywhere, even a single sub-component) — a coverage/confidence marker per
  A4's data-honesty principle. Threshold chosen deliberately low (any
  exclusion, not just a stage collapsing to one input): the point is to make
  a reduced-input score visibly distinguishable from a fully-supported one,
  not to only flag severe cases — downstream (render) decides how prominently
  to surface it, but the underlying data should never hide a partial read
  behind a number that looks identical to a complete one.

  The reference's error-path fallback (`score: 0.0, color: "Green"` on an
  unhandled exception) was the same anti-pattern one level up — a crash
  silently became an indistinguishable-from-real "neutral" reading. Fixed to
  `score: None` here too.
"""

import json
import logging
import datetime
from pathlib import Path

log = logging.getLogger(__name__)

AUDIT_LOG_FILE = "audit_log.json"


class ScoreEngine:
    def __init__(self, macro_data: dict):
        self.macro_data = macro_data or {}
        self.weights = {
            "acceleration": 0.65,   # revenue acceleration — primary bottleneck signal
            "constraints":  0.20,   # sub-layer supply pressure
            "smart_money":  0.15,   # confirmation
        }
        self.audit_log = {}

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
        return max(lo, min(hi, float(value)))

    # ── Stage 1: Revenue Acceleration (65%) ───────────────────────────────────

    def calculate_acceleration(self, data: dict, missing: list) -> tuple[float | None, float | None]:
        """
        Primary bottleneck signal: is revenue growth ACCELERATING?

        Three sub-components, renormalized if any are missing:
          50% Growth delta  — QoQ change in YoY growth rate (needs BOTH
                              growth_curr and growth_prev)
          30% Growth level  — absolute YoY revenue growth (needs growth_curr)
          20% Margin bonus  — gross margin delta (needs gm_delta)

        Returns (score_or_None, delta_or_None). score is None only when ALL
        THREE inputs are missing — see module docstring for why that's the
        ticker-level "insufficient data" trigger.

        Fundamental override: negative delta HARD CAPS score at 40 (unchanged
        from reference — this prevents any decelerating company from scoring
        Red, independent of missing-data handling).
        """
        g_curr = data.get("growth_curr")
        g_prev = data.get("growth_prev")
        gm     = data.get("gm_delta")

        if g_curr is None:
            missing.append("growth_curr")
        if g_prev is None:
            missing.append("growth_prev")
        if gm is None:
            missing.append("gm_delta")

        components = []  # (name, score_0_100, weight)

        delta = None
        if g_curr is not None and g_prev is not None:
            delta = g_curr - g_prev
            # Scaled so: delta +0.25 -> 100, delta 0 -> 50, delta -0.25 -> 0
            delta_score = self._clamp(delta * 200 + 50)
            components.append(("growth_delta", delta_score, 0.50))

        if g_curr is not None:
            if g_curr >= 1.0:        # 100%+ YoY — exceptional
                level_score = 100.0
            elif g_curr >= 0.50:     # 50-100% YoY — very strong
                level_score = self._clamp(75 + (g_curr - 0.50) * 50)
            elif g_curr >= 0.20:     # 20-50% YoY — solid growth
                level_score = self._clamp(50 + (g_curr - 0.20) * 83)
            elif g_curr >= 0.10:     # 10-20% YoY — moderate
                level_score = self._clamp(25 + (g_curr - 0.10) * 250)
            elif g_curr > 0:         # 0-10% — slow
                level_score = self._clamp(g_curr * 250)
            else:                    # negative growth
                level_score = 0.0
            components.append(("growth_level", level_score, 0.30))

        if gm is not None:
            # Only reward margin expansion — contraction doesn't penalise
            # separately (already captured by fundamentals narrative)
            margin_bonus = self._clamp(gm * 500) if gm > 0 else 0.0
            components.append(("margin_delta", margin_bonus, 0.20))

        if not components:
            # Acceleration has zero usable input — ticker-level insufficient
            # data trigger (module docstring).
            return None, None

        total_w = sum(w for _, _, w in components)
        raw = sum(score * (w / total_w) for _, score, w in components)

        # High-margin multiplier: +8% for high-margin accelerators (GM > 55%).
        # Absence of gross_margin just skips the (optional, additive-only)
        # bonus — never fabricates a penalty, so no missing-data risk here.
        gross_margin = data.get("gross_margin")
        if gross_margin is None:
            missing.append("gross_margin")
        elif gross_margin > 0.55 and (delta is None or delta >= 0):
            raw = min(raw * 1.08, 100.0)

        # Fundamental override — negative delta = decelerating = can't be a bottleneck
        if delta is not None and delta < 0:
            raw = min(raw, 40.0)

        return self._clamp(raw), delta

    # ── Stage 2: Constraints (20%) ────────────────────────────────────────────

    def calculate_constraints(self, data: dict, missing: list) -> float | None:
        """
        Supply pressure signal. news_velocity (60%) + capex_div (40%),
        renormalized if either is missing. The both-signal bonus and
        single-signal cap only fire when BOTH raw inputs are actually
        present — they're business rules about a real weak/strong signal,
        not applicable when a signal is simply absent.
        """
        news  = data.get("news_velocity")
        capex = data.get("capex_div")

        if news is None:
            missing.append("news_velocity")
        if capex is None:
            missing.append("capex_div")

        components = []
        if news is not None:
            components.append(("news_velocity", self._clamp(news * 10), 0.60))
        if capex is not None:
            components.append(("capex_div", self._clamp(capex * 100), 0.40))

        if not components:
            return None

        total_w = sum(w for _, _, w in components)
        raw = sum(score * (w / total_w) for _, score, w in components)

        if news is not None and capex is not None:
            # Both-signal bonus: reward when news AND capex both confirm constraint
            if news >= 3 and capex >= 0.3:
                raw = min(raw * 1.15, 100)
            # Single-signal cap: pure news without capex confirmation -> max 60
            if capex < 0.1 and news > 0:
                raw = min(raw, 60.0)

        return self._clamp(raw)

    # ── Stage 3: Smart Money (15%) ────────────────────────────────────────────

    def calculate_smart_money(self, data: dict, missing: list) -> float | None:
        """
        Confirmation signal only. Five weighted sub-components, renormalized
        over whichever are present: vol_spike (35%), analyst_upgrades (25%),
        short_int_change (15%), price_momentum (15%), price_30d_return (10%).
        price_act is a dampener MODIFIER on vol_score, not a weighted
        sub-component — if it's missing, the dampener just isn't applied
        (conservative default: no adjustment, not a fabricated one).
        """
        vol      = data.get("vol_spike")
        price    = data.get("price_act")
        upgrades = data.get("analyst_upgrades")
        short_ch = data.get("short_int_change")
        momentum = data.get("price_momentum")
        ret_30d  = data.get("price_30d_return")

        components = []

        if vol is not None:
            vol_score = self._clamp((vol - 1.0) * 50)
            if price is not None:
                if price < -0.03 and vol > 1.5:
                    vol_score *= 0.3
            else:
                missing.append("price_act")
            components.append(("vol_spike", vol_score, 0.35))
        else:
            missing.append("vol_spike")

        if upgrades is not None:
            components.append(("analyst_upgrades", self._clamp(upgrades * 15, 0, 30), 0.25))
        else:
            missing.append("analyst_upgrades")

        if short_ch is not None:
            components.append(("short_int_change", self._clamp(-short_ch * 200), 0.15))
        else:
            missing.append("short_int_change")

        if momentum is not None:
            momentum_score = self._clamp((momentum - 1.0) * 20) if momentum > 1.0 else 0.0
            components.append(("price_momentum", momentum_score, 0.15))
        else:
            missing.append("price_momentum")

        if ret_30d is not None:
            ret_score = self._clamp(ret_30d * 100) if ret_30d > 0 else 0.0
            components.append(("price_30d_return", ret_score, 0.10))
        else:
            missing.append("price_30d_return")

        if not components:
            return None

        total_w = sum(w for _, _, w in components)
        return self._clamp(sum(score * (w / total_w) for _, score, w in components))

    # ── Stage 4: Hype detection ───────────────────────────────────────────────

    def calculate_hype(self, data: dict, delta: float | None, missing: list) -> tuple[bool, list[str]]:
        """
        Hype warning: price running ahead of revenue fundamentals. A WARNING
        FLAG only, never a color override. Missing inputs just mean a rule
        can't be evaluated this run — it's skipped (never fired on a
        fabricated value), which is the safe failure direction for a warning.
        """
        price_30d  = data.get("price_30d_return")
        rev_growth = data.get("growth_curr")
        peer_outpf = data.get("peer_outperformance")
        if peer_outpf is None:
            missing.append("peer_outperformance")
        # price_30d_return / growth_curr are already tracked in `missing` by
        # calculate_smart_money / calculate_acceleration if absent.

        reasons = []

        if price_30d is not None and rev_growth is not None:
            if price_30d > 0.15 and rev_growth < 0.10:
                reasons.append(
                    f"Price +{price_30d*100:.0f}% in 30d "
                    f"but revenue growth only {rev_growth*100:.0f}%"
                )

        if peer_outpf is not None:
            if peer_outpf > 0.20 and (delta is None or delta < -0.02):
                reasons.append(
                    f"Outperforming peers by {peer_outpf*100:.0f}% "
                    f"with weak growth delta ({(delta or 0)*100:.1f}%)"
                )

        return len(reasons) > 0, reasons

    # ── Stage 5: Macro multiplier ─────────────────────────────────────────────

    def get_macro_multiplier(self, missing: list = None) -> tuple[float, str]:
        """
        Macro regime dampener, voting across up to 3 signals. A missing
        signal (None — fetch_macro() now returns None on failure, decision
        #6) is excluded from the vote entirely, not treated as a neutral
        default. `.get(key, default)` would NOT have caught this: the key is
        present with value None, so the reference's `.get("vix", 20.0)`
        pattern returned None itself and crashed on `None > 30` — this isn't
        just a decision-#6 honesty fix, it's also a correctness fix.

        If all 3 signals are missing, returns an explicit "Unknown" regime at
        1.0x (no dampening applied) rather than silently computing Risk-Off/
        Neutral from fabricated defaults.
        """
        missing = missing if missing is not None else []
        vix          = self.macro_data.get("vix")
        yield_change = self.macro_data.get("yield_10y_change")
        nasdaq_rel   = self.macro_data.get("nasdaq_vs_spx_20d")

        risk_signals = 0
        neut_signals = 0
        usable = 0

        if vix is not None:
            usable += 1
            if vix > 30:          risk_signals += 1
            elif vix > 20:        neut_signals += 1
        else:
            missing.append("macro_vix")

        if yield_change is not None:
            usable += 1
            if yield_change > 100:   risk_signals += 1
            elif yield_change > 50:  neut_signals += 1
        else:
            missing.append("macro_yield_10y_change")

        if nasdaq_rel is not None:
            usable += 1
            if nasdaq_rel < -0.05:   risk_signals += 1
            elif nasdaq_rel < -0.02: neut_signals += 1
        else:
            missing.append("macro_nasdaq_vs_spx_20d")

        if usable == 0:
            return 1.0, "Unknown (macro data unavailable)"

        if risk_signals >= 2:
            return 0.65, "Risk-Off"
        elif risk_signals == 1 or neut_signals >= 2:
            return 0.85, "Neutral"
        return 1.00, "Risk-On"

    # ── Stage 6: Color assignment ─────────────────────────────────────────────

    def determine_color(self, score: float, delta: float | None,
                        hype: bool, hype_reasons: list) -> tuple[str, str]:
        """
        Bottleneck-calibrated color thresholds (unchanged from reference —
        this stage only runs once `score` is already a real number; the
        ticker-level insufficient-data case is handled before this is
        called, in process_sector()).
        """
        if delta is not None and delta < 0:
            return "Blue", f"Cooling — negative growth delta ({delta*100:.1f}%)"

        if score > 65:
            if delta is not None and delta < 0.05:
                return "Orange", f"Emerging — high score but acceleration slowing ({delta*100:.1f}%)"
            return "Red", "Confirmed bottleneck — revenue accelerating into supply constraint"
        elif score >= 45:
            return "Orange", "Emerging — acceleration building"
        elif score < 25:
            return "Blue", "Cooling — constraint easing"
        else:
            return "Green", "Neutral — healthy growth, no constraint pressure"

    # ── Main entry point ──────────────────────────────────────────────────────

    def process_sector(self, sector_name: str, data: dict) -> dict:
        """
        Full scoring pipeline for one ticker. Never crashes. Always writes
        to audit_log. `score` is None when acceleration has zero usable
        input (ticker-level insufficient data) or on an unhandled error —
        never a fabricated number standing in for either case.
        """
        missing_fields = []
        stages_used = []

        try:
            accel_score, delta = self.calculate_acceleration(data, missing_fields)

            if accel_score is None:
                result = {
                    "score":         None,
                    "color":         None,
                    "status":        "Insufficient data — no usable growth data "
                                     "(growth_curr, growth_prev, gm_delta all missing)",
                    "regime":        None,
                    "multiplier":    None,
                    "sub_scores":    {},
                    "fund_delta":    None,
                    "is_hype":       False,
                    "hype_reasons":  [],
                    "stages_used":   [],
                    "data_missing":  missing_fields,
                    "reduced_input": True,
                    "data_status":   "Insufficient data",
                    "timestamp":     datetime.datetime.now().isoformat(),
                }
                self._record(sector_name, result, missing_fields)
                return result

            stages_used.append("acceleration")

            c_score = self.calculate_constraints(data, missing_fields)
            if c_score is not None:
                stages_used.append("constraints")

            s_score = self.calculate_smart_money(data, missing_fields)
            if s_score is not None:
                stages_used.append("smart_money")

            is_hype, hype_reasons = self.calculate_hype(data, delta, missing_fields)

            # ── Composite — renormalize top-level weights across used stages ──
            stage_scores  = {"acceleration": accel_score, "constraints": c_score, "smart_money": s_score}
            usable_stages = {k: v for k, v in stage_scores.items() if v is not None}
            total_w = sum(self.weights[k] for k in usable_stages)
            raw = sum(v * (self.weights[k] / total_w) for k, v in usable_stages.items())

            multiplier, regime = self.get_macro_multiplier(missing_fields)
            final_score = self._clamp(raw * multiplier)

            color, status = self.determine_color(final_score, delta, is_hype, hype_reasons)

            result = {
                "score":      round(final_score, 2),
                "color":      color,
                "status":     status,
                "regime":     regime,
                "multiplier": multiplier,
                "sub_scores": {
                    "acceleration":  round(accel_score, 2),
                    "constraints":   round(c_score, 2) if c_score is not None else None,
                    "smart_money":   round(s_score, 2) if s_score is not None else None,
                    "raw_composite": round(raw, 2),
                },
                "fund_delta":    round(delta, 4) if delta is not None else None,
                "is_hype":       is_hype,
                "hype_reasons":  hype_reasons,
                "stages_used":   stages_used,
                "data_missing":  missing_fields,
                "reduced_input": len(missing_fields) > 0,
                "data_status":   "Full" if not missing_fields else f"Reduced input — missing: {', '.join(missing_fields)}",
                "timestamp":     datetime.datetime.now().isoformat(),
            }

        except Exception as e:
            log.error(f"ScoreEngine error [{sector_name}]: {e}")
            missing_fields = missing_fields or ["pipeline_error"]
            result = {
                "score":         None,
                "color":         None,
                "status":        f"Scoring error — {e}",
                "regime":        None,
                "multiplier":    None,
                "sub_scores":    {},
                "fund_delta":    None,
                "is_hype":       False,
                "hype_reasons":  [],
                "stages_used":   [],
                "data_missing":  missing_fields,
                "reduced_input": True,
                "data_status":   f"Error: {e}",
                "timestamp":     datetime.datetime.now().isoformat(),
            }

        self._record(sector_name, result, missing_fields)
        return result

    # ── Audit log ─────────────────────────────────────────────────────────────

    def _record(self, sector_name: str, result: dict, missing_fields: list):
        self.audit_log[sector_name] = {
            "score":          result["score"],
            "color":          result["color"],
            "regime":         result["regime"],
            "sub_scores":     result.get("sub_scores", {}),
            "missing_fields": missing_fields,
            "data_status":    result["data_status"],
            "timestamp":      result["timestamp"],
        }
        self._append_audit(sector_name, result, missing_fields)

    def _append_audit(self, sector_name: str, result: dict, missing_fields: list):
        path = Path(AUDIT_LOG_FILE)
        log_entries = []
        if path.exists():
            try:
                log_entries = json.loads(path.read_text())
            except Exception:
                log_entries = []

        log_entries.append({
            "date":           datetime.datetime.now().strftime("%Y-%m-%d"),
            "time":           datetime.datetime.now().strftime("%H:%M:%S"),
            "sector":         sector_name,
            "score":          result["score"],
            "color":          result["color"],
            "regime":         result["regime"],
            "multiplier":     result.get("multiplier"),
            "sub_scores":     result.get("sub_scores", {}),
            "fund_delta":     result.get("fund_delta"),
            "is_hype":        result.get("is_hype", False),
            "stages_used":    result.get("stages_used", []),
            "missing_fields": missing_fields,
            "data_status":    result["data_status"],
        })

        log_entries = log_entries[-500:]
        path.write_text(json.dumps(log_entries, indent=2, ensure_ascii=False))


# ── Self-test ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    engine = ScoreEngine({
        "vix":               16.6,
        "yield_10y_change":  24.8,
        "nasdaq_vs_spx_20d": 0.017,
    })

    print("\n" + "="*60)
    print("  ScoreEngine v3.1 (decision #6 None-handling) — self-test")
    print("="*60)

    print("\nTest 1 — full data (VRT-shaped, confirmed bottleneck)")
    r = engine.process_sector("cooling_VRT", {
        "growth_curr": 0.1369, "growth_prev": -0.0098, "gm_delta": -0.0002,
        "gross_margin": 0.3804, "news_velocity": 2.0, "capex_div": 0.1587,
        "vol_spike": 0.68, "price_act": 0.0077, "analyst_upgrades": 0,
        "short_int_change": 0.0142, "price_30d_return": -0.0754,
        "price_momentum": 4.0, "peer_outperformance": 0.0,
    })
    print(f"  Score: {r['score']} | Color: {r['color']} | reduced_input={r['reduced_input']}")
    print(f"  stages_used={r['stages_used']} data_missing={r['data_missing']}")

    print("\nTest 2 — missing news_velocity only (constraints reduces to capex-only)")
    r2 = engine.process_sector("test_missing_news", {
        "growth_curr": 0.20, "growth_prev": 0.10, "gm_delta": 0.02,
        "gross_margin": 0.40, "capex_div": 0.3,
        "vol_spike": 1.2, "price_act": 0.01, "analyst_upgrades": 1,
        "short_int_change": 0.0, "price_30d_return": 0.05,
        "price_momentum": 1.1, "peer_outperformance": 0.0,
    })
    print(f"  Score: {r2['score']} | Color: {r2['color']} | reduced_input={r2['reduced_input']}")
    print(f"  stages_used={r2['stages_used']} data_missing={r2['data_missing']}")

    print("\nTest 3 — acceleration fully blind (growth_curr/prev/gm_delta all missing)")
    r3 = engine.process_sector("test_insufficient", {
        "news_velocity": 5.0, "capex_div": 0.4,
        "vol_spike": 1.3, "price_act": 0.02, "analyst_upgrades": 2,
        "short_int_change": -0.01, "price_30d_return": 0.10,
        "price_momentum": 1.5, "peer_outperformance": 0.05,
    })
    print(f"  Score: {r3['score']} | Color: {r3['color']} | status: {r3['status']}")
    assert r3["score"] is None, "expected insufficient-data ticker-level score to be None"

    print("\nTest 4 — macro with VIX missing (2/3 signals usable)")
    engine_partial_macro = ScoreEngine({"vix": None, "yield_10y_change": 24.8, "nasdaq_vs_spx_20d": 0.017})
    mult, regime = engine_partial_macro.get_macro_multiplier([])
    print(f"  multiplier={mult} regime={regime}")

    print("\nTest 5 — macro fully missing (0/3 signals usable)")
    engine_no_macro = ScoreEngine({"vix": None, "yield_10y_change": None, "nasdaq_vs_spx_20d": None})
    mult5, regime5 = engine_no_macro.get_macro_multiplier([])
    print(f"  multiplier={mult5} regime={regime5}")
    assert regime5 == "Unknown (macro data unavailable)"

    print("\nSelf-test complete.")
