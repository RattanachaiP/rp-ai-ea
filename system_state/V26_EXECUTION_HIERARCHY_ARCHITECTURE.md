# RP V26 EXECUTION HIERARCHY ARCHITECTURE

Generated: 2026-05-21 05:56:13

Purpose:
Transform RP Trading GPT from fear-optimized filtering AI into controlled probabilistic execution intelligence.

---

# 1. Critical System Decision

Current main problem is no longer trend direction.

Current main problem:

```text
EXECUTION PARALYSIS
```

Observed behavior:

The system blocks too many trades through:

- TRANSITION
- WAIT
- SOFT LOCK
- STALE
- COOLDOWN
- NO_TRADE

Result:

- strong trend opportunities skipped
- execution frequency too low
- no meaningful expectancy growth
- weak real-world learning
- AI becomes fear-optimized

---

# 2. New Core Philosophy

AI must stop trying to eliminate all losses.

Controlled losses are acceptable and necessary for:

- trend participation
- expectancy development
- timing improvement
- execution learning
- pullback learning
- runner evolution

Goal:

```text
controlled execution
NOT paralysis
```

---

# 3. WAIT Is Not NO_TRADE

## WAIT

Means:

```text
timing not ideal yet
```

## NO_TRADE

Means:

```text
market structurally invalid
or infrastructure unsafe
```

These must be separated clearly.

---

# 4. V26 Core Architecture Change

## Old System

```text
hard veto chain
```

Example:

```text
1 filter fail
=> NO_TRADE
```

## New System

```text
probabilistic execution scoring
```

Most conditions become score adjustments instead of hard vetoes.

---

# 5. Execution Confidence Engine

V26 introduces:

```text
execution_confidence_score
```

Suggested score model:

| Condition | Score Impact |
|---|---:|
| H1/H4 aligned | +40 |
| M15 structure good | +25 |
| M3 timing acceptable | +15 |
| Good RR | +15 |
| Good entry location | +15 |
| Late entry risk | -15 |
| Exhaustion risk | -20 |
| Weak pullback | -10 |

---

# 6. New Execution States

V26 does not use only TRADE / NO_TRADE.

Required states:

```text
EXECUTE_AGGRESSIVE
EXECUTE_NORMAL
EXECUTE_CAUTIOUS
WAIT
NO_TRADE
```

| State | Meaning |
|---|---|
| EXECUTE_AGGRESSIVE | Strong trend + good location + good RR |
| EXECUTE_NORMAL | Valid setup with acceptable confidence |
| EXECUTE_CAUTIOUS | Lower confidence, controlled scalp only |
| WAIT | Timing not ready, but bias preserved |
| NO_TRADE | Hard invalid / unsafe / structurally bad |

---

# 7. M3 Authority Reduction

Current issue:

```text
M3 fully vetoes H1/H4 trends.
```

New structure:

```text
H1/H4 = market authority
M15 = setup structure
M3 = timing refinement only
```

M3 should not fully block strong higher-timeframe alignment except during:

- severe exhaustion
- extreme reversal probability
- structural invalidation

---

# 8. Hard Blocks Must Be Rare

Keep only true safety hard blocks:

- stale decision beyond live tolerance
- file corruption
- invalid JSON
- abnormal spread
- no liquidity
- broker freeze
- invalid market data
- invalid schema
- hard risk guard

Everything else:

```text
score adjustment
not hard veto
```

---

# 9. Required decision.json Fields

```json
{
  "execution_state": "EXECUTE_CAUTIOUS",
  "execution_confidence_score": 62,
  "execution_confidence_reason": "H1/H4 aligned; M15 acceptable; M3 timing weak penalty",
  "htf_authority": "BUY",
  "m15_setup_quality": 70,
  "m3_timing_quality": 45,
  "hard_block": false,
  "hard_block_reason": "",
  "wait_reason": "",
  "next_trigger": "",
  "bias_preserved": true
}
```

---

# 10. V26 Priority Stack

Order of authority:

```text
1. Infrastructure safety
2. HTF direction authority
3. M15 setup quality
4. Entry location / RR
5. M3 timing refinement
6. Momentum confirmation
7. Indicator context
```

Important:

```text
M3 timing can reduce confidence.
M3 timing should not automatically kill HTF trend.
```

---

# 11. Controlled Execution Dataset Objective

System must execute enough trades to learn:

- actual win/loss distribution
- entry timing quality
- pullback survival
- continuation quality
- exit behavior
- structure BE behavior
- scalp vs hold behavior

No-trade spam is not useful.

---

# 12. Final Objective

Transform RP Trading GPT from:

```text
fear-optimized filtering AI
```

into:

```text
controlled probabilistic execution intelligence
```

Priority:

```text
execution quality with sufficient participation
NOT paralysis
```

---

# 13. Implementation Recommendation

Recommended next file:

```text
ai_decision_engine_xauusd_v26_execution_confidence_engine.py
```

Base file:

```text
ai_decision_engine_xauusd_v25_6_spike_pullback_reentry.py
```

V26.0 should implement:

1. execution_confidence_score
2. execution_state
3. WAIT vs NO_TRADE separation
4. HTF/M15/M3 hierarchy
5. hard_block_reason audit
6. controlled SCALP_TP execution when confidence is acceptable

Do not re-enable uncontrolled runner yet.
