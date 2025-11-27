#!/usr/bin/env python3
"""
DR-3A — Stable TUI for BLE Scanning with RSSI Bars
- Non-blinking, dashboard refresh 5s
- CSV logging
- RSSI bars visualized in gold
- Commands while running: hide / unhide, s / summary, q / quit, help
- Filter known devices to find new ones easily
"""

import os
import sys
import csv
import asyncio
import shutil
from datetime import datetime
from typing import Dict, Any
from bleak import BleakScanner

# ---------- Config ----------
LOG_FILE = "ble_scan_log.csv"
SCAN_TIMEOUT = 5.0        # seconds per BLE scan
TUI_REFRESH = 5.0         # seconds between dashboard refreshes
MIN_RSSI = -100
MAX_RSSI = -30
BAR_MAX_WIDTH_RATIO = 0.4
DEBUG = False             # Set to True to see raw device RSSI extraction
# ----------------------------

CSI = "\x1b["
RESET = CSI + "0m"
GOLD = CSI + "33;1m"

seen_devices: Dict[str, Dict[str, Any]] = {}
saved_devices: set = set()  # Addresses of devices to hide from view
device_index_map: Dict[int, str] = {}  # Maps display numbers to addresses
seen_lock = asyncio.Lock()
_running = True
_inspecting = False  # Flag to pause refresh while user reads device details
sort_type = "discovery"  # "discovery" (default order) or "signal" (closest first)
_locating = False  # Flag to enter locator mode
_locate_addr = None  # Target device address for locator
_locate_rssi_history = []  # Track RSSI history for trend detection

# ---------- Helpers ----------

def term_size():
    return shutil.get_terminal_size(fallback=(80, 24))

def now_iso():
    return datetime.now().strftime("%d/%m/%y %H:%M")

def append_csv(row: dict):
    try:
        file_exists = False
        try:
            with open(LOG_FILE, "r"):
                file_exists = True
        except FileNotFoundError:
            file_exists = False
        with open(LOG_FILE, "a", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=row.keys())
            if not file_exists:
                writer.writeheader()
            writer.writerow(row)
    except Exception as e:
        print(f"{CSI}31m[CSV ERROR] {e}{RESET}", file=sys.stderr)

def extract_rssi(d):
    # Try several common locations where different bleak backends expose RSSI
    # 1) direct attribute
    r = getattr(d, "rssi", None)
    if isinstance(r, int):
        return r

    # 2) metadata dict (some backends put rssi here)
    try:
        meta = getattr(d, "metadata", {}) or {}
        r = meta.get("rssi")
        if isinstance(r, int):
            return r
    except Exception:
        pass

    # 3) advertisement_data attached object (Bleak v0.20+ sometimes pairs device+advertisement)
    #    some platforms set `advertisement_data` with an .rssi attribute
    try:
        ad = getattr(d, "advertisement_data", None) or getattr(d, "advertisement", None)
        if ad is not None:
            r = getattr(ad, "rssi", None)
            if isinstance(r, int):
                return r
            # some backends use 'rssi' inside a dict-like object
            if hasattr(ad, "__dict__"):
                r = ad.__dict__.get("rssi")
                if isinstance(r, int):
                    return r
    except Exception:
        pass

    # 3b) BlueZ via bleak on Linux often attaches a 'details' dict with 'props' containing 'RSSI'
    try:
        details = getattr(d, 'details', None)
        if isinstance(details, dict):
            props = details.get('props', {}) or {}
            # BlueZ uses 'RSSI' capitalized in props
            r = props.get('RSSI') if 'RSSI' in props else props.get('rssi')
            if isinstance(r, int):
                return r
    except Exception:
        pass

    # 4) sometimes the device object has other fields; if DEBUG, show them for troubleshooting
    if DEBUG:
        try:
            details = getattr(d, 'details', None)
            # Safe repr truncated
            try:
                details_repr = repr(details)
            except Exception:
                details_repr = f"<unrepr-able {type(details)}>"
            if len(details_repr) > 300:
                details_repr = details_repr[:300] + '...'

            info = {
                'address': getattr(d, 'address', None),
                'name': getattr(d, 'name', None),
                'details_type': type(details).__name__,
                'details_repr': details_repr,
                'attrs': [a for a in dir(d) if not a.startswith('__')][:50]
            }
        except Exception:
            info = {'repr': repr(d)}
        print(f"[DEBUG extract_rssi] Couldn't find RSSI for device: {info}", file=sys.stderr)

    return None

