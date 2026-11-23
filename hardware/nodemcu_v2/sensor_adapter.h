#pragma once
#include <math.h>
// ESP8266 has ONE analog input. A0 is already used by the existing LDR.
// Implement with the team's actual external ADC/multiplexer or digital sensors.
// Do not connect a second analog sensor to A0 or invent a GPIO.
inline float readSoilMoisturePercent() { return NAN; }
// raw ADC * 60000/1023 is not a calibrated lux measurement.
inline float readCalibratedLightLux() { return NAN; }
