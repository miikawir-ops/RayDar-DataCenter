"""
config.py — Sub-layer and ticker definitions for RayDar Data Center.

Single source of truth for the 5 data-center sub-layers (Part B2 of
DATACENTER_RAYDAR_SPEC.md). fetch_market.py, main.py, and render.py all
import from here rather than defining tickers/keywords inline.

brand_keywords vs context_keywords split (added after the 4a checkpoint
found universal 10.0 saturation): a bare company-name mention (e.g.
"Vertiv") is guaranteed to appear in almost every headline about that
ticker regardless of whether there's any real constraint-relevant news
that day — ticker-ownership is already established via the headline's
`ticker` field, not by matching the brand name in text. So brand names
no longer count as a real match on their own for ticker-sourced
headlines; only context_keywords do. brand_keywords are kept separately
because they're still useful for GENERIC headlines (no ticker field),
where a brand mention is the only way to tie an unattributed headline to
a specific company.

GENERIC_BOTTLENECK_KEYWORDS (added after re-checking the 4a checkpoint):
the first context_keywords pass was technical-jargon-heavy (e.g. "DWDM",
"1.6T") and missed how real financial journalism actually describes a
supply/demand bottleneck — plain language like "backlog" or "supply
constraint", not spec-level jargon. Confirmed on CIEN specifically: 10/10
headlines carried genuine bottleneck content ("backlog just hit $8.5B",
"supply constraints", "supply risks") but scored 0 matches because none
of the jargon terms were present. Added to ALL 5 sub-layers uniformly —
not just the ones whose first-pass score disagreed with a prediction —
so this is a general vocabulary fix, not a targeted one dressed up as
general.
"""

GENERIC_BOTTLENECK_KEYWORDS = [
    "backlog", "supply constraint", "supply constraints", "supply risk",
    "supply risks", "demand outpacing supply", "capacity constrained",
    "demand surge", "sold out", "supply tight",
]

CAPEX_TICKERS = ["MSFT", "GOOGL", "AMZN", "META"]  # Part B5 hyperscaler capex-trend universe

# Single-quarter YoY capex-trend label thresholds (PLAN.md decision #4).
# Picked from verified capex history, not guessed: pre-AI hyperscaler capex growth
# topped out around 30-43% in strong years (2018: +43%; 2016-2020 avg: ~32%) and ran
# near-flat in soft years (2019: +1%). The current AI-driven regime has run ~70-80%+
# YoY sustained since ~Q2 2023 — the 4b real readings (2026-09-17: MSFT +109.6%,
# GOOGL +100.1%, AMZN +76.7%, META +82.1%) reflect that established regime, not a
# fresh spike. Expect ACCELERATING to read true for an extended period while the
# supercycle holds — that's the regime being real, not the thresholds being stuck.
CAPEX_YOY_ACCELERATING_PCT = 0.30  # >30% YoY = accelerating
CAPEX_YOY_DECELERATING_PCT = 0.05  # <5% YoY = decelerating; 5-30% = stable

# Minimum hyperscalers required to compute an aggregate capex direction
# (PLAN.md step 5b). With only 0-1 of 4 reporting, there's no real "aggregate"
# to speak of — it would just be one company's number mislabeled as a
# consensus. 2+ is the minimum bar for an averaged magnitude to mean anything
# as an aggregate, even though it's still a partial one (always disclosed via
# "reporting": "N/4", never silently presented as if it were 4/4).
#
# HONEST CAVEAT: that reasoning only actually justifies "must be >=2" (ruling
# out the degenerate 1-company case) — it does NOT establish why 2 specifically
# rather than 3 (a stricter majority-of-4 bar). 3 would be a legitimate,
# arguably more conservative alternative given GOOGL's documented fragility
# (decision #4 — exactly 5 quarters total, zero margin on the 4-back slot,
# one bad data pull from flipping to insufficient-data). That tradeoff wasn't
# actually weighed when 2 was picked; this isn't a data-derived cutoff like
# the two thresholds above, it's the simplest floor above the degenerate case.
# Revisit if a real run ever drops below 4/4 and 2 vs 3 starts to matter in
# practice. Untested against real data as of 2026-09-18 — every run so far
# has been 4/4;
# documented so the rule exists before the branch is ever exercised.
CAPEX_MIN_REPORTING = 2

