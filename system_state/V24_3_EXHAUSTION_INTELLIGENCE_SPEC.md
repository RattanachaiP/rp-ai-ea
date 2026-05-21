# RP Trading GPT — V24.3 Exhaustion Intelligence REPORT MODE

## Goal

Add an Exhaustion Intelligence Layer that:

* detects possible trend exhaustion
* detects late continuation risk
* detects momentum decay
* evaluates runner safety
* improves expectancy analysis

IMPORTANT:

V24.3 is REPORT MODE only.

It must:

* NOT hard block trades yet
* NOT change core V23/V24 entry logic aggressively
* NOT freeze the AI
* only add diagnostics + intelligence fields

---

# Core Philosophy

Current system:

* already follows trend better
* already has improved synchronization
* already has better continuation awareness

Main remaining weakness:

AI still enters too late during mature trends.

V24.3 objective:

Teach AI to understand:

* trend maturity
* exhaustion probability
* continuation quality decay
* runner danger level

without destroying trade frequency.

---

# V24.3 Modules

## 1. Vertical Expansion Detector

Purpose:

Detect abnormal expansion candles.

Signals:

* large candle body expansion
* ATR expansion spike
* BB distance expansion
* consecutive impulse candles

Output:

```json
"vertical_expansion": true,
"expansion_strength": 78
```

---

## 2. RSI Blowoff Detector

Purpose:

Detect overextended momentum.

Rules example:

BUY side:

* RSI >= 72

SELL side:

* RSI <= 28

Output:

```json
"rsi_blowoff": true,
"rsi_exhaustion_score": 80
```

---

## 3. Wick Rejection Detector

Purpose:

Detect rejection near exhaustion.

Signals:

* upper wick exhaustion
* lower wick exhaustion
* wick/body imbalance

Output:

```json
"wick_rejection": true,
"wick_direction": "UPPER",
"wick_risk": 67
```

---

## 4. Momentum Decay Detector

Purpose:

Detect weakening continuation.

Examples:

* price still trends
* MACD histogram weakens
* AO momentum fades
* expansion loses acceleration

Output:

```json
"momentum_decay": true,
"momentum_decay_score": 74
```

---

## 5. Trend Age Estimator

Purpose:

Estimate lifecycle stage.

States:

```text
FRESH
MATURE
EXHAUSTING
```

Output:

```json
"trend_age": "MATURE",
"trend_age_score": 62
```

---

## 6. Runner Safety Estimator

Purpose:

Determine if HOLD_TRAIL is safe.

Output:

```json
"runner_safety": "LOW",
"runner_risk_score": 81
```

IMPORTANT:

V24.3 only REPORTS.

It does NOT disable runner yet.

---

# Required decision.json Additions

```json
"vertical_expansion": false,
"expansion_strength": 0,

"rsi_blowoff": false,
"rsi_exhaustion_score": 0,

"wick_rejection": false,
"wick_direction": "NONE",
"wick_risk": 0,

"momentum_decay": false,
"momentum_decay_score": 0,

"trend_age": "FRESH",
"trend_age_score": 0,

"runner_safety": "SAFE",
"runner_risk_score": 0,

"exhaustion_risk": 0
```

---

# Exhaustion Risk Aggregation

Suggested formula:

```text
exhaustion_risk =
(
vertical_expansion
+ rsi_exhaustion
+ wick_rejection
+ momentum_decay
+ trend_age
) / weighted average
```

Range:

```text
0-100
```

---

# IMPORTANT SAFETY RULES

V24.3 MUST NOT:

* hard block trades aggressively
* disable continuation logic globally
* replace V23/V24 strategy flow
* freeze TREND mode

V24.3 should:

* observe
* report
* measure
* log
* prepare V24.4 runner protection

---

# Future Integration Plan

## V24.4

Runner Protection Layer

Use:

* exhaustion_risk
* runner_safety
* trend_age

to:

* delay HOLD_TRAIL
* reduce runner activation
* protect expectancy

---

## V24.5

RR-First Decision Engine

Goal:

Prefer:

* high expectancy setups
* lower exhaustion risk
* better trend lifecycle positioning

instead of:

* maximum trade frequency

---

# Current Development Phase

```text
OBSERVE
→ UNDERSTAND
→ REPORT
→ REFINE
→ CONTROL
```

NOT:

```text
PATCH EVERYTHING IMMEDIATELY
```

---

# Strategic Objective

Transform RP Trading GPT from:

```text
Indicator-based trend EA
```

into:

```text
Market Behavior Intelligence System
```
