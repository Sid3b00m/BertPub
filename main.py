"""BertAlert Android front end.

Replaces the original argparse + terminal interface: the -v/-q verbosity flags
become a toggle, -t becomes the cooldown field, and the scrolling print output
becomes two live lists.
"""

import asyncio
import threading
import time

from kivy.app import App
from kivy.clock import Clock, mainthread
from kivy.lang import Builder
from kivy.properties import BooleanProperty, StringProperty
from kivy.uix.boxlayout import BoxLayout

from scanner import Engine
from storage import Store

MAX_ROWS = 200

RUNTIME_PERMISSIONS = [
    "android.permission.ACCESS_FINE_LOCATION",
    "android.permission.ACCESS_COARSE_LOCATION",
    "android.permission.BLUETOOTH_SCAN",
    "android.permission.BLUETOOTH_CONNECT",
    "android.permission.POST_NOTIFICATIONS",
]

KV = """
<Root>:
    orientation: 'vertical'
    padding: dp(8)
    spacing: dp(6)

    Label:
        text: 'B E R T  A L E R T'
        font_size: '22sp'
        bold: True
        size_hint_y: None
        height: dp(38)

    Label:
        id: status
        text: root.status
        font_size: '13sp'
        size_hint_y: None
        height: dp(30)

    BoxLayout:
        size_hint_y: None
        height: dp(48)
        spacing: dp(6)

        Button:
            id: toggle
            text: 'Stop' if root.running else 'Start'
            on_release: root.toggle()

        Button:
            text: 'Verbose: on' if root.verbose else 'Verbose: off'
            on_release: root.verbose = not root.verbose

    Label:
        text: 'Hits'
        font_size: '14sp'
        bold: True
        size_hint_y: None
        height: dp(26)

    ScrollView:
        size_hint_y: 0.45
        Label:
            text: root.hits_text
            font_size: '12sp'
            halign: 'left'
            valign: 'top'
            text_size: self.width, None
            size_hint_y: None
            height: self.texture_size[1]

    Label:
        text: 'Seen'
        font_size: '14sp'
        bold: True
        size_hint_y: None
        height: dp(26)

    ScrollView:
        size_hint_y: 0.55
        Label:
            text: root.seen_text
            font_size: '11sp'
            halign: 'left'
            valign: 'top'
            text_size: self.width, None
            size_hint_y: None
            height: self.texture_size[1]
"""


class Root(BoxLayout):
    status = StringProperty("Idle")
    hits_text = StringProperty("")
    seen_text = StringProperty("")
    running = BooleanProperty(False)
    verbose = BooleanProperty(True)

    def toggle(self):
        app = App.get_running_app()
        if self.running:
            app.stop_scan()
        else:
            app.start_scan()


class BertAlertApp(App):
    def build(self):
        Builder.load_string(KV)
        self.root_widget = Root()
        self._loop = None
        self._engine = None
        self._thread = None
        self._seen_rows = []
        self._hit_rows = []
        self._store = Store(self.user_data_dir)
        return self.root_widget

    def on_start(self):
        self._request_permissions()

    def _request_permissions(self):
        try:
            from android.permissions import request_permissions
        except ImportError:
            self._set_status("Not running on Android")
            return
        # Background location is deliberately left out of this batch. Bundling
        # it makes Android deny the whole request outright (bleak issue #1542).
        request_permissions(RUNTIME_PERMISSIONS)

    @mainthread
    def _set_status(self, text):
        self.root_widget.status = text

    def start_scan(self):
        if self.root_widget.running:
            return

        notifier = None
        wifi = None
        problems = []

        try:
            from notify import Notifier
            notifier = Notifier()
        except Exception as exc:
            problems.append(f"notifications off ({exc})")

        try:
            from wifi_android import WifiScanner
            wifi = WifiScanner()
            if not wifi.enabled:
                problems.append("wi-fi radio off")
        except Exception as exc:
            problems.append(f"wi-fi off ({exc})")
            wifi = None

        self.root_widget.running = True
        self._set_status("Scanning. " + ("; ".join(problems) if problems else "BLE + Wi-Fi"))

        self._thread = threading.Thread(
            target=self._run_engine, args=(notifier, wifi), daemon=True
        )
        self._thread.start()

    def _run_engine(self, notifier, wifi):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._engine = Engine(
            store=self._store,
            notifier=notifier,
            wifi=wifi,
            on_sighting=self._on_sighting,
            on_hit=self._on_hit,
            on_error=self._set_status,
        )
        try:
            self._loop.run_until_complete(self._engine.run())
        except Exception as exc:
            self._set_status(f"stopped: {exc}")
        finally:
            self._loop.close()
            Clock.schedule_once(lambda _dt: self._mark_stopped(), 0)

    def _mark_stopped(self):
        self.root_widget.running = False

    def stop_scan(self):
        if self._engine and self._loop and not self._loop.is_closed():
            self._loop.call_soon_threadsafe(self._engine.stop)
        self._set_status("Stopping")

    def _on_sighting(self, mac, label, signal, kind, vendor):
        if not self.root_widget.verbose or vendor:
            return
        row = f"{mac}  {kind:<4}  {signal:>4}  {label or ''}"
        self._push(self._seen_rows, row, "seen_text")

    def _on_hit(self, mac, label, signal, kind, vendor):
        stamp = time.strftime("%H:%M:%S")
        row = f"[{stamp}] {vendor} -- {mac} {kind} {signal} {label or ''}"
        self._push(self._hit_rows, row, "hits_text")

    def _push(self, rows, row, prop):
        rows.insert(0, row)
        del rows[MAX_ROWS:]
        text = "\n".join(rows)
        Clock.schedule_once(lambda _dt: setattr(self.root_widget, prop, text), 0)

    def on_stop(self):
        self.stop_scan()
        self._store.close()


if __name__ == "__main__":
    BertAlertApp().run()