def clamp(v, low, high):
    return max(low, min(high, v))

def rssi_to_percentage(rssi):
    """Convert RSSI (dBm) to signal strength 0-100%."""
    if rssi is None:
        return 0
    r = clamp(rssi, MIN_RSSI, MAX_RSSI)
    percentage = int(((r - MIN_RSSI) / (MAX_RSSI - MIN_RSSI)) * 100)
    return clamp(percentage, 0, 100)

def rssi_to_distance_estimate(rssi):
    """Rough distance estimate in meters based on RSSI (rule of thumb: ~1.5m per 10dBm)."""
    if rssi is None:
        return "??"
    # Empirical: -42 ~ 0m, -58 ~ 2.5m, -90 ~ 10m+
    if rssi >= -42:
        return "<0.5m"
    elif rssi >= -52:
        return "0.5-1.5m"
    elif rssi >= -62:
        return "1.5-3m"
    elif rssi >= -75:
        return "3-6m"
    else:
        return "6m+"

def get_trend_symbol(rssi_history):
    """Detect if RSSI is improving (getting closer) or worsening."""
    if len(rssi_history) < 2:
        return "→ STABLE"
    recent = [r for r in rssi_history[-5:] if r is not None]
    if len(recent) < 2:
        return "→ STABLE"
    if recent[-1] > recent[0]:  # Higher dBm = stronger = closer
        return "↗ IMPROVING"
    elif recent[-1] < recent[0]:
        return "↘ WORSENING"
    else:
        return "→ STABLE"

def render_locator_tactical(device_name, rssi, distance, trend, scan_progress):
    """Render Andor-style tactical grid for locator mode."""
    os.system("clear")
    columns = term_size().columns
    
    # Header
    header = " ◆ TACTICAL LOCATOR ◆ "
    print(GOLD + header.center(columns, "=") + RESET)
    print(GOLD + f"TARGET: {device_name}".ljust(columns) + RESET)
    print("=" * columns)
    
    # Signal strength bar
    percentage = rssi_to_percentage(rssi)
    bar_width = int(columns * 0.6)
    bar_colored, filled_len = rssi_to_bar(rssi, bar_width)
    padding = bar_width - filled_len
    bar_field = (bar_colored if filled_len > 0 else '') + (" " * max(0, padding))
    
    print(f"SIGNAL: {bar_field} {percentage:>3}%")
    print(f"RSSI:   {rssi if rssi else 'N/A':>5} dBm")
    print(f"DISTANCE: {distance}")
    print("-" * columns)
    
    # Scan activity indicator
    scan_bar = "▓" * scan_progress + "░" * (20 - scan_progress)
    print(f"SCAN: [{scan_bar}] {scan_progress*5}%")
    
    # Movement status
    print(f"MOVEMENT: {trend}")
    print("-" * columns)
    
    # Tactical info box
    print(GOLD + "NAVIGATION".center(columns, "-") + RESET)
    print("  [1] Continue tracking")
    print("  [q] Exit locator mode")
    print(GOLD + "-" * columns + RESET)

def rssi_to_bar(rssi, max_width):
    # Return a tuple: (colored_bar_string, visible_filled_length)
    if rssi is None or max_width <= 0:
        return "", 0
    r = clamp(rssi, MIN_RSSI, MAX_RSSI)
    frac = (r - MIN_RSSI) / (MAX_RSSI - MIN_RSSI)
    filled_len = int(frac * max_width)
    bar_plain = "█" * filled_len
    bar_colored = GOLD + bar_plain + RESET if filled_len > 0 else ""
    return bar_colored, filled_len

