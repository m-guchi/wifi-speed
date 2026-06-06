from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from typing import Optional


@dataclass
class WifiSignal:
    ssid: Optional[str]
    signal_dbm: Optional[int]
    link_quality: Optional[str]
    interface: Optional[str]


def collect_wifi_signal(interface: str = "wlan0") -> WifiSignal:
    """iwconfig から WiFi 信号強度を取得する。"""
    try:
        result = subprocess.run(
            ["iwconfig", interface],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return WifiSignal(None, None, None, interface)

    if result.returncode != 0:
        return WifiSignal(None, None, None, interface)

    output = result.stdout + result.stderr
    ssid = _extract_ssid(output)
    signal_dbm = _extract_signal_dbm(output)
    link_quality = _extract_link_quality(output)

    return WifiSignal(ssid, signal_dbm, link_quality, interface)


def _extract_ssid(text: str) -> Optional[str]:
    match = re.search(r'ESSID:"([^"]*)"', text)
    if match and match.group(1):
        return match.group(1)
    return None


def _extract_signal_dbm(text: str) -> Optional[int]:
    match = re.search(r"Signal level=(-?\d+)\s*dBm", text)
    if match:
        return int(match.group(1))
    return None


def _extract_link_quality(text: str) -> Optional[str]:
    match = re.search(r"Link Quality=(\S+)", text)
    if match:
        return match.group(1)
    return None
