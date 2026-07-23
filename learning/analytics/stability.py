"""Sequential contiguous-lineage stability calculations."""
from __future__ import annotations
from .aggregation import finite
FIELDS = ("sample_count", "verified_win_rate", "average_rr", "average_profit", "average_loss", "mae", "mfe", "consistency", "statistical_significance")

def stability(records, config):
    out, by_pattern = [], {}
    for record in records: by_pattern.setdefault(record.pattern_uuid, []).append(record)
    for lineage, items in sorted(by_pattern.items()):
        items = sorted(items, key=lambda item: (item.knowledge_version, item.created_timestamp, item.knowledge_uuid))
        valid = len(items) >= 2 and all(item.knowledge_version == position for position, item in enumerate(items, 1))
        if not valid:
            out.append({"pattern_uuid": lineage, "classification": "INSUFFICIENT_HISTORY", "knowledge_ids": [item.knowledge_uuid for item in items], "lineage_integrity": "NON_CONTIGUOUS"})
            continue
        old, new, deltas = items[-2], items[-1], {}
        for field in FIELDS:
            before, after = finite(getattr(old, field, None)), finite(getattr(new, field, None))
            if before is not None and after is not None: deltas[field] = after - before
        win, rr = deltas.get("verified_win_rate"), deltas.get("average_rr")
        if win is None and rr is None: classification = "INSUFFICIENT_HISTORY"
        elif abs(win or 0) <= config.stable_win_rate_delta and abs(rr or 0) <= config.stable_rr_delta: classification = "STABLE"
        elif (win is not None and win >= config.improving_win_rate_delta) or (rr is not None and rr >= config.improving_rr_delta): classification = "IMPROVING"
        elif (win is not None and win <= -config.improving_win_rate_delta) or (rr is not None and rr <= -config.improving_rr_delta): classification = "DEGRADING"
        else: classification = "TRANSITIONAL"
        out.append({"pattern_uuid": lineage, "previous_knowledge_uuid": old.knowledge_uuid, "knowledge_uuid": new.knowledge_uuid, "deltas": deltas, "classification": classification, "lineage_integrity": "CONTIGUOUS"})
    return {"lineages": out}
