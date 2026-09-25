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

Run it as a launchd service instead of a terminal you have to remember:

```sh
./launchd/install.sh     # renders the plist, bootstraps the agent
```

It starts at login, respawns if it dies, and logs to `~/.laya/logs/`. Remove
with `launchctl bootout gui/$UID/com.laya.decisions`.

Then install the plugin and leave `baseUrl` at its default
(`http://127.0.0.1:8787/ask`). Set `apiKey` only if you deliberately want the
hosted endpoint instead.

## Status

Working end to end against a real local Laya. Measured on an Apple M5,
`convaiinnovations/laya` (multilingual), three `noul` questions per request:

- **Latency: 15 ms warm.** First call is ~2 s of model warmup, then 15 ms for
  three questions — matching the published 7-15 ms. Not a concern.
- **Calibration: do not leave `keepThreshold` at 0.5.** Laya ranks correctly
  but its probabilities are compressed around 0.5, not spread like Jev's.
  One probe set, same state:

  | probe | noul |
  |---|---|
  | relevant (Read of the file under test) | 0.643 |
  | irrelevant (LS /tmp, 12k chars) | 0.554 |
  | absurd (echo hello, 200 turns ago, unrelated) | 0.347 |

  The ordering is right, but at the default 0.5 the *irrelevant* result is
  kept. Around 0.6 separates them here. Absolute values also move a lot with
  question wording and state — an earlier probe set scored 0.90-0.97 across
  the board — so treat the threshold as something to tune against your own
  transcripts, not a constant to copy from this table.

Untested: whether tuning `keepThreshold` yields a useful reduction ratio on a
real session without dropping something that mattered. That is the question
this repo exists to answer, and it is not answered yet.
