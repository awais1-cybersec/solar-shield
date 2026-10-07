# Evaluation status and reproducibility protocol

## Current evidence

| Item | Status |
| --- | --- |
| Trained model | Present at Ai-engine/models/solar_shield.keras; not executed in this maintenance review |
| Original scaler | Owner-supplied at Ai-engine/scaler.pkl; compatibility not yet verified |
| Original dataset / provenance | Not supplied in this repository |
| Train/validation/test split | Not documented; cannot verify absence of leakage |
| Threshold calibration | Not documented; previous fixed 0.12 is not treated as validated |
| Accuracy / false positives / latency | Unmeasured in this review |
| Demo | Deterministic synthetic telemetry for plumbing tests only |

## Required steps before publishing results

1. Record dataset source, license, dates, sample counts, units, feature order, and dataset hashes.
2. Split by independent recording/session or time before constructing windows. Avoid overlapping windows across splits. Fit preprocessing on training data only.
3. Export the original scaler and model together with dependency versions and hashes.
4. Select a threshold on a separate normal validation set and document the target false-positive rate. Freeze it before test evaluation.
5. Evaluate held-out normal and labeled anomaly sessions. Supply one JSON object per line with all eight feature keys and label 0/1. Windows contain 20 consecutive records; label is 1 if any record in that window is anomalous. Evaluate independent sessions separately to avoid cross-session windows.
6. Run evaluate.py. Report confusion counts and denominators; null metrics mean their denominator is zero. Report hardware, runtime, window count and both mean and p95 latency. Latency includes scaling, inference and MSE, including the initial call, but excludes MQTT and database operations.
7. Evaluate drift, frozen telemetry, sensor faults and benign environmental changes separately. Compare against a simple baseline and describe limitations. Anomalies are not automatically malicious.

The owner supplied the original scaler. No replacement scaler or benchmark figures have been fabricated; compatibility still requires validation against the training pipeline.

## Streaming limitations

The live buffer assumes one ordered stream with a consistent sampling interval. It does not currently reject duplicate or out-of-order timestamps or clear the buffer on gaps. It runs model and synchronous database work in the MQTT callback. Queueing, backpressure, timestamp validation and end-to-end latency testing remain deployment work.
