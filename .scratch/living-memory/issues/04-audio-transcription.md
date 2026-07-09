# Audio transcription approach

Type: research
Status: resolved
Blocked by: —

## Question

Going-forward entries can be spoken. Audio → text feeds the same proofread gate as handwriting.
Research the options and recommend one:
- **Local Whisper** (whisper.cpp / faster-whisper) — private, offline, no per-minute cost.
- **Hosted API** (OpenAI Whisper API, Deepgram, etc.) — accuracy + speed, but audio leaves machine.
- **Gemini audio** — one vendor with extraction; multimodal transcription in the same call.

Compare on accuracy for reflective/first-person speech, latency, cost, privacy, and how cleanly
it fits behind the provider adapter. Produce a short markdown summary as the linked asset.

## Answer

**faster-whisper (large-v3 / turbo), local, behind a `Transcriber` adapter.** Unlike the embedder,
local transcription is a *genuine* privacy win — the raw voice recording never leaves the machine;
only the proofread text transcript goes to Gemini for extraction. It's also $0/min, works offline,
and the proofread gate covers any accuracy gap (so best-in-class WER isn't needed). Fallback if
Whisper struggles on the user's voice in the prototype: Gemini audio (no new vendor), then a hosted
STT. Full comparison + sources: [findings](../assets/04-audio-transcription-findings.md).
