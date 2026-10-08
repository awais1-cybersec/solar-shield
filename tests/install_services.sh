#!/usr/bin/env bash
# Download pinned native test services without installing system services.
set -euo pipefail
test_services_dir="${1:-.test-services}"
mkdir -p "$test_services_dir"
test_services_dir="$(cd "$test_services_dir" && pwd)"
for program in curl tar make gcc openssl sha256sum; do
  command -v "$program" >/dev/null
done

download() {
  local url="$1" filename="$2" expected="$3"
  if [ ! -f "$test_services_dir/$filename" ]; then
    curl --fail --silent --show-error --location --retry 2 "$url" -o "$test_services_dir/$filename"
  fi
  printf '%s  %s\n' "$expected" "$test_services_dir/$filename" | sha256sum --check -
}

# Mosquitto matches the owner's 2.0.18 environment. These are reproducibility
# pins for a loopback test, not a recommendation for production versions.
download 'https://mosquitto.org/files/source/mosquitto-2.0.18.tar.gz' 'mosquitto.tar.gz' 'd665fe7d0032881b1371a47f34169ee4edab67903b2cd2b4c083822823f4448a'
download 'https://download.influxdata.com/influxdb/releases/influxdb2-2.9.1_linux_amd64.tar.gz' 'influxdb.tar.gz' '762e4fc825c4386e0c5138e7c3f91fc778081db2bada1ec47066e786bf55d9ff'
download 'https://dl.grafana.com/grafana/release/13.1.7/grafana_13.1.7_36414001255_linux_amd64.tar.gz' 'grafana-oss.tar.gz' '7c168c1fe147e5f3550fa15e5f59362bde5719ab98c905a91a37aa969203c92f'

tar --no-same-owner -xzf "$test_services_dir/mosquitto.tar.gz" -C "$test_services_dir"
make -C "$test_services_dir/mosquitto-2.0.18" -j2 WITH_DOCS=no WITH_CJSON=no WITH_CONTROL=no WITH_STATIC_LIBRARIES=no
tar --no-same-owner -xzf "$test_services_dir/influxdb.tar.gz" -C "$test_services_dir"
mkdir -p "$test_services_dir/oss"
tar --no-same-owner -xzf "$test_services_dir/grafana-oss.tar.gz" -C "$test_services_dir/oss"
