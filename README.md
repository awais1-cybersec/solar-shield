# Solar Shield

A capstone research prototype for detecting deviations in simulated solar-inverter telemetry using an LSTM autoencoder, MQTT, InfluxDB, and Grafana. An anomaly indicates a deviation for investigation, not proof of a cyberattack.

**Status:** the original model and scaler passed an isolated real-service test: MQTT over TLS → Python inference → InfluxDB writes → Grafana panel queries. Eighty synthetic samples produced 61 stored windows (`80 - 20 + 1`). See [the measured results](docs/stack-validation-results.json) and [reproduction instructions](docs/LOCAL_STACK.md). This verifies the test setup; the owner's hosted accounts, physical hardware, training feature order and real-world accuracy remain unverified. The test threshold 0.12 is historical and uncalibrated.

## Architecture

ESP32 simulated telemetry → MQTT broker → Python scaling and reconstruction → InfluxDB → Grafana. The firmware generates eight correlated features; it is not a validated physical inverter model. Inference runs on the host, not on the ESP32.

- [Inference](Ai-engine/run_inference.py)
- [Firmware](Firmware/simulation.ino)
- [Grafana dashboard](Dashboards/solar-shield.json)
- [Demo video](Assets/Demo.mp4)
- [Evaluation status and protocol](docs/EVALUATION.md)
- [Credential cleanup](SECURITY.md)
- [Run an isolated stack without cloud accounts](docs/LOCAL_STACK.md)

## Hardware-free schema demo

Python 3.10+ is sufficient; no ML packages or services are required:

```bash
git clone https://github.com/awais1-cybersec/solar-shield.git
cd solar-shield
python3 Ai-engine/demo_telemetry.py > local-telemetry.jsonl
python3 -m unittest discover -s tests -v
```

This produces deterministic synthetic records with a normal segment followed by injected current spikes. It tests input structure and evaluation plumbing; it does not establish model detection performance.

## Full inference setup

1. Use the supplied original scaler at `Ai-engine/scaler.pkl`. Confirm feature order, units, and preprocessing against the training pipeline. Load only trusted model/scaler artifacts. Do not fit a replacement scaler on test or live data.
2. Use Python 3.12 and install the verified CPU inference dependencies in `Ai-engine/requirements.txt`. These direct versions passed the isolated test; they are not a full transitive lockfile. The original unverified environment snapshot is preserved as `Ai-engine/requirements-original-snapshot.txt`.
3. Copy `.env.example` to `.env`, enter newly issued local credentials, and export them. Never commit `.env`.
4. Set up InfluxDB 2.x with the configured organization/bucket and a bucket-scoped write token. Give Grafana a separate read token, configure a Flux data source and its default bucket, then import `Dashboards/solar-shield.json` and select that data source.
5. Set up Mosquitto authentication and either TLS for the Python client or an isolated plaintext lab. The supplied `Configs/solarshield.conf` defaults to laptop-only `127.0.0.1`: for ESP32 access replace it with a currently assigned isolated LAN IP, create `/etc/mosquitto/passwd` using `mosquitto_passwd`, install it under your broker's configuration directory, and restart the broker. Restrict access to lab hosts.
6. Choose a threshold using held-out normal validation data, then run:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r Ai-engine/requirements.txt
cp .env.example .env
# Edit .env before exporting it.
set -a; source .env; set +a
# Set THRESHOLD to the value established on held-out validation data.
python3 Ai-engine/run_inference.py --threshold "$THRESHOLD" --ca-cert /path/to/ca.pem
# Isolated plaintext lab alternative:
python3 Ai-engine/run_inference.py --threshold "$THRESHOLD" --port 1883 --allow-insecure-lab
```

The model/scaler defaults are resolved relative to the script, independently of the working directory. `--model`, `--scaler`, `--broker`, `--topic`, and `--port` can override defaults.

## ESP32 lab

Copy `Firmware/secrets.example.h` to `Firmware/secrets.h`, fill in local settings, and flash `simulation.ino` with WiFi, PubSubClient and ArduinoJson v7 support. The firmware uses plaintext MQTT on port 1883 and must stay on an isolated lab network; Python TLS support does not encrypt the firmware connection. TLS firmware deployment remains future work.

The command topic `solarshield/commands` accepts NORMAL, FDI, REPLAY and VOLATILITY. REPLAY freezes a subset of simulated features; it is not a comprehensive replay-attack benchmark. Apply broker topic ACLs before sharing a lab.

## Evaluation

See [the evaluation protocol](docs/EVALUATION.md). Example once original artifacts and labeled held-out data are available:

```bash
python3 Ai-engine/evaluate.py held-out.jsonl --model Ai-engine/models/solar_shield.keras --scaler Ai-engine/scaler.pkl --threshold "$THRESHOLD" > local-evaluation.json
```

The evaluator reports confusion counts, precision, recall, false-positive rate, and local processing latency. It does not train, select a threshold, or claim that synthetic demo metrics generalize to real inverters.

## Credits

Team: Muhammad Awais Asgher, Muhammad Ahmed, Mohammad Huzaifa Asim. Supervisor: Dr. Amna Iqbal, Riphah International University.

[MIT License](LICENSE).
