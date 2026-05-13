#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h> // Ensure you are using ArduinoJson v7+

// ==========================================
// CONFIGURATION
// ==========================================
const char* ssid = "XXXXXXXX";
const char* password = "XXXXXXXX";

// MQTT Broker settings (Your Ubuntu Gateway)
const char* mqtt_server = "X.X.X.X";
const int mqtt_port = 1883; 
const char* mqtt_topic = "solarshield/telemetry/inverter1";
const char* command_topic = "solarshield/commands"; // Naya topic commands ke liye

const char* mqtt_user = "esp32_client"; 
const char* mqtt_password = "solarshield"; 

WiFiClient espClient; 
PubSubClient client(espClient);

unsigned long lastTelemetryTime = 0;
float time_counter = 0.0;
const unsigned long telemetryInterval = 1000; // 1 second

unsigned long lastReconnectAttempt = 0;
const unsigned long reconnectInterval = 5000; // 5 seconds

// ==========================================
// RED TEAM SIMULATION STATES
// ==========================================
enum AttackType { NORMAL, FDI, REPLAY, VOLATILITY };
AttackType currentAttack = NORMAL;
unsigned long attackStartTime = 0;
bool takeSnapshot = false;

// Variables to hold frozen data for REPLAY attack
float rep_irr, rep_dc_c, rep_dc_v, rep_temp, rep_ac_v, rep_ac_f;

// ==========================================
// HELPER FUNCTIONS
// ==========================================
float randomFloat(float min, float max) {
  return min + (float)random(10000) / 10000.0 * (max - min);
}

// MQTT Callback: Ubuntu terminal se attack commands sunne ke liye
void mqttCallback(char* topic, byte* payload, unsigned int length) {
  String message = "";
  for (int i = 0; i < length; i++) {
    message += (char)payload[i];
  }
  
  Serial.print("\n[!] RED TEAM COMMAND RECEIVED: ");
  Serial.println(message);

  if (message == "FDI") {
    currentAttack = FDI;
    attackStartTime = millis();
  } 
  else if (message == "REPLAY") {
    currentAttack = REPLAY;
    attackStartTime = millis();
    takeSnapshot = true; // Agle loop mein data freeze karne ka flag
  } 
  else if (message == "VOLATILITY") {
    currentAttack = VOLATILITY;
    attackStartTime = millis();
  } 
  else if (message == "NORMAL") {
    currentAttack = NORMAL;
  }
}

// Wi-Fi Setup
void setup_wifi() {
  Serial.println();
  Serial.print("Connecting to Wi-Fi: ");
  Serial.println(ssid);

  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);

  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 10) {
    delay(500); 
    Serial.print(".");
    attempts++;
  }
  
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\nWi-Fi connected.");
    Serial.print("IP address: ");
    Serial.println(WiFi.localIP());
  }
}

// MQTT Reconnect
boolean reconnect() {
  Serial.print("Attempting MQTT connection...");
  String clientId = "SolarShield-ESP32S3-";
  clientId += String(random(0xffff), HEX);

  if (client.connect(clientId.c_str(), mqtt_user, mqtt_password)) {
    Serial.println("connected");
    client.subscribe(command_topic); // Commands wale topic ko subscribe kiya
    return true;
  } else {
    Serial.print("failed, rc=");
    Serial.print(client.state());
    Serial.println(" - will try again in 5 seconds");
    return false;
  }
}

