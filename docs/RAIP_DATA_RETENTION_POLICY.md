# RAIP Data Retention and Operations

RAIP keeps append-only events, immutable snapshots, daily reports, rejections, and future collector state below the configured review-data root. Sprint 1 does not purge data. Review-data loss or disk failure can lose RAIP evidence but cannot affect trading because errors are isolated in RAIP and no trading path waits for acknowledgment.

The default Windows root is `D:\RP_AI_EA\review_data\`; tests use a temporary root. Paths are normalized and snapshot IDs reject traversal. No credentials, personal names, or raw account numbers are stored; only a pre-hashed account identifier may be observed.
