#!/usr/bin/env python3
"""Generate the theme-focused stage-1 batch for small-cap reversal mining.

Uses blind_mining_engine.candidate_id / expression_hash so the ledger stays
compatible with the three-stage genetic engine for later stages.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

SKILL_SCRIPTS = Path(r"c:\Users\攀泊桓\Desktop\Quant_Lab\Quant_Lab\skill-factor-mining-pandaai\scripts")
sys.path.insert(0, str(SKILL_SCRIPTS))

from blind_mining_engine import candidate_id, expression_hash  # noqa: E402
from pandaai_quant_operators import validate  # noqa: E402

# (family, formula, direction, hypothesis, parameters)
CANDIDATES = (
    # Family 1: pure short/mid-horizon reversal (close-based)
    ("reversal", "ref(close,5)/close-1", 1,
     "5-day short-horizon reversal: past losers bounce back", {"lookback": 5}),
    ("reversal", "ref(close,10)/close-1", 1,
     "10-day short-horizon reversal", {"lookback": 10}),
    ("reversal", "ref(close,20)/close-1", 1,
     "20-day monthly reversal", {"lookback": 20}),
    ("reversal", "ref(close,40)/close-1", 1,
     "40-day medium reversal", {"lookback": 40}),
    # Family 2: reversal scaled by small-size proxy (market_cap / amount)
    ("size_reversal", "(ref(close,5)/close-1)/(abs(market_cap)+0.000001)", 1,
     "5-day reversal amplified by small market cap", {"lookback": 5, "size_proxy": "market_cap"}),
    ("size_reversal", "(ref(close,10)/close-1)/(abs(market_cap)+0.000001)", 1,
     "10-day reversal amplified by small market cap", {"lookback": 10, "size_proxy": "market_cap"}),
    ("size_reversal", "(ref(close,20)/close-1)/(abs(market_cap)+0.000001)", 1,
     "20-day reversal amplified by small market cap", {"lookback": 20, "size_proxy": "market_cap"}),
    ("size_reversal", "(ref(close,5)/close-1)/(amount+0.000001)", 1,
     "5-day reversal amplified by low turnover amount (size proxy)", {"lookback": 5, "size_proxy": "amount"}),
)

MARKET_FIELD = {
    "name": "CLOSE", "category": "market", "type": "double",
    "description": "收盘价", "source": "default",
}

population = []
for family, formula, direction, hypothesis, params in CANDIDATES:
    check = validate(formula)
    if not check["valid"]:
        raise SystemExit(f"invalid formula {formula}: {check}")
    population.append({
        "schema_version": 2,
        "candidate_id": candidate_id(formula, direction),
        "expression_hash": expression_hash(formula),
        "generation": 1,
        "stage": 1,
        "genome": {
            "stage": 1, "family": family, "field": "close",
            "other_field": None, "window": params["lookback"],
            "ts_op": "none", "cs_op": "none", "direction": direction,
        },
        "family": family,
        "fields": [dict(MARKET_FIELD)],
        "factor_direction": direction,
        "formula": formula,
        "hypothesis": hypothesis,
        "parameters": params,
        "status": "proposed",
        "metrics": {},
        "fitness": None,
    })

payload = {
    "engine": "theme-focused-stage1",
    "research_theme": "small-cap-reversal",
    "stage": 1,
    "generation": 1,
    "audit": {
        "unique_candidates": len(population),
        "families": sorted({x["family"] for x in population}),
        "note": "platform market_cap/amount availability is validated by this run",
    },
    "population": population,
}

out = Path(__file__).with_name("batch_stage1.json")
out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"wrote {len(population)} candidates -> {out}")
