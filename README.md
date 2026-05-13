# F1 2020 Keyboard Telemetry HUD

A real-time telemetry HUD for the **Ant Esports MK1300V2** RGB keyboard, built for **F1 2020**.

This project listens to F1 2020 UDP telemetry packets and maps live race data to per-key RGB lighting using Python and HID control.

## Features

- RPM bar displayed across mapped keyboard keys
- DRS status indicator on both Shift keys
- ERS battery level indicator
- Tire wear and damage indicators
- Safety car warning lights
- Low-latency UDP telemetry parsing
- Direct HID-based RGB control

## Technical Overview

The script listens on UDP port `20777`, parses F1 2020 telemetry packets, and updates selected keys on the Ant Esports MK1300V2 keyboard.

Tracked signals include:

- RPM percentage
- DRS availability and activation
- ERS deployment mode and battery level
- Tire wear
- Wing damage
- Safety car status

Keyboard: Ant Esports MK1300V2
VID: 0x36ae
PID: 0xfe9c

## Usage

Run the Python script and set the keyboard lighting mode to `Userlight` or `Custom` mode.

```bash
python Hud.py