// Generate and Publish Telemetry
void publishTelemetry() {
  time_counter += 0.05; 
  unsigned long currentTime = millis();

  // 1. STANDARD BASELINE (Master Solar Cycle)
  float day_cycle = sin(time_counter * 0.05); 
  float normalized_cycle = (day_cycle + 1.0) / 2.0; 

  float irradiance = 100.0 + (normalized_cycle * 800.0) + randomFloat(-5.0, 5.0); 
  float dc_current = 1.0 + (normalized_cycle * 11.0) + randomFloat(-0.2, 0.2);    
  float dc_voltage = 500.0 + (normalized_cycle * 40.0) + randomFloat(-2.0, 2.0);  
  float inverter_temperature = 25.0 + (normalized_cycle * 20.0) + randomFloat(-0.5, 0.5); 
  
  float ac_voltage = 230.0 + randomFloat(-1.0, 1.0);
  float ac_frequency = 50.0 + randomFloat(-0.02, 0.02);
  float power_factor = 0.97 + randomFloat(-0.005, 0.005);

  // 2. RED TEAM PAYLOAD INJECTION
  float elapsedTime = (currentTime - attackStartTime) / 1000.0;

  switch (currentAttack) {
    case FDI:
      if (elapsedTime <= 15.0) { // 15-second slow drift attack
        dc_voltage += (elapsedTime * 3.0);   // Gradually increase voltage
        ac_frequency -= (elapsedTime * 0.1); // Gradually drop grid frequency
      } else {
        currentAttack = NORMAL; // Auto-stop after 15 secs
      }
      break;

    case REPLAY:
      if (takeSnapshot) {
        // Attack shuru hote hi ek dafa data ko lock kar do
        rep_irr = irradiance; rep_dc_c = dc_current; rep_dc_v = dc_voltage;
        rep_temp = inverter_temperature; rep_ac_v = ac_voltage; rep_ac_f = ac_frequency;
        takeSnapshot = false;
      }
      if (elapsedTime <= 30.0) { // Hold static data for 30 seconds
        irradiance = rep_irr; dc_current = rep_dc_c; dc_voltage = rep_dc_v;
        inverter_temperature = rep_temp; ac_voltage = rep_ac_v; ac_frequency = rep_ac_f;
      } else {
        currentAttack = NORMAL;
      }
      break;

    case VOLATILITY:
      // Alternate seconds par extreme hardware tampering spikes
      if ((currentTime / 1000) % 2 == 0) {
        dc_current *= 3.5; 
        power_factor = 0.45; 
      }
      break;
      
    case NORMAL:
    default:
      // Normal physics simulation continue rakhein
      break;
  }

  // 3. FINAL CALCULATIONS & JSON PUBLISH
  float output_power = (dc_voltage * dc_current / 1000.0) * 0.98;

  JsonDocument doc; 
  doc["timestamp_ms"] = currentTime;
  doc["DC_voltage"] = serialized(String(dc_voltage, 2));
  doc["DC_current"] = serialized(String(dc_current, 2));         
  doc["AC_voltage"] = serialized(String(ac_voltage, 2));     
  doc["AC_frequency"] = serialized(String(ac_frequency, 2)); 
  doc["output_power"] = serialized(String(output_power, 3)); 
  doc["power_factor"] = serialized(String(power_factor, 3));
  doc["inverter_temperature"] = serialized(String(inverter_temperature, 2)); 
  doc["irradiance"] = serialized(String(irradiance, 1)); 

  char jsonBuffer[256];
  serializeJson(doc, jsonBuffer);

  if (client.publish(mqtt_topic, jsonBuffer)) {
    Serial.print(currentAttack == NORMAL ? "Published [NORMAL]: " : "Published [ATTACK]: ");
    Serial.println(jsonBuffer);
  } else {
    Serial.println("Publish failed.");
  }
}

// ==========================================
// MAIN SETUP & LOOP
// ==========================================
void setup() {
  Serial.begin(115200);
  randomSeed(analogRead(0)); 
  
  setup_wifi();
  client.setServer(mqtt_server, mqtt_port);
  client.setCallback(mqttCallback); // Set up MQTT command listener
}

void loop() {
  unsigned long currentMillis = millis();

  if (WiFi.status() != WL_CONNECTED) {
    WiFi.disconnect();
    WiFi.reconnect();
  }

  if (WiFi.status() == WL_CONNECTED) {
    if (!client.connected()) {
      if (currentMillis - lastReconnectAttempt > reconnectInterval) {
        lastReconnectAttempt = currentMillis;
        if (reconnect()) {
          lastReconnectAttempt = 0; 
        }
      }
    } else {
      client.loop(); // Check for incoming commands

      if (currentMillis - lastTelemetryTime >= telemetryInterval) {
        lastTelemetryTime = currentMillis; 
        publishTelemetry();
      }
    }
  }
}
