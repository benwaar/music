#!/usr/bin/env bash
# Play a demo scale through all five waveforms.
set -euo pipefail
cd "$(dirname "$0")"

cargo build --release --quiet

cat <<'JSON' | ./target/release/beeper-synth -o demo.wav
[
  {"pitch_hz":261.63,"duration_ms":250,"waveform":"pulse","duty_cycle":0.25,"volume":0.7,"channel":0,"effects":[]},
  {"pitch_hz":293.66,"duration_ms":250,"waveform":"pulse","duty_cycle":0.25,"volume":0.7,"channel":0,"effects":[]},
  {"pitch_hz":329.63,"duration_ms":250,"waveform":"pulse","duty_cycle":0.25,"volume":0.7,"channel":0,"effects":[]},
  {"pitch_hz":349.23,"duration_ms":250,"waveform":"pulse","duty_cycle":0.25,"volume":0.7,"channel":0,"effects":[]},
  {"pitch_hz":392.00,"duration_ms":250,"waveform":"pulse","duty_cycle":0.25,"volume":0.7,"channel":0,"effects":[]},
  {"pitch_hz":440.00,"duration_ms":250,"waveform":"pulse","duty_cycle":0.25,"volume":0.7,"channel":0,"effects":[]},
  {"pitch_hz":493.88,"duration_ms":250,"waveform":"pulse","duty_cycle":0.25,"volume":0.7,"channel":0,"effects":[]},
  {"pitch_hz":523.25,"duration_ms":500,"waveform":"pulse","duty_cycle":0.25,"volume":0.7,"channel":0,"effects":[]}
]
JSON

echo "demo.wav written — open with: afplay demo.wav"
