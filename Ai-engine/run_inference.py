import argparse
from pathlib import Path
from telemetry import extract_features
import json
import time
import logging
import numpy as np
import tensorflow as tf
import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion
from collections import deque
import joblib  # Scaler load karne ke liye zaroori hai

# --- Naye InfluxDB Imports ---
import os
from influxdb_client.client.influxdb_client import InfluxDBClient
from influxdb_client.client.write.point import Point
from influxdb_client.client.write_api import SYNCHRONOUS

# Configure console logging for the research prototype
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - [R-TADS] - %(levelname)s - %(message)s'
)

class SolarShieldRTADS:
    """
    Real-Time Anomaly Detection System for Solar Shield.
    Runtime contract: 8 features and 20 records per reconstruction window.
    """
    def __init__(self, args):
        # 1. System Configuration
        self.broker = args.broker
        self.topic = args.topic
        self.threshold = args.threshold 
        self.window_size = 20  
        self.n_features = 8    
        
        # --- Naya: InfluxDB Configuration ---
        self.influx_url = os.environ.get("INFLUX_URL", "http://localhost:8086")
        self.influx_token = os.environ.get("INFLUX_TOKEN", "")
        self.influx_org = os.environ.get("INFLUX_ORG", "solar_shield_org")
        self.influx_bucket = os.environ.get("INFLUX_BUCKET", "solar_shield_telemetry")
        
        if not self.influx_token:
            raise ValueError("Set INFLUX_TOKEN in the environment")
        logging.info("Initializing InfluxDB Client...")
        self.influx_client = InfluxDBClient(url=self.influx_url, token=self.influx_token, org=self.influx_org)
        self.write_api = self.influx_client.write_api(write_options=SYNCHRONOUS)

        # 2. State Management (The Rolling Buffer)
        self.buffer = deque(maxlen=self.window_size)
        
        # 3. Load Global Scaler
        logging.info("Loading Data Scaler...")
        try:
            self.scaler = joblib.load(args.scaler)
        except Exception as e:
            logging.error(f"Failed to load 'scaler.pkl'. Error: {e}")
            exit(1)

        # 4. Load ML Model
        logging.info("Initializing SOC AI Engine: Loading LSTM Autoencoder...")
        try:
            self.model = tf.keras.models.load_model(args.model, compile=False) 
            logging.info("Model loaded successfully. Engine ready.")
        except Exception as e:
            logging.error(f"Failed to load model. Ensure 'solar_shield.keras' is present. Error: {e}")
            exit(1)

        # 5. MQTT Client Setup
        self.client = mqtt.Client(CallbackAPIVersion.VERSION2)
        self.port = args.port
        username = os.environ.get("MQTT_USERNAME")
        password = os.environ.get("MQTT_PASSWORD")
        if not username or not password:
            raise ValueError("Set MQTT_USERNAME and MQTT_PASSWORD")
        self.client.username_pw_set(username=username, password=password)
        if args.ca_cert:
            self.client.tls_set(ca_certs=args.ca_cert)
        elif not args.allow_insecure_lab:
            raise ValueError("Use --ca-cert for TLS or explicitly opt into --allow-insecure-lab")
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message

    def on_connect(self, client, userdata, flags, rc, properties=None):
        if rc == 0:
            logging.info(f"Connected to Mosquitto broker at {self.broker}")
            self.client.subscribe(self.topic, qos=1)
            logging.info(f"Actively monitoring telemetry on topic: {self.topic}")
        else:
            logging.error(f"Broker connection failed with return code {rc}")

    def on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode())
            
            # Extract exactly the 8 features the model was trained on
            features = extract_features(payload)
            
            self.buffer.append(features)

            # Trigger on 20 records; timing depends on publisher delivery cadence
            if len(self.buffer) == self.window_size:
                self.run_inference(payload) # Payload pass kiya taake InfluxDB mein bheja ja sake

        except json.JSONDecodeError:
            logging.warning("Received malformed JSON payload. Dropping packet.")
        except Exception as e:
            logging.error(f"Unexpected error processing telemetry: {e}")

    def run_inference(self, payload):
        window_data = np.array(self.buffer)

        # --- Apply Saved Scaler ---
        scaled_window = self.scaler.transform(window_data)
        input_tensor = np.expand_dims(scaled_window, axis=0)

        # --- Inference ---
        reconstructed = self.model.predict(input_tensor, verbose=0)

        # --- Reconstruction Error (MSE) Calculation ---
        if reconstructed.shape != input_tensor.shape or not np.isfinite(reconstructed).all():
            raise ValueError("Invalid model reconstruction shape or non-finite values")
        mse = float(np.mean(np.square(input_tensor - reconstructed)))
        if not np.isfinite(mse):
            raise ValueError("Invalid model reconstruction shape or non-finite error")
        is_anomaly = bool(mse > self.threshold)

        # --- SOC Alerting Logic ---
        if is_anomaly:
            print(f"\n[ANOMALY — TRIAGE REQUIRED] Deviation Detected - MSE: {mse:.4f}\n")
            
        # --- Naya: Write to InfluxDB ---
        try:
            point = (
                Point("inverter_telemetry")
                .tag("sensor_id", "inverter_01")
                .field("DC_voltage", float(payload.get("DC_voltage", 0.0)))
                .field("DC_current", float(payload.get("DC_current", 0.0)))
                .field("AC_voltage", float(payload.get("AC_voltage", 0.0)))
                .field("AC_frequency", float(payload.get("AC_frequency", 0.0)))
                .field("output_power", float(payload.get("output_power", 0.0)))
                .field("power_factor", float(payload.get("power_factor", 0.0)))
                .field("inverter_temperature", float(payload.get("inverter_temperature", 0.0)))
                .field("irradiance", float(payload.get("irradiance", 0.0)))
                .field("mse", mse)
                .field("threshold", float(self.threshold))
                .field("is_anomaly", is_anomaly)
            )
            self.write_api.write(bucket=self.influx_bucket, org=self.influx_org, record=point)
        except Exception as e:
            logging.error(f"Failed to write to InfluxDB: {e}")

    def start_monitoring(self):
        try:
            self.client.connect(self.broker, self.port, 60)
            self.client.loop_start()
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logging.info("SOC Analyst initiated shutdown. Stopping R-TADS...")
        finally:
            self.client.loop_stop()
            self.client.disconnect()
            self.influx_client.close() # InfluxDB client safely close karna
            logging.info("Disconnected from broker safely.")

def parse_args():
    base = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description="Solar Shield telemetry inference (research prototype)")
    parser.add_argument("--model", type=Path, default=base / "models/solar_shield.keras")
    parser.add_argument("--scaler", type=Path, default=base / "scaler.pkl")
    parser.add_argument("--broker", default=os.environ.get("MQTT_HOST", "localhost"))
    parser.add_argument("--port", type=int, default=8883)
    parser.add_argument("--topic", default="solarshield/telemetry/inverter1")
    parser.add_argument("--threshold", type=float, required=True, help="Threshold calibrated on held-out normal data")
    parser.add_argument("--ca-cert", help="Trusted MQTT broker CA certificate")
    parser.add_argument("--allow-insecure-lab", action="store_true", help="Permit plaintext MQTT only in an isolated lab")
    args = parser.parse_args()
    if not np.isfinite(args.threshold) or args.threshold < 0:
        parser.error("threshold must be finite and nonnegative")
    for path in (args.model, args.scaler):
        if not path.is_file():
            parser.error(f"Missing artifact: {path}. Restore the original training-compatible model/scaler pair; do not fit a replacement on evaluation data.")
    return args

if __name__ == "__main__":
    detector = SolarShieldRTADS(parse_args())
    detector.start_monitoring()
