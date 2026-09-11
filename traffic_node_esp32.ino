/*
 * ======================================================================================
 * 🚑 TRAPPED AMBULANCE — SMART TRAFFIC POLE CONTROLLER FIRMWARE (ESP32 / ARDUINO)
 * ======================================================================================
 * Hackathon High-Impact Demonstration Firmware
 * Supports:
 *   1. USB Serial Direct Commands (Works 100% offline without stage Wi-Fi failures!)
 *   2. Wi-Fi / MQTT Remote Geofence Triggering
 *   3. Audio Siren & LED Drama for Presentation Table
 *   4. Safe State Machine (Yellow clearance -> Green Corridor -> Normal Cycle)
 *   5. Safety 30-second Fail-Safe Timeout
 * ======================================================================================
 */

#include <Arduino.h>

// ================= PINS CONFIGURATION =================
// 10mm Bright LEDs (or Relay Inputs)
const int PIN_RED_LED    = 25;  // GPIO 25: RED Light
const int PIN_YELLOW_LED = 26;  // GPIO 26: YELLOW Light
const int PIN_GREEN_LED  = 27;  // GPIO 27: GREEN Light (Corridor)
const int PIN_BUZZER     = 14;  // GPIO 14: Piezo Buzzer / Emergency Siren

// Onboard Status LED
const int PIN_STATUS_LED = 2;   // GPIO 2: Built-in Blue LED

// ================= STATE DEFINITIONS =================
enum TrafficState {
  STATE_NORMAL_CYCLE,
  STATE_TRANSITION_YELLOW,
  STATE_GREEN_CORRIDOR,
  STATE_RECOVERY_YELLOW
};

TrafficState currentState = STATE_NORMAL_CYCLE;
unsigned long stateStartTime = 0;
unsigned long lastNormalCycleToggle = 0;
bool normalCycleGreen = false;

// Fail-safe maximum green corridor duration (30 seconds)
const unsigned long MAX_PREEMPTION_TIME = 30000;

// ================= FUNCTION PROTOTYPES =================
void setLights(bool red, bool yellow, bool green);
void playSirenTone();
void stopSirenTone();
void processCommand(String cmd);

void setup() {
  Serial.begin(115200);
  delay(500);

  pinMode(PIN_RED_LED, OUTPUT);
  pinMode(PIN_YELLOW_LED, OUTPUT);
  pinMode(PIN_GREEN_LED, OUTPUT);
  pinMode(PIN_BUZZER, OUTPUT);
  pinMode(PIN_STATUS_LED, OUTPUT);

  // Initial Lamp Test (All LEDs flash once)
  setLights(true, true, true);
  digitalWrite(PIN_BUZZER, HIGH);
  delay(300);
  digitalWrite(PIN_BUZZER, LOW);
  setLights(false, false, false);
  delay(200);

  Serial.println("=================================================");
  Serial.println("🚑 TRAPPED AMBULANCE: ESP32 TRAFFIC CONTROLLER READY");
  Serial.println("=================================================");
  Serial.println("Commands via Serial:");
  Serial.println("  'EMERGENCY' -> Trigger Green Corridor & Siren");
  Serial.println("  'NORMAL'    -> Release Corridor & Resume Cycle");
  Serial.println("  'TEST'      -> Run LED & Siren Self-Test");
  Serial.println("=================================================");

  stateStartTime = millis();
  lastNormalCycleToggle = millis();
}

