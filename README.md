# DreaScanner
**Drea Scanner — LARP Recon & Hacking Simulation Tool**

A tactical BLE device scanner designed for immersive Star Wars-themed live action role-play. DreaScanner simulates advanced recon and electronic warfare capabilities when deployed on DR-3A (a Raspberry Pi droid), enabling players to locate, track, and analyze wireless devices in real-time.

## Features

- **Real-time BLE Scanning** – Discover and monitor nearby Bluetooth Low Energy devices
- **RSSI Signal Visualization** – View signal strength as colored bars with percentage display
- **Tactical Locator Mode** – Target and track individual devices with live RSSI trends and distance estimation
- **Sortable Dashboard** – Organize devices by discovery order or proximity (closest first)
- **Device Filtering** – Hide/unhide devices to focus on new targets
- **CSV Logging** – Timestamped audit trail with automatic session numbering (prevents overwrites)
- **Responsive TUI** – Adaptive terminal layout optimized for mobile (Termux) and desktop deployment

## Usage

```bash
python3 DreaScan.py
```

### Commands
- **1-N** – Inspect device details
- **c** – Sort by signal strength (closest first)
- **d** – Reset to discovery order
- **l** – Enter tactical locator mode
- **h/uh** – Hide/unhide devices
- **s** – Show summary (all devices)
- **q** – Exit program (or exit locator if active)
- **?** – Show help

## Platform Support

- **Linux** (Termux on Android, BlueZ backend)
- **Windows** (via WinBLE)
- **macOS** (via Core Bluetooth)

## Deployment

Optimized for deployment on:
- **Raspberry Pi (DR-3A droid)** – Primary deployment platform
- **Android tablets via Termux** – Mobile reconnaissance

Real-time BLE scanning over 5-second cycles.

---

**⚠️ Hobby Use Only**  
This tool is designed for recreational LARP scenarios and hobby projects. Not intended for unauthorized device tracking or security vulnerabilities.

**Project Note**

This project was developed with AI-assisted code generation as part of a personal learning exercise. It is intended for educational and hobby use to explore BLE scanning, terminal UIs, and small tooling workflows.

**© Drea Corporation**

## Screenshots

Below are example screenshots showing the DreaScanner UI in typical states. To include these in the README, add the corresponding image files to `docs/screenshots/` (create the folder if it doesn't exist) and name them exactly as shown.

Note: images are displayed smaller for readability — adjust the `width` values if you prefer larger or smaller thumbnails.


1. Recent devices (known hidden)

<p align="center"><img src="docs/screenshots/50.png" alt="Recent devices (known hidden)" width="480"/></p>

2. Default dashboard view

<p align="center"><img src="docs/screenshots/33.png" alt="Default dashboard" width="480"/></p>

3. Device inspection (device #18)

<p align="center"><img src="docs/screenshots/51.png" alt="Device inspection #18" width="480"/></p>

4. Tactical locator approaching a TV

<p align="center"><img src="docs/screenshots/40.png" alt="Tactical locator approaching TV" width="480"/></p>

5. Sorted by closest-first view

<p align="center"><img src="docs/screenshots/18.png" alt="Closest-first view" width="480"/></p>
