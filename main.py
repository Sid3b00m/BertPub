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

import permissions
from scanner import Engine
from storage import Store

MAX_ROWS = 200

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

    # Collapses to nothing once there is no blocker left to clear.
    Button:
        text: root.blocker_action
        on_release: root.fix_blocker()
        size_hint_y: None
        height: dp(44) if root.blocker_action else 0
        opacity: 1 if root.blocker_action else 0
        disabled: not root.blocker_action

    BoxLayout:
        size_hint_y: None
        height: dp(48)
        spacing: dp(6)

        Button:
            id: toggle
            text: 'Stop' if root.running else 'Start'
            disabled: not root.ready
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
    status = StringProperty("Starting")
    hits_text = StringProperty("")
    seen_text = StringProperty("")
    running = BooleanProperty(False)
    verbose = BooleanProperty(True)
    ready = BooleanProperty(False)
    blocker_action = StringProperty("")

    def toggle(self):
        app = App.get_running_app()
        if self.running:
            app.stop_scan()
        else:
            app.start_scan()

    def fix_blocker(self):
        App.get_running_app().fix_blocker()


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
        self._blocker = None
        self._prompts = 0
        return self.root_widget

    def on_start(self):
        if not permissions.AVAILABLE:
            self.root_widget.ready = True
            self._set_status("Desktop mode: BLE only, no Wi-Fi")
            return
        # Asked as one batch on first launch so the user clears the dialogs
        # once rather than meeting a new one per feature. Background location
        # stays out of it -- bundling that makes Android deny the whole
        # request outright (bleak issue #1542).
        pending = permissions.missing(permissions.required() + permissions.optional())
        if pending:
            self._set_status("Waiting for permission")
            self._prompts = 1
            permissions.request(pending, self._on_permission_result)
        else:
            self._refresh_readiness()

    def _on_permission_result(self, _permissions, _results):
        self._refresh_readiness()

    def on_resume(self):
        # Catches the return trip from Settings, the location toggle or the
        # Bluetooth radio, any of which can clear the current blocker.
        self._refresh_readiness()

    def _find_blocker(self):
        """The first thing standing between the user and a working scan."""
        if permissions.missing(permissions.required()):
            if not permissions.precise_location() and permissions.granted(
                permissions.LOCATION_COARSE
            ):
                return ("permissions", "Grant precise location",
                        "Approximate location is too coarse for Wi-Fi scans")
            return ("permissions", "Grant permissions",
                    "Location and Bluetooth permission needed to scan")
        if not permissions.location_services_enabled():
            return ("location", "Turn on location",
                    "Location services are off; both radios return nothing")
        if not permissions.bluetooth_enabled():
            return ("bluetooth", "Turn on Bluetooth", "Bluetooth is off")
        return None

    @mainthread
    def _refresh_readiness(self):
        # Android hands permission results back on its own thread, and a scan
        # in progress owns the status line, so this is both deferred to the UI
        # thread and skipped while running. Off Android there is nothing to
        # query and every permission would read as denied.
        if not permissions.AVAILABLE or self.root_widget.running:
            return

        blocker = self._find_blocker()
        self._blocker = blocker[0] if blocker else None
        self.root_widget.blocker_action = blocker[1] if blocker else ""
        self.root_widget.ready = blocker is None

        if blocker:
            self._set_status(blocker[2])
        elif permissions.missing(permissions.optional()):
            self._set_status("Ready. Alerts are on-screen only")
        else:
            self._set_status("Ready")

    def fix_blocker(self):
        if self._blocker == "location":
            permissions.open_location_settings()
        elif self._blocker == "bluetooth":
            permissions.request_bluetooth_enable()
        elif self._blocker == "permissions":
            pending = permissions.missing(
                permissions.required() + permissions.optional())
            # One in-app retry, then Settings: a permission denied twice is
            # marked permanently denied and request() stops raising a dialog
            # at all, which would leave this button doing nothing visible.
            if pending and self._prompts < 2:
                self._prompts += 1
                permissions.request(pending, self._on_permission_result)
            else:
                permissions.open_app_settings()

    @mainthread
    def _set_status(self, text):
        self.root_widget.status = text

    def start_scan(self):
        if self.root_widget.running or not self.root_widget.ready:
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
        # A scan usually ends because a radio or permission went away, so the
        # blocker is re-evaluated rather than assumed unchanged.
        self._refresh_readiness()

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
