"""Deterministic aggregation helpers; never read evidence or market data."""
from __future__ import annotations
from math import isfinite
from statistics import median

def finite(value):
    try: return float(value) if isfinite(float(value)) else None
    except (TypeError, ValueError): return None

def performance(records):
    fields = {"sample_count":"sample_count", "win_rate":"verified_win_rate", "average_rr":"average_rr", "average_profit":"average_profit", "average_loss":"average_loss", "mae":"mae", "mfe":"mfe", "holding_time":"holding_time", "significance":"statistical_significance", "consistency":"consistency"}
    out = {"record_count": len(records)}
    for label, attr in fields.items():
        values=[finite(getattr(r, attr, None)) for r in records]; values=[v for v in values if v is not None]
        if values: out[label] = sum(values) if label == "sample_count" else sum(values)/len(values)
    for label, attr in (("median_profit", "average_profit"), ("median_loss", "average_loss")):
        values=[finite(getattr(r,attr,None)) for r in records]; values=[v for v in values if v is not None]
        if values: out[label]=median(values)
    return out
