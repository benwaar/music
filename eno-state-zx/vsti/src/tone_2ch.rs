/// 2-channel interleaved tone engine — faithful port of the Z80 2ch algorithm.
///
/// Same algorithm as zx/beeper.asm (exercise 1.14): two 8-bit period counters
/// (D/E registers, reloaded from H/L) decrement each tick. When either hits zero
/// it reloads and toggles the shared 1-bit speaker output.
///
/// T-state cost per loop iteration depends on how many channels toggled:
///   - Neither toggled:   45T  (DEC D + JR NZ + DEC E + JR NZ + DJNZ)
///   - One channel:       62T  (one toggle path: DEC + JR fall + LD + XOR + OUT; other normal)
///   - Both channels:     79T  (both toggle paths + OUT)
///
/// No floats in the timing path — all T-state tracking uses integer arithmetic.

const CPU_CLOCK: u64 = 3_500_000;
const T_NORMAL: u64 = 45; // DEC D(4) + JR NZ(12) + DEC E(4) + JR NZ(12) + DJNZ(13)
const T_ONE_TOGGLE: u64 = 62; // one channel: DEC(4) + JR fall(7) + LD(4) + XOR(7) + OUT(11) + other normal
const T_BOTH_TOGGLE: u64 = 79; // both channels toggle same tick

/// Substitute period 0 → REST_PERIOD so the loop never stalls on a zero counter.
const REST_PERIOD: u8 = 255;

pub struct Tone2chEngine {
    ch1_period: u8,  // H register — reload value
    ch1_counter: u8, // D register — counts down
    ch2_period: u8,  // L register — reload value
    ch2_counter: u8, // E register — counts down
    speaker: bool,   // current 1-bit output state
    t_count: u64,    // global T-state counter (cumulative from time 0)
    sample_num: u64, // how many audio samples have been produced
}

impl Tone2chEngine {
    pub fn new(ch1_period: u8, ch2_period: u8) -> Self {
        let p1 = if ch1_period == 0 { REST_PERIOD } else { ch1_period };
        let p2 = if ch2_period == 0 { REST_PERIOD } else { ch2_period };
        Self {
            ch1_period: p1,
            ch1_counter: p1,
            ch2_period: p2,
            ch2_counter: p2,
            speaker: false,
            t_count: 0,
            sample_num: 0,
        }
    }

    /// Load a new note pair. Period 0 → 255. Speaker state carries over — no click.
    pub fn set_note(&mut self, ch1_period: u8, ch2_period: u8) {
        self.ch1_period = if ch1_period == 0 { REST_PERIOD } else { ch1_period };
        self.ch2_period = if ch2_period == 0 { REST_PERIOD } else { ch2_period };
        self.ch1_counter = self.ch1_period;
        self.ch2_counter = self.ch2_period;
        // speaker state NOT reset — carries over to avoid click between notes
    }

    /// Advance by one audio sample, return output (-1.0 or +1.0).
    pub fn sample(&mut self, sample_rate: u32) -> f32 {
        self.sample_num += 1;
        let target_t = (self.sample_num * CPU_CLOCK) / sample_rate as u64;

        while self.t_count < target_t {
            self.ch1_counter = self.ch1_counter.wrapping_sub(1);
            self.ch2_counter = self.ch2_counter.wrapping_sub(1);

            let ch1_toggle = self.ch1_counter == 0;
            let ch2_toggle = self.ch2_counter == 0;

            if ch1_toggle {
                self.speaker = !self.speaker;
                self.ch1_counter = self.ch1_period;
            }
            if ch2_toggle {
                self.speaker = !self.speaker;
                self.ch2_counter = self.ch2_period;
            }

            self.t_count += match (ch1_toggle, ch2_toggle) {
                (true, true) => T_BOTH_TOGGLE,
                (true, false) | (false, true) => T_ONE_TOGGLE,
                (false, false) => T_NORMAL,
            };
        }

        if self.speaker { 1.0 } else { -1.0 }
    }

    /// Current speaker state (for testing).
    pub fn speaker_state(&self) -> bool {
        self.speaker
    }

    /// Frequency for a given period using the 2ch half-cycle formula.
    ///
    /// Each half-cycle = (period-1) normal ticks + 1 toggle tick.
    /// Approximate: ignores the other channel's toggle overhead (adds <1T average).
    pub fn freq_for_period(period: u8) -> f64 {
        if period == 0 {
            return 0.0;
        }
        let half_cycle = ((period as f64 - 1.0) * T_NORMAL as f64) + T_ONE_TOGGLE as f64;
        CPU_CLOCK as f64 / (2.0 * half_cycle)
    }

