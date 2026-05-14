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
from influxdb_client.client.write_api import ASYNCHRONOUS, SYNCHRONOUS

# Configure production-grade logging for the SOC console
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - [R-TADS] - %(levelname)s - %(message)s'
)

class SolarShieldRTADS:
    """
    Real-Time Anomaly Detection System for Solar Shield.
    Fully synchronized with LSTM Autoencoder (8 features, window=20).
    """
    def __init__(self, broker="localhost", topic="solarshield/telemetry/inverter1"):
        # 1. System Configuration
        self.broker = broker
        self.topic = topic
        self.threshold = 0.12 
        self.window_size = 20  
        self.n_features = 8    
        
        # --- Naya: InfluxDB Configuration ---
        self.influx_url = "http://localhost:8086"
        self.influx_token = "7tYbOsJdvsJSLGM10MPi4bujCSuumXc3Qw1mh1qXlU2423Br9TgQy0KSQRHNgnLUtXgbJAQi5xLz8RDyA9UeAQ==" # <-- Yahan apna API Token dalein
        self.influx_org = "solar_shield_org"
        self.influx_bucket = "solar_shield_telemetry"
        
        logging.info("Initializing InfluxDB Client...")
        self.influx_client = InfluxDBClient(url=self.influx_url, token=self.influx_token, org=self.influx_org)
        self.write_api = self.influx_client.write_api(write_options=SYNCHRONOUS)

        # 2. State Management (The Rolling Buffer)
        self.buffer = deque(maxlen=self.window_size)
        
        # 3. Load Global Scaler
        logging.info("Loading Data Scaler...")
        try:
            self.scaler = joblib.load("scaler.pkl")
        except Exception as e:
            logging.error(f"Failed to load 'scaler.pkl'. Error: {e}")
            exit(1)

        # 4. Load ML Model
        logging.info("Initializing SOC AI Engine: Loading LSTM Autoencoder...")
        try:
            self.model = tf.keras.models.load_model("solar_shield.keras") 
            logging.info("Model loaded successfully. Engine ready.")
        except Exception as e:
            logging.error(f"Failed to load model. Ensure 'solar_shield.keras' is present. Error: {e}")
            exit(1)

        # 5. MQTT Client Setup
        self.client = mqtt.Client(CallbackAPIVersion.VERSION2)
        self.client.username_pw_set(username="esp32_client", password="solarshield")  
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message

    def on_connect(self, client, userdata, flags, rc, properties=None):
        if rc == 0:
            logging.info(f"Securely connected to Mosquitto broker at {self.broker}")
            self.client.subscribe(self.topic)
            logging.info(f"Actively monitoring telemetry on topic: {self.topic}")
        else:
            logging.error(f"Broker connection failed with return code {rc}")

    def on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode())
            
            # Extract exactly the 8 features the model was trained on
            features = [
                float(payload.get("DC_voltage", 0.0)),
                float(payload.get("DC_current", 0.0)),
                float(payload.get("AC_voltage", 0.0)),
                float(payload.get("AC_frequency", 0.0)),
                float(payload.get("output_power", 0.0)),
                float(payload.get("power_factor", 0.0)),
                float(payload.get("inverter_temperature", 0.0)),
                float(payload.get("irradiance", 0.0))
            ]
            
            self.buffer.append(features)

            # Only trigger inference if we have a full 20-second window
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
        mse = float(np.mean(np.square(input_tensor - reconstructed)))
        is_anomaly = bool(mse > self.threshold)

        # --- SOC Alerting Logic ---
        if is_anomaly:
            print(f"\n[CRITICAL THREAT] Anomaly Detected - MSE: {mse:.4f}\n")
            
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
                .field("is_anomaly", is_anomaly)
            )
            self.write_api.write(bucket=self.influx_bucket, org=self.influx_org, record=point)
        except Exception as e:
            logging.error(f"Failed to write to InfluxDB: {e}")

    def start_monitoring(self):
        try:
            self.client.connect(self.broker, 1883, 60)
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

if __name__ == "__main__":
    detector = SolarShieldRTADS(broker="X.X.X.X")
    detector.start_monitoring()
