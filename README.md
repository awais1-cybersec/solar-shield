<div align="center">
 
  <img src="https://capsule-render.vercel.app/api?type=waving&color=0f172a&height=250&section=header&text=☀️%20SOLAR%20SHIELD&fontSize=60&fontColor=00F2FE&animation=fadeIn&desc=AI-Powered%20Real-Time%20Anomaly%20Detection&descSize=20&descColor=9ca3af&descAlign=50&descAlignY=65" alt="Solar Shield Header">
  
  <img src="https://readme-typing-svg.herokuapp.com?font=Courier+New&weight=600&size=18&pause=1000&color=00F2FE&center=true&vCenter=true&width=800&lines=Initializing+Master+Solar+Cycle...;LSTM+Autoencoder+Active...;Monitoring+ESP32-S3+Telemetry...;Defending+against+False+Data+Injection" alt="Typing Effect">
  <br><br>

  <!-- Tech Stack Badges -->
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python"></a>
  <a href="https://www.tensorflow.org/"><img src="https://img.shields.io/badge/TensorFlow-Keras-FF6F00?style=for-the-badge&logo=tensorflow&logoColor=white" alt="TensorFlow"></a>
  <a href="https://espressif.com/"><img src="https://img.shields.io/badge/Edge-ESP32--S3-E7352C?style=for-the-badge&logo=espressif&logoColor=white" alt="ESP32"></a>
  <a href="https://mosquitto.org/"><img src="https://img.shields.io/badge/MQTT-3C528?style=for-the-badge&logo=eclipse&logoColor=white" alt="MQTT"></a>
  <a href="https://grafana.com/"><img src="https://img.shields.io/badge/Grafana-Cloud-F46800?style=for-the-badge&logo=grafana&logoColor=white" alt="Grafana"></a>
  <a href="https://opensource.org/licenses/MIT"><img src="https://img.shields.io/badge/License-MIT-22c55e?style=for-the-badge" alt="MIT License"></a>

  <br><br>
  
</div>

---
> *Defending cyber-physical systems through predictive multivariate analysis and edge intelligence.*

---

## 🎥 Live Demonstration

Watch the Solar Shield in action. The video below demonstrates real-time MQTT attack injections (FDI, Volatility) and the immediate response of the LSTM Autoencoder triggering the SOC dashboard from **SYSTEM NORMAL** to **THREAT DETECTED**.

https://github.com/user-attachments/assets/e5c0492c-c9f8-4e50-8ca1-4f84070c6a7d

---

## 🌟 Key Features

* **🧠 AI-Driven Detection:** Utilizes a custom Long Short-Term Memory (LSTM) Autoencoder to identify complex, nonlinear deviations in telemetry data.
* **⚡ Real-Time Monitoring:** Sub-second inference pipeline designed specifically for SOC (Security Operations Center) environments and Blue Team monitoring.
* **⚔️ Red Team Validation:** Built-in simulated attack vectors to test detection efficacy against False Data Injection, replay, and hardware tampering.
* **🔗 Physics-Informed Logic:** Validates data against a "Master Solar Cycle" to ensure sensor readings adhere to real-world thermodynamic and electrical laws.

---

## 🏗️ High-Level System Architecture


<img width="996" height="660" alt="image" src="https://github.com/user-attachments/assets/d21613da-a44f-4a79-b9dc-f6893fbd0756" />


The architecture is divided into three distinct layers, ensuring physical segmentation and secure telemetry transport from the edge to the SOC dashboard.

---

## 🛠️ Tech Stack

| Layer | Technologies Used | Description |
| --- | --- | --- |
| **Edge Layer** | C++, ESP32-S3 | Simulates physical solar inverter hardware and telemetry generation. |
| **Transport Layer** | Eclipse Mosquitto, MQTT | Secure message brokering deployed on an Ubuntu 24.04.4 LTS Gateway. |
| **AI Engine** | Python, TensorFlow/Keras | Real-Time Anomaly Detection System (R-TADS) script executing `solar_shield.keras`. |
| **Data & Visibility** | InfluxDB, Grafana | Time-series storage and real-time SOC dashboarding for Blue Team triage. |

---

## ⚙️ How It Works: Multivariate Correlation