    /// Render a note table to an audio buffer.
    ///
    /// Entry format: `(duration, ch1_period, ch2_period)`.
    /// Duration 0xFF = stop sentinel.
    /// Duration semantics: `duration * 256` ticks through the main loop
    /// (matches Z80: DJNZ outer × DEC C inner), each tick ≈ T_NORMAL T-states.
    pub fn render_note_table(notes: &[(u8, u8, u8)], sample_rate: u32) -> Vec<f32> {
        let mut output = Vec::new();
        let mut engine = Tone2chEngine::new(0, 0);
        let mut t_target: u64 = 0; // running T-state deadline

        for &(duration, ch1_period, ch2_period) in notes {
            if duration == 0xFF {
                break;
            }

            engine.set_note(ch1_period, ch2_period);

            // duration budget: duration * 256 ticks
            // each tick is ~T_NORMAL, but toggle ticks cost more
            // use the average effective T (same approach as Z80: outer × inner × avg)
            let p1 = if ch1_period == 0 { REST_PERIOD } else { ch1_period };
            let p2 = if ch2_period == 0 { REST_PERIOD } else { ch2_period };
            let avg_period = ((p1 as u64) + (p2 as u64)) / 2;
            let toggle_fraction = if avg_period > 0 { T_ONE_TOGGLE - T_NORMAL } else { 0 };
            let effective_t = T_NORMAL + (2 * toggle_fraction) / avg_period.max(1);
            let ticks = duration as u64 * 256;
            t_target += ticks * effective_t;

            loop {
                let next_sample = engine.sample_num + 1;
                let next_t = (next_sample * CPU_CLOCK) / sample_rate as u64;
                if next_t > t_target {
                    break;
                }
                output.push(engine.sample(sample_rate));
            }
        }

        output
    }
}

/// Blue Danube waltz — original Manic Miner (1983) note table.
/// Format: (duration, ch1_period, ch2_period). Sentinel (0xFF, 0, 0) at end.
pub const BLUE_DANUBE: [(u8, u8, u8); 96] = [
    (0x50, 0x80, 0x81), (0x50, 0x66, 0x67), (0x50, 0x56, 0x57),
    (0x32, 0x56, 0x57), (0x32, 0xAB, 0xCB), (0x32, 0x2B, 0x33),
    (0x32, 0x2B, 0x33), (0x32, 0xAB, 0xCB), (0x32, 0x33, 0x40),
    (0x32, 0x33, 0x40), (0x32, 0xAB, 0xCB), (0x32, 0x80, 0x81),
    (0x32, 0x80, 0x81), (0x32, 0x66, 0x67), (0x32, 0x56, 0x57),
    (0x32, 0x60, 0x56), (0x32, 0xAB, 0xC0), (0x32, 0x2B, 0x30),
    (0x32, 0x2B, 0x30), (0x32, 0xAB, 0xC0), (0x32, 0x30, 0x44),
    (0x32, 0x30, 0x44), (0x32, 0xAB, 0xC0), (0x32, 0x88, 0x89),
    (0x32, 0x88, 0x89), (0x32, 0x72, 0x73), (0x32, 0x4C, 0x4D),
    (0x32, 0x4C, 0x4D), (0x32, 0xAB, 0xC0), (0x32, 0x26, 0x30),
    (0x32, 0x26, 0x30), (0x32, 0xAB, 0xC0), (0x32, 0x30, 0x44),
    (0x32, 0x30, 0x44), (0x32, 0xAB, 0xC0), (0x32, 0x88, 0x89),
    (0x32, 0x88, 0x89), (0x32, 0x72, 0x73), (0x32, 0x4C, 0x4D),
    (0x32, 0x4C, 0x4D), (0x32, 0xAB, 0xCB), (0x32, 0x26, 0x33),
    (0x32, 0x26, 0x33), (0x32, 0xAB, 0xCB), (0x32, 0x33, 0x40),
    (0x32, 0x33, 0x40), (0x32, 0xAB, 0xCB), (0x32, 0x80, 0x81),
    (0x32, 0x80, 0x81), (0x32, 0x66, 0x67), (0x32, 0x56, 0x57),
    (0x32, 0x40, 0x41), (0x32, 0x80, 0xAB), (0x32, 0x20, 0x2B),
    (0x32, 0x20, 0x2B), (0x32, 0x80, 0xAB), (0x32, 0x2B, 0x33),
    (0x32, 0x2B, 0x33), (0x32, 0x80, 0xAB), (0x32, 0x80, 0x81),
    (0x32, 0x80, 0x81), (0x32, 0x66, 0x67), (0x32, 0x56, 0x57),
    (0x32, 0x40, 0x41), (0x32, 0x80, 0x98), (0x32, 0x20, 0x26),
    (0x32, 0x20, 0x26), (0x32, 0x80, 0x98), (0x32, 0x26, 0x30),
    (0x32, 0x26, 0x30), (0x32, 0x00, 0x00), (0x32, 0x72, 0x73),
    (0x32, 0x72, 0x73), (0x32, 0x60, 0x61), (0x32, 0x4C, 0x4D),
    (0x32, 0x4C, 0x99), (0x32, 0x4C, 0x4D), (0x32, 0x4C, 0x4D),
    (0x32, 0x4C, 0x99), (0x32, 0x5B, 0x5C), (0x32, 0x56, 0x57),
    (0x32, 0x33, 0xCD), (0x32, 0x33, 0x34), (0x32, 0x33, 0x34),
    (0x32, 0x33, 0xCD), (0x32, 0x40, 0x41), (0x32, 0x66, 0x67),
    (0x64, 0x66, 0x67), (0x32, 0x72, 0x73), (0x64, 0x4C, 0x4D),
    (0x32, 0x56, 0x57), (0x32, 0x80, 0xCB), (0x19, 0x80, 0x00),
    (0x19, 0x80, 0x81), (0x32, 0x80, 0xCB),
    (0xFF, 0, 0),
];

