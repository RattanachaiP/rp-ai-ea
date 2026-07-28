# PR235 Runtime Transition

The runtime begins in `STARTING`. A fallback or rejected publication cannot
promote it. The first verified NORMAL publication records `STARTING -> RUNNING`
and then `RUNNING -> HEALTHY`. Until that point `promotion_invariant` names the
exact preventing invariant; terminal initialization failures remain `STOPPED`.

A rejected NORMAL verification does not increment publication or success
counters. It first persists `DEGRADED`, the exact owner, canonical reason, and
diagnostic detail. If the runtime was already running, `status=RUNNING` and its
historical counters/evidence remain intact until a higher-sequence verified
NORMAL publication restores `HEALTHY`.
