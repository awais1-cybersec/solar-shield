# Evaluation status and reproducibility protocol

## Current evidence

| Item | Status |
| --- | --- |
| Trained model | Loaded and executed; input/output shape (batch, 20, 8) |
| Original scaler | Owner-supplied; eight-feature transformation and model inference pass; training feature order not recorded in scaler |
| Original dataset / provenance | Not supplied in this repository |
| Train/validation/test split | Not documented; cannot verify absence of leakage |
| Threshold calibration | Not documented; previous fixed 0.12 is not treated as validated |
| Accuracy / false positives / latency | Synthetic counts and local warm inference timing recorded below; real-world performance unmeasured |
| Demo | Deterministic synthetic telemetry for plumbing tests only |

## Required steps before publishing results

1. Record dataset source, license, dates, sample counts, units, feature order, and dataset hashes.
2. Split by independent recording/session or time before constructing windows. Avoid overlapping windows across splits. Fit preprocessing on training data only.
3. Export the original scaler and model together with dependency versions and hashes.
4. Select a threshold on a separate normal validation set and document the target false-positive rate. Freeze it before test evaluation.
5. Evaluate held-out normal and labeled anomaly sessions. Supply one JSON object per line with all eight feature keys and label 0/1. Windows contain 20 consecutive records; label is 1 if any record in that window is anomalous. Evaluate independent sessions separately to avoid cross-session windows.
6. Run evaluate.py. Report confusion counts and denominators; null metrics mean their denominator is zero. Report hardware, runtime, window count and both mean and p95 latency. Latency includes scaling, inference and MSE, including the initial call, but excludes MQTT and database operations.
7. Evaluate drift, frozen telemetry, sensor faults and benign environmental changes separately. Compare against a simple baseline and describe limitations. Anomalies are not automatically malicious.

The owner supplied the original scaler. No replacement scaler or benchmark figures have been fabricated; runtime shape compatibility is verified, but feature order, units and preprocessing still require confirmation against the training pipeline.

## Streaming limitations

The live buffer assumes one ordered stream with a consistent sampling interval. It does not currently reject duplicate or out-of-order timestamps or clear the buffer on gaps. It runs model and synchronous database work in the MQTT callback. Queueing, backpressure, timestamp validation, outage recovery and per-record latency testing remain deployment work. A synthetic burst through real local services is recorded below.

## Executed synthetic integration check

The [recorded result](validation-results.json) was produced on 2026-10-08 using the committed model and original scaler. The test calls the real telemetry callback, scaler, model and InfluxDB point serializer. Only database delivery is replaced with a local capture; no MQTT network, real database, Grafana or ESP32 is exercised.

- 80 deterministic samples; 61 sliding windows; 61 serialized database points.
- Every reconstruction has the expected shape and finite values; malformed JSON leaves the buffer and captured records unchanged.
- At the historical, uncalibrated threshold 0.12: TP 39, FP 0, TN 21, FN 1. These synthetic counts do not establish detection accuracy on real inverters.
- Warm model prediction averaged about 113 ms (p95 265 ms) on this container. This excludes scaling, transport and storage and is not deployment latency.
- The report includes artifact SHA-256 hashes and runtime versions. The scaler does not record feature names, so dimensional compatibility alone cannot prove correct training feature order.

Reproduce from the repository root using Python 3.12:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r tests/requirements-validation.txt
python tests/validate_model.py --output local-evaluation.json
```

This script loads the repository's trusted serialized model/scaler and requires no service credentials. The six lightweight contract tests remain runnable without ML dependencies. This earlier check captured database writes locally. The subsequent real-service check below verifies delivery and test credential revocation in a new isolated environment. Owner-account credential revocation, threshold calibration and held-out evaluation remain pending.

## Executed real-service integration check

See [stack-validation-results.json](stack-validation-results.json) for measured evidence
and [LOCAL_STACK.md](LOCAL_STACK.md) for the executable procedure. Mosquitto, InfluxDB
and Grafana were newly created local services; no service transport or database write
was mocked. The original model/scaler artifacts were used without fitting preprocessing.

- 80 valid samples and one malformed JSON message traveled through real MQTT TLS.
- 61 windows were stored in InfluxDB with finite MSE, matching anomaly flags and the running threshold.
- Grafana data-source health returned OK; all three imported dashboard panel queries returned data.
- Generated MQTT credentials were replaced and the old password rejected. A generated InfluxDB token was revoked and rejected. Grafana's separate read-only token was denied a write.
- This validates the isolated setup, not the owner's laptop or cloud deployment. No exposed owner credential was used or revoked.
- The recorded burst took about 12.36 seconds from publication until all records were visible in the database. This is not per-record latency, throughput or real-inverter performance.
- Backend panel queries were exercised; browser rendering was not exercised in the recorded run.

The synthetic dataset, overlapping windows and historical threshold cannot establish
real-world detection quality. Training data, feature-order provenance, split evidence
and threshold calibration are still needed for held-out evaluation.
