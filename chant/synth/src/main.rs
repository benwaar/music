use eno_state_zx::tone_1ch::ToneEngine;
use eno_state_zx::tone_2ch::Tone2chEngine;
use eno_state_zx::wav;
use midly::{Smf, TrackEventKind, MidiMessage, Timing};
use std::path::PathBuf;

// Z80 T-state constants (must match eno-state-zx internals)
const CPU_CLOCK: f64 = 3_500_000.0;
const T_PER_TICK: f64 = 24.0;
const T_TOGGLE_OVERHEAD: f64 = 57.0;

fn print_usage() {
    eprintln!("Usage: chant-host <input.mid> -o <output.wav> [--2ch] [--sample-rate 44100]");
}

/// Convert a frequency in Hz to a Z80 beeper period (1-255).
/// Inverts ToneEngine::freq_for_period:
///   freq = CPU_CLOCK / (2 * ((period - 1) * T_PER_TICK + T_TOGGLE_OVERHEAD))
fn freq_to_period(freq: f64) -> u8 {
    if freq <= 0.0 {
        return 255; // lowest pitch = longest period
    }
    let half_cycle = CPU_CLOCK / (2.0 * freq);
    let period = ((half_cycle - T_TOGGLE_OVERHEAD) / T_PER_TICK) + 1.0;
    (period.round() as i64).clamp(1, 255) as u8
}

/// Convert a MIDI note number to frequency in Hz.
fn midi_note_to_freq(note: u8) -> f64 {
    440.0 * 2.0_f64.powf((note as f64 - 69.0) / 12.0)
}

/// Convert a duration in milliseconds to Z80 duration units.
/// Each unit = 256 toggle groups. Total T-states per unit depends on period.
fn ms_to_z80_duration(ms: f64, period: u8) -> u8 {
    if ms <= 0.0 {
        return 1;
    }
    let half_cycle_t = if period > 0 {
        ((period as f64 - 1.0) * T_PER_TICK) + T_TOGGLE_OVERHEAD
    } else {
        (254.0 * T_PER_TICK) + T_TOGGLE_OVERHEAD
    };
    let t_per_unit = 256.0 * half_cycle_t;
    let ms_per_unit = (t_per_unit / CPU_CLOCK) * 1000.0;
    let units = ms / ms_per_unit;
    (units.round() as i64).clamp(1, 254) as u8
}

struct MidiNote {
    channel: u8,
    period: u8,
    duration_z80: u8,
}

/// Parse a MIDI file into a list of notes with Z80-native values.
fn parse_midi(data: &[u8]) -> Vec<MidiNote> {
    let smf = Smf::parse(data).expect("failed to parse MIDI file");

    let ticks_per_beat: f64 = match smf.header.timing {
        Timing::Metrical(tpb) => tpb.as_int() as f64,
        Timing::Timecode(fps, sub) => (fps.as_f32() as f64) * (sub as f64),
    };

    // Default 120 BPM → 500ms per beat
    let ms_per_tick = 500.0 / ticks_per_beat;

    let mut notes: Vec<MidiNote> = Vec::new();

    for track in &smf.tracks {
        // Collect note-on events with absolute tick positions
        let mut abs_tick: u64 = 0;
        // Track pending note-ons: (channel, note) → (abs_tick_on)
        let mut pending: std::collections::HashMap<(u8, u8), u64> =
            std::collections::HashMap::new();

        for event in track {
            abs_tick += event.delta.as_int() as u64;
            match event.kind {
                TrackEventKind::Midi { channel, message } => match message {
                    MidiMessage::NoteOn { key, vel } => {
                        if vel.as_int() == 0 {
                            // note-on with velocity 0 = note-off
                            if let Some(tick_on) = pending.remove(&(channel.as_int(), key.as_int())) {
                                let duration_ticks = abs_tick.saturating_sub(tick_on);
                                let duration_ms = duration_ticks as f64 * ms_per_tick;
                                let freq = midi_note_to_freq(key.as_int());
                                let period = freq_to_period(freq);
                                notes.push(MidiNote {
                                    channel: channel.as_int(),
                                    period,
                                    duration_z80: ms_to_z80_duration(duration_ms, period),
                                });
                            }
                        } else {
                            pending.insert((channel.as_int(), key.as_int()), abs_tick);
                        }
                    }
                    MidiMessage::NoteOff { key, .. } => {
                        if let Some(tick_on) = pending.remove(&(channel.as_int(), key.as_int())) {
                            let duration_ticks = abs_tick.saturating_sub(tick_on);
                            let duration_ms = duration_ticks as f64 * ms_per_tick;
                            let freq = midi_note_to_freq(key.as_int());
                            let period = freq_to_period(freq);
                            notes.push(MidiNote {
                                channel: channel.as_int(),
                                period,
                                duration_z80: ms_to_z80_duration(duration_ms, period),
                            });
                        }
                    }
                    _ => {}
                },
                _ => {}
            }
        }
    }

    // Sort by original order (already in order per track, but multi-track
    // files interleave — for now this is fine since we flatten to mono)
    notes
}

