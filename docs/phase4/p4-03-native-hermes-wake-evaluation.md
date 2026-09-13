# P4-03 — Native Hermes wake evaluation and `Hey Orion` custom model

**Status:** IN PROGRESS  
**Date:** 2026-09-13  
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

MIT environmental room impulse response acquisition completed successfully for augmentation.

## Precomputed negative-feature datasets

The required openWakeWord precomputed feature datasets were downloaded to the isolated training workspace and SHA-256 verified against their expected published values:

- `openwakeword_features_ACAV100M_2000_hrs_16bit.npy`
  - size: `17280000128` bytes
  - SHA-256: `721a66d0682c65a1b5c1da0aa109409cede1d20e28b15235c344b000cbb7654f`
- `validation_set_features.npy`
  - SHA-256: `a56a8a0f8e0efb91900acc6de4c0cdf4c564842e8475a7d49b36c039e17a690f`

Feature-data acquisition is accepted for this custom-model experiment. These local arrays are training inputs only and are not committed to the Orion repository.

## Two-iteration training result and interpretation

Two substantive custom-model training iterations completed. This exhausts the pre-authorized two-iteration training budget; do not launch a third custom-model training run without a new owner decision.

V1 and v2 are **not** two deliberately selected negative-weight schedules. In v1, `best_val_fp` remained frozen at its initialization value of `1000`, which was always above the `0.2 FP/hour` target. Both negative-weight escalation checks therefore fired regardless of measured validation performance, and the resulting `1500 -> 3000 -> 6000` schedule was an artifact of the defect rather than an evidence-driven training choice.

V2 is the first run in which the escalation decisions were driven by measured validation FP/hour. Sequence 1 measured `0.2655 FP/hour`, correctly triggering escalation from `1500` to `3000`. Sequence 2 then measured `0.0885 FP/hour`, below the target, so no second escalation occurred and sequence 3 remained at `3000`. Sequence 3 later measured `0.7080 FP/hour`.

Final-model results:

| Run | Training interpretation | Final recall | Final FP/hour |
| --- | --- | ---: | ---: |
| v1 | defective feedback path; escalation schedule not evidence-driven | `36.30%` | `0.442` |
| v2 | corrected feedback path; first measured escalation decisions | `37.75%` | `0.7965` |

Despite restoring the intended feedback behavior, final recall increased only from `36.30%` in the broken v1 run to `37.75%` in the corrected v2 run. This supports the narrower conclusion that the stale `best_val_fp` defect was real but was **not the primary cause of the poor recall**. It does not establish that any single remaining factor is solely responsible.

One additional observed result matters for that interpretation: v2's final combined-model FP/hour (`0.7965`) was worse than v1's (`0.442`) even though v2's measured sequence-level FP/hour values included substantially better intermediate results (`0.2655` for sequence 1 and `0.0885` for sequence 2). The final model is produced by merging selected saved checkpoints, so this divergence is evidence that later training/checkpoint selection and the final merge may add variability on top of any corpus or model-capacity ceiling. That is a plausible contributor, not a proven causal diagnosis; the record should retain corpus quality/coverage, the small 32-unit DNN, stochastic training behavior, and checkpoint-merging behavior as unresolved contributors rather than collapsing the outcome to a single cause.

V2 completed successfully with metrics parsed from the preserved source log:

- final accuracy: `0.687749981880188`
- final recall: `0.3774999976158142`
- final FP/hour: `0.7964601516723633`
- sequence 1 best validation FP/hour: `0.2654867172241211`
- sequence 2 best validation FP/hour: `0.08849557489156723`
- sequence 3 best validation FP/hour: `0.7079645991325378`
- observed negative-weight escalation events: `1`
- training start: `2026-09-13T03:18:09-04:00`
- training end: `2026-09-13T03:32:03-04:00`
- exit code: `0`
- ONNX export: successful
- TFLite conversion: intentionally skipped

## V1 immutable artifact integrity

The existing v1 preservation record was checked read-only before the live comparison. Every manifest-listed artifact matched its preserved on-disk SHA-256. No v1 artifact was modified or retrained.

Verified v1 artifacts:

| Artifact | Preserved file | SHA-256 |
| --- | --- | --- |
| model | `hey_orion_v1.onnx` | `ead8248c37cccb82e66cc17ba023e879381000c2116aa9518168afde985f4e89` |
| training log | `train-20260913-021421.log` | `e6e0b40896198413564bbc0e2715957cbebe95ecf3a59046ba8e8a9291f5ab0f` |
| canonical config | `hey_orion_v1.yml` | `e24ed3b2110aca4a3a7daeb8effc93e4b824787aa8e13ae1bfe1c20e56f4be91` |
| derived config | `hey_orion_v1_ext4.yml` | `85fcdfa89cc47aeec4ec19068500543cf88813d87b128b9f1e6afb0e71f75bfa` |
| derived trainer | `train_onnx_only.py` | `a02549d00f76ca13c4f3af97c9ef656ea28b6f5ac58c25011f6f944862d0475f` |

Integrity result: **`V1 PRESERVATION INTEGRITY PASS`**.

## V2 immutable artifact preservation

V2 preservation completed successfully on 2026-09-13 using a fail-closed preservation script that parses measured results from the training log, refuses to overwrite an existing `models/v2` record, copies the model/log/config/derived trainer, and verifies source and destination SHA-256 values after each copy.

Preserved directory:

`D:\Orion\training\hey-orion\models\v2`

WSL view:

