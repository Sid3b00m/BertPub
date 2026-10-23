"""Runtime permission state for the first-launch grant flow.

Which permissions exist is a function of the device's API level, not of the
manifest. The manifest declares the whole set, but asking for one that the
running Android does not know about gets an immediate silent denial, so a
naive "all granted?" gate would lock out every device below the newest API:

* BLUETOOTH_SCAN / BLUETOOTH_CONNECT arrived in API 31. Below that the old
  install-time BLUETOOTH and BLUETOOTH_ADMIN cover scanning and never need a
  prompt.
* POST_NOTIFICATIONS arrived in API 33. Below that a notification channel is
  allowed to post without asking.

The split between required and optional matters for the same reason: losing
notifications costs an alert style, losing location costs every scan result on
both radios, so only the latter blocks the Start button.
"""

LOCATION_FINE = "android.permission.ACCESS_FINE_LOCATION"
LOCATION_COARSE = "android.permission.ACCESS_COARSE_LOCATION"
BLUETOOTH_SCAN = "android.permission.BLUETOOTH_SCAN"
BLUETOOTH_CONNECT = "android.permission.BLUETOOTH_CONNECT"
POST_NOTIFICATIONS = "android.permission.POST_NOTIFICATIONS"

try:
    from jnius import autoclass, cast

    _Build = autoclass("android.os.Build$VERSION")
    _Context = autoclass("android.content.Context")
    _Intent = autoclass("android.content.Intent")
    _PythonActivity = autoclass("org.kivy.android.PythonActivity")
    _Settings = autoclass("android.provider.Settings")
    _Uri = autoclass("android.net.Uri")
    _BluetoothAdapter = autoclass("android.bluetooth.BluetoothAdapter")
    _LocationManager = autoclass("android.location.LocationManager")

    SDK_INT = _Build.SDK_INT
    AVAILABLE = True
except Exception:  # not running on Android
    SDK_INT = 0
    AVAILABLE = False


def _activity():
    return _PythonActivity.mActivity


def required():
    """Permissions without which neither radio returns anything."""
    perms = [LOCATION_FINE, LOCATION_COARSE]
    if SDK_INT >= 31:
        perms += [BLUETOOTH_SCAN, BLUETOOTH_CONNECT]
    return perms


def optional():
    """Permissions that degrade a feature rather than block scanning."""
    return [POST_NOTIFICATIONS] if SDK_INT >= 33 else []


def granted(permission):
    if not AVAILABLE:
        return False
    from android.permissions import check_permission

    return bool(check_permission(permission))


def missing(permissions):
    return [p for p in permissions if not granted(p)]


def request(permissions, callback=None):
    """Fire the system dialogs for `permissions`.

    The callback comes back on Android's permission-result thread, so anything
    it touches in the UI has to be marshalled onto the Kivy clock by the caller.
    """
    if not AVAILABLE or not permissions:
        return False
    from android.permissions import request_permissions

    request_permissions(permissions, callback)
    return True


def precise_location():
    """True when FINE was granted rather than the "Approximate" downgrade.

    The single location dialog lets the user pick Approximate, which grants
    COARSE only. Wi-Fi scan results come back as an empty list in that case
    instead of raising, so it has to be detected rather than caught.
    """
    return granted(LOCATION_FINE)


def location_services_enabled():
    """Whether the system location toggle is on.

    Separate from the permission, and just as fatal: with it off, both
    getScanResults() and BLE advertisement callbacks go silent.
    """
    if not AVAILABLE:
        return False
    try:
        manager = cast(
            "android.location.LocationManager",
            _activity().getSystemService(_Context.LOCATION_SERVICE),
        )
        if SDK_INT >= 28:
            return bool(manager.isLocationEnabled())
        # minapi is 26, so the pre-28 provider check still has to exist.
        return bool(
            manager.isProviderEnabled(_LocationManager.GPS_PROVIDER)
            or manager.isProviderEnabled(_LocationManager.NETWORK_PROVIDER)
        )
    except Exception:
        return False


def bluetooth_enabled():
    if not AVAILABLE:
        return False
    try:
        adapter = _BluetoothAdapter.getDefaultAdapter()
        return bool(adapter and adapter.isEnabled())
    except Exception:
        return False


def open_app_settings():
    """Last resort once a permission has been denied permanently."""
    if not AVAILABLE:
        return
    activity = _activity()
    intent = _Intent(_Settings.ACTION_APPLICATION_DETAILS_SETTINGS)
    intent.setData(_Uri.fromParts("package", activity.getPackageName(), None))
    activity.startActivity(intent)


def open_location_settings():
    if not AVAILABLE:
        return
    _activity().startActivity(_Intent(_Settings.ACTION_LOCATION_SOURCE_SETTINGS))


def request_bluetooth_enable():
    if not AVAILABLE:
        return
    _activity().startActivity(_Intent(_BluetoothAdapter.ACTION_REQUEST_ENABLE))
