# PR #139 — Repository Dependency Report

## Result: CONDITIONAL PASS

### Verified dependency direction

Static AST inspection found these production package-root dependencies only:

| Consumer | Permitted dependency | Result |
| --- | --- | --- |
| `bridge` | `brain` | Pass — decision engine consumes decision-model outputs. |
| `runtime` | `brain` | Pass — writer adapter consumes `DecisionPackage`. |
| `runtime` | `bridge` | Pass — executor consumes the decision-writer read contract. |
| `review_engine` | Trading roots | Pass — no `brain`, `bridge`, or `runtime` import exists. |

`analysis` contains reporting/validation helpers and is not a runtime dependency. Test imports
are excluded from the production direction decision.

### External dependency verification

The production Python code uses the standard library except the optional bridge voice utility's
`pyttsx3` import. The full test suite passed in the audited environment.

### Certification limitation

No `pyproject.toml`, `requirements*.txt`, lock file, or equivalent dependency manifest is
tracked. Consequently, exact environment reconstruction and explicit declaration of the
optional `pyttsx3` dependency cannot be certified from repository metadata.

### Required follow-up

Add a pinned dependency manifest, supported Python-version policy, and installation/check
instructions in a dedicated non-runtime maintenance change. This report does not infer versions
or alter dependency resolution.
