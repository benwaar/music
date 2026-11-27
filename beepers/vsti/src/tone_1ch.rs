/// 1-channel tone engine — faithful port of the Z80 period-countdown algorithm.
///
/// Same algorithm as zx/beeper.asm (exercise 1.10): an 8-bit period counter
/// decrements each "tick" (24 T-states). When it hits zero, the speaker toggles
/// and the counter reloads. This gives the exact same frequencies as the Spectrum.
///
/// No floats in the timing path — all T-state tracking uses integer arithmetic.

const CPU_CLOCK: u64 = 3_500_000;
const T_PER_TICK: u64 = 24; // DEC D (4) + NOP (4) + NOP (4) + JR NZ (12)
const T_TOGGLE_OVERHEAD: u64 = 57; // toggle path total T-states when D hits zero

pub struct ToneEngine {
    period: u8,      // E register — pitch value (1-255, 0 = silent)
    counter: u8,     // D register — counts down each tick
    speaker: bool,   // current 1-bit output state
    t_count: u64,    // global T-state counter (cumulative from time 0)
    sample_num: u64, // how many audio samples have been produced
}

impl ToneEngine {
    pub fn new(period: u8) -> Self {
        Self {
            period,
            counter: period,
            speaker: false,
            t_count: 0,
            sample_num: 0,
        }
    }

    pub fn set_period(&mut self, period: u8) {
        self.period = period;
        self.counter = period;
        // speaker state carries over — no reset, no click between notes
    }

    /// Advance by one audio sample, return output (-1.0 or +1.0).
    pub fn sample(&mut self, sample_rate: u32) -> f32 {
        if self.period == 0 {
            return 0.0; // silence (rest)
        }

        self.sample_num += 1;
        let target_t = (self.sample_num * CPU_CLOCK) / sample_rate as u64;

        // consume T-states in tick-sized chunks until we reach the target
        while self.t_count < target_t {
            // guard: reload a stale zero counter before decrementing
            if self.counter == 0 {
                self.counter = self.period;
            }

            self.counter -= 1;

            if self.counter == 0 {
                // toggle path costs 57T total instead of the normal 24T
                self.t_count += T_TOGGLE_OVERHEAD;
                self.speaker = !self.speaker;
                self.counter = self.period;
            } else {
                self.t_count += T_PER_TICK;
            }
        }

        if self.speaker { 1.0 } else { -1.0 }
    }

    /// Calculate the frequency for a given period value (matches the Z80 formula).
    pub fn freq_for_period(period: u8) -> f64 {
        if period == 0 {
            return 0.0;
        }
        let half_cycle = ((period as f64 - 1.0) * T_PER_TICK as f64) + T_TOGGLE_OVERHEAD as f64;
        CPU_CLOCK as f64 / (2.0 * half_cycle)
    }

    /// Render a note table to an audio buffer.
    ///
    /// Format matches the Z80 exactly: slice of (duration, period) pairs.
    /// Duration = number of 256-toggle groups (C register value).
    /// Period = pitch (1-255). Sentinel 0xFF in duration = stop.
    pub fn render_note_table(notes: &[(u8, u8)], sample_rate: u32) -> Vec<f32> {
        let mut output = Vec::new();
        let mut engine = ToneEngine::new(0);
        let mut t_target: u64 = 0; // running T-state deadline (no gaps between notes)

        for &(duration, period) in notes {
            if duration == 0xFF {
                break;
            }

            engine.set_period(period);

            // add this note's total T-states to the running target
            let half_cycle_t: u64 = if period > 0 {
                ((period as u64 - 1) * T_PER_TICK) + T_TOGGLE_OVERHEAD
            } else {
                (254 * T_PER_TICK) + T_TOGGLE_OVERHEAD
            };
            let total_toggles = duration as u64 * 256;
            t_target += total_toggles * half_cycle_t;

            // render samples until the engine reaches this note's end
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

/// The D major scale from zx/beeper.asm — same periods, same order.
pub const D_MAJOR_SCALE: [(u8, u8); 16] = [
    (3, 248),  // D4
    (3, 221),  // E4
    (3, 197),  // F#4
    (3, 186),  // G4
    (3, 166),  // A4
    (3, 148),  // B4
    (3, 132),  // C#5
    (6, 124),  // D5 (held)
    (3, 124),  // D5
    (3, 132),  // C#5
    (3, 148),  // B4
    (3, 166),  // A4
    (3, 186),  // G4
    (3, 197),  // F#4
    (3, 221),  // E4
    (6, 248),  // D4 (held)
];

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn speaker_is_square_wave() {
        let mut engine = ToneEngine::new(86);
        for _ in 0..1000 {
            let s = engine.sample(44100);
            assert!(s == 1.0 || s == -1.0, "output must be +1 or -1, got {s}");
        }
    }

    #[test]
    fn period_86_frequency() {
        let expected = ToneEngine::freq_for_period(86);
        let sample_rate = 44100;
        let mut engine = ToneEngine::new(86);

        // render 0.1 seconds, count zero-crossings
        let num_samples = sample_rate / 10;
        let mut crossings = 0u32;
        let mut prev = engine.sample(sample_rate);
        for _ in 1..num_samples {
            let s = engine.sample(sample_rate);
            if (s > 0.0) != (prev > 0.0) {
                crossings += 1;
            }
            prev = s;
        }

        // each full cycle has 2 crossings
        let measured_freq = crossings as f64 / 2.0 * 10.0;
        let tolerance = expected * 0.03; // 3% tolerance (integer rounding is marginally coarser)
        assert!(
            (measured_freq - expected).abs() < tolerance,
            "expected ~{expected:.0} Hz, measured {measured_freq:.0} Hz"
        );
    }

    #[test]
    fn period_doubles_octave() {
        let freq_high = ToneEngine::freq_for_period(124); // D5
        let freq_low = ToneEngine::freq_for_period(248);  // D4
        let ratio = freq_high / freq_low;
        assert!(
            (ratio - 2.0).abs() < 0.05,
            "D5/D4 ratio should be ~2.0, got {ratio:.3}"
        );
    }

    #[test]
    fn scale_has_correct_length() {
        let sample_rate = 44100;
        let buf = ToneEngine::render_note_table(&D_MAJOR_SCALE, sample_rate);

        // total duration = sum of (duration × 256 × half_cycle_t / CPU_CLOCK) for each note
        // rough: 15 notes × 3dur + 1 note × 6dur = 51 groups × 256 toggles
        // at average period ~180: half_cycle ≈ (179*24)+57 = 4353 T
        // total ≈ 51 * 256 * 4353 / 3_500_000 ≈ 16.2 seconds? No that's too long.
        // Actually: each note 3 groups × 256 toggles × ~2000T half-cycle ≈ 0.44s
        // 15 × 0.44 + 1 × 0.88 ≈ 7.5 seconds → ~330k samples at 44.1kHz

        // just check it's reasonable: between 10 and 25 seconds
        // (15 notes × ~1s + 2 held notes × ~2s ≈ 17s)
        let seconds = buf.len() as f64 / sample_rate as f64;
        assert!(
            seconds > 10.0 && seconds < 25.0,
            "scale should be 10-25 seconds, got {seconds:.1}s"
        );
    }

    #[test]
    fn silence_for_period_zero() {
        let mut engine = ToneEngine::new(0);
        for _ in 0..100 {
            assert_eq!(engine.sample(44100), 0.0);
        }
    }
}
