/**
 * High-performance HTML5 Canvas Piano Roll Visualizer.
 * Displays notes in a 2D timeline (pitch vs. time) with distinct color coding
 * for original input vs. generated continuation, and synchronized playhead animation.
 */

class PianoRollVisualizer {
  constructor(canvasId) {
    this.canvas = document.getElementById(canvasId);
    this.ctx = this.canvas ? this.canvas.getContext('2d') : null;

    this.events = [];
    this.bpm = 120;
    this.activeNoteIndex = -1;
    this.playheadSec = -1;
    this.totalDurationSec = 0;
    this.totalBeats = 0;

    // View bounds
    this.minMidi = 48; // C3 default
    this.maxMidi = 76; // E5 default
    this.keyWidth = 48; // Left piano key rail
    this.pixelsPerBeat = 40;
    this.noteHeight = 14;

    this.colors = {
      bg: '#070b16',
      gridLine: 'rgba(255, 255, 255, 0.05)',
      beatLine: 'rgba(255, 255, 255, 0.1)',
      barLine: 'rgba(255, 255, 255, 0.22)',
      whiteKey: '#1e293b',
      blackKey: '#0f172a',
      keyText: '#64748b',

      // Original melody
      origFill: '#06b6d4',
      origBorder: '#22d3ee',
      origGlow: 'rgba(6, 182, 212, 0.4)',

      // Continuation
      contFill: '#a855f7',
      contBorder: '#c084fc',
      contGlow: 'rgba(168, 85, 247, 0.4)',

      // Playhead & Active
      playhead: '#ffffff',
      activeGlow: '#ffffff'
    };

    this.setupListeners();
  }

  setupListeners() {
    window.addEventListener('resize', () => this.resizeCanvas());
  }

  resizeCanvas() {
    if (!this.canvas) return;
    const parentWidth = this.canvas.parentElement.clientWidth;
    // Calculate required width based on total beats
    const contentWidth = Math.max(parentWidth, this.keyWidth + (this.totalBeats * this.pixelsPerBeat) + 60);
    this.canvas.width = contentWidth;

    const pitchRange = Math.max(12, this.maxMidi - this.minMidi + 2);
    this.canvas.height = Math.max(220, pitchRange * this.noteHeight + 30);

    this.draw();
  }

  setMelody(events, bpm = 120) {
    this.events = events || [];
    this.bpm = bpm;
    this.activeNoteIndex = -1;
    this.playheadSec = -1;

    // Calculate bounds
    let beats = 0;
    let minP = 127;
    let maxP = 0;
    let hasNotes = false;

    for (const ev of this.events) {
      beats += (ev.duration || 1.0);
      if (!ev.is_rest && ev.midi != null) {
        hasNotes = true;
        if (ev.midi < minP) minP = ev.midi;
        if (ev.midi > maxP) maxP = ev.midi;
      }
    }

    this.totalBeats = Math.max(8, Math.ceil(beats));
    this.totalDurationSec = (this.totalBeats * 60) / this.bpm;

    if (hasNotes) {
      this.minMidi = Math.max(24, minP - 2);
      this.maxMidi = Math.min(108, maxP + 2);
    } else {
      this.minMidi = 48;
      this.maxMidi = 76;
    }

    this.resizeCanvas();
  }

  setPlayheadTime(sec) {
    this.playheadSec = sec;
    this.draw();
  }

  setActiveNote(index) {
    this.activeNoteIndex = index;
    this.draw();
  }

  draw() {
    if (!this.ctx || !this.canvas) return;
    const ctx = this.ctx;
    const width = this.canvas.width;
    const height = this.canvas.height;

    // 1. Clear background
    ctx.fillStyle = this.colors.bg;
    ctx.fillRect(0, 0, width, height);

    const pitchCount = this.maxMidi - this.minMidi + 1;
    const noteH = (height - 24) / Math.max(1, pitchCount);

    // 2. Draw Pitch Rows (Alternating black & white keys)
    for (let p = this.minMidi; p <= this.maxMidi; p++) {
      const y = height - 24 - ((p - this.minMidi + 1) * noteH);
      const isBlack = [1, 3, 6, 8, 10].includes(p % 12);

      // Row background
      ctx.fillStyle = isBlack ? 'rgba(0, 0, 0, 0.35)' : 'rgba(255, 255, 255, 0.02)';
      ctx.fillRect(this.keyWidth, y, width - this.keyWidth, noteH);

      // Left Piano Key Rail
      ctx.fillStyle = isBlack ? this.colors.blackKey : this.colors.whiteKey;
      ctx.fillRect(0, y, this.keyWidth, noteH);
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.08)';
      ctx.strokeRect(0, y, this.keyWidth, noteH);

      // Note labels on C keys
      if (p % 12 === 0) {
        const octave = Math.floor(p / 12) - 1;
        ctx.fillStyle = '#cbd5e1';
        ctx.font = 'bold 9px JetBrains Mono, monospace';
        ctx.textAlign = 'right';
        ctx.textBaseline = 'middle';
        ctx.fillText(`C${octave}`, this.keyWidth - 6, y + noteH / 2);
      }
    }

