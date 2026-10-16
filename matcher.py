"""Shared OUI matching for the BLE and Wi-Fi scan paths.

The tables in lizt.py mix upper and lower case, and the two platform APIs
disagree as well: Android's ScanResult.BSSID comes back lower case while
BluetoothDevice.getAddress() comes back upper. A case-sensitive dict lookup
therefore misses most of hWifi on Android. Everything is folded to lower case
here so a match never depends on which side produced the address.
"""

from lizt import haters, hWifi

BLE = "BT"
WIFI = "WiFi"

_TABLES = {
    BLE: {k.lower(): v for k, v in haters.items()},
    WIFI: {k.lower(): v for k, v in hWifi.items()},
}

_HEX = set("0123456789abcdef")


def normalize(mac):
    """Return a lower-case colon-separated MAC, or None if it isn't one."""
    if not mac:
        return None
    cleaned = str(mac).strip().lower().replace("-", ":")
    octets = cleaned.split(":")
    if len(octets) != 6:
        return None
    if not all(len(o) == 2 and o[0] in _HEX and o[1] in _HEX for o in octets):
        return None
    return ":".join(octets)


def classify(mac, kind):
    """Vendor name for a MAC's OUI, or None when the prefix isn't in the list."""
    normalized = normalize(mac)
    if normalized is None:
        return None
    return _TABLES[kind].get(normalized[:8])
