# PR238 Native MetaEditor Warning 43 Review

The external compile of revision `3611d5c` reported **0 errors and 10 Warning 43 diagnostics**. Warning 43 identifies a potentially lossy type conversion. None is suppressed. Each call is corrected at its type boundary.

| Compile line / occurrence | Current type at warning | Correct type | Why current type is incorrect | Why new type is correct |
|---|---|---|---|---|
| 38 | `ushort` passed to `CharToString(uchar)` | `ushort` passed to `ShortToString(ushort)` | A validated Unicode BMP code unit can exceed `0xFF`; narrowing it to `uchar` loses its high byte. | The branch proves `code_point <= 0xFFFF` and rejects surrogate values, so the explicit `uint -> ushort` conversion is range-safe; `ShortToString` preserves that complete code unit. |
| 43 | `ushort` high surrogate passed to `CharToString(uchar)` | `ushort` passed to `ShortToString(ushort)` | Every high surrogate exceeds the `uchar` range. | For an accepted scalar `0x10000..0x10FFFF`, the expression is proven to produce `0xD800..0xDBFF`, exactly representable by `ushort`. |
| 44 | `ushort` low surrogate passed to `CharToString(uchar)` | `ushort` passed to `ShortToString(ushort)` | Every low surrogate exceeds the `uchar` range. | Masking with `0x3FF` proves the result is `0xDC00..0xDFFF`, exactly representable by `ushort`. |
| 97 | decoded UTF-16 `ushort unit` passed to `CharToString(uchar)` | `ushort` passed to `ShortToString(ushort)` | A non-surrogate UTF-16 code unit is not limited to one byte. | `unit` is constructed from exactly two input bytes and is already the correct `ushort` code-unit type. |
| 176 | JSON character `ushort c` passed to `CharToString(uchar)` | `ushort` passed to `ShortToString(ushort)` | `StringGetCharacter` returns a UTF-16 code unit; narrowing corrupts non-ASCII JSON text. | `ShortToString` accepts the exact type returned by `StringGetCharacter`. |
| 179 | JSON escape `ushort escape` passed to `CharToString(uchar)` | `ushort` passed to `ShortToString(ushort)` | The old function required an avoidable narrowing conversion. | The parser retains its native `ushort` representation through conversion; allowed escaped punctuation remains unchanged. |
| 192, first call | validated high-surrogate `ushort high` passed to `CharToString(uchar)` | `ushort` passed to `ShortToString(ushort)` | A high surrogate cannot be represented by `uchar`. | `ParseHexUnit` produces `ushort`, and the immediately preceding guard proves `0xD800..0xDBFF`. |
| 192, second call | validated low-surrogate `ushort low` passed to `CharToString(uchar)` | `ushort` passed to `ShortToString(ushort)` | A low surrogate cannot be represented by `uchar`. | `ParseHexUnit` produces `ushort`, and the immediately preceding guard proves `0xDC00..0xDFFF`. |
| 195 | parsed `ushort high` passed to `CharToString(uchar)` | `ushort` passed to `ShortToString(ushort)` | A `\\uXXXX` code unit may exceed `0xFF`; narrowing changes its value. | The value is already `ushort`, lone low surrogates were rejected, and `ShortToString` preserves the parsed code unit. |
| 464 | signed `long InpMagic` assigned to unsigned `ulong request.magic` | `ulong InpMagic` assigned to `ulong request.magic` | A signed input permits negative values and does not match the MQL trade-request field. | MT5 magic numbers are non-negative identifiers and `MqlTradeRequest.magic` is `ulong`; matching the declared type removes conversion without a cast. |

## Narrowing audit

The remaining explicit `uint -> ushort` conversions are limited to Unicode assembly at lines 38, 43, and 44 and are range-proven above. UTF-16 byte assembly at lines 84–90 combines exactly two `uchar` values into one `ushort`, so no information is discarded. No `ulong -> long` conversion remains in the modified executor path: the magic input, request field, broker ticket, and `%I64u` formatting remain unsigned end-to-end.

## Required native confirmation

This source correction must still be compiled in MetaEditor. The merge gate remains **NOT READY** until the corrected revision has an attached native result of **0 errors / 0 warnings**.
