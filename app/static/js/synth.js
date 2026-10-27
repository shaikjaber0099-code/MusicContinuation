/**
 * Web Audio API Synthesis Engine for Music Continuation Tool.
 * Provides polyphonic multi-timbre sound generation, robust ADSR envelopes,
 * and high-precision playback scheduling with synchronized callbacks.
 */

class WebAudioSynth {
  constructor() {
    this.ctx = null;
    this.masterGain = null;
    this.isPlaying = false;
    this.activeTimeouts = [];
    this.activeVoices = [];
    this.volume = 0.85;
    this.timbre = 'piano'; // 'piano', 'synth', 'keys', 'pluck'

    // Callbacks
    this.onNoteStart = null;
    this.onNoteEnd = null;
    this.onEnded = null;
  }

  /**
   * Initializes or resumes the AudioContext on user gesture.
   */
  async ensureContext() {
    if (!this.ctx) {
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      if (!AudioCtx) {
        throw new Error("Web Audio API is not supported in this browser.");
      }
      this.ctx = new AudioCtx();
      this.masterGain = this.ctx.createGain();
      this.masterGain.gain.setValueAtTime(this.volume, this.ctx.currentTime);
      this.masterGain.connect(this.ctx.destination);
    }

    if (this.ctx.state === 'suspended') {
      await this.ctx.resume();
    }

    // Always maintain masterGain at current volume (never 0)
    if (this.masterGain) {
      this.masterGain.gain.setValueAtTime(this.volume, this.ctx.currentTime);
    }

    return this.ctx;
  }

  setVolume(val) {
    this.volume = Math.max(0, Math.min(1, val));
    if (this.masterGain && this.ctx) {
      this.masterGain.gain.cancelScheduledValues(this.ctx.currentTime);
      this.masterGain.gain.setValueAtTime(this.volume, this.ctx.currentTime);
    }
  }

  setTimbre(timbreName) {
    this.timbre = timbreName || 'piano';
  }

  /**
   * Plays a single note immediately (used by mini virtual piano keyboard and preview chips).
   */
  async playPreviewNote(frequency, durationSec = 0.45) {
    if (!frequency || frequency <= 0) return;
    try {
      const ctx = await this.ensureContext();
      // Ensure scheduling is safely in the future to avoid DOMException
      const now = ctx.currentTime + 0.01;
      this.triggerVoice(frequency, now, durationSec, 0.95);
    } catch (e) {
      console.warn("Audio preview failed:", e);
    }
  }

  /**
   * Triggers an individual synthesized voice with timbre-specific harmonics.
   */
  triggerVoice(frequency, startTime, duration, velocity = 0.85) {
    if (!frequency || frequency <= 0 || !this.ctx) return;

    const ctx = this.ctx;
    // Guarantee start time is at least 8ms in the future of audio clock
    const t0 = Math.max(ctx.currentTime + 0.008, startTime);
    const effectiveDuration = Math.max(0.1, duration);
    const stopTime = t0 + effectiveDuration;

    const voiceGain = ctx.createGain();
    voiceGain.connect(this.masterGain);

    const baseGain = Math.max(0.08, Math.min(0.9, velocity * 0.45));
    const oscs = [];

    if (this.timbre === 'piano') {
      // Acoustic Piano: Fundamental + harmonics
      const osc1 = ctx.createOscillator();
      const osc2 = ctx.createOscillator();
      const osc3 = ctx.createOscillator();

      osc1.type = 'triangle';
      osc1.frequency.setValueAtTime(frequency, t0);

      osc2.type = 'sine';
      osc2.frequency.setValueAtTime(frequency * 2, t0);

      osc3.type = 'sine';
      osc3.frequency.setValueAtTime(frequency * 3, t0);

      const h2Gain = ctx.createGain();
      h2Gain.gain.setValueAtTime(0.28, t0);
      const h3Gain = ctx.createGain();
      h3Gain.gain.setValueAtTime(0.12, t0);

      osc1.connect(voiceGain);
      osc2.connect(h2Gain);
      h2Gain.connect(voiceGain);
      osc3.connect(h3Gain);
      h3Gain.connect(voiceGain);

      oscs.push(osc1, osc2, osc3);

      // ADSR Piano Envelope
      voiceGain.gain.setValueAtTime(0.001, t0);
      voiceGain.gain.linearRampToValueAtTime(baseGain, t0 + 0.018);
      voiceGain.gain.exponentialRampToValueAtTime(Math.max(0.001, baseGain * 0.65), t0 + 0.1);
      voiceGain.gain.exponentialRampToValueAtTime(0.0001, stopTime + 0.12);

    } else if (this.timbre === 'synth') {
      // Warm Analog Synth: Sawtooth through lowpass resonant filter
      const osc = ctx.createOscillator();
      osc.type = 'sawtooth';
      osc.frequency.setValueAtTime(frequency, t0);

      const filter = ctx.createBiquadFilter();
      filter.type = 'lowpass';
      filter.frequency.setValueAtTime(Math.min(8000, frequency * 4), t0);
      filter.frequency.exponentialRampToValueAtTime(Math.max(250, frequency * 1.5), stopTime);

      osc.connect(filter);
      filter.connect(voiceGain);
      oscs.push(osc);

      voiceGain.gain.setValueAtTime(0.001, t0);
      voiceGain.gain.linearRampToValueAtTime(baseGain * 0.75, t0 + 0.025);
      voiceGain.gain.exponentialRampToValueAtTime(0.0001, stopTime + 0.1);

    } else if (this.timbre === 'pluck') {
      // Marimba / Pluck: Sine fundamental + triangle mallet strike with rapid percussive attack
      const osc1 = ctx.createOscillator();
      osc1.type = 'sine';
      osc1.frequency.setValueAtTime(frequency, t0);

      const osc2 = ctx.createOscillator();
      osc2.type = 'triangle';
      osc2.frequency.setValueAtTime(frequency * 3, t0); // Mallet overtone

      const malletGain = ctx.createGain();
      malletGain.gain.setValueAtTime(0.3, t0);
      malletGain.gain.exponentialRampToValueAtTime(0.0001, t0 + 0.05);

      osc1.connect(voiceGain);
      osc2.connect(malletGain);
      malletGain.connect(voiceGain);
      oscs.push(osc1, osc2);

      const decayEnd = Math.min(stopTime, t0 + 0.65);
      voiceGain.gain.setValueAtTime(0.001, t0);
      voiceGain.gain.linearRampToValueAtTime(baseGain * 0.95, t0 + 0.006);
      voiceGain.gain.exponentialRampToValueAtTime(0.0001, decayEnd);

    } else {
      // Electric Keys (Sine + Square blend)
      const osc1 = ctx.createOscillator();
      osc1.type = 'sine';
      osc1.frequency.setValueAtTime(frequency, t0);

      const osc2 = ctx.createOscillator();
      osc2.type = 'square';
      osc2.frequency.setValueAtTime(frequency, t0);

      const sqGain = ctx.createGain();
      sqGain.gain.setValueAtTime(0.2, t0);

      osc1.connect(voiceGain);
      osc2.connect(sqGain);
      sqGain.connect(voiceGain);
      oscs.push(osc1, osc2);

      voiceGain.gain.setValueAtTime(0.001, t0);
      voiceGain.gain.linearRampToValueAtTime(baseGain * 0.8, t0 + 0.02);
      voiceGain.gain.exponentialRampToValueAtTime(0.0001, stopTime + 0.1);
    }

    // Start all oscillators and schedule stop
    oscs.forEach(osc => {
      osc.start(t0);
      osc.stop(stopTime + 0.25);
    });

    const voiceRecord = { oscs, voiceGain, stopTime: stopTime + 0.25 };
    this.activeVoices.push(voiceRecord);

    setTimeout(() => {
      const idx = this.activeVoices.indexOf(voiceRecord);
      if (idx !== -1) this.activeVoices.splice(idx, 1);
    }, (stopTime + 0.3 - ctx.currentTime) * 1000);
  }

