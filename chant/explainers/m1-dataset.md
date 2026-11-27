# M1 Dataset — Text-to-Note-Table Pairs

The M1 dataset is a collection of (text caption, metadata) pairs built from drift's chip-tune archive. It covers 2,684 tracks across five formats: SID, AY, MOD, XM, and VGM.

## Building the dataset

```bash
python -m chant.build_dataset
```

This walks `_data/` (symlinked from drift), parses every file, generates a caption, and saves `train.jsonl` + `val.jsonl` to `_data/dataset/`.

Options:
- `--data-dir _data` — source directory (default: `_data`)
- `--output-dir _data/dataset` — output directory (default: `_data/dataset`)
- `--seed 42` — random seed for reproducible splits (default: 42)

## Output format

Each line in the JSONL files is a JSON object:

```json
{
  "caption": "Commodore 64 SID (MOS8580), 6-channel, \"The Shuffle\", by Zack Maxis, released 2026 Hokuto Force",
  "source_format": "sid",
  "source_path": "_data/hvsc/sid/The_Shuffle.sid",
  "title": "The Shuffle",
  "author": "Zack Maxis",
  "chip": "MOS8580",
  "channels": 6,
  "sub_songs": 1,
  "extra": {"magic": "PSID", "version": 2, "released": "2026 Hokuto Force"}
}
```

| Field | Type | Description |
|-------|------|-------------|
| `caption` | string | Generated text description (the "text" half of the training pair) |
| `source_format` | string | `sid`, `ay`, `mod`, `xm`, or `vgm` |
| `source_path` | string | Relative path to the source file |
| `title` | string | Track title |
| `author` | string | Composer (may be empty for MOD/XM/some VGM) |
| `chip` | string? | Sound chip enum value (null if unknown) |
| `channels` | int | Number of audio channels |
| `sub_songs` | int | Number of sub-songs in the file |
| `extra` | object | Format-specific metadata (see below) |

## How captions are generated

Captions are deterministic — same metadata always produces the same text. The `caption()` function in `chant/caption.py` builds a comma-separated description from:

1. **Chip description** — human-readable chip name (e.g. "Commodore 64 SID (MOS8580)")
2. **Channel count** — "N-channel"
3. **Title** — quoted
4. **Author** — "by Name" (if present)
5. **Format-specific extras:**
   - SID: released info
   - AY: misc field (often contains credits/context)
   - XM: BPM + instrument count
   - MOD: filtered instrument names (ST- prefixed sample library names)
   - VGM: game name + system name from GD3 tag
6. **Sub-songs** — "N sub-songs" (only if > 1)

### MOD instrument name filtering

MOD files abuse instrument name fields for liner notes, greetings, and ASCII art. The filter keeps names that:
- Are 2–20 characters
- Don't contain special characters (`[]{}()/\!@#$&*`)
- Don't contain double spaces
- Aren't pure digits
- Aren't prose (4+ words) unless they start with `ST-` (standard sample library prefix)

## Format-specific `extra` fields

| Format | Extra fields |
|--------|-------------|
| SID | `magic` (PSID/RSID), `version`, `released` |
| AY | `file_version`, `player_version`, `misc`, `raw_author`, `raw_song_name` |
| MOD | `magic` (M.K./8CHN/etc), `instruments` (list of names) |
| XM | `tracker`, `num_instruments`, `bpm` |
| VGM | `gd3` (dict of GD3 tag fields), `is_compressed` |

## Train/val split

- 90% train, 10% val
- Seeded shuffle (`seed=42`) for reproducibility
- Split is format-proportional (no stratification — the shuffle mixes formats)

## Corpus stats

| Format | Files | Notes |
|--------|------:|-------|
| SID | 1,257 | Richest metadata (title, author, chip model, released) |
| AY | 500 | Author often blank — falls back to directory name |
| MOD | 348 | Instrument names double as liner notes |
| XM | 311 | BPM and instrument count in header |
| VGM | 189 | GD3 has game/system info; some garbled UTF-16 |
| VGZ | 79 | Gzip-compressed VGM (counted under VGM in dataset) |
| **Total** | **2,684** | **2,416 train / 268 val** |

## Coming from C

The dataset builder is a classic ETL pipeline: extract (parsers), transform (caption), load (JSONL). In C you'd write it as a `for` loop over `readdir()` with `switch` on the file extension. Python's `pathlib.rglob()` and dictionary dispatch do the same thing with less ceremony.

## Coming from JS/TS

Think of each JSONL line as a typed object. The `build_dataset()` function is `Array.flatMap()` over format-specific parsers, and `split_and_save()` is `Array.slice()` after a seeded shuffle. The JSONL format is one `JSON.stringify()` per line — no surrounding array brackets, which makes streaming reads easy.

## What's missing (future milestones)

M1 captions describe **metadata only** — chip, channels, title, author. They don't describe the music itself (melody, rhythm, effects) because the parsers don't extract note events yet. Adding note events requires:

- SID: emulation (6502 → register writes → note events)
- AY: Z80 emulation or pre-extracted event tables
- MOD/XM: pattern data parsing (feasible — well-documented format)
- VGM: register write stream parsing (chip-specific)

MOD/XM pattern parsing is the most accessible next step — the data is right there in the file, no emulation needed.
