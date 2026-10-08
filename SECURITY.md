# Credential cleanup and deployment scope

Earlier commits contained an InfluxDB token and MQTT credentials. Their validity has not been tested. Removing them from current source does not revoke them or erase Git history.

Required owner actions:

1. Revoke the previously committed InfluxDB token in the actual InfluxDB service and create a scoped replacement.
2. Change the MQTT password in the broker's password store and update local clients.
3. Review service access logs if those credentials were used on reachable services.
4. After rotation, assess whether coordinated history cleanup is needed. No history rewrite was performed by this maintenance change.

Use .env and Firmware/secrets.h locally; both are ignored. Never paste replacement credentials into issues or documentation. The provided firmware/broker configuration is for isolated plaintext labs. Do not describe this setup as encrypted transport.

Reference: https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository

## Isolated service validation

The repository's `tests/validate_stack.py` creates fresh, temporary test credentials
and verifies password replacement, InfluxDB token revocation, MQTT TLS and a Grafana
read-only token. Results are recorded in `docs/stack-validation-results.json`.
These checks do not revoke credentials previously exposed from the owner's services.
No old owner token or password is used by the test. Temporary credentials, keys and
service state are removed when the harness exits; they are never committed.

The broker template now binds to loopback by default. The real-service test creates
a separate loopback TLS listener. Any ESP32 or LAN deployment needs its own supported
network address, authentication, topic ACLs and transport configuration.