SUB_LAYERS = {
    "cooling": {
        "name": "Cooling",
        "tickers": ["VRT"],
        "brand_keywords": ["vertiv"],
        "context_keywords": [
            "liquid cooling", "direct liquid cooling", "DLC",
            "cooling", "thermal management", "power density",
            "heat dissipation", "immersion cooling", "cold plate",
            "rack density", "cooling capacity", "cooling systems",
            "heat exchanger", "CDU", "coolant distribution unit",
        ] + GENERIC_BOTTLENECK_KEYWORDS,
    },
    "networking": {
        "name": "Networking",
        "tickers": ["ANET", "CSCO"],
        "brand_keywords": ["arista", "cisco"],
        "context_keywords": [
            "networking", "ethernet", "InfiniBand",
            "interconnect", "Ultra Ethernet", "switching", "network switch",
            "network bandwidth", "network fabric", "spine leaf",
            "data center networking", "AI networking",
        ] + GENERIC_BOTTLENECK_KEYWORDS,
    },
    "optical": {
        "name": "Optical",
        "tickers": ["CIEN", "LITE", "COHR", "GLW"],
        "brand_keywords": ["ciena", "lumentum", "coherent", "corning"],
        "context_keywords": [
            "optical networking", "optical transceiver", "400G", "800G",
            "1.6T", "fiber", "wavelength", "DWDM", "pluggable optics",
            "silicon photonics", "optical module", "transceiver",
            "fiber optic", "optical interconnect",
        ] + GENERIC_BOTTLENECK_KEYWORDS,
    },
    "compute": {
        "name": "Compute Assembly",
        "tickers": ["SMCI", "DELL", "HPE"],
        "brand_keywords": ["supermicro", "dell technologies", "hewlett packard enterprise"],
        "context_keywords": [
            "server rack", "AI server", "server integration", "rack-scale",
            "rack scale", "GPU cluster", "AI factory", "server shipment",
            "server assembly", "compute infrastructure",
        ] + GENERIC_BOTTLENECK_KEYWORDS,
    },
    "colocation": {
        "name": "Colocation",
        "tickers": ["EQIX", "DLR"],
        "brand_keywords": ["equinix", "digital realty"],
        "context_keywords": [
            "colocation", "hyperscale",
            "data center real estate", "data center capacity",
            "data center leasing", "data center REIT", "powered shell",
            "data center campus",
        ] + GENERIC_BOTTLENECK_KEYWORDS,
    },
}

# Capex beneficiary taxonomy (Part B3), consumed by render (step 6), not
# score_engine (decision #1 — display overlay only, never a scoring input).
#
# STATIC CONTEXTUAL TAXONOMY, NOT A PER-CATEGORY BREAKDOWN. fetch_capex_trend()
# reports one YoY% per hyperscaler (MSFT/GOOGL/AMZN/META) — it does NOT
# differentiate what that capex is actually being spent on (GPU clusters vs.
# interconnect vs. facilities). So when the aggregate direction reads
# "accelerating," ALL THREE categories below surface together as context for
# where AI capex generally flows — this is not a claim that this specific
# run's capex went disproportionately toward GPUs, or interconnect, or
# facilities. A future version with spend-category-level data could make this
# targeted; this one can't, and shouldn't be read as if it already is.
#
# Part B4 boundary: this map covers IN-BUILDING power distribution only
# (PDUs/UPS, folded into the cooling/compute GPU-cluster category below).
# Site-level power delivery (generation, grid, transmission, substations)
# belongs to the parent's Energy layer — do not add it here.
CAPEX_BENEFICIARY_MAP = {
    "gpu_clusters": {
        "description": "More GPU clusters deployed",
        "sub_layers":  ["cooling", "compute"],
    },
    "interconnect": {
        "description": "More interconnect bandwidth needed",
        "sub_layers":  ["networking", "optical"],
    },
    "facilities": {
        "description": "More data center facilities/capacity",
        "sub_layers":  ["colocation"],
    },
}
