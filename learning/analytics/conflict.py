"""Deterministic conflict findings; invalid metrics are never coerced."""
from __future__ import annotations
from .aggregation import finite

def detect_conflicts(records, config):
    findings = []
    def key(record):
        return (tuple(sorted(record.applicable_symbols)), tuple(sorted(record.applicable_sessions)), tuple(sorted(record.applicable_market_states)))
    groups = {}
    for record in records:
        groups.setdefault(key(record), []).append(record)
    for condition, rows in sorted(groups.items(), key=lambda item: repr(item[0])):
        active = [record for record in rows if record.knowledge_status == "ACTIVE"]
        for index, left in enumerate(active):
            for right in active[index + 1:]:
                left_win, right_win = finite(left.verified_win_rate), finite(right.verified_win_rate)
                left_rr, right_rr = finite(left.average_rr), finite(right.average_rr)
                win = abs(left_win - right_win) if left_win is not None and right_win is not None else None
                rr = abs(left_rr - right_rr) if left_rr is not None and right_rr is not None else None
                if not ((win is not None and win >= config.conflict_win_rate_delta) or (rr is not None and rr >= config.conflict_rr_delta)):
                    continue
                high = ((win is not None and win >= 2 * config.conflict_win_rate_delta) or (rr is not None and rr >= 2 * config.conflict_rr_delta))
                finding = {"severity": "HIGH" if high else "MEDIUM", "condition": {"symbols": list(condition[0]), "sessions": list(condition[1]), "market_states": list(condition[2])}, "knowledge_ids": sorted((left.knowledge_uuid, right.knowledge_uuid))}
                if win is not None: finding["win_rate_delta"] = win
                if rr is not None: finding["average_rr_delta"] = rr
                findings.append(finding)
    return tuple(sorted(findings, key=lambda item: (item["severity"], item["knowledge_ids"])))[:config.maximum_findings]
