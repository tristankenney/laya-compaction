# laya-compaction

Verbatim context compaction for Claude Code, scored by a **local** Laya model.
No API key, nothing leaves the machine.

Claude Code's built-in compaction asks an LLM to summarise old turns, which is
lossy — a file path, an exact error, a constraint can vanish. This keeps user
and assistant text byte-for-byte and only drops or truncates *tool calls* that
a decision model says are no longer needed.

## Why this exists

[`fast-jev-compaction`](https://github.com/tamaratran/fast-jev-compaction) does
the hard part, but sends conversation state to a hosted endpoint. Tool results
are omitted, but tool **inputs** (bash commands, file paths, grep patterns) and
message text go verbatim — which is a poor fit for work under NDA.

[`fast-jev-compaction-laya`](https://github.com/kaiyes/fast-jev-compaction-laya)
solved that with a local Laya server, but targets opencode, not Claude Code.

This is the missing combination: upstream's Claude Code plugin and scoring
logic, pointed at that local server.

## How it differs from upstream

One config value. Upstream's hook drops `baseUrl` on the floor when building
the request; here it is threaded through from `userConfig`, and the API key
becomes optional when `baseUrl` is set. Everything else — the two-`noul`
calibrated scoring, `keepThreshold`, the state fitting — is upstream's,
imported from the published package rather than vendored.

The local server is Jev-wire-compatible by design: `POST /ask` with
`{state, questions}` returning `{"answers": {...}}` where each `noul` answer
carries `P(true)`, which is exactly what `parseJevResponse` expects.

## Setup

```sh
pip install laya-mlx            # Apple Silicon; ~650 MB checkpoint on first run
python server.py                # http://127.0.0.1:8787 — keep it running
```

Then install the plugin and leave `baseUrl` at its default
(`http://127.0.0.1:8787/ask`). Set `apiKey` only if you deliberately want the
hosted endpoint instead.

## Status

Unproven. The transport is verified — a stub server on localhost round-trips
`buildJevRequest` → `parseJevResponse` correctly — but two things have not been
measured against a real Laya:

- **Threshold calibration.** `keepThreshold` defaults to 0.5 against *Jev's*
  calibration. If Laya's probabilities run colder, context gets dropped that
  should have been kept, silently. Measure before trusting it.
- **Latency at a 25k-token state.** The published 7–15 ms figures are for short
  decisions; this resends full state per request.

## Credits

Derived from two MIT projects, notices retained in `LICENSE.upstream` and
`LICENSE.laya-port`: the hook from tamaratran/fast-jev-compaction, `server.py`
from kaiyes/fast-jev-compaction-laya.
