# PR236 First Package

The checked-in `execution_package.json` is a controlled acceptance artifact,
not a claim of live broker execution. It demonstrates the complete canonical
shape using decision UUID `00000000-0000-4000-8000-000000000236`, market source
UUID `dc3777c6-cf0d-5a7b-bd58-8a5c44568475`, and market sequence 42.

The corresponding health artifact reports `VERIFIED` and `executor_ready=true`.
The trace records acceptance, construction, validation, and atomic publication.
A production invocation replaces these artifacts only from a fresh, verified
`decision.json` publication.