Solar Shield operates on the premise that a sophisticated cyber-physical attack will likely break the underlying physical correlations between variables, even if individual metrics remain within "normal" thresholds.

The ESP32-S3 edge device generates an **8-feature multivariate dataset** (including Voltage, Current, Irradiance, Temperature, etc.) governed by a programmatic **Master Solar Cycle**. This cycle guarantees that when Irradiance peaks, Voltage and Current exhibit appropriate, proportional responses based on simulated photovoltaic physics.

Instead of relying on static thresholds, the R-TADS Python script feeds this telemetry into the pre-trained **LSTM Autoencoder**. The model attempts to compress and reconstruct the time-series sequence. Because it was trained exclusively on benign, physically accurate data, any deviation from the Master Solar Cycle (e.g., high current during zero irradiance) results in a high reconstruction error, flagging an anomaly.

---

## 🚀 Installation & Setup Guide

### Prerequisites

* Ubuntu 24.04.4 LTS environment (Gateway/Host).
* ESP32-S3 Microcontroller.
* Python 3.10+ installed.

### Step 1: Transport Layer (MQTT Broker)

Deploy the Mosquitto broker to handle edge communications.

```bash
sudo apt update
sudo apt install mosquitto mosquitto-clients
sudo systemctl enable mosquitto
sudo systemctl start mosquitto

```

### Step 2: Data Stack (InfluxDB & Grafana)

1. Install and start InfluxDB to capture time-series telemetry.
2. Install Grafana and import the `dashboards/SOC_Solar_Shield.json` template.
3. Connect Grafana to your InfluxDB instance via the Data Sources menu.

### Step 3: AI Engine (R-TADS)

Clone the repository and initialize the AI detection environment.

```bash
git clone https://github.com/awais1-cybersec/solar-shield.git
cd solar-shield/ai-engine
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 run_inference.py --model models/solar_shield.keras

```

### Step 4: Edge Layer (ESP32-S3)

Open the `Firmware` directory using PlatformIO or the Arduino IDE. Update the `simulation.ino` file with your MQTT Broker IP and flash the firmware to the ESP32-S3.

---

## 🎯 Red Team Validation Scenarios

To ensure the SOC dashboard and AI engine perform optimally under duress, the Edge firmware includes triggers for specific threat vectors:

1. **False Data Injection (FDI) via Drifting:** Simulates a compromised sensor gradually shifting voltage or frequency metrics. Traditional threshold alerts fail here, but the LSTM detects the breaking of the multivariate correlation.
2. **Replay Attacks (Stale Data):** An attacker intercepts and rebroadcasts previous legitimate network traffic (e.g., transmitting high-noon irradiance data at midnight). The temporal awareness of the LSTM model immediately flags the sequence irregularity.
3. **Volatility Attacks (Hardware Tampering):** Injects sudden, erratic spikes in current or temperature, simulating an adversary physically tampering with the inverter's electrical load.

---

## 📊 Performance: MSE Thresholding

Anomaly classification is determined dynamically using **Mean Squared Error (MSE)**.

The formula for the reconstruction error is evaluated continuously:
$MSE = \frac{1}{n} \sum_{i=1}^{n} (Y_i - \hat{Y_i})^2$

* **$Y_i$** = The actual observed telemetry value from the ESP32-S3.
* **$\hat{Y_i}$** = The value reconstructed by the LSTM Autoencoder.

During normal operation, the MSE hovers below a calculated `MAX_NORMAL_MSE` threshold. When an attack scenario (like FDI or a Replay attack) occurs, the model fails to reconstruct the malicious pattern, causing the MSE to spike exponentially. The Grafana SOC dashboard tracks this MSE value in real-time, instantly shifting from a green status to critical red when the threshold is breached, enabling rapid Blue Team response.

---

## 🤝 Credits & License

**TEAM MEMBERS:** Muhammad Awais Asgher, Muhammad Ahmed, Mohammad Huzaifa Asim

**Supervised By:** Dr.Amna Iqbal (Assistant_Professor@RiphahInternationalUniversity)

**Project Scope:** Capstone / Independent Security Research

**License:** This project is licensed under the MIT License - see the [LICENSE]() file for details.
