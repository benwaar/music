use nih_plug::prelude::*;
use std::sync::Arc;

use eno_state_zx::tone_2ch::Tone2chEngine;

fn midi_note_to_period(note: u8) -> u8 {
    let freq = 440.0_f64 * 2.0_f64.powf((note as f64 - 69.0) / 12.0);
    let period = (3_500_000.0 / (2.0 * freq * 45.0)).round() as i64;
    period.clamp(1, 255) as u8
}

struct BeeperSynth {
    params: Arc<BeeperParams>,
    engine: Tone2chEngine,
    sample_rate: u32,
}

#[derive(Params)]
struct BeeperParams {
    #[id = "detune"]
    pub detune: IntParam,
}

impl Default for BeeperParams {
    fn default() -> Self {
        Self {
            detune: IntParam::new("Detune", 1, IntRange::Linear { min: 1, max: 127 }),
        }
    }
}

impl Default for BeeperSynth {
    fn default() -> Self {
        Self {
            params: Arc::new(BeeperParams::default()),
            engine: Tone2chEngine::new(255, 255),
            sample_rate: 44100,
        }
    }
}

impl Plugin for BeeperSynth {
    const NAME: &'static str = "Eno State ZX";
    const VENDOR: &'static str = "beepers";
    const URL: &'static str = "";
    const EMAIL: &'static str = "";
    const VERSION: &'static str = env!("CARGO_PKG_VERSION");

    const AUDIO_IO_LAYOUTS: &'static [AudioIOLayout] = &[AudioIOLayout {
        main_input_channels: None,
        main_output_channels: NonZeroU32::new(2),
        ..AudioIOLayout::const_default()
    }];

    const MIDI_INPUT: MidiConfig = MidiConfig::Basic;
    type SysExMessage = ();
    type BackgroundTask = ();

    fn params(&self) -> Arc<dyn Params> {
        self.params.clone()
    }

    fn initialize(
        &mut self,
        _audio_io_layout: &AudioIOLayout,
        buffer_config: &BufferConfig,
        _context: &mut impl InitContext<Self>,
    ) -> bool {
        self.sample_rate = buffer_config.sample_rate as u32;
        true
    }

    fn reset(&mut self) {
        self.engine = Tone2chEngine::new(255, 255);
    }

    fn process(
        &mut self,
        buffer: &mut Buffer,
        _aux: &mut AuxiliaryBuffers,
        context: &mut impl ProcessContext<Self>,
    ) -> ProcessStatus {
        let sample_rate = self.sample_rate;
        let detune = self.params.detune.value() as u8;

        let mut next_event = context.next_event();

        for (sample_id, channel_samples) in buffer.iter_samples().enumerate() {
            while let Some(event) = next_event {
                if event.timing() > sample_id as u32 {
                    break;
                }
                match event {
                    NoteEvent::NoteOn { note, velocity, .. } if velocity > 0.0 => {
                        let ch1 = midi_note_to_period(note);
                        let ch2 = (ch1 as u16 + detune as u16).min(255).max(1) as u8;
                        self.engine.set_note(ch1, ch2);
                    }
                    NoteEvent::NoteOn { .. } | NoteEvent::NoteOff { .. } => {
                        self.engine.set_note(255, 255);
                    }
                    _ => {}
                }
                next_event = context.next_event();
            }

            let s = self.engine.sample(sample_rate);
            for channel_sample in channel_samples {
                *channel_sample = s;
            }
        }

        ProcessStatus::Normal
    }
}

impl ClapPlugin for BeeperSynth {
    const CLAP_ID: &'static str = "com.beepers.eno-state-zx";
    const CLAP_DESCRIPTION: Option<&'static str> = Some("1-bit Z80 beeper synth");
    const CLAP_MANUAL_URL: Option<&'static str> = None;
    const CLAP_SUPPORT_URL: Option<&'static str> = None;
    const CLAP_FEATURES: &'static [ClapFeature] = &[
        ClapFeature::Synthesizer,
        ClapFeature::Mono,
    ];
}

impl Vst3Plugin for BeeperSynth {
    const VST3_CLASS_ID: [u8; 16] = *b"EnoStateZX_v0001";
    const VST3_SUBCATEGORIES: &'static [Vst3SubCategory] = &[
        Vst3SubCategory::Synth,
        Vst3SubCategory::Instrument,
    ];
}

nih_export_clap!(BeeperSynth);
nih_export_vst3!(BeeperSynth);
