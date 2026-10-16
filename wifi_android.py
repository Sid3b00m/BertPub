"""Wi-Fi scanning through Android's WifiManager.

pywifi cannot be used here. It drives either the Windows WLAN API or
wpa_supplicant's control socket, and on Android that socket is denied to
unprivileged apps by SELinux, so the platform API is the only route.

Android caps startScan() at four calls per two minutes for a foreground app
(ScanRequestProxy.SCAN_REQUEST_THROTTLE_MAX_IN_TIME_WINDOW_FG_APPS), which is
why scans are requested no more than once per SCAN_INTERVAL. Reading
getScanResults() is a cache read and is not throttled, so it is polled far more
often -- scans issued by other apps refresh that same cache, which frequently
yields fresher data than our own request cadence alone.
"""

import time

SCAN_INTERVAL = 30.0

try:
    from jnius import autoclass, cast

    _Context = autoclass("android.content.Context")
    _PythonActivity = autoclass("org.kivy.android.PythonActivity")
    AVAILABLE = True
except Exception:  # not running on Android
    AVAILABLE = False


class WifiScanner:
    """Returns (bssid, ssid, level) tuples from the platform scan cache."""

    def __init__(self):
        if not AVAILABLE:
            raise RuntimeError("WifiScanner requires Android")
        context = _PythonActivity.mActivity.getApplicationContext()
        self._manager = cast(
            "android.net.wifi.WifiManager",
            context.getSystemService(_Context.WIFI_SERVICE),
        )
        self._last_request = 0.0

    @property
    def enabled(self):
        try:
            return bool(self._manager.isWifiEnabled())
        except Exception:
            return False

    def request_scan(self):
        """Ask for a fresh scan if the throttle window allows it."""
        now = time.monotonic()
        if now - self._last_request < SCAN_INTERVAL:
            return False
        self._last_request = now
        try:
            return bool(self._manager.startScan())
        except Exception:
            # Throttled, Wi-Fi off, or permission revoked mid-run. The cached
            # results are still worth reading, so this is not fatal.
            return False

    def results(self):
        try:
            found = self._manager.getScanResults()
        except Exception:
            return []
        out = []
        for i in range(found.size()):
            entry = found.get(i)
            out.append((entry.BSSID, entry.SSID, entry.level))
        return out
