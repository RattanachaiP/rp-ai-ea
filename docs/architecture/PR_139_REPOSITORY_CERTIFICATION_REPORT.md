# PR #139 — Repository Certification Report

**Assessment date:** 2026-07-23  
**Scope:** repository architecture, contracts, schemas, dependencies, boundaries, imports,
documentation, and tracked-file hygiene.  
**Change classification:** certification documentation only; no runtime source, domain, or
feature behavior is changed.

## Certification decision

**CONDITIONALLY CERTIFIED FOR ARCHITECTURE REVIEW.** The repository's tested runtime and RAIP
domains are internally coherent at this baseline. Architecture Review must record acceptance of
the two non-runtime follow-ups below before treating this as a fully reproducible release
certification:

1. Add a pinned Python dependency manifest and documented supported Python version.
2. Resolve the intentionally unassigned V8 authority before a future V8-dependent domain or
contract is proposed.

Neither follow-up authorizes a runtime change, new RAIP domain, or merge by itself.

## Audit method and evidence

* Executed the complete Python suite with `python -m pytest`: **256 passed**. The only output
  was three expected unknown-CSV-schema warnings from trade-statistics fixtures.
* Parsed all Python imports with `ast`; production cross-root edges are limited to
  `bridge -> brain`, `runtime -> brain`, and `runtime -> bridge`. `review_engine` has no imports
  from trading roots.
* Compared domain contracts and schema constants against the canonical registry and interface
  specification.
* Examined tracked and ignored repository content, source layout, documentation references, and
  the complete dependency surface.

## Architecture result

The repository has two intentionally separated concerns:

* **Trading runtime:** `bridge`, `brain`, and `runtime`, with the dashboard/MT5 integration
  retained at the edge.
* **Passive RAIP domains:** `review_engine`, progressing from observation through V10 offline
  qualification without a dependency back into the trading runtime.

The documented V27 runtime authority and V28 proposal gate remain intact. V29 code is present as
a separate versioned bridge package. No audit change activates V28 or V29.

## Required Architecture Review disposition

Review this report together with the Dependency, Contract, Schema, and Consistency reports in
this directory. Record one of: **accepted conditional certification**, **rework requested**, or
**rejected**. Do not make a merge decision until that Engineering Completion Report is reviewed.