  /**
   * Plays a scheduled sequence of notes.
   */
  async playSchedule(schedule) {
    if (!schedule || schedule.length === 0) {
      return { startTime: 0, totalDuration: 0 };
    }

    await this.ensureContext();
    this.stop(); // Stop any currently sounding notes

    this.isPlaying = true;
    const ctx = this.ctx;
    const scheduleStartTime = ctx.currentTime + 0.06; // 60ms safe buffer

    let maxEndTime = 0;

    schedule.forEach((note, idx) => {
      const noteStartTime = scheduleStartTime + note.start_time;
      const noteDuration = Math.max(0.08, note.duration);
      const noteEndTime = noteStartTime + noteDuration;

      if (noteEndTime > maxEndTime) {
        maxEndTime = noteEndTime;
      }

      // Schedule Web Audio synthesis voice
      this.triggerVoice(note.frequency_hz, noteStartTime, noteDuration, 0.9);

      // UI Note Start Timeout
      const startDelayMs = Math.max(0, (noteStartTime - ctx.currentTime) * 1000);
      const startTid = setTimeout(() => {
        if (!this.isPlaying) return;
        if (this.onNoteStart) {
          this.onNoteStart(idx, note);
        }
      }, startDelayMs);
      this.activeTimeouts.push(startTid);

      // UI Note End Timeout
      const endDelayMs = Math.max(0, (noteEndTime - ctx.currentTime) * 1000);
      const endTid = setTimeout(() => {
        if (!this.isPlaying) return;
        if (this.onNoteEnd) {
          this.onNoteEnd(idx, note);
        }
      }, endDelayMs);
      this.activeTimeouts.push(endTid);
    });

    const totalDurationSec = maxEndTime - scheduleStartTime;
    const completeDelayMs = Math.max(0, (maxEndTime - ctx.currentTime) * 1000) + 120;

    const completeTid = setTimeout(() => {
      if (!this.isPlaying) return;
      this.isPlaying = false;
      if (this.onEnded) {
        this.onEnded();
      }
    }, completeDelayMs);
    this.activeTimeouts.push(completeTid);

    return {
      startTime: scheduleStartTime,
      totalDuration: totalDurationSec
    };
  }

  /**
   * Halts all scheduled audio and active oscillators immediately.
   */
  stop() {
    this.isPlaying = false;

    // Clear all scheduled timeouts
    this.activeTimeouts.forEach(tid => clearTimeout(tid));
    this.activeTimeouts = [];

    // Stop active sounding voices
    if (this.activeVoices && this.activeVoices.length > 0) {
      this.activeVoices.forEach(v => {
        try {
          if (v.voiceGain && this.ctx) {
            v.voiceGain.gain.cancelScheduledValues(this.ctx.currentTime);
            v.voiceGain.gain.setValueAtTime(0, this.ctx.currentTime);
          }
          if (v.oscs) {
            v.oscs.forEach(osc => {
              try { osc.stop(); } catch (e) {}
            });
          }
        } catch (e) {}
      });
      this.activeVoices = [];
    }

    // Keep masterGain at volume (never mute to 0)
    if (this.masterGain && this.ctx) {
      this.masterGain.gain.cancelScheduledValues(this.ctx.currentTime);
      this.masterGain.gain.setValueAtTime(this.volume, this.ctx.currentTime);
    }
  }
}

// Global synth instance
window.musicSynth = new WebAudioSynth();
