# BertAlert
## LEO detection Tool

It does things

v2.0.666

- SqlDB
- CLeaned up and rewrote most of scan function
- theres more im going sleep

#### Activate virtual environment and install modules.

```cd BertAlert &&\
python -m venv myenv &&\
source ./venv/bin/activate &&\
pip install -r requirements.txt
python3 bert.py [options]
```

---

## Android port

This fork adds an Android build alongside the original desktop script. The APK is
produced by GitHub Actions rather than locally, since Buildozer only runs on Linux.

Grab it from the **Build APK** workflow run under the Actions tab, or:

```
gh run download --name BertAlert-debug-apk
adb install BertAlert-*-debug.apk
```

The build is debug-signed and sideload-only.

### Why it is a rewrite and not a repackage

`pywifi` cannot run on Android at all. It drives the Windows WLAN API or
wpa_supplicant's control socket, and SELinux denies that socket to unprivileged
apps, so the Wi-Fi half goes through `WifiManager` via pyjnius instead. The
terminal interface (`argparse`, `shutil.get_terminal_size`, `os.system('clear')`)
has no equivalent on a phone and became a Kivy UI.

| Module | Replaces | Notes |
| --- | --- | --- |
| `main.py` | `bert.py` UI | Kivy interface, runtime permissions |
| `scanner.py` | `sniff()` | async BLE + Wi-Fi engine |
| `wifi_android.py` | `pywifi` | `WifiManager` through pyjnius |
| `notify.py` | `phoneHome` / `fourKUltra` | local notification + vibration |
| `storage.py` | `toot.py` | same schema, reads an existing `pork.db` |
| `matcher.py` | inline `b[:8] in haters` | case-normalized OUI lookup |

`lizt.py` is shared unchanged between both versions.

### Known limits

- **Wi-Fi detection lags up to ~30s.** Android caps `startScan()` at four calls
  per two minutes per foreground app, so the original's 2.5-second rescan loop is
  not achievable. BLE is continuous and unaffected, which is where bodycams show up.
- **MAC randomization.** Devices using rotating Resolvable Private Addresses never
  OUI-match. Plenty of bodycams still broadcast static public addresses, so this
  mostly works, but expect misses on newer equipment.
- **Foreground only.** The app must stay open; Doze kills background scanning
  without a foreground service, which is not wired up yet.
- Effectiveness depends entirely on what your local agencies actually deploy.
  Amend `lizt.py` accordingly. Treat this as a hobby RF scanner, not something to
  depend on.

### Changed from the original on purpose

The Discord webhook and camera-still upload were dropped rather than ported. They
required a bot token embedded in the build, and an APK is trivially decompiled, so
that token would be public the moment the file was shared. Alerts are local.

### Bugs fixed while porting

These affect the desktop script too:

- **OUI tables could not match.** `haters` keys are uppercase and `hWifi` is mixed,
  but both were compared against platform output with a case-sensitive `in`, so a
  large share of entries could never fire. Both sides are now folded to lower case.
- `toot.py:addID` raised `ProgrammingError` whenever `sqssid` was `None` — the SQL
  had one placeholder but three parameters were passed.
- The upsert's `SET sqsignal = sqsignal, protocal = protocal` were self-assignments
  that never updated anything; they now use `excluded.*`.
- `time.sleep()` inside `async def sniff()` blocked the event loop.
- `match.group(1)` was unguarded and raised on any device whose string carried no MAC.
- `-t/--timing` was parsed into `delay` and never read, so a device alerted once and
  then stayed silent forever. It is now a real per-MAC cooldown.

## Credits

Original tool: **[slaptat/BertPub](https://github.com/slaptat/BertPub)** — this repo
is a fork, all of the concept, OUI research and detection logic is theirs.

As the original README notes, BertAlert is based on and inspired by the work of
**nullagent** and **dataparty**.