`/mnt/d/Orion/training/hey-orion/models/v2`

Preserved artifacts:

| Artifact | Preserved file | SHA-256 |
| --- | --- | --- |
| model | `hey_orion_v2.onnx` | `990567d4a2320e540e9dbf93d66a126498d14c3275010899a027b23732428dcd` |
| training log | `train-v2-20260913-031809.log` | `e3a9a92b2e69b15afab15179f804cad42d1e607a6648be032d1557b63338e384` |
| derived config | `hey_orion_v2_ext4.yml` | `a7acb66de27b7ce1220e8437f930447900e7d40165d00dcb59765b128957f530` |
| derived trainer | `train_onnx_only_v2.py` | `121ad3ec890a4c1cee0b45fb7653485e679cb3cfb5e91f369c1d3fbf34aa7de5` |

Manifest:

`/mnt/d/Orion/training/hey-orion/models/v2/hey_orion_v2_manifest.json`

Preservation result: **`V2 PRESERVATION PASS`**.

The v2 model SHA-256 above is now the immutable artifact identity for subsequent comparison. Do not replace, retrain in place, or silently regenerate this artifact.

## Live JLab/MME custom-model screening

The immutable v1 and v2 models were screened on the accepted Windows/JLab microphone path using Hermes/openWakeWord with the same fixed runtime settings for both models:

- JLab headset microphone through MME
- local capture
- sensitivity `0.5`
- confirmation frames `3`
- phrase `Hey Orion`
- no per-model threshold tuning
- `start_new_session: false` for the screening run only, to avoid creating one Hermes session per successful wake

Working screening gate: at least 40 controlled intended attempts per model and `>=95%` intended detection (`>=38/40`).

Recovered results:

| Model | Recorded attempts | Hits | Misses | Recorded detection rate | Gate disposition |
| --- | ---: | ---: | ---: | ---: | --- |
| v1 | `39` | `19` | `20` | `48.7%` | FAIL |
| v2 | `40` | `14` | `26` | `35.0%` | FAIL |

The recovered v1 tally file ends at attempt 39. No attempt-40 result is present in the durable tally, so this record does not invent one. Even if the missing 40th attempt had been a hit, v1 could have reached at most `20/40 = 50%`, still far below the `95%` screening gate. Therefore the incomplete final v1 line does not affect the accept/reject decision.

V2 completed all 40 planned attempts and produced `14/40 = 35%` detection. V2 was therefore worse than v1 in this live microphone screen despite being the first training run with corrected FP-driven escalation logic.

**Custom-model disposition: NOT ACCEPTED.** Neither v1 nor v2 is credible enough to proceed to the larger `>=95/100` intended-wake and six-hour ambient false-wake gate. The current two-iteration custom `Hey Orion` training path is rejected for Orion runtime use.

This live result reinforces the earlier training-side conclusion that fixing the `best_val_fp` defect did not solve the main recall problem. It does not, by itself, identify one root cause. Corpus/acoustic mismatch, model capacity, stochastic training behavior, checkpoint selection, and merge behavior remain unresolved contributors.

## Current work

The two authorized custom-model training iterations, artifact preservation/integrity checks, and fixed live JLab/MME screening are complete. The custom v1/v2 `Hey Orion` path is **not accepted** and should not be loaded into the Orion runtime.

No v3 training run is authorized automatically. The next wake-word step is an owner strategy decision using the already-collected evidence. Reasonable options include retaining Hermes/openWakeWord with an already-performing stock phrase/model, revisiting `Hey Orion` only under a separately approved data/model redesign, or using push-to-talk/another supported fallback while the rest of Phase 4 proceeds.

P4-03 remains **IN PROGRESS** because the final Orion wake strategy has not yet received an owner disposition and the broader Phase 4 voice requirements remain open.

## Acceptance direction

The custom-model branch has failed its initial screening gate and will not proceed to extended acceptance testing.

Any future `Hey Orion` custom-model work requires a new explicit owner decision and should not simply repeat v1/v2 with more training steps. A future redesign should begin from the observed failure mode and justify what materially changes in data coverage, model architecture/capacity, training/selection procedure, or evaluation design.

Until then:

- do not launch v3 automatically;
- do not patch accepted Hermes wake logic to rescue these models;
- do not lower the acceptance gate merely to make v1/v2 pass;
- keep the accepted JLab/MME capture path and Hermes runtime boundaries intact;
- preserve v1/v2 as immutable experimental evidence.

## Open items

1. Owner disposition on the Phase 4 wake strategy after rejection of custom `Hey Orion` v1/v2.
2. If an alternate supported Hermes/openWakeWord phrase/model is selected, run a bounded acceptance protocol on the same JLab/MME path before runtime acceptance.
3. If `Hey Orion` is revisited later, authorize it as a new data/model-design effort rather than an automatic v3 continuation.
4. Continue Phase 4 voice work for shared conversation, spoken streaming, visible privacy modes, bounded follow-up, and barge-in without introducing a parallel voice stack.
5. Close P4-03 only after the final wake strategy receives an evidence-backed owner disposition.

## Safety / non-regression boundary

- No Hermes runtime source patch is authorized by this record.
- No separate hotword service is introduced.
- No Hermes/Ollama/iai dependency upgrade is part of P4-03.
- No accepted operator-control change is part of custom-model training.
- WSL is training tooling only; Orion remains a native-Windows product and runtime.
- Training datasets, generated WAV corpora, model caches, and large feature arrays are local artifacts and are not to be committed to this repository.