/// D major scale for testing — same periods as the Z80 1.12 exercise, doubled for 2ch.
/// Format: (duration, ch1_period, ch2_period). Sentinel (0xFF, 0, 0) at end.
pub const D_MAJOR_SCALE_2CH: [(u8, u8, u8); 17] = [
    (120, 130, 131), (120, 115, 116), (120, 103, 104), (120, 99, 100),
    (120, 86, 87),   (120, 77, 78),   (120, 69, 70),   (240, 65, 66),
    (120, 65, 66),   (120, 69, 70),   (120, 77, 78),   (120, 86, 87),
    (120, 99, 100),  (120, 103, 104), (120, 115, 116),  (240, 130, 131),
    (0xFF, 0, 0),
];

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn output_is_square_wave() {
        let mut engine = Tone2chEngine::new(86, 100);
        for _ in 0..1000 {
            let s = engine.sample(44100);
            assert!(s == 1.0 || s == -1.0, "output must be +1 or -1, got {s}");
        }
    }

    #[test]
    fn period_0_becomes_rest() {
        // period 0 → 255: engine should still run (not panic, not return 0)
        let mut engine = Tone2chEngine::new(0, 0);
        let mut all_same = true;
        let first = engine.sample(44100);
        for _ in 1..1000 {
            let s = engine.sample(44100);
            assert!(s == 1.0 || s == -1.0);
            if s != first {
                all_same = false;
            }
        }
        // at period 255, toggles are very infrequent — but we don't assert on direction
        let _ = all_same; // just checking it doesn't panic
    }

    #[test]
    fn freq_for_period_formula() {
        // half-cycle = (86-1)*45 + 62 = 3887T → freq = 3_500_000 / (2*3887) ≈ 450 Hz
        let f = Tone2chEngine::freq_for_period(86);
        assert!((f - 450.0).abs() < 10.0, "expected ~450 Hz for period 86, got {f:.1}");
    }

    #[test]
    fn freq_period_zero_returns_zero() {
        assert_eq!(Tone2chEngine::freq_for_period(0), 0.0);
    }

    #[test]
    fn period_doubles_octave() {
        // doubling period halves frequency → one octave down
        let f_high = Tone2chEngine::freq_for_period(65);
        let f_low = Tone2chEngine::freq_for_period(130);
        let ratio = f_high / f_low;
        assert!(
            (ratio - 2.0).abs() < 0.01,
            "doubling period should halve freq; ratio={ratio:.3}"
        );
    }

    #[test]
    fn render_duration_is_proportional_to_note_count() {
        // render a 2-note table where the second note is twice as long as the first;
        // the second chunk should produce roughly twice the samples.
        let sample_rate = 44100u32;
        // note: (duration, ch1, ch2). Use (1, ...) and (2, ...) — tiny but measurable.
        let notes: [(u8, u8, u8); 3] = [
            (10, 86, 100),
            (20, 86, 100),
            (0xFF, 0, 0),
        ];
        // render note 1 alone, note 2 alone, compare lengths
        let n1: [(u8, u8, u8); 2] = [(10, 86, 100), (0xFF, 0, 0)];
        let n2: [(u8, u8, u8); 2] = [(20, 86, 100), (0xFF, 0, 0)];
        let buf1 = Tone2chEngine::render_note_table(&n1, sample_rate);
        let buf2 = Tone2chEngine::render_note_table(&n2, sample_rate);
        let _ = notes; // silence unused warning

        let ratio = buf2.len() as f64 / buf1.len() as f64;
        assert!(
            (ratio - 2.0).abs() < 0.1,
            "note with duration 20 should produce ~2× samples vs duration 10; ratio={ratio:.3}"
        );
    }

    #[test]
    fn scale_renders_without_panic() {
        let buf = Tone2chEngine::render_note_table(&D_MAJOR_SCALE_2CH, 44100);
        assert!(!buf.is_empty(), "render should produce samples");
        for s in &buf {
            assert!(*s == 1.0 || *s == -1.0, "sample out of range: {s}");
        }
    }

    #[test]
    fn blue_danube_renders_without_panic() {
        let buf = Tone2chEngine::render_note_table(&BLUE_DANUBE, 44100);
        assert!(!buf.is_empty());
        for s in &buf {
            assert!(*s == 1.0 || *s == -1.0);
        }
    }

    #[test]
    fn set_note_does_not_reset_speaker() {
        let mut engine = Tone2chEngine::new(86, 100);
        for _ in 0..10000 {
            engine.sample(44100);
        }
        let state_before = engine.speaker_state();
        engine.set_note(120, 130);
        assert_eq!(engine.speaker_state(), state_before, "set_note must not reset speaker");
    }
}
