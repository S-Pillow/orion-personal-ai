# P4 Sherpa “Hey Orion” Retune Plan

Status: planning / no runtime mutation  
Date: 2026-09-21  
Baseline: Hermes v2026.8.27 / package 0.20.6 / commit 5fc308a70719a83cccdbba4c0e39c23f5a8239d5

## Why revisit Sherpa without pretending the old result did not happen

The accepted P4-03 record already screened the pinned Sherpa engine on the real Windows/JLab/MME path. `Hey Orion` reached only about 6/10 at sensitivity 0.5 and 0.4, while `Hey Jarvis` was materially stronger. That result is real and remains evidence against accepting the current Sherpa configuration.

The goal, however, is still a supported local Hermes `Hey Orion` wake path. The failed custom openWakeWord v1/v2 method does not require abandoning that goal.

Pinned-source review found:

- the accepted Hermes commit already contains `_SherpaKwsEngine`;
- `wake_word.phrase` is the actual detection phrase for Sherpa;
- the model is the small English streaming zipformer KWS model;
- Hermes maps the shared 0..1 `sensitivity` setting to Sherpa `keywords_threshold` as:
  `threshold = 0.05 + 0.4 * sensitivity`;
- the accepted wrapper does **not** expose Sherpa `keywords_score`, so sherpa-onnx uses its default score.

Sherpa’s upstream API treats these as separate controls:

- lower `keywords_threshold` -> easier trigger / more recall, at false-accept cost;
- higher `keywords_score` -> keyword paths survive beam search more easily, also at false-accept cost.

Therefore there is a bounded configuration space that the original 0.5/0.4 screen did not exhaust.

## Do not start with a live source patch

The next experiment should be configuration/evaluation work, not an installed Hermes code change.

Sensitivity maps to threshold as follows:

| Hermes sensitivity | Sherpa threshold |
| ---: | ---: |
| 0.5 | 0.25 |
| 0.4 | 0.21 |
| 0.3 | 0.17 |
| 0.2 | 0.13 |
| 0.1 | 0.09 |
| 0.0 | 0.05 |

The prior evidence covers approximately 0.25 and 0.21. The next useful threshold-only candidates are 0.17 and 0.13. Do not jump straight to the loosest setting and call high recall a success; false wakes are the counter-metric.

## Better experiment: fixed deployment corpus first

Repeated live utterances make A/B comparison noisy. Build one local, non-committed evaluation corpus from the actual JLab/MME deployment path, then run parameter sweeps against identical audio.

### Positive corpus

Capture at least 40 distinct `Hey Orion` clips from Steven through the JLab:

- normal seated position;
- small changes in pace/pitch;
- near and slightly farther mic position;
- some normal room background;
- preserve every intended attempt, including weak or imperfect utterances.

Use 16 kHz mono PCM16 WAV for the evaluator. Keep raw recordings outside the Git repo.

### Negative/ambient corpus

Capture representative non-wake audio from the same room, including:

- Steven speaking normal sentences that do not contain `Hey Orion`;
- TV/video/podcast speech;
- keyboard/desk noise;
- room silence/HVAC;
- ordinary conversation if available.

For screening, a smaller ambient set is enough to reject obviously loose candidates. The final accepted wake candidate still needs the previously planned extended ambient gate.

## Offline grid

Run identical positive/negative audio through:

1. threshold-only baseline:
   - threshold 0.25 / score 1.0 (reproduce old default);
   - threshold 0.21 / score 1.0;
   - threshold 0.17 / score 1.0;
   - threshold 0.13 / score 1.0.
2. Only if threshold-only cannot achieve acceptable recall without false wakes, evaluate score as a new source-only tuning seam. Suggested diagnostic grid, not acceptance defaults:
   - score 1.5 and 2.0;
   - pair only with the least-loose thresholds that remain promising.
3. Avoid using the sherpa example values (score 3.0 / threshold 0.1) as an Orion recommendation merely because they appear in upstream samples. They demonstrate parameter capability, not a safe product operating point.

For every cell record:

- positive hits / total;
- false accepts / negative hours;
- exact phrase;
- model identity;
- threshold;
- score;
- input corpus hash/manifest.

Use the same corpus for every cell.

## Stop/advance rules

Stage 1 screen:

- if a setting cannot reach at least 19/20 on a representative first 20 positive clips, do not advance it;
- if it produces obvious ambient false fires during the small negative screen, reject it even if recall improves.

Stage 2 controlled live screen:

- take the best offline candidate back to the actual live JLab path;
- retain the existing working gate: >=38/40 intended detections (>=95%);
- do not lower the gate because this is a different engine/tuning method.

Stage 3 extended acceptance:

- only a candidate that clears the controlled live screen proceeds to the larger >=95/100 intended-wake check plus the six-hour realistic ambient false-wake gate already envisioned by P4-03;
- include TV/background speech because it is a known stress case for wake detectors.

## If threshold-only works

Prefer configuration over a Hermes source patch.

A passing setting using the already-exposed `sensitivity` knob is the lowest-complexity path. Record the exact COMPANION config delta and make the normal owner-approved runtime change only after the live screen is accepted.

## If threshold-only fails but score helps materially

Then there is a demonstrated interface gap: sherpa-onnx supports `keywords_score`, but the accepted Hermes wrapper does not expose it.

A narrowly qualified candidate patch may add:

```yaml
wake_word:
  sherpa:
    keywords_score: 1.0
```

with these constraints:

- default exactly 1.0 so existing behavior is unchanged;
- bounded numeric validation;
- passed only to `sherpa_onnx.KeywordSpotter`;
- no second wake service;
- no dependency upgrade;
- source tests proving default compatibility and invalid-value handling;
- isolated Windows/JLab qualification before any accepted runtime patch.

If score tuning still cannot meet recall and ambient gates, stop the Sherpa path. Do not keep adding knobs indefinitely.

## If Sherpa still fails

The goal remains `Hey Orion`, but the approach changes again.

Remaining evidence-backed options are:

1. redesign custom openWakeWord training using deployment-specific positives/negatives and a materially different experiment, rather than v3-by-inertia;
2. consider an OpenWakeWord verifier only if the main problem becomes false accepts rather than missed intended wakes; a verifier cannot rescue a base detector that rarely fires;
3. make an explicit owner/product decision to defer wake while retaining PTT—without pretending PRD Phase 4 wake acceptance is complete.

## Research basis

- Accepted pinned Hermes source: Sherpa is already a first-class open-vocabulary provider.
- sherpa-onnx Python API: `keywords_score` increases keyword-path survival and `keywords_threshold` controls trigger probability.
- openWakeWord recommends tuning activation thresholds to the actual environment and measuring false accepts against realistic continuous speech/noise.
- P4-03 already established that capture itself can perform well on other wake phrases, so a weak `Hey Orion` result should not automatically be blamed on the JLab path.

## Immediate no-side-effect preflight

Run the source-controlled `scripts/phase4/p4-sherpa-readonly-preflight.py` with the accepted Hermes venv before any wake change. It fingerprints installed source, reports whether dependencies/model cache already exist, and reads only the wake configuration subset. It does not install dependencies, download the model, open the microphone, enable wake, or write configuration.