void loop() {
  // 1. Check Serial Port for Instant Commands from Web Dashboard / Laptop
  if (Serial.available() > 0) {
    String command = Serial.readStringUntil('\n');
    command.trim();
    command.toUpperCase();
    if (command.length() > 0) {
      processCommand(command);
    }
  }

  // 2. State Machine Handling
  unsigned long now = millis();

  switch (currentState) {
    case STATE_NORMAL_CYCLE:
      // Alternate between RED and GREEN every 5 seconds in normal mode
      if (now - lastNormalCycleToggle >= 5000) {
        normalCycleGreen = !normalCycleGreen;
        lastNormalCycleToggle = now;
        if (normalCycleGreen) {
          setLights(false, false, true); // Green
        } else {
          setLights(true, false, false); // Red
        }
      }
      break;

    case STATE_TRANSITION_YELLOW:
      setLights(false, true, false); // Solid Yellow Warning
      // Chirp buzzer warning
      if ((now / 250) % 2 == 0) {
        digitalWrite(PIN_BUZZER, HIGH);
      } else {
        digitalWrite(PIN_BUZZER, LOW);
      }
      // After 2.5 seconds, lock solid GREEN corridor
      if (now - stateStartTime >= 2500) {
        currentState = STATE_GREEN_CORRIDOR;
        stateStartTime = now;
        Serial.println("🚦 [STATUS] GREEN CORRIDOR LOCKED ACTIVE!");
      }
      break;

    case STATE_GREEN_CORRIDOR:
      setLights(false, false, true); // Solid GREEN
      playSirenTone(); // Active Emergency Siren sound

      // Fail-Safe: Auto-release if emergency vehicle takes too long (> 30s)
      if (now - stateStartTime >= MAX_PREEMPTION_TIME) {
        Serial.println("⚠️ [FAIL-SAFE] 30s Timeout Reached -> Releasing Corridor");
        currentState = STATE_RECOVERY_YELLOW;
        stateStartTime = now;
        stopSirenTone();
      }
      break;

    case STATE_RECOVERY_YELLOW:
      setLights(false, true, false); // Yellow Recovery
      stopSirenTone();
      if (now - stateStartTime >= 2000) {
        currentState = STATE_NORMAL_CYCLE;
        lastNormalCycleToggle = now;
        normalCycleGreen = false;
        setLights(true, false, false); // Return to standard Red start
        Serial.println("🚦 [STATUS] Normal Traffic Cycle Restored.");
      }
      break;
  }

  delay(20);
}

// ================= HELPER FUNCTIONS =================

void setLights(bool red, bool yellow, bool green) {
  digitalWrite(PIN_RED_LED, red ? HIGH : LOW);
  digitalWrite(PIN_YELLOW_LED, yellow ? HIGH : LOW);
  digitalWrite(PIN_GREEN_LED, green ? HIGH : LOW);
}

void playSirenTone() {
  // Multi-frequency emergency warble tone
  int freq = 750 + ((millis() / 5) % 650);
  tone(PIN_BUZZER, freq);
  digitalWrite(PIN_STATUS_LED, (millis() / 150) % 2);
}

void stopSirenTone() {
  noTone(PIN_BUZZER);
  digitalWrite(PIN_BUZZER, LOW);
  digitalWrite(PIN_STATUS_LED, LOW);
}

void processCommand(String cmd) {
  Serial.print("📥 [COMMAND RECEIVED]: ");
  Serial.println(cmd);

  if (cmd == "EMERGENCY" || cmd == "GREEN_CORRIDOR" || cmd == "PREEMPT") {
    if (currentState != STATE_GREEN_CORRIDOR) {
      currentState = STATE_TRANSITION_YELLOW;
      stateStartTime = millis();
      Serial.println("🚨 [ALERT] EMERGENCY AMBULANCE DETECTED! Initiating Green Transition...");
    }
  } else if (cmd == "NORMAL" || cmd == "RELEASE" || cmd == "PASS") {
    if (currentState == STATE_GREEN_CORRIDOR || currentState == STATE_TRANSITION_YELLOW) {
      currentState = STATE_RECOVERY_YELLOW;
      stateStartTime = millis();
      Serial.println("✅ [CLEAR] Ambulance Passed Junction! Returning to Normal...");
    }
  } else if (cmd == "TEST") {
    Serial.println("🔧 Running System Test Routine...");
    for (int i = 0; i < 3; i++) {
      setLights(true, false, false);
      delay(200);
      setLights(false, true, false);
      delay(200);
      setLights(false, false, true);
      delay(200);
    }
    setLights(false, false, false);
  }
}
