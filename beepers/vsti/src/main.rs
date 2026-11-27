use eno_state_zx::tone_1ch::{ToneEngine, D_MAJOR_SCALE};
use eno_state_zx::tone_2ch::{Tone2chEngine, BLUE_DANUBE, D_MAJOR_SCALE_2CH};
use eno_state_zx::wav;
use std::path::PathBuf;

fn print_usage() {
    eprintln!("Usage: beeper-synth [--demo | --2ch] [-o output.wav] [--sample-rate 44100]");
    eprintln!();
    eprintln!("  --demo    1ch tone engine — D major scale (default)");
    eprintln!("  --2ch     2ch interleave engine — D major scale with chorus");
    eprintln!("  --danube  2ch interleave engine — The Blue Danube (Manic Miner)");
}

fn main() {
    let args: Vec<String> = std::env::args().collect();

    let mut output_path = PathBuf::from("demo.wav");
    let mut sample_rate: u32 = 44100;
    let mut mode = "1ch";

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
            "--demo" => { mode = "1ch"; }
            "--2ch" => { mode = "2ch"; }
            "--danube" => { mode = "danube"; }
            "-h" | "--help" => {
                print_usage();
                return;
            }
            _ => {
                eprintln!("unknown argument: {}", args[i]);
                print_usage();
                std::process::exit(1);
            }
        }
        i += 1;
    }

    let (samples, label) = match mode {
        "1ch" => (
            ToneEngine::render_note_table(&D_MAJOR_SCALE, sample_rate),
            "1ch D major scale",
        ),
        "2ch" => (
            Tone2chEngine::render_note_table(&D_MAJOR_SCALE_2CH, sample_rate),
            "2ch D major scale (chorus)",
        ),
        "danube" => (
            Tone2chEngine::render_note_table(&BLUE_DANUBE, sample_rate),
            "2ch Blue Danube (Manic Miner)",
        ),
        _ => unreachable!(),
    };

    wav::write_wav(&output_path, &samples, sample_rate).expect("failed to write WAV");

    eprintln!(
        "{}: wrote {} samples ({:.2}s) to {}",
        label,
        samples.len(),
        samples.len() as f64 / sample_rate as f64,
        output_path.display()
    );
}
