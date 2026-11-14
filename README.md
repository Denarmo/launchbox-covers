# launchbox-covers

Box cover lookups from the [LaunchBox Games Database](https://gamesdb.launchbox-app.com/), split
into small static files, so a game frontend can find a game's cover without downloading the
database's 100 MB `Metadata.zip` on every device.

Only the data needed to find a front cover is here, and in files of their own the other faces
of each game's box, cartridge and disc, for frontends that draw games as 3D objects. The images themselves stay on LaunchBox's
server, `https://images.launchbox-app.com/<file>`.

This project is not affiliated with LaunchBox or Unbroken Software. The game data is theirs and
their community's. The tools in `tools/` are under the MIT licence.

## Layout

```
data/manifest.json                 version, platforms, libretro names, image base address
data/covers/<platform>/<b>.json    the games of one platform whose key starts with <b>
data/faces/<platform>/<b>.json     the other faces of those games, by database id
```

`manifest.json`:

```json
{
  "format": 1,
  "version": "2026-11-14",
  "images": "https://images.launchbox-app.com/",
  "libretro": { "Nintendo - Game Boy Advance": "Nintendo Game Boy Advance", "...": "..." },
  "platforms": {
    "Nintendo Game Boy Advance": { "dir": "nintendo-game-boy-advance", "games": 2249,
                                   "buckets": ["0", "a", "b", "..."],
                                   "faces": ["0", "a", "..."] }
  }
}
```

- `platforms` uses LaunchBox's platform names. `dir` is the folder under `covers/`, and
  `buckets` lists the files that exist. A bucket that isn't listed has no games.
- `libretro` maps libretro thumbnail folder names (No-Intro and Redump system names) to
  LaunchBox platforms, for frontends that already know those names.
- `version` changes whenever the data is rebuilt. A client can keep what it downloaded until the
  version changes.

A bucket file maps each key to the games with that key:

```json
{"castlevaniaariaofsorrow": [[3349, "Castlevania: Aria of Sorrow",
  [["Europe", "42f3dffe-....jpg"], ["Japan", "297f69a9-....png"], ["North America", "23588e39-....jpg"]]]]}
```

Each game is `[LaunchBox database id, name, [[region, file], ...]]`. The region is LaunchBox's
own name (`North America`, `Europe`, `Japan`, `World`, `Germany`, ...), or `""` when the cover
has none. A game is listed under its name and under each alternate name it has in the database.
The file is a `Box - Front` cover. A game without one uses `Box - Front - Reconstructed`, and
failing that `Fanart - Box - Front`.

## Faces

`data/faces/<platform>/<b>.json` holds, for the games of the cover file `<b>.json`, their other
images, by LaunchBox database id. A platform's `faces` in the manifest lists the files that
exist; a game missing from its file has none. Front-only clients never need these files.

```json
{"3349": {"back": [["North America", "....jpg"]], "cart": [["Europe", "....png"]]}}
```

| Face | LaunchBox image types, best first |
|---|---|
| `back` | `Box - Back`, `Box - Back - Reconstructed`, `Fanart - Box - Back` |
| `spine` | `Box - Spine` |
| `cart` | `Cart - Front`, `Fanart - Cart - Front` |
| `cart_back` | `Cart - Back`, `Fanart - Cart - Back` |
| `disc` | `Disc`, `Fanart - Disc` |

The manifest's `face_kinds` lists these names; a client ignores names it does not know. The
faces arrived without a new `format`: clients of format 1 read covers exactly as before.

## Devices

A platform's `device` in the manifest, when it has one, is the file of its `Platform Device
Thumb` image: the console photographed from the front on a clear background. Metadata.zip
leaves platform images out, so `tools/devices.py` reads them from the database's platform pages
into `tools/devices.json`, which `build.py` copies into the manifest.

## Keys

A key is the title:
1. in lower case
2. with the Latin accents in `ACCENTS` (`tools/build.py`) replaced by plain letters
3. with `&` read as `and`
4. without a leading `the ` or a `, the` after the main title
5. keeping only `a`–`z` and `0`–`9`

The bucket is the key's first character, `0` for any digit.

For example, `The Legend of Zelda: A Link to the Past` and `Legend of Zelda, The - A Link to the Past`
both give `legendofzeldaalinktothepast`, in bucket `l`.

## Fetching

Clients read the files from
`https://raw.githubusercontent.com/Denarmo/launchbox-covers/main/data/...`. Fetch
`manifest.json`, then only the bucket a title needs, and cache both until `version` changes.

## Updating

```bash
python -I tools/build.py
```

This downloads the current `Metadata.zip` once and rewrites `data/`. Then commit and push. Run
it now and then, not on a schedule: LaunchBox publishes the database for its users, and this
copy exists so that frontends don't each fetch it from LaunchBox.