# ---------- Dashboard ----------


# FIKSAA LEVEYS! Numerot vie rivityksen pieleen! 


def render_dashboard(devices):
    os.system("clear")
    columns = term_size().columns
    header = " DR-3A SURVEILLANCE GRID "
    print(GOLD + header.center(columns, "=") + RESET)
    
    # Filter out saved devices and create indexed list
    visible_devices = {addr: info for addr, info in devices.items() if addr not in saved_devices}
    
    # Store the indexed mapping globally for selection
    global device_index_map
    device_index_map = {}
    
    print(f"Active Devices: {len(visible_devices)} | Hidden: {len(saved_devices)}")
    print("=" * columns)

    if not visible_devices:
        print("No devices detected...\n")
        return
    # Compute dynamic column widths so the table fits the terminal width.
    count = max(1, len(visible_devices))
    idx_col = max(3, len(str(count)) + 2)  # space for numbers + padding
    rssi_col = 5
    signal_col = 15  # Widened signal column (bar + %)
    last_seen_col = 16

    # Initial bar width proposal, then adapt to remaining space
    proposed_bar = int(signal_col * 0.6)

    # Available width for name column = remaining after other columns and separators
    # There are 4 separators (spaces) between columns in the printed line (removed Address)
    separators = 4
    name_col = columns - (idx_col + rssi_col + signal_col + last_seen_col + separators)
    name_col = max(8, min(30, name_col))

    # Recompute bar width based on the finalized columns
    bar_width = int(signal_col * 0.6)

    print(f"{('#'):<{idx_col}} {'Name':{name_col}} {'RSSI':>{rssi_col}} {'Signal':{signal_col}} {'Last Seen':{last_seen_col}}")
    print("-" * columns)

    # Sort devices based on sort_type
    if sort_type == "signal":
        sorted_devices = sorted(visible_devices.items(), key=lambda x: x[1].get('last_rssi') or -100, reverse=True)
    else:  # discovery order (default)
        sorted_devices = visible_devices.items()

    for idx, (addr, info) in enumerate(sorted_devices, 1):
        device_index_map[idx] = addr
        name = info.get('name', 'Unknown')
        rssi = info.get('last_rssi', None)
        last_seen = info.get('last_seen', '--')
        bar_colored, filled_len = rssi_to_bar(rssi, bar_width)
        rssi_text = str(rssi) if rssi is not None else "---"
        percentage = rssi_to_percentage(rssi)

        # Build bar field: colored blocks plus padding spaces (padding counts visible chars)
        if bar_width > 0:
            padding = bar_width - filled_len
            bar_field = (bar_colored if filled_len > 0 else '') + (" " * max(0, padding))
        else:
            bar_field = ''

        # Append percentage label to bar field
        signal_display = f"{bar_field}{percentage:>3}%"

        name_display = (name[:name_col]) if len(name) > name_col else name
        print(f"{idx:<{idx_col}} {name_display:{name_col}} {rssi_text:>{rssi_col}} {signal_display:{signal_col}} {last_seen}")

    print("=" * columns)
    print("Commands: [1-N] inspect, h/hide, uh/unhide, s/summary, q/quit, ?/help")

# ---------- Scanner Task ----------

