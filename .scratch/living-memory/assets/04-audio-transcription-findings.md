# Findings: Audio transcription approach

Research asset for ticket [04-audio-transcription](../issues/04-audio-transcription.md).

## The three options, on our axes

| | Accuracy (clean WER) | Noisy speech | Cost | Privacy | Ops |
|---|---|---|---|---|---|
| **faster-whisper, local** (large-v3 / v3-turbo) | ~2.8% (turbo +~0.3%) | good | **$0/min** (GPU/CPU only) | **audio never leaves machine** | download model, run locally |
| **Gemini audio** (one call) | near-top, close to best | good | per-token | audio → Google | none (same vendor as extraction) |
| **Hosted STT** (Deepgram Nova-3 / AssemblyAI Universal-2) | best (~2.1%, ~8% noisy) | best | $0.36–$1.31/hr | audio → new vendor | new API key/vendor |

Whisper large-v3 remains the best open-source option and is competitive with the paid APIs on
clean speech; `large-v3-turbo` gives ~4× faster inference for ~0.3% WER cost. The hosted APIs win
mainly on *streaming/real-time* and diarization — neither of which we need (journaling is batch,
one speaker).

## Recommendation: **faster-whisper (large-v3 / turbo), local — behind a `Transcriber` adapter**

Reasoning specific to this project:
1. **Audio is a daily going-forward feature.** Local = $0/min forever, no per-minute cost anxiety,
   and it works offline (journal without connectivity).
2. **It's a genuine privacy win — unlike the embedder decision.** For embeddings, local bought no
   privacy (text already goes to Gemini for extraction). Here it's different: transcribing locally
   means the **raw voice recording never leaves the machine** — only the *proofread transcript*
   (text) goes to Gemini for extraction. Voice is more intimate/biometric than text; keeping it
   local is worth it.
3. **The proofread gate covers the accuracy gap.** We don't need best-in-class WER because you
   review every transcript before it's committed. Whisper large-v3 (~2.8%) is more than enough.
4. **Clean adapter fit.** `Transcriber.transcribe(audio) -> text` — swap to Gemini-audio or
   Deepgram later if your accent/speech proves hard for Whisper. One-config change.

Not a one-way door: if Whisper struggles on your voice in the prototype, fall back to Gemini audio
(zero new vendors) before reaching for a paid STT.

## Sources
- [CodeSOTA — Speech Recognition 2026: Whisper vs Gemini vs AssemblyAI vs Deepgram](https://www.codesota.com/guides/speech-recognition)
- [Coval — Best STT Providers 2026: Independent Benchmarks](https://www.coval.ai/blog/best-speech-to-text-providers-in-2026-independent-benchmarks-and-how-to-choose/)
- [Deepgram — Whisper vs Deepgram](https://deepgram.com/learn/whisper-vs-deepgram)
