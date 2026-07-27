# PR213 market-state producer integration gate

## Canonical source boundary

The production writer is
`RP_Market_State_Writer_V13_FULL_LOGIC_ATOMIC_WRITE.mq5`. Its name is recorded
in the system state, but its source is not tracked in this repository. The
tracked MQL5 programs are consumers of `market_state.json`; none is the
production market-state writer.

PR213 therefore must not introduce a reduced writer under the production V13
name. Doing so would silently discard the existing market-state calculations
and fields without providing schema compatibility evidence. The canonical V13
source must be imported from the production-controlled source before its
publication boundary can safely be changed.

## Required producer change

After the canonical source is available, its existing typed payload builder
must write these non-configurable values:

| Field | Canonical value |
|---|---|
| `producer` | `RP_AI_MT5_MARKET_STATE` |
| `producer_version` | `V1` |
| `schema_version` | `1.0` |
| `source_uuid` | `dc3777c6-cf0d-5a7b-bd58-8a5c44568475` |

The builder must not accept raw JSON fragments. Identity, sequence, heartbeat,
and producer-session fields are reserved producer-owned fields. Quality and
slippage values must enter the builder as typed results from an authoritative,
versioned calculation policy and must carry that policy's UUID, digest,
version, and source provenance. Spread must not be used as slippage.

EA restart semantics must be explicit: either persist a monotonically
increasing sequence across restarts or publish a stable
`producer_session_uuid` and boot epoch with each sequence. Runtime support for
the selected governed restart contract must be reviewed before deployment; it
must not be inferred or fabricated during startup.

## Merge evidence

The producer change is not production-ready until all of the following evidence
is captured from the actual V13 writer:

1. A before/after schema regression proving every existing market-state field
   and calculation is preserved.
2. Tests proving reserved-field injection and duplicate JSON keys are
   impossible and every output parses as JSON.
3. Tests binding slippage and quality fields to their governed policy identity
   and provenance.
4. A restart test proving the selected sequence/session semantics.
5. MetaEditor compilation with zero errors and zero warnings.
6. A live or demo run proving timer publication, atomic replacement, heartbeat
   and sequence progression, exact identity values, and acceptance by the
   unchanged PR212 fail-closed runtime validator.

Until that evidence exists, `runtime.environment_observation` remains unchanged
and must continue to reject missing or mismatched producer identity.
