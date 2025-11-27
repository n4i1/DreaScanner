# DR-3A Surveillance Grid
**Drea Corporation — LARP Recon & Hacking Simulation Tool**

A tactical BLE device scanner designed for immersive Star Wars-themed live action role-play. DR-3A simulates advanced recon and electronic warfare capabilities, enabling players to locate, track, and analyze wireless devices in real-time.

## Features

- **Real-time BLE Scanning** – Discover and monitor nearby Bluetooth Low Energy devices
- **RSSI Signal Visualization** – View signal strength as colored bars with percentage display
- **Tactical Locator Mode** – Target and track individual devices with live RSSI trends and distance estimation
- **Sortable Dashboard** – Organize devices by discovery order or proximity (closest first)
- **Device Filtering** – Hide/unhide devices to focus on new targets
- **CSV Logging** – Complete audit trail of all scanned devices and timestamps
- **Responsive TUI** – Adaptive terminal layout optimized for mobile (Termux) and desktop deployment

## Usage

```bash
python3 DreaScan03.py
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

Optimized for deployment on Android tablets via Termux with real-time BLE scanning over 5-second cycles.

---

**⚠️ Hobby Use Only**  
This tool is designed for recreational LARP scenarios and hobby projects. Not intended for unauthorized device tracking or security vulnerabilities.

**© Drea Corporation**
