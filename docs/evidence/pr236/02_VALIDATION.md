# PR236 Validation

Assembly fails closed for missing mandatory decision fields, missing or invalid
producer identity, non-canonical UUIDs, incompatible decision or package schema,
a heartbeat outside 120 seconds, invalid lineage, non-finite execution numbers,
invalid direction/lot size, and a market sequence not greater than the currently
published package.

Every outcome records an accountable owner (`ASSEMBLY`, `VALIDATION`, or
`PUBLICATION`) and reason in both the JSON-lines trace and atomic health file.
The target is written to a same-directory temporary file, flushed and fsynced,
then installed with `os.replace`; failed validation never touches the target.
