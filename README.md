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

## Status: does not work. Do not enable.

Measured against a realistic 100-tool-call transcript (200 noul questions) on
an Apple M5, `convaiinnovations/laya` multilingual. The transport is fine; the
decisions are not.

**Laya does not discriminate on this task.** Half the tool calls were junk
(`LS /tmp`), half were relevant (`Read src/auth*.ts`) for a stated goal of
fixing auth tests. It scored them the same, and the junk marginally *higher*:

| calls | mean keepResult | sd |
|---|---|---|
| junk `LS /tmp` (n=50) | 0.9282 | 0.0128 |
| relevant `Read src/auth*.ts` (n=47) | 0.9157 | 0.0074 |

Separation **-0.0125**, inside the noise. Every one of 200 decisions landed in
0.93-0.97. At `keepThreshold` 0.6 or 0.8 nothing is dropped and reduction is
0%; at 0.95 it drops 56 calls and reports 55% reduction, but that is slicing
through a 4-point band of noise, so it discards context at random. That is
worse than no compaction: silent, arbitrary loss.

Shrinking the state does not help — it saturates instead. With a 40-message
state every answer comes back `noul: 1.0, confidence: 1.0`.

**Context window mismatch, which is real but not the cure.** The model's
window is 8192 tokens (`max_position_embeddings`, and the tokenizer agrees)
while the plugin defaults to `maxStateTokens: 25000` — 3x over, so the state is
truncated. Fitting under the window is impossible for a long transcript anyway:
the library's own fitting bottoms out at ~5775 tokens, leaving ~2400 for
questions, and splitting to fit produces concurrent requests that the server
serialises behind one lock.

**Latency.** ~8.3 s per compaction of 200 questions, warm. Earlier notes in
this repo claimed 15 ms; that was 3 questions against a 2-message state and
did not predict anything. The `BrokenPipeError`s in `~/.laya/logs/laya.err.log`
are Claude Code abandoning the dispatch and hanging up mid-response.

**Conclusion.** The idea is sound and the plumbing works — a local decision
model scoring a Jev-shaped request, no data leaving the machine. This
particular model cannot make the judgement. Reviving this needs a decision
model that discriminates on relevance at transcript scale, not a threshold.
