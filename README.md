# Solar Shield

A capstone research prototype for detecting deviations in simulated solar-inverter telemetry using an LSTM autoencoder, MQTT, InfluxDB, and Grafana. An anomaly indicates a deviation for investigation, not proof of a cyberattack.

**Status:** source, model, and the owner-supplied original scaler are available. Model/scaler compatibility and end-to-end inference have not yet been verified in this maintenance review. Training/evaluation data and calibration evidence are not included, so no accuracy, replay-detection guarantee, or latency benchmark is claimed.

## Architecture

ESP32 simulated telemetry → MQTT broker → Python scaling and reconstruction → InfluxDB → Grafana. The firmware generates eight correlated features; it is not a validated physical inverter model. Inference runs on the host, not on the ESP32.

- [Inference](Ai-engine/run_inference.py)
- [Firmware](Firmware/simulation.ino)
- [Grafana dashboard](Dashboards/solar-shield.json)
- [Demo video](Assets/Demo.mp4)
- [Evaluation status and protocol](docs/EVALUATION.md)
- [Credential cleanup](SECURITY.md)

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
2. Create a virtual environment and install `Ai-engine/requirements.txt`. This is the original pinned environment snapshot, not a newly verified compatibility lockfile.
3. Copy `.env.example` to `.env`, enter newly issued local credentials, and export them. Never commit `.env`.
4. Set up InfluxDB with the configured organization/bucket and a scoped token; import `Dashboards/solar-shield.json` into Grafana and select your local data source.
5. Set up Mosquitto authentication and either TLS for the Python client or an isolated plaintext lab. The supplied `Configs/solarshield.conf` is a lab template: replace its bind IP, create `/etc/mosquitto/passwd` using `mosquitto_passwd`, install it under your broker's configuration directory, and restart the broker. Restrict access to lab hosts.
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
