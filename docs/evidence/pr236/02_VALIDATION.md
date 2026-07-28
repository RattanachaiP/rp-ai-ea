# PR236 Validation

Assembly imports producer, producer-version, schema, and freshness values from
their owning runtime modules. It fails closed for missing mandatory fields,
invalid producer identity/version, non-canonical UUIDs, incompatible schema,
stale heartbeat, invalid lineage, absent runtime execution authorization,
non-finite execution numbers, invalid direction/lot size, and a market sequence
not greater than durable `execution_package_state.json` authority.

Every outcome records an accountable owner (`ASSEMBLY`, `VALIDATION`, or
`PUBLICATION`) and reason in both the JSON-lines trace and atomic health file.
The state advances before package publication, so a crash can suppress a
package but cannot allow an older sequence after package deletion. Files are
written to same-directory temporary files, flushed, fsynced, and installed with
`os.replace`. On POSIX the parent directory is also fsynced; other platforms
retain atomic replacement but directory durability remains platform-dependent.

Health is observational evidence only. It has no `executor_ready` field and is
never execution authority. A health-write failure is explicitly traced as
`EVIDENCE_FAILED` and cannot manufacture or revoke an already published package.
