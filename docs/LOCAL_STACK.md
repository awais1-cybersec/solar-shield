# Reproduce the isolated Solar Shield pipeline

This test starts its own real Mosquitto, InfluxDB and Grafana processes. It requires
no cloud accounts, existing service passwords, ESP32 or physical inverter. It does
not modify an existing Mosquitto installation or contact the owner's hosted services.

## Ubuntu x86-64 setup

Use Python 3.12, a C compiler, Make, OpenSSL headers, curl, tar and sha256sum.
On Ubuntu, install the native dependencies with:

```bash
sudo apt-get update
sudo apt-get install -y build-essential libssl-dev curl openssl
```

From the repository root:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r tests/requirements-validation.txt
bash tests/install_services.sh
python tests/validate_stack.py \
  --mosquitto .test-services/mosquitto-2.0.18/src/mosquitto \
  --mosquitto-passwd .test-services/mosquitto-2.0.18/apps/mosquitto_passwd/mosquitto_passwd \
  --influxd .test-services/influxdb2-2.9.1/influxd \
  --grafana-home .test-services/oss/grafana-13.1.7 \
  --output local-stack-results.json
```

The installer downloads pinned archives from the projects' official HTTPS hosts,
checks their SHA-256 values and compiles Mosquitto with TLS. The Grafana checksum
was checked against its official download page; the Mosquitto and InfluxDB hashes
record the archives used in this test. This is a reproducible test environment,
not a production package-management or upgrade policy.

The same commands run in the **Real service integration** GitHub Actions workflow.
The workflow uploads a result JSON containing no credentials.

## What the test verifies

1. Mosquitto starts on a randomly assigned loopback port with password authentication,
   topic ACLs and a short-lived TLS certificate. The Python publisher validates it.
2. An initial generated password authenticates. After replacement and broker restart,
   the old password and anonymous connections are rejected; the new password works.
3. A fresh InfluxDB organization and bucket are created. A test write token is revoked
   and its subsequent write returns HTTP 401. Separate bucket-scoped writer and reader
   tokens are created; the reader cannot write.
4. The actual inference CLI connects over MQTT TLS and writes through the real
   synchronous InfluxDB client. It uses the committed original model and scaler.
5. A malformed JSON message is rejected. Eighty synthetic telemetry samples produce
   `80 - 20 + 1 = 61` stored sliding-window records with finite MSE, matching flags and
   the configured threshold.
6. Grafana imports the portable three-panel dashboard, passes data-source health,
   and executes each panel's Flux query against real stored data through its plugin.

Every run uses a private temporary directory and new credentials. The harness stops
all child services and removes their temporary state on exit. Its URLs are temporary
loopback addresses, not publicly hosted dashboards. The test does not leave a stack
running for everyday use.

## Dashboard import for an existing deployment

Create an InfluxDB **Flux** data source with the correct URL, organization and default
bucket. Give Grafana a token with read access to that bucket; the detector needs a
separate write token. Import `Dashboards/solar-shield.json` and select this data source
when prompted. The dashboard no longer requires an ID from the original cloud account.
The MSE panel reads the running detector's `threshold` field rather than displaying
a hardcoded threshold. Older records without that field can still show MSE.

## Evidence and limits

See [the committed real-service results](stack-validation-results.json) and
[the evaluation protocol](EVALUATION.md). The test uses deterministic synthetic
telemetry and the historical **uncalibrated** threshold 0.12. It verifies integration,
not real-inverter accuracy, resistance to attacks, throughput or production readiness.
The recorded burst duration is the time from publication until all database records
are visible; it is not a per-record latency benchmark.

Grafana data-source health, dashboard import and backend panel queries are checked.
Browser rendering is optional: install Playwright and Chromium, then add
`--screenshot /path/to/dashboard.png` (or `--chromium /path/to/browser`). The recorded
result explicitly states whether a browser was exercised.

Original training feature order, dataset provenance and held-out threshold calibration
remain unverified. ESP32 firmware and a physical inverter are not exercised. MQTT QoS 1
supports redelivery; the detector has no duplicate/timestamp handling or durable retry
queue. Database failures are logged; this test does not establish outage recovery.
Previously exposed owner credentials still require revocation in the owner's services.

References:

- https://mosquitto.org/download/
- https://mosquitto.org/man/mosquitto-conf-5.html
- https://docs.influxdata.com/influxdb/v2/install/
- https://docs.influxdata.com/influxdb/v2/get-started/setup/
- https://grafana.com/grafana/download/13.1.7?edition=oss
- https://grafana.com/docs/grafana/latest/developer-resources/api-reference/http-api/api-legacy/data_source/
