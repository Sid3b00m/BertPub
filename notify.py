"""On-device alerting: a notification channel plus vibration.

This replaces the original's Discord webhook and camera-still upload. An APK is
trivially decompiled, so a bot token shipped inside one is a published token;
alerts stay local instead.
"""

CHANNEL_ID = "bertalert_hits"
CHANNEL_NAME = "Detections"
VIBRATE_MS = 400

try:
    from jnius import autoclass, cast

    _Context = autoclass("android.content.Context")
    _PythonActivity = autoclass("org.kivy.android.PythonActivity")
    _NotificationChannel = autoclass("android.app.NotificationChannel")
    _NotificationManager = autoclass("android.app.NotificationManager")
    _NotificationBuilder = autoclass("android.app.Notification$Builder")
    _VibrationEffect = autoclass("android.os.VibrationEffect")
    AVAILABLE = True
except Exception:  # not running on Android
    AVAILABLE = False


class Notifier:
    def __init__(self):
        if not AVAILABLE:
            raise RuntimeError("Notifier requires Android")
        self._context = _PythonActivity.mActivity.getApplicationContext()
        self._manager = cast(
            "android.app.NotificationManager",
            self._context.getSystemService(_Context.NOTIFICATION_SERVICE),
        )
        self._vibrator = cast(
            "android.os.Vibrator",
            self._context.getSystemService(_Context.VIBRATOR_SERVICE),
        )
        self._icon = self._context.getApplicationInfo().icon
        self._next_id = 1
        self._create_channel()

    def _create_channel(self):
        # minapi is 26, so the channel always exists and needs no version branch.
        channel = _NotificationChannel(
            CHANNEL_ID, CHANNEL_NAME, _NotificationManager.IMPORTANCE_HIGH
        )
        channel.setDescription("Known device OUI seen nearby")
        channel.enableVibration(True)
        self._manager.createNotificationChannel(channel)

    def alert(self, vendor, mac, kind, signal):
        builder = _NotificationBuilder(self._context, CHANNEL_ID)
        builder.setContentTitle(f"{vendor} nearby")
        builder.setContentText(f"{kind}  {mac}  {signal}")
        builder.setSmallIcon(self._icon)
        builder.setAutoCancel(True)
        self._manager.notify(self._next_id, builder.build())
        self._next_id += 1
        self._vibrate()

    def _vibrate(self):
        try:
            effect = _VibrationEffect.createOneShot(
                VIBRATE_MS, _VibrationEffect.DEFAULT_AMPLITUDE
            )
            self._vibrator.vibrate(effect)
        except Exception:
            pass
