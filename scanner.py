"""Async scan engine driving the BLE and Wi-Fi paths concurrently.

Differences from the original sniff() worth knowing:

* Every delay is an awaited asyncio.sleep. The original called time.sleep()
  inside the coroutine, which blocks the event loop -- on Android that reads as
  an unresponsive app and gets the process killed.
* Addresses come from device.address rather than a regex over str(device), so
  there is no unguarded match.group(1) to raise on nameless devices.
* The --timing cooldown is actually implemented. In the original it was parsed
  into `delay` and never read, so a device alerted once and then stayed silent
  forever because nothing ever left the `sed` dict.
"""

import asyncio
import time

from bleak import BleakScanner

from matcher import BLE, WIFI, classify, normalize

WIFI_POLL_INTERVAL = 3.0


class Engine:
    def __init__(self, store, notifier=None, wifi=None, cooldown_minutes=10,
                 suppress=(), watch=None, on_sighting=None, on_hit=None,
                 on_error=None):
        self._store = store
        self._notifier = notifier
        self._wifi = wifi
        self._cooldown = cooldown_minutes * 60
        self._suppress = {m for m in (normalize(s) for s in suppress) if m}
        self._watch = {
            normalize(k): v for k, v in (watch or {}).items() if normalize(k)
        }
        self._on_sighting = on_sighting
        self._on_hit = on_hit
        self._on_error = on_error
        self._last_alert = {}
        self._stop = asyncio.Event()

    def stop(self):
        self._stop.set()

    async def run(self):
        tasks = [asyncio.create_task(self._ble_loop())]
        if self._wifi is not None:
            tasks.append(asyncio.create_task(self._wifi_loop()))
        try:
            await asyncio.gather(*tasks)
        finally:
            for task in tasks:
                task.cancel()

    def _due_for_alert(self, mac):
        now = time.monotonic()
        last = self._last_alert.get(mac)
        if last is not None and now - last < self._cooldown:
            return False
        self._last_alert[mac] = now
        return True

    def _report(self, error):
        if self._on_error:
            self._on_error(str(error))

    def _handle(self, raw_mac, label, signal, kind):
        mac = normalize(raw_mac)
        if mac is None or mac in self._suppress:
            return

        vendor = self._watch.get(mac) or classify(mac, kind)

        if self._on_sighting:
            self._on_sighting(mac, label, signal, kind, vendor)

        if not vendor or not self._due_for_alert(mac):
            return

        try:
            self._store.add_sighting(mac, label, signal, kind)
            self._store.update_group(mac, is_ble=(kind == BLE))
        except Exception as exc:
            self._report(f"db: {exc}")

        if self._notifier:
            try:
                self._notifier.alert(vendor, mac, kind, signal)
            except Exception as exc:
                self._report(f"notify: {exc}")

        if self._on_hit:
            self._on_hit(mac, label, signal, kind, vendor)

    async def _ble_loop(self):
        while not self._stop.is_set():
            try:
                async with BleakScanner() as scanner:
                    async for device, ad in scanner.advertisement_data():
                        if self._stop.is_set():
                            break
                        name = ad.local_name or device.name
                        self._handle(device.address, name, ad.rssi, BLE)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                # Adapter off or permission denied. Back off and retry so the
                # Wi-Fi half keeps running and the app recovers on its own.
                self._report(f"ble: {exc}")
                await asyncio.sleep(5.0)

    async def _wifi_loop(self):
        while not self._stop.is_set():
            try:
                self._wifi.request_scan()
                for bssid, ssid, level in self._wifi.results():
                    self._handle(bssid, ssid, level, WIFI)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self._report(f"wifi: {exc}")
            await asyncio.sleep(WIFI_POLL_INTERVAL)
