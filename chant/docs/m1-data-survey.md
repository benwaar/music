# M1 Data Survey — Drift Raw Chip-Tune Corpus

Surveyed: `drift/_data/` (will be symlinked as `_data/` from chant).
Skipped derived dirs: `rendered_wav`, `segments`, `checkpoints*`, `generated`, `noise`, `eval`, `chiptune_wav`, `segments_loops`.

---

## Raw Source Summary

| Format | Dir | Files | Size | Primary Ext(s) |
|--------|-----|------:|-----:|----------------|
| SID (C64) | `hvsc/` | 1 257 | 20.5 MB | `.sid` |
| VGM/VGZ | `vgm/` | 268 | 10.2 MB | `.vgm` (189), `.vgz` (79) |
| MOD/XM | `modarchive/` | 659 | 496.6 MB | `.mod` (348), `.xm` (311) |
| AY (ZX Spectrum) | `ay/` | 500 | 3.1 MB | `.emul` |

**Total raw: ~530 MB, ~2 684 files**

(The `modarchive/` dir also contains 4 stray `.wav` files — ignore.)

---

## Per-Format Metadata

### SID (`hvsc/`)

- **Magic**: `PSID` or `RSID` (4 bytes)
- **Header fields** (fixed-offset, ASCII/null-padded):
  - Song title (32 bytes @ 0x16)
  - Author (32 bytes @ 0x36)
  - Released / copyright (32 bytes @ 0x56)
  - Number of sub-songs (uint16 @ 0x0e)
  - SID chip model (MOS6581 / MOS8580, flags field v2+)
- **Channels**: always 3 voices per SID chip; v3 "2SID" files use two chips (6 voices)
- **Parser difficulty**: easy — fixed-offset binary header, well-documented spec (HVSC `.txt` companion files add extra context)
- **Sample**:
  ```
  name='The Shuffle'  author='Zack Maxis (manganoid)'  released='2026 Hokuto Force'  songs=1  chip=MOS8580
  ```

---

### VGM / VGZ (`vgm/`)

- **Magic**: `Vgm ` (4 bytes); VGZ is gzip-compressed VGM
- **GD3 tag** (optional, at relative offset from 0x14): UTF-16LE strings:
  - Track name (EN + JP)
  - Game name (EN + JP)
  - System name (EN + JP)
  - Author (EN + JP)
  - Release date, ripper, notes
- **Data** encodes raw register writes for many chips (SN76489, YM2612, etc.)
- **Notes**: GD3 encoding is inconsistent in older files — some have byte-swapped UTF-16 producing garbled text. Roughly 50–70% of files in this corpus have readable GD3.
- **Parser difficulty**: medium — need gzip decompress for VGZ, GD3 offset arithmetic, UTF-16LE decoding; chip-register stream parsing adds complexity if BPM/channel info is needed
- **Sample**:
  ```
  track='Chemical Plant Zone (Act 2)'  game='Sonic Mania'  system='Sega Mega Drive / Genesis'  author='Tee Lopes, Masato Nakamura'
  ```

---

### MOD / XM (`modarchive/`)

- **MOD** (`M.K.`, `6CHN`, `8CHN`, `FLT4`, …):
  - Song title: bytes 0–19 (ASCII null-padded)
  - 31 instrument names: 22 bytes each from offset 20
  - Channel count: inferred from 4-byte magic tag at offset 1080
  - Mostly 4-channel; some 6/8-channel variants
- **XM** (`Extended Module: `):
  - Module name: bytes 17–36
  - Tracker name: bytes 38–57
  - Channel count: uint16 @ 0x44
  - Instrument count: uint16 @ 0x48
  - BPM baked in header (uint16 @ 0x50)
- **Both**: instrument names are often the richest metadata (tracker community used them as liner notes / credits)
- **Parser difficulty**: medium-low for MOD (spec is 1980s-era but well-documented); medium for XM (more complex nested instrument/sample tables). Python `pymoo`/`modfile` libs exist but are not installed — raw struct parsing is feasible.
- **Size note**: MOD/XM corpus is by far the largest (497 MB) — these files embed raw PCM samples
- **Sample MOD**:
  ```
  title='{qasteron}'  magic=M.K.  channels=4  inst[0]='don-cato // talent'
  ```
- **Sample XM**:
  ```
  name='"I Can`t Fly"'  tracker='FastTracker v2.00'  channels=10  instruments=30
  ```

---

### AY / ZXAYEMUL (`ay/`)

- **Magic**: `ZXAYEMUL` (8 bytes)
- **Header fields**:
  - Number of sub-songs (byte 4, 0-based)
  - Author name (relative-pointer string in first ~200 bytes)
  - Misc / title (relative-pointer string)
  - Song title: embedded as a string shortly after header (e.g. `@Spring`)
  - Per-song names are in a song table but appear to be blank in many files; author/misc carry the useful metadata
- **Channels**: AY-3-8910 chip = 3 channels (square wave + noise)
- **Parser difficulty**: medium — pointer-based variable-length header, all big-endian; some files have dozens of sub-songs (up to 70 seen)
- **Sample**:
  ```
  songs=70  author='by SirIl/4D 1999'  misc='=chaos construction 999= ay msx compo'  title='Spring'
  ```

---

## Parser Difficulty Summary

| Format | Difficulty | Key Gotcha |
|--------|-----------|------------|
| SID | Easy | Fixed offsets; `2SID` v3 files need flag check |
| VGM/VGZ | Medium | GD3 optional + sometimes garbled UTF-16; gzip for VGZ |
| MOD | Medium-low | Magic varies (4/6/8 ch); no standard for channel labels |
| XM | Medium | Nested instrument/sample tables; BPM oddities in some files |
| AY (.emul) | Medium | Relative pointers, big-endian, variable sub-song counts |

---

## Notes for M1

- SID and AY are the smallest and cleanest — good for initial pipeline testing.
- MOD/XM has the richest instrument-level metadata (names double as credits/notes) but also the most raw PCM bulk.
- VGM GD3 encoding quality is inconsistent — worth a quick audit pass to flag files missing usable metadata.
- All four formats embed at minimum: title, author, sub-song count. Channel count is always derivable.
