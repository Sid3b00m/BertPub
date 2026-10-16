[app]

title = BertAlert
package.name = bertalert
package.domain = org.bertalert

source.dir = .
source.include_exts = py,png,jpg,kv,atlas
# The original desktop tool is kept in the repo but must not ship: bert.py runs
# argparse and pywifi at import time, and neither works on Android.
source.exclude_patterns = bert.py,toot.py,requirements.txt,.github/*

version = 2.0.666

requirements = python3,kivy,pyjnius,android,bleak

# bleak has no recipe in the p4a tree, so p4a falls back to installing it as a
# plain pip package. That ships the Python half of its Android backend but never
# compiles the PythonScanCallback / PythonBluetoothGattCallback Java classes it
# binds to, so scanning raises at runtime in an otherwise healthy APK. bleak
# carries its own recipe; CI populates this directory from the installed copy.
p4a.local_recipes = ./p4a-recipes

orientation = portrait
fullscreen = 0

# ACCESS_FINE_LOCATION is required for Wi-Fi scan results on API 29+ and is what
# makes BLE MACs visible, so BLUETOOTH_SCAN deliberately omits the
# neverForLocation flag -- setting it filters beacons out of our results for no
# benefit, since we need location permission regardless.
android.permissions = ACCESS_FINE_LOCATION, ACCESS_COARSE_LOCATION, ACCESS_WIFI_STATE, CHANGE_WIFI_STATE, BLUETOOTH_SCAN, BLUETOOTH_CONNECT, POST_NOTIFICATIONS, VIBRATE, WAKE_LOCK, FOREGROUND_SERVICE, (name=android.permission.BLUETOOTH;maxSdkVersion=30), (name=android.permission.BLUETOOTH_ADMIN;maxSdkVersion=30)

android.api = 34
android.minapi = 26
android.ndk_api = 26

# Left unpinned, buildozer grabs the newest build-tools (37.x), whose licence
# differs from the ones pre-accepted in CI, and the install silently skips --
# which surfaces much later as "Aidl not found". Pin it to match android.api.
android.build_tools_version = 34.0.0

android.accept_sdk_license = True

# arm64 only for now. Every phone from roughly 2016 on is arm64-v8a, and adding
# armeabi-v7a doubles CI build time.
android.archs = arm64-v8a

android.wakelock = 1
android.allow_backup = 0

p4a.bootstrap = sdl2

[buildozer]
log_level = 2
warn_on_root = 1