fn render_1ch(notes: &[MidiNote], sample_rate: u32) -> Vec<f32> {
    let table: Vec<(u8, u8)> = notes
        .iter()
        .map(|n| (n.duration_z80, n.period))
        .chain(std::iter::once((0xFF, 0)))
        .collect();
    ToneEngine::render_note_table(&table, sample_rate)
}

fn render_2ch(notes: &[MidiNote], sample_rate: u32) -> Vec<f32> {
    // Split into ch0 and ch1; pair them up
    let ch0: Vec<&MidiNote> = notes.iter().filter(|n| n.channel == 0).collect();
    let ch1: Vec<&MidiNote> = notes.iter().filter(|n| n.channel == 1).collect();
    let len = ch0.len().max(ch1.len());

    let mut table: Vec<(u8, u8, u8)> = Vec::with_capacity(len + 1);
    for i in 0..len {
        let dur = if i < ch0.len() { ch0[i].duration_z80 }
                  else if i < ch1.len() { ch1[i].duration_z80 }
                  else { 1 };
        let p0 = if i < ch0.len() { ch0[i].period } else { 0 };
        let p1 = if i < ch1.len() { ch1[i].period } else { 0 };
        table.push((dur, p0, p1));
    }
    table.push((0xFF, 0, 0));
    Tone2chEngine::render_note_table(&table, sample_rate)
}

fn main() {
    let args: Vec<String> = std::env::args().collect();

    if args.len() < 2 {
        print_usage();
        std::process::exit(1);
    }

    let mut input_path: Option<PathBuf> = None;
    let mut output_path = PathBuf::from("output.wav");
    let mut sample_rate: u32 = 44100;
    let mut two_ch = false;

    let mut i = 1;
    while i < args.len() {
        match args[i].as_str() {
            "-o" | "--output" => {
                i += 1;
                output_path = PathBuf::from(&args[i]);
            }
            "--sample-rate" => {
                i += 1;
                sample_rate = args[i].parse().expect("invalid sample rate");
            }
            "--2ch" => { two_ch = true; }
            "-h" | "--help" => {
                print_usage();
                return;
            }
            other => {
                if input_path.is_none() {
                    input_path = Some(PathBuf::from(other));
                } else {
                    eprintln!("unexpected argument: {}", other);
                    print_usage();
                    std::process::exit(1);
                }
            }
        }
        i += 1;
    }

    let input_path = input_path.unwrap_or_else(|| {
        eprintln!("error: no input MIDI file specified");
        print_usage();
        std::process::exit(1);
    });

    let data = std::fs::read(&input_path).unwrap_or_else(|e| {
        eprintln!("error reading {}: {}", input_path.display(), e);
        std::process::exit(1);
    });

    let notes = parse_midi(&data);
    if notes.is_empty() {
        eprintln!("warning: no notes found in {}", input_path.display());
    }

    let samples = if two_ch {
        render_2ch(&notes, sample_rate)
    } else {
        render_1ch(&notes, sample_rate)
    };

    wav::write_wav(&output_path, &samples, sample_rate).unwrap_or_else(|e| {
        eprintln!("error writing {}: {}", output_path.display(), e);
        std::process::exit(1);
    });

    eprintln!(
        "chant-host: {} notes → {} samples ({:.2}s) → {}",
        notes.len(),
        samples.len(),
        samples.len() as f64 / sample_rate as f64,
        output_path.display()
    );
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_a4_period() {
        // A4 = 440 Hz. freq_for_period inverts to a specific period.
        let period = freq_to_period(440.0);
        // Verify roundtrip: period → freq should be close to 440
        let freq_back = ToneEngine::freq_for_period(period);
        assert!((freq_back - 440.0).abs() < 50.0, "got {}", freq_back);
    }

    #[test]
    fn test_low_freq_clamps_to_255() {
        assert_eq!(freq_to_period(10.0), 255);
    }

    #[test]
    fn test_very_high_freq_clamps_to_1() {
        assert_eq!(freq_to_period(100_000.0), 1);
    }

    #[test]
    fn test_zero_freq_returns_255() {
        assert_eq!(freq_to_period(0.0), 255);
    }

    #[test]
    fn test_negative_freq_returns_255() {
        assert_eq!(freq_to_period(-100.0), 255);
    }

    #[test]
    fn test_midi_note_69_is_440() {
        let freq = midi_note_to_freq(69);
        assert!((freq - 440.0).abs() < 0.01);
    }

    #[test]
    fn test_midi_note_60_is_middle_c() {
        let freq = midi_note_to_freq(60);
        assert!((freq - 261.63).abs() < 0.1);
    }

    #[test]
    fn test_duration_conversion_positive() {
        let dur = ms_to_z80_duration(100.0, 50);
        assert!(dur >= 1);
        assert!(dur <= 254);
    }

    #[test]
    fn test_duration_zero_ms_returns_1() {
        assert_eq!(ms_to_z80_duration(0.0, 50), 1);
    }

    #[test]
    fn test_period_monotonic() {
        // Higher frequency → lower period
        let p_low = freq_to_period(220.0);
        let p_high = freq_to_period(880.0);
        assert!(p_low > p_high, "220Hz period {} should be > 880Hz period {}", p_low, p_high);
    }
}
