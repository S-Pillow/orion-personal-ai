# P4-03 — Native Hermes wake evaluation and `Hey Orion` custom model

**Status:** IN PROGRESS  
**Date:** 2026-09-12  
**Controlling PRD:** ORION Master PRD v2.8  
**Primary requirements:** OR-VOICE-002, OR-VOICE-006, OR-VOICE-007, OR-VOICE-008, OR-VOICE-009

## Scope

P4-03 validates the accepted Hermes native wake path for Orion and selects the supported local wake-engine configuration for the preferred phrase **"Hey Orion"**. It does not introduce a separate always-on hotword service, speech runtime, or parallel gateway.

Hermes remains the native voice/wake authority. Custom training is isolated tooling only; the accepted Orion runtime is not modified during model development.

## Accepted runtime baseline

- Hermes tag: `v2026.8.27`
- Hermes package: `0.20.6`
- Hermes commit: `5fc308a70719a83cccdbba4c0e39c23f5a8239d5`
- wake provider selected for fixed-phrase evaluation: `openwakeword`
- openWakeWord runtime version: `0.6.0`
- sensitivity: `0.5`
- confirmation frames: `3`
- `wake_word.input_device`: unset
- Windows input path: default JLab headset microphone through MME
- capture conversion observed: default device rate `44100` -> engine rate `16000`

Do not pin the known-dead DirectSound input path, do not permanently pin the transient PortAudio device index, and do not patch sample rate handling absent new evidence.

## Engine decision

The current architecture decision is to continue with Hermes' trained **openWakeWord** path for Orion's fixed wake phrase.

Evidence on the actual Windows/JLab setup:

- Sherpa `Hey Orion` did not meet the wake gate. Controlled runs reached approximately `6/10` at the tested `0.5` and `0.4` sensitivity points.
- Sherpa `Hey Jarvis` reached `18/20` in a controlled diagnostic run, showing the capture path itself was capable of materially better results than the `Hey Orion` Sherpa phrase result.
- openWakeWord stock `hey_mycroft` produced `19/20` logged fires in a controlled 20-attempt window.
- openWakeWord stock `hey_jarvis` produced 19 consecutive confirmed fires in its bounded run. The nominal target was 20 attempts, but no synthetic denominator is recorded.
- openWakeWord stock `hey_hermes` produced 18 confirmed logged successes with no perceived misses; the intended attempt count was 20 but the actual denominator was not reliably tracked, so no `18/20` claim is made.

This is sufficient to select the trained fixed-phrase engine class without continuing a stock-model sweep. Porcupine is not part of the Orion path because its current licensing/business fit is unacceptable for this project.

## Microphone/status finding

Hermes' yellow `mic delivers only silence` warning is not accepted as proof of a dead microphone path. In repeated live tests, the same stream later logged `mic audio detected — stream healthy` and then fired the wake callback without device reconfiguration.

Treat the warning as a separate Hermes readiness/status UX issue unless future evidence shows a real capture failure. Do not change the accepted JLab/MME configuration solely because that warning appears.

## Custom `Hey Orion` model — training provenance

Training workspace:

- Windows: `D:\Orion\training\hey-orion`
- WSL: `/mnt/d/Orion/training/hey-orion`
- WSL distro: Ubuntu under WSL2
- GPU: NVIDIA GeForce RTX 3070, 8 GB
- isolated Python: `3.10.21`
- openWakeWord training source: tag `v0.6.0`, commit `c8ef6912c5feccf1037b852d9bc6c7ed644135ba`
- Piper sample generator: `dscripka/piper-sample-generator`, commit `f1988a4d54eddb23d99e86f0adfef6226a85acc7`
- PyTorch: `1.13.1+cu117`
- torchaudio: `0.13.1+cu117`
- NumPy: `1.23.5`
- ONNX Runtime: `1.16.3`

The WSL CUDA driver library is exposed process-locally with:

`LD_LIBRARY_PATH=/usr/lib/wsl/lib`

No Linux NVIDIA display driver, global CUDA-toolkit change, Hermes dependency change, or Windows driver mutation is part of this work.

Piper LibriTTS High model:

- file: `en-us-libritts-high.pt`
- size: `255226835` bytes
- SHA-256: `5258f21adf77c29248d9a89d51ca9492f6e75a498140584dcbed0edcab81960a`

