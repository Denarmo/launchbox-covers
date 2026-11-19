# AGENTS

EmuDEN's default box art data, built from the LaunchBox Games Database so devices never download
LaunchBox's Metadata.zip themselves.

- Refresh only when the owner asks: `python -I tools/build.py`, check the platform and game counts
  it prints, commit and push to main. No schedule or automation, so LaunchBox is not hit unasked.
- The key rules in README "Keys" must stay identical to `LaunchBoxKey` in EmuDEN's
  `library/src/launchbox_covers.cpp`.

## How we work

- Work without asking. Make the choices yourself, carry on to the next step and report at the end.
  Stop only for something destructive, something outside the owner's accounts, or a decision only
  the owner can make (a password, a purchase, a key).
- Finish things over re-verifying them. Bundle 5 to 10 changes per build and test round (builds,
  uploads and benchmarks are slow), keep each one separable so a regression can be bisected, then
  run one short smoke check of what changed. No screenshot-every-state rounds and no routine
  review passes unless the change touches user data, sync or security. Report honestly what was
  not tested.
- Build, test and package locally, never on GitHub Actions (it costs the owner money): do not
  trigger or re-run workflows and do not add workflows or push triggers. Windows builds run on
  this PC, Linux builds in WSL Debian, Android with the NDK and Gradle on this PC. Releases are
  published from local builds with `gh release create` / `gh release upload`.
- Git: commit and push to the owner's `Denarmo/*` repositories without asking. No force pushes,
  no deleting repositories or changing their visibility, and no pull requests or issues on other
  people's repositories without asking. `gh` without `-R` can resolve to an upstream repository,
  so pass `-R Denarmo/<name>`. LF line endings.
- Experiment switches (env flags that pick between candidate fixes) never merge; a proven fix
  ships unconditionally and a disproven one is dropped. Diagnostics stay, off unless enabled.
- Keep comments to a reasonable level and do not touch unrelated parts of the code.

## Never

- Commit or upload BIOS, console keys, firmware, game files, game shaders, textures or saves.
  EmuDEN never handles console keys, and only offers cores that need no BIOS (fork or build one
  where none exists).
- Read, print, copy or commit the signing keys in `C:\Users\david\.emuden-plugin-signing\` or any
  keystore password; pass the key path to the signing tool and nothing else.
- Ask for, type or repeat any of the owner's passwords. `sudo` on a device is for the owner.
- Write to `D:\ROMS` (the test ROMs, read-only) or touch `C:\Users\david\Desktop\Lichii` (the
  owner's own install). Test from your build folder with a portable `user` folder, close every
  window you open, and kill only processes you started.
- In a test, activate a Steam or PC-store tile, open a web link, or change per-game or per-console
  settings on a device (they sync to every device).

## Devices

Both handhelds are the owner's own, and they play on them. Before driving, installing on or
stopping anything on a device:

1. Check it is idle: no game running in the foreground, no recent input. If it is in use, do not
   send input, install or force-stop; skip the device step and report "device in use".
2. Take its lock: write `<session name> <time>` into the lock file below and delete it when done.
   Hold it 20 minutes at most; a lock older than 30 minutes is stale. If it is locked, test on
   another device that shows the same thing instead of waiting.
3. Close everything you started when the test ends.

**Legion Go S (SteamOS)**: `ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new deck@<ip>`,
key login from this PC (`C:\Users\david\.ssh\id_ed25519`), `scp` with the same flags. Lock file
`~/.cache/emuden-device-lock`.
- The address comes from DHCP and moves (it has been .54, .57, .58 and .61 in 192.168.68.0/22).
  Find it by its ed25519 host key with one `ssh-keyscan` per candidate; never sweep the LAN or
  retry in a tight loop (sshd starts refusing the PC). One attempt, then wait minutes, then ask
  the owner for `ip -4 addr` or to wake the device.
- Games live in `~/Games/<Name>/` as AppImages; EmuDEN is `~/Games/EmuDEN/EmuDEN-x86_64.AppImage`
  (installed with `tools/linux/install-steamos.sh --steam <AppImage>` from the emuden repo).
  `steamos-add-to-steam` over ssh needs `DISPLAY=:0 XDG_RUNTIME_DIR=/run/user/1000`.
- Game Mode shows only what Steam started: a window started over ssh runs hidden. Launch through
  the Steam shortcut (Steam's CEF on 127.0.0.1:8080, SharedJSContext:
  `SteamClient.Apps.SetShortcutLaunchOptions(appid, "ENV=1 %command%")`, then `RunGame`), clear
  the launch options afterwards, and take screenshots with `gamescopectl screenshot`. Helpers are
  in `~/Games/EmuDEN/test-tools`.
- End every test with `pkill -KILL -x AppRun` (or the process you started); never leave a
  `systemd-run --user` unit running. A leftover emulator plus a level load filling the 8 GiB GPU
  memory cap has frozen the device.

**Retroid Pocket Duo (Android)**: wireless adb only, so it can charge; never ask for USB.
- adb is `C:\Users\david\AppData\Local\Android\Sdk\platform-tools\adb.exe` (in bash set
  `MSYS_NO_PATHCONV=1`). Use `-s <ip>:5555` (it has been 192.168.68.52 and .59); if it is not
  listed, `adb mdns services` shows `adb-ec7e4eb9` with its address, then `adb connect`.
- After a reboot 5555 may stop answering: ask the owner to turn on Developer options > Wireless
  debugging (then `adb mdns services`, or `adb pair <ip:port> <code>` if pairing was lost).
- Lock file `/data/local/tmp/emuden-device-lock`. Check
  `dumpsys activity activities | grep topResumedActivity` before driving or installing.
- Delete only the files you pushed to `/data/local/tmp`, by name; never a wildcard there (other
  sessions keep their tools in it).

**This PC** (Windows 11): runs its own builds with their own data folders, so it is
the fallback when a handheld is busy.
