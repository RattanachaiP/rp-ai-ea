# PR235 Runtime Transition

The runtime begins in `STARTING`. A fallback or rejected publication cannot
promote it. The first verified NORMAL publication records `STARTING -> RUNNING`
and then `RUNNING -> HEALTHY`. Until that point `promotion_invariant` names the
exact preventing invariant; terminal initialization failures remain `STOPPED`.

