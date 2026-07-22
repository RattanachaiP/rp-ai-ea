# RAIP data retention and operations
RAIP retains append-only events, immutable snapshots, daily factual reviews, and invalid-record quarantine artifacts under the configured review-data root. Atomic writes use a temporary file, flush, fsync where supported, and rename. A restart can safely replay closed exports because snapshot writes are idempotent. Source-side loss before RAIP observes an export cannot be recovered by RAIP.

Deploy only with an explicit `enabled=True` configuration and a writable review-data root. Roll back by setting `enabled=False`; this performs no writes and leaves existing evidence intact. No credentials, personal names, canonical trading files, or decision/execution files are read or written.