A narrow ONNX Runtime executable-stack compatibility fix was applied only inside the isolated training venv by clearing the executable-stack flag on `onnxruntime_pybind11_state...so`; no system security setting was changed.

## Corpus milestone

Iteration-1 configuration uses:

- model name: `hey_orion_v1`
- target phrase: `Hey Orion`
- positive train samples: `25,000`
- positive validation samples: `2,000`
- adversarial negative train samples: `25,000`
- adversarial negative validation samples: `2,000`
- TTS batch size: `20`
- model type: `dnn`
- layer size: `32`
- training steps: `50,000`
- target false positives/hour: `0.2`

Generated corpus validation:

| Corpus | Files | Valid | Bad | Duration min/avg/max (s) |
| --- | ---: | ---: | ---: | --- |
| positive_train | 25,000 | 25,000 | 0 | 0.545 / 1.144 / 5.375 |
| positive_test | 2,000 | 2,000 | 0 | 0.545 / 1.083 / 2.405 |
| negative_train | 25,000 | 25,000 | 0 | 0.275 / 1.012 / 7.835 |
| negative_test | 2,000 | 2,000 | 0 | 0.305 / 0.996 / 2.375 |

Total generated corpus: **54,000 valid 16 kHz mono PCM16 WAV files, zero malformed files**.

A separate 200-sample Piper sanity corpus also passed `200/200` structural validation, and 20 manually spot-checked clips were acceptable before the full generation run.

MIT environmental room impulse response acquisition has completed successfully for augmentation.

## Precomputed negative-feature datasets

The required openWakeWord precomputed feature datasets were downloaded to the isolated training workspace and SHA-256 verified against their expected published values:

- `openwakeword_features_ACAV100M_2000_hrs_16bit.npy`
  - size: `17280000128` bytes
  - SHA-256: `721a66d0682c65a1b5c1da0aa109409cede1d20e28b15235c344b000cbb7654f`
- `validation_set_features.npy`
  - SHA-256: `a56a8a0f8e0efb91900acc6de4c0cdf4c564842e8475a7d49b36c039e17a690f`

Feature-data acquisition is therefore accepted for iteration 1. These local arrays are training inputs only and are not committed to the Orion repository.

## Current work

Synthetic corpus generation, RIR acquisition, and required precomputed generic-negative / false-positive validation feature acquisition are complete. Background/noise augmentation data, augmentation/feature extraction, model training, ONNX export, Hermes loading, and live `Hey Orion` acceptance testing remain pending.

Do not mark P4-03 closed until a produced `hey_orion_v1.onnx` (or explicitly accepted successor iteration) is provenance-recorded and passes live testing on the accepted Windows/JLab runtime.

## Acceptance direction

Initial live screening target for the custom model:

- at least 40 controlled intended wake attempts
- intended detection rate `>=95%`
- accepted runtime baseline remains sensitivity `0.5`, confirmation frames `3`, default JLab/MME input
- no architecture change based only on the Hermes silence-warning banner

Final acceptance should include a larger intended-wake run and an ambient false-wake observation window. The working target is `>=95/100` intended detections and zero false wakes during at least six hours of mixed ambient exposure before closing the wake-phrase gate.

If iteration 1 is weak, change the training corpus/negative data first. Do not patch accepted Hermes wake logic merely to rescue an underperforming custom model. Limit this effort to at most two substantial custom-model iterations before owner review of phrase/model strategy.

## Open items

1. Complete background/noise acquisition and augmentation inputs.
2. Generate openWakeWord features from the synthetic corpus.
3. Train and export `hey_orion_v1.onnx`.
4. Record model SHA-256 and exact training manifest.
5. Load the custom model through Hermes' supported openWakeWord path without modifying accepted Hermes source.
6. Run controlled live detection and ambient false-wake acceptance.
7. Continue Phase 4 voice work for shared conversation, spoken streaming, visible privacy modes, bounded follow-up, and barge-in after the wake gate is credible.

## Safety / non-regression boundary

- No Hermes runtime source patch is authorized by this record.
- No separate hotword service is introduced.
- No Hermes/Ollama/iai dependency upgrade is part of P4-03.
- No accepted operator-control change is part of custom-model training.
- WSL is training tooling only; Orion remains a native-Windows product and runtime.
- Training datasets, generated WAV corpora, model caches, and large feature arrays are local artifacts and are not to be committed to this repository.
