#!/bin/bash
# play.sh — build the tone engine demo and open the WAV
set -euo pipefail
cd "$(dirname "$0")"

cargo run --release -- -o demo.wav 2>&1
open demo.wav
