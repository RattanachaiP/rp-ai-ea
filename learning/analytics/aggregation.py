"""Deterministic macro and sample-weighted verified-statistic aggregation."""
from __future__ import annotations
from math import isfinite
from statistics import median
def finite(value):
    try: return float(value) if isfinite(float(value)) else None
    except (TypeError,ValueError): return None
def performance(records):
    fields={"win_rate":"verified_win_rate","average_rr":"average_rr","average_profit":"average_profit","average_loss":"average_loss","mae":"mae","mfe":"mfe","holding_time":"holding_time","significance":"statistical_significance","consistency":"consistency"}; out={"record_count":len(records),"aggregation_contract":"macro_average_and_sample_weighted_average"}
    sample_counts=[finite(getattr(r,"sample_count",None)) for r in records]; out["sample_count"]=sum(v for v in sample_counts if v is not None)
    for label,attr in fields.items():
        pairs=[(finite(getattr(r,attr,None)),finite(getattr(r,"sample_count",None))) for r in records]; valid=[(v,n) for v,n in pairs if v is not None]
        if valid: out[f"macro_{label}"]=sum(v for v,_ in valid)/len(valid)
        weighted=[(v,n) for v,n in valid if n is not None and n>0]
        if weighted: out[f"sample_weighted_{label}"]=sum(v*n for v,n in weighted)/sum(n for _,n in weighted)
    for label,attr in (("median_profit","average_profit"),("median_loss","average_loss")):
        values=[finite(getattr(r,attr,None)) for r in records]; values=[v for v in values if v is not None]
        if values: out[label]=median(values)
    return out