    // 3. Draw Timeline Beat / Bar Grid
    const secondsPerBeat = 60 / this.bpm;
    for (let b = 0; b <= this.totalBeats; b++) {
      const x = this.keyWidth + (b * this.pixelsPerBeat);
      const isBar = (b % 4 === 0);

      ctx.beginPath();
      ctx.strokeStyle = isBar ? this.colors.barLine : this.colors.beatLine;
      ctx.lineWidth = isBar ? 1.5 : 0.8;
      ctx.moveTo(x, 0);
      ctx.lineTo(x, height - 24);
      ctx.stroke();

      // Measure number on bottom timeline
      if (isBar) {
        ctx.fillStyle = this.colors.keyText;
        ctx.font = '10px JetBrains Mono, monospace';
        ctx.textAlign = 'center';
        ctx.fillText(`m.${(b / 4) + 1}`, x, height - 8);
      }
    }

    // 4. Render Note Blocks
    let currentBeat = 0;
    this.events.forEach((ev, idx) => {
      const dur = ev.duration || 1.0;
      const startX = this.keyWidth + (currentBeat * this.pixelsPerBeat);
      const blockW = Math.max(4, dur * this.pixelsPerBeat - 3);

      if (!ev.is_rest && ev.midi != null && ev.midi >= this.minMidi && ev.midi <= this.maxMidi) {
        const noteY = height - 24 - ((ev.midi - this.minMidi + 1) * noteH);
        const isContinuation = (ev.source === 'continuation');
        const isActive = (this.activeNoteIndex === idx);

        // Styling
        const fillColor = isContinuation ? this.colors.contFill : this.colors.origFill;
        const borderColor = isContinuation ? this.colors.contBorder : this.colors.origBorder;

        // Shadow glow for active note or high-contrast
        ctx.save();
        if (isActive) {
          ctx.shadowColor = '#ffffff';
          ctx.shadowBlur = 14;
        } else {
          ctx.shadowColor = isContinuation ? this.colors.contGlow : this.colors.origGlow;
          ctx.shadowBlur = 6;
        }

        // Draw note rectangle
        ctx.fillStyle = isActive ? '#ffffff' : fillColor;
        ctx.beginPath();
        const r = 3;
        ctx.roundRect(startX, noteY + 1, blockW, noteH - 2, r);
        ctx.fill();

        ctx.strokeStyle = isActive ? '#ffffff' : borderColor;
        ctx.lineWidth = 1.2;
        ctx.stroke();
        ctx.restore();

        // Note text inside block if width permits
        if (blockW > 24) {
          ctx.fillStyle = isActive ? '#0f172a' : '#ffffff';
          ctx.font = 'bold 9px JetBrains Mono, monospace';
          ctx.textAlign = 'center';
          ctx.textBaseline = 'middle';
          ctx.fillText(ev.pitch || '', startX + blockW / 2, noteY + noteH / 2);
        }
      }

      currentBeat += dur;
    });

    // 5. Draw Playhead Cursor
    if (this.playheadSec >= 0 && this.playheadSec <= this.totalDurationSec) {
      const currentPlayheadBeat = (this.playheadSec / 60) * this.bpm;
      const playheadX = this.keyWidth + (currentPlayheadBeat * this.pixelsPerBeat);

      ctx.save();
      ctx.beginPath();
      ctx.strokeStyle = this.colors.playhead;
      ctx.lineWidth = 2.5;
      ctx.shadowColor = '#38bdf8';
      ctx.shadowBlur = 10;
      ctx.moveTo(playheadX, 0);
      ctx.lineTo(playheadX, height - 24);
      ctx.stroke();

      // Playhead top handle triangle
      ctx.fillStyle = '#38bdf8';
      ctx.beginPath();
      ctx.moveTo(playheadX - 6, 0);
      ctx.lineTo(playheadX + 6, 0);
      ctx.lineTo(playheadX, 10);
      ctx.closePath();
      ctx.fill();
      ctx.restore();
    }
  }
}

window.PianoRollVisualizer = PianoRollVisualizer;
