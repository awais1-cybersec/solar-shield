"""Run real, isolated Mosquitto -> detector -> InfluxDB -> Grafana checks.

Requires local service binaries; never contacts the owner's hosted accounts.
Temporary credentials and state are removed, and child services stop on exit.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import pwd
import secrets
import socket
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime, timezone
from importlib.metadata import version

import requests
import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion
from influxdb_client import InfluxDBClient

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / 'Ai-engine'))
from demo_telemetry import records


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def wait_for(check, seconds=60):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            value = check()
            if value:
                return value
        except (requests.RequestException, ConnectionError, OSError):
            pass
        time.sleep(.2)
    raise TimeoutError('Service or pipeline did not become ready before the deadline')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mosquitto', type=Path, required=True)
    parser.add_argument('--mosquitto-passwd', type=Path, required=True)
    parser.add_argument('--influxd', type=Path, required=True)
    parser.add_argument('--grafana-home', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--screenshot', type=Path, help='Optional: requires Playwright and Chromium')
    parser.add_argument('--chromium', type=Path, help='Optional browser executable for --screenshot')
    args = parser.parse_args()
    for name in ('mosquitto', 'mosquitto_passwd', 'influxd', 'grafana_home'):
        setattr(args, name, getattr(args, name).resolve())
    children = []
    logs = []
    with tempfile.TemporaryDirectory(prefix='solar-shield-stack-') as directory:
        state = Path(directory)

        def spawn(command, name, env=None, cwd=None):
            log = (state / (name + '.log')).open('w')
            logs.append(log)
            process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT,
                                       env=env, cwd=cwd)
            children.append(process)
            return process

        def stop(process):
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)

        mqtt_port, influx_port, grafana_port = free_port(), free_port(), free_port()
        influx_url = f'http://127.0.0.1:{influx_port}'
        grafana_url = f'http://127.0.0.1:{grafana_port}'
        org, bucket, topic = 'solar_shield_org', 'solar_shield_telemetry', 'solarshield/telemetry/inverter1'
        try:
            # Self-signed trust anchor with explicit loopback SAN, used only in this test.
            subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes',
                            '-keyout', str(state / 'key.pem'), '-out', str(state / 'ca.pem'),
                            '-days', '1', '-subj', '/CN=localhost',
                            '-addext', 'subjectAltName=DNS:localhost,IP:127.0.0.1'],
                           check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            (state / 'key.pem').chmod(0o600)
            username, old_password, password = 'solar-test', secrets.token_urlsafe(24), secrets.token_urlsafe(24)

            def set_password(value, create=False):
                command = [str(args.mosquitto_passwd)]
                if create:
                    command.append('-c')
                command += [str(state / 'passwd'), username]
                subprocess.run(command, input=value + '\n' + value + '\n', text=True,
                               check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            set_password(old_password, create=True)
            (state / 'passwd').chmod(0o600)
            (state / 'acl').write_text(f'user {username}\ntopic readwrite {topic}\n')
            config = state / 'mosquitto.conf'
            config.write_text(f'listener {mqtt_port} 127.0.0.1\nallow_anonymous false\n'
                              f'user {pwd.getpwuid(os.getuid()).pw_name}\n'
                              f'password_file {state / "passwd"}\nacl_file {state / "acl"}\n'
                              f'certfile {state / "ca.pem"}\nkeyfile {state / "key.pem"}\n'
                              'log_dest stdout\nlog_type all\n')
            broker = spawn([str(args.mosquitto), '-c', str(config)], 'mqtt-before-rotation')

            def connect(password_value=None, anonymous=False):
                client = mqtt.Client(CallbackAPIVersion.VERSION2)
                client.tls_set(ca_certs=str(state / 'ca.pem'))
                if not anonymous:
                    client.username_pw_set(username, password_value)
                event = threading.Event()
                reason = []
                client.on_connect = lambda c, u, f, rc, p: (reason.append(rc), event.set())
                client.connect('127.0.0.1', mqtt_port, 30)
                client.loop_start()
                require(event.wait(10), 'MQTT connection callback timed out')
                return client, reason[0]

            wait_for(lambda: socket.create_connection(('127.0.0.1', mqtt_port), timeout=1).close() or True)
            client, rc = connect(old_password)
            require(rc == 0, 'Initial MQTT credential rejected')
            client.disconnect(); client.loop_stop()
            stop(broker)
            set_password(password)
            broker = spawn([str(args.mosquitto), '-c', str(config)], 'mqtt-after-rotation')
            wait_for(lambda: socket.create_connection(('127.0.0.1', mqtt_port), timeout=1).close() or True)
            for candidate, anonymous in ((old_password, False), (None, True)):
                client, rc = connect(candidate, anonymous)
                require(rc != 0, 'Revoked or anonymous MQTT login unexpectedly accepted')
                client.disconnect(); client.loop_stop()
            publisher, rc = connect(password)
            require(rc == 0, 'Replacement MQTT credential rejected')

            influx = spawn([str(args.influxd), '--http-bind-address', f'127.0.0.1:{influx_port}',
                            '--bolt-path', str(state / 'influx.bolt'), '--sqlite-path', str(state / 'influx.sqlite'),
                            '--engine-path', str(state / 'engine'), '--reporting-disabled'], 'influx')
            wait_for(lambda: requests.get(influx_url + '/health', timeout=2).status_code == 200)
            setup = requests.post(influx_url + '/api/v2/setup', json={
                'username': 'solar-admin', 'password': secrets.token_urlsafe(24),
                'org': org, 'bucket': bucket, 'retentionPeriodSeconds': 3600}, timeout=15)
            setup.raise_for_status()
            data = setup.json()
            admin_token, org_id, bucket_id = data['auth']['token'], data['org']['id'], data['bucket']['id']
            admin_headers = {'Authorization': 'Token ' + admin_token}

            def token(action):
                response = requests.post(influx_url + '/api/v2/authorizations', headers=admin_headers,
                    json={'orgID': org_id, 'description': 'isolated-test-' + action, 'permissions': [
                        {'action': action, 'resource': {'type': 'buckets', 'id': bucket_id, 'orgID': org_id}}]}, timeout=10)
                response.raise_for_status()
                return response.json()

            retired = token('write')
            response = requests.delete(influx_url + '/api/v2/authorizations/' + retired['id'],
                                       headers=admin_headers, timeout=10)
            require(response.status_code == 204, 'Token revocation failed')
            response = requests.post(influx_url + '/api/v2/write', params={'org': org, 'bucket': bucket},
                headers={'Authorization': 'Token ' + retired['token']}, data='credential_probe value=1', timeout=10)
            require(response.status_code == 401, 'Revoked InfluxDB token was not rejected')
            writer_token, reader_token = token('write')['token'], token('read')['token']
            # A Grafana reader must not be able to write telemetry.
            response = requests.post(influx_url + '/api/v2/write', params={'org': org, 'bucket': bucket},
                headers={'Authorization': 'Token ' + reader_token}, data='credential_probe value=1', timeout=10)
            require(response.status_code in (401, 403), 'Read-only token could write')

            grafana_password = secrets.token_urlsafe(24)
            grafana_env = os.environ.copy()
            grafana_env.update({'GF_SERVER_HTTP_ADDR': '127.0.0.1', 'GF_SERVER_HTTP_PORT': str(grafana_port),
                'GF_PATHS_DATA': str(state / 'grafana-data'), 'GF_PATHS_LOGS': str(state / 'grafana-logs'),
                'GF_PATHS_PLUGINS': str(state / 'plugins'), 'GF_PATHS_PROVISIONING': str(state / 'provisioning'),
                'GF_SECURITY_ADMIN_USER': 'solar-admin', 'GF_SECURITY_ADMIN_PASSWORD': grafana_password,
                'GF_SECURITY_SECRET_KEY': secrets.token_urlsafe(32), 'GF_ANALYTICS_REPORTING_ENABLED': 'false',
                'GF_ANALYTICS_CHECK_FOR_UPDATES': 'false', 'GF_ANALYTICS_CHECK_FOR_PLUGIN_UPDATES': 'false',
                'GF_LOG_LEVEL': 'warn'})
            grafana = spawn([str(args.grafana_home / 'bin/grafana'), 'server', '--homepath', str(args.grafana_home)],
                            'grafana', env=grafana_env, cwd=args.grafana_home)
            wait_for(lambda: requests.get(grafana_url + '/api/health', timeout=2).status_code == 200)
            session = requests.Session()
            session.auth = ('solar-admin', grafana_password)
            ds_uid = 'solar-shield-influxdb'
            response = session.post(grafana_url + '/api/datasources', json={
                'uid': ds_uid, 'name': 'Solar Shield InfluxDB', 'type': 'influxdb', 'access': 'proxy',
                'url': influx_url, 'jsonData': {'version': 'Flux', 'organization': org, 'defaultBucket': bucket},
                'secureJsonData': {'token': reader_token}}, timeout=15)
            response.raise_for_status()
            health = session.get(grafana_url + f'/api/datasources/uid/{ds_uid}/health', timeout=15)
            health.raise_for_status()
            require(health.json().get('status') == 'OK', 'Grafana data-source health failed')
            dashboard = json.loads((BASE / 'Dashboards/solar-shield.json').read_text().replace('${DS_INFLUXDB}', ds_uid))
            dashboard.pop('__inputs', None)
            response = session.post(grafana_url + '/api/dashboards/db', json={'dashboard': dashboard, 'overwrite': True}, timeout=15)
            response.raise_for_status()
            dashboard_url = response.json()['url']
            response = session.get(grafana_url + '/api/dashboards/uid/solar-shield', timeout=15)
            response.raise_for_status()
            require(len(response.json()['dashboard']['panels']) == 3, 'Dashboard import lost panels')

            detector_env = os.environ.copy()
            detector_env.update({'INFLUX_URL': influx_url, 'INFLUX_TOKEN': writer_token, 'INFLUX_ORG': org,
                'INFLUX_BUCKET': bucket, 'MQTT_USERNAME': username, 'MQTT_PASSWORD': password,
                'TF_NUM_INTRAOP_THREADS': '1', 'TF_NUM_INTEROP_THREADS': '1', 'PYTHONUNBUFFERED': '1'})
            detector = spawn([sys.executable, str(BASE / 'Ai-engine/run_inference.py'), '--broker', '127.0.0.1',
                              '--port', str(mqtt_port), '--ca-cert', str(state / 'ca.pem'), '--threshold', '0.12'],
                             'detector', env=detector_env)
            wait_for(lambda: 'Actively monitoring telemetry' in (state / 'detector.log').read_text(), seconds=120)
            # Wait for a SUBACK observed by the publisher-independent broker log.
            wait_for(lambda: 'Sending SUBACK' in (state / 'mqtt-after-rotation.log').read_text())
            rows = list(records(80))
            started = time.perf_counter()
            for payload in [b'{invalid'] + [json.dumps(row).encode() for row in rows]:
                info = publisher.publish(topic, payload, qos=1)
                info.wait_for_publish(timeout=10)
                require(info.is_published(), 'MQTT publish was not acknowledged')
            reader = InfluxDBClient(url=influx_url, token=reader_token, org=org)
            query = f'from(bucket: "{bucket}") |> range(start: -1h) |> filter(fn: (r) => r._measurement == "inverter_telemetry" and r._field == "mse")'

            def stored():
                tables = reader.query_api().query(query)
                return [record.get_value() for table in tables for record in table.records]

            values = wait_for(lambda: (v if len(v := stored()) == 61 else None), seconds=120)
            elapsed = time.perf_counter() - started
            require(all(math.isfinite(value) for value in values), 'Non-finite stored MSE')
            flags_query = query.replace('r._field == "mse"', 'r._field == "is_anomaly"')
            flags = [r.get_value() for t in reader.query_api().query(flags_query) for r in t.records]
            threshold_query = query.replace('r._field == "mse"', 'r._field == "threshold"')
            thresholds = [r.get_value() for t in reader.query_api().query(threshold_query) for r in t.records]
            require(len(flags) == 61 and len(thresholds) == 61, 'Missing anomaly/threshold fields')
            require(all(value == .12 for value in thresholds), 'Recorded threshold mismatch')
            require(flags == [value > .12 for value in values], 'Stored flags disagree with MSE')
            # Query every actual dashboard panel through Grafana's InfluxDB plugin.
            panel_results = []
            now_ms = int(time.time() * 1000)
            for panel in dashboard['panels']:
                target = panel['targets'][0].copy()
                target.update({'datasource': {'type': 'influxdb', 'uid': ds_uid}, 'intervalMs': 1000,
                               'maxDataPoints': 1000})
                response = session.post(grafana_url + '/api/ds/query', json={
                    'from': str(now_ms - 3600000), 'to': str(now_ms), 'queries': [target]}, timeout=30)
                response.raise_for_status()
                result = response.json()['results']['A']
                require(not result.get('error'), 'Grafana panel query returned an error')
                frames = result.get('frames', [])
                count = sum(len(frame.get('data', {}).get('values', [[]])[0]) for frame in frames)
                require(count > 0, 'Grafana panel query returned no values')
                panel_results.append({'title': panel['title'], 'frames': len(frames), 'rows': count})
            detector_log = (state / 'detector.log').read_text()
            require('malformed JSON' in detector_log and 'Failed to write' not in detector_log
                    and 'Unexpected error' not in detector_log, 'Detector logged a processing failure')
            if args.screenshot:
                from playwright.sync_api import sync_playwright
                args.screenshot.parent.mkdir(parents=True, exist_ok=True)
                with sync_playwright() as playwright:
                    browser = playwright.chromium.launch(headless=True, args=['--no-sandbox'],
                        **({'executable_path': str(args.chromium.resolve())} if args.chromium else {}))
                    context = browser.new_context(viewport={'width': 1440, 'height': 1000},
                        http_credentials={'username': 'solar-admin', 'password': grafana_password})
                    page = context.new_page()
                    page.goto(grafana_url + dashboard_url, wait_until='networkidle', timeout=60000)
                    page.wait_for_timeout(5000)
                    require(page.get_by_text('Reconstruction Error and Active Threshold', exact=True).count() > 0,
                            'Dashboard panel was not rendered')
                    page.screenshot(path=str(args.screenshot), full_page=True)
                    browser.close()
            result = {'validated_at_utc': datetime.now(timezone.utc).isoformat(),
                'scope': 'Isolated real local services; synthetic publisher, original model/scaler; no physical inverter or owner cloud account.',
                'python': platform.python_version(),
                'dependencies': {name: version(name) for name in ('tensorflow-cpu', 'keras', 'numpy', 'scikit-learn', 'paho-mqtt', 'influxdb-client')},
                'services': {'mosquitto': subprocess.run([str(args.mosquitto), '-h'], capture_output=True, text=True).stdout.splitlines()[0],
                    'influxdb': requests.get(influx_url + '/health', timeout=5).json().get('version'),
                    'grafana': requests.get(grafana_url + '/api/health', timeout=5).json().get('version')},
                'mqtt_tls_verified': True, 'anonymous_mqtt_rejected': True, 'rotated_old_mqtt_password_rejected': True,
                'revoked_test_influx_token_rejected': True, 'grafana_read_token_write_rejected': True,
                'real_service_credentials_rotated': 'Only newly created isolated test credentials; owner credentials not accessed or revoked.',
                'records_published': len(rows), 'invalid_json_published': 1, 'stored_windows': len(values),
                'expected_windows_calculation': '80 - 20 + 1 = 61', 'threshold': .12,
                'threshold_status': 'Historical uncalibrated value used for a plumbing test',
                'normal_flags': flags.count(False), 'anomaly_flags': flags.count(True),
                'mse_min': min(values), 'mse_max': max(values),
                'publish_to_all_records_stored_seconds': elapsed,
                'timing_scope': 'Entire 80-record burst including MQTT delivery, inference and DB writes; not per-record latency or hardware benchmark.',
                'grafana_data_source_health': health.json()['status'], 'grafana_dashboard_panels': panel_results,
                'browser_render_checked': bool(args.screenshot),
                'artifact_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in
                    (BASE / 'Ai-engine/scaler.pkl', BASE / 'Ai-engine/models/solar_shield.keras')}}
            reader.close()
            publisher.disconnect(); publisher.loop_stop()
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(result, indent=2) + '\n')
            print(json.dumps(result, indent=2))
        finally:
            # Do not echo logs: services may log sensitive configuration on failure.
            for process in reversed(children):
                stop(process)
            for log in logs:
                log.close()


if __name__ == '__main__':
    main()