async def scanner_task():
    global _running
    while _running:
        try:
            devices = await BleakScanner.discover(timeout=SCAN_TIMEOUT)
        except Exception as e:
            print(f"{CSI}31m[BLE ERROR] discover() failed: {e}{RESET}", file=sys.stderr)
            devices = []

        now = now_iso()
        async with seen_lock:
            for d in devices:
                addr = d.address
                rssi = extract_rssi(d)
                if DEBUG and rssi is None:
                    print(f"[FIRST SCAN] {d.address} {d.name} - RSSI extracted as None", file=sys.stderr)
                info = seen_devices.get(addr)
                if not info:
                    info = {
                        "name": d.name or "Unknown",
                        "first_seen": now,
                        "last_seen": now,
                        "first_rssi": rssi,
                        "last_rssi": rssi,
                        "count": 1,
                    }
                else:
                    info["name"] = d.name or info.get("name", "Unknown")
                    info["last_seen"] = now
                    info["last_rssi"] = rssi
                    info["count"] = info.get("count", 0) + 1

                seen_devices[addr] = info

                # CSV log
                row = {
                    "timestamp": now,
                    "address": addr,
                    "name": d.name or "Unknown",
                    "rssi": rssi if rssi is not None else "",
                }
                append_csv(row)

        # Skip dashboard refresh if user is locating or inspecting a device
        if _locating and _locate_addr:
            # Locator mode: update tactical display
            info = seen_devices.get(_locate_addr)
            if info:
                rssi = info.get('last_rssi')
                if rssi is not None:
                    _locate_rssi_history.append(rssi)
                    if len(_locate_rssi_history) > 10:
                        _locate_rssi_history.pop(0)
                
                distance = rssi_to_distance_estimate(rssi)
                trend = get_trend_symbol(_locate_rssi_history)
                # Scan progress is cyclical 0-20
                scan_progress = (int(__import__('time').time() * 5) % 20)
                render_locator_tactical(info.get('name', 'Unknown'), rssi, distance, trend, scan_progress)
        elif not _inspecting:
            render_dashboard(seen_devices)
        await asyncio.sleep(TUI_REFRESH)

# ---------- Input Listener ----------

