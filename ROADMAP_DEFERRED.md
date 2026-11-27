# SahamYar - Deferred Roadmap

## Final Phase: Persian Voice Capabilities (ASR / TTS)

**Priority:** Deferred - Final Development Phase  
**Start condition:** Only after the backend and Android frontend are fully
implemented, integrated, tested, and considered stable.

### Objective
Add Persian voice interaction to SahamYar, allowing users to:
- Convert Persian speech into text (ASR / Speech-to-Text).
- Read analysis results and other supported content aloud (TTS / Text-to-Speech).
- Use voice capabilities locally and offline where technically feasible.

### Preferred Technology Stack

1. **Sherpa-ONNX**
   - Primary on-device inference runtime.
   - Android integration through Kotlin/Java.
   - https://github.com/k2-fsa/sherpa-onnx

2. **Shenava Rizeh - Persian ASR**
   - Initial candidate for Persian speech recognition.
   - https://huggingface.co/Reza2kn/Shenava-Rizeh-v1.0-sherpa-onnx

3. **Persian-TTS by Ali Fathi**
   - Initial candidate for Persian text-to-speech.
   - https://huggingface.co/alifthi/persian-TTS
   - https://github.com/alifthi/persian-tts

### Implementation Plan

1. Create an isolated SahamYar-Voice-Lab proof of concept.
2. Test Shenava Rizeh recognition quality with real Persian speech.
3. Test Persian-TTS voice quality, pronunciation, speed and device performance.
4. Verify Android compatibility and offline operation using Sherpa-ONNX.
5. Review model, runtime and dependency licenses before any distribution
   or commercial use. Model and dependency licenses must be checked separately.
6. Design independent, replaceable ASR and TTS interfaces.
7. Build a domain-specific normalization dictionary for Iranian market terms,
   symbols and abbreviations, including فولاد، فملی، RSI، MACD، EPS، P/E،
   TSETMC and Codal.
8. Integrate into SahamYar only after successful tests and approval.

### Engineering Constraints

- Do not start this phase while backend or frontend implementation is ongoing.
- Do not modify or destabilize existing backend and frontend work for this task.
- Keep voice processing modular and independently testable.
- Do not assume model quality, performance, licensing or offline compatibility
  until verified on target Android devices.
- Preserve the ability to replace ASR/TTS models without rewriting the app.

### Initial Status
PLANNED - NOT STARTED

This is a deferred final-phase feature, not part of the current implementation.