async def input_listener():
    global _running
    while _running:
        try:
            cmd = await asyncio.to_thread(input, "")
        except Exception:
            cmd = ""
        cmd = (cmd or "").strip().lower()

        async with seen_lock:
            # Check if command is a number (device selection)
            if cmd.isdigit():
                device_num = int(cmd)
                if device_num in device_index_map:
                    addr = device_index_map[device_num]
                    info = seen_devices.get(addr)
                    if info:
                        global _inspecting
                        _inspecting = True
                        print(GOLD + f"\n=== Device #{device_num} Details ===" + RESET, file=sys.stderr)
                        print(f"Name:        {info.get('name', 'Unknown')}", file=sys.stderr)
                        print(f"Address:     {addr}", file=sys.stderr)
                        print(f"First Seen:  {info.get('first_seen', 'N/A')}", file=sys.stderr)
                        print(f"Last Seen:   {info.get('last_seen', 'N/A')}", file=sys.stderr)
                        print(f"First RSSI:  {info.get('first_rssi', 'N/A')}", file=sys.stderr)
                        print(f"Last RSSI:   {info.get('last_rssi', 'N/A')}", file=sys.stderr)
                        print(f"Scan Count:  {info.get('count', 0)}", file=sys.stderr)
                        print(GOLD + "======================" + RESET, file=sys.stderr)
                        print(GOLD + "(Press Enter to resume dashboard)" + RESET, file=sys.stderr)
                        await asyncio.to_thread(input, "")
                        _inspecting = False
                else:
                    print(GOLD + f"\n[DR-3A] Device #{device_num} not found.\n" + RESET, file=sys.stderr)
            elif cmd in ("s", "summary"):
                print(GOLD + "\n=== DR-3A Summary ===" + RESET, file=sys.stderr)
                for addr, info in seen_devices.items():
                    hidden = " [HIDDEN]" if addr in saved_devices else ""
                    print(f"{info.get('name','Unknown')} ({addr}) | last_rssi={info.get('last_rssi')} | last_seen={info.get('last_seen')}{hidden}", file=sys.stderr)
                print(GOLD + "=== end summary ===\n" + RESET, file=sys.stderr)
            elif cmd in ("h", "hide"):
                # Hide all currently visible devices
                visible_addrs = [addr for addr in seen_devices.keys() if addr not in saved_devices]
                saved_devices.update(visible_addrs)
                print(GOLD + f"\n[DR-3A] Hidden {len(visible_addrs)} devices from view." + RESET, file=sys.stderr)
            elif cmd in ("uh", "unhide"):
                # Clear the saved devices list
                count = len(saved_devices)
                saved_devices.clear()
                print(GOLD + f"\n[DR-3A] Unhidden {count} devices. All devices now visible." + RESET, file=sys.stderr)
            elif cmd in ("sort", "c", "closest"):
                global sort_type
                sort_type = "signal"
                print(GOLD + f"\n[DR-3A] Sorting by signal strength (closest first)." + RESET, file=sys.stderr)
            elif cmd in ("d", "default"):
                sort_type = "discovery"
                print(GOLD + f"\n[DR-3A] Reset to discovery order." + RESET, file=sys.stderr)
            elif cmd in ("l", "locate"):
                # Locator mode: select target device
                print(GOLD + "\n[DR-3A] Enter target device number (1-N) to locate: " + RESET, file=sys.stderr, end="")
                try:
                    target_str = await asyncio.to_thread(input, "")
                    target_num = int(target_str.strip())
                    if target_num in device_index_map:
                        global _locating, _locate_addr, _locate_rssi_history
                        _locate_addr = device_index_map[target_num]
                        _locate_rssi_history = []
                        _locating = True
                        print(GOLD + f"\n[DR-3A] Locator activated. Press 'q' to exit.\n" + RESET, file=sys.stderr)
                    else:
                        print(GOLD + f"\n[DR-3A] Device #{target_num} not found.\n" + RESET, file=sys.stderr)
                except (ValueError, KeyError):
                    print(GOLD + "\n[DR-3A] Invalid input.\n" + RESET, file=sys.stderr)
            elif cmd in ("q", "quit", "exit"):
                if _locating:
                    # Exit locator mode, return to dashboard
                    _locating = False
                    _locate_addr = None
                    print(GOLD + f"\n[DR-3A] Locator mode deactivated. Returning to dashboard.\n" + RESET, file=sys.stderr)
                else:
                    # Exit program
                    _running = False
                    break
            elif cmd in ("?", "help"):
                print(GOLD + "\nCommands:" + RESET, file=sys.stderr)
                print("  1-N         - Inspect device details by number", file=sys.stderr)
                print("  h/hide      - Hide currently visible devices from display", file=sys.stderr)
                print("  uh/unhide   - Show all devices again (unhide all)", file=sys.stderr)
                print("  s/summary   - Show all devices including hidden ones", file=sys.stderr)
                print("  c/closest   - Sort by signal strength (closest first)", file=sys.stderr)
                print("  d/default   - Reset to discovery order", file=sys.stderr)
                print("  l/locate    - Enter tactical locator mode for target device", file=sys.stderr)
                print("  q/quit      - Exit the program", file=sys.stderr)
                print("  ?/help      - Show this help\n", file=sys.stderr)
            elif cmd == "":
                continue
            else:
                print(GOLD + f"[DR-3A] Unknown command: {cmd}. Type '?'." + RESET, file=sys.stderr)

# ---------- Cleanup ----------

def final_summary_and_cleanup():
    sys.stdout.write(CSI + "2J" + CSI + "H" + CSI + "?25h")
    sys.stdout.flush()
    print("\nDR-3A session terminated.")
    print("Seen devices summary:")
    for addr, info in seen_devices.items():
        hidden = " [HIDDEN]" if addr in saved_devices else ""
        print(f" {info.get('name','Unknown')} ({addr})  last_rssi={info.get('last_rssi')}  last_seen={info.get('last_seen')}{hidden}")
    print("\nLog saved to", LOG_FILE)

# ---------- Main ----------

async def main():
    tasks = [
        asyncio.create_task(scanner_task()),
        asyncio.create_task(input_listener()),
    ]
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    finally:
        _running = False
        final_summary_and_cleanup()
