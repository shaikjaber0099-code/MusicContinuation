/**
 * Main Frontend Application Controller for Music Continuation Tool.
 * Manages user inputs, API synchronization, audio playback scheduling,
 * and piano roll visualization.
 */

document.addEventListener('DOMContentLoaded', () => {
  // DOM Elements
  const tabManual = document.getElementById('tabManual');
  const tabMidi = document.getElementById('tabMidi');
  const manualInputArea = document.getElementById('manualInputArea');
  const midiUploadArea = document.getElementById('midiUploadArea');
  const melodyInput = document.getElementById('melodyInput');
  const fileInput = document.getElementById('fileInput');
  const dropzone = document.getElementById('dropzone');
  const selectedFileInfo = document.getElementById('selectedFileInfo');
  const selectedFileName = document.getElementById('selectedFileName');
  const removeFileBtn = document.getElementById('removeFileBtn');

  // Preview & Input Playback elements
  const inputPreviewBox = document.getElementById('inputPreviewBox');
  const inputPreviewNotes = document.getElementById('inputPreviewNotes');
  const inputPreviewCount = document.getElementById('inputPreviewCount');
  const btnPlayInput = document.getElementById('btnPlayInput');
  const btnStopInput = document.getElementById('btnStopInput');
  const presetLyricsCard = document.getElementById('presetLyricsCard');
  const lyricsLinesContainer = document.getElementById('lyricsLinesContainer');
  const presetSongTitle = document.getElementById('presetSongTitle');

  // Controls & Settings
  const presetPills = document.querySelectorAll('.preset-pill');
  const selectLength = document.getElementById('selectLength');
  const sliderTemp = document.getElementById('sliderTemp');
  const tempValBadge = document.getElementById('tempValBadge');
  const sliderBpm = document.getElementById('sliderBpm');
  const bpmValBadge = document.getElementById('bpmValBadge');
  const selectTimbre = document.getElementById('selectTimbre');

  // Primary Action & Status
  const btnGenerate = document.getElementById('btnGenerate');
  const statusBanner = document.getElementById('statusBanner');
  const statusIcon = document.getElementById('statusIcon');
  const statusText = document.getElementById('statusText');

  // Result Section
  const resultSection = document.getElementById('resultSection');
  const origNotesContainer = document.getElementById('origNotesContainer');
  const contNotesContainer = document.getElementById('contNotesContainer');
  const origCountBadge = document.getElementById('origCountBadge');
  const contCountBadge = document.getElementById('contCountBadge');

  // Playback & Export
  const btnPlay = document.getElementById('btnPlay');
  const btnStop = document.getElementById('btnStop');
  const btnDownloadMidi = document.getElementById('btnDownloadMidi');
  const btnRegenerate = document.getElementById('btnRegenerate');
  const btnCopyNotes = document.getElementById('btnCopyNotes');
  const volumeSlider = document.getElementById('volumeSlider');

  // Mini Keyboard
  const miniKeyboard = document.getElementById('miniKeyboard');
  const octaveBtns = document.querySelectorAll('.octave-btn');

  // State
  let currentInputMode = 'manual'; // 'manual' or 'midi'
  let uploadedMidiFile = null;
  let currentOctave = 4;
  let validatedInputEvents = [];
  let activeMelodyData = null;
  let isGenerating = false;
  let isPlayingInput = false;
  let playheadAnimId = null;
  let playbackStartTime = 0;
  let totalPlaybackSec = 0;

  // Initialize Canvas Piano Roll
  const pianoRoll = new window.PianoRollVisualizer('pianoRollCanvas');

  // Initialize synth timbre and volume
  window.musicSynth.setTimbre(selectTimbre.value);
  window.musicSynth.setVolume(parseFloat(volumeSlider.value));

  // ==========================================
  // Helper: Compute audio schedule from events & BPM
  // ==========================================
  function computeSchedule(events, bpm) {
    const secondsPerBeat = 60.0 / Math.max(40, Math.min(300, bpm));
    const schedule = [];
    let currentTime = 0.0;

    events.forEach((ev, idx) => {
      const durBeats = parseFloat(ev.duration || 1.0);
      const durSec = durBeats * secondsPerBeat;
      const isRest = ev.is_rest || ev.pitch === 'REST';

      if (!isRest && ev.midi != null) {
        const freq = 440.0 * Math.pow(2.0, (ev.midi - 69) / 12.0);
        schedule.push({
          index: idx,
          pitch: ev.pitch || '',
          midi: ev.midi,
          frequency_hz: Math.round(freq * 1000) / 1000,
          start_time: Math.round(currentTime * 1000) / 1000,
          duration: Math.round(durSec * 1000) / 1000,
          source: ev.source || 'original'
        });
      }
      currentTime += durSec;
    });

    return schedule;
  }

  // ==========================================
  // 1. System Health Check
  // ==========================================
  async function checkSystemHealth() {
    try {
      const res = await fetch('/api/health');
      const data = await res.json();
      const statusBadge = document.getElementById('systemHealthBadge');
      if (statusBadge) {
        if (data.status === 'healthy') {
          statusBadge.innerHTML = `<span class="status-dot"></span> Model Ready (${data.model.model_type})`;
        } else {
          statusBadge.innerHTML = `<span class="status-dot" style="background:#ef4444;box-shadow:0 0 8px #ef4444;"></span> Model Setup Required`;
          statusBadge.style.color = '#ef4444';
          statusBadge.style.borderColor = 'rgba(239, 68, 68, 0.4)';
        }
      }
    } catch (e) {
      console.warn("Could not check health:", e);
    }
  }
  checkSystemHealth();

  // ==========================================
  // 2. Mode Switching (Manual vs MIDI)
  // ==========================================
  tabManual.addEventListener('click', () => {
    currentInputMode = 'manual';
    tabManual.classList.add('active');
    tabMidi.classList.remove('active');
    manualInputArea.style.display = 'block';
    midiUploadArea.style.display = 'none';
    validateCurrentInput();
  });

  tabMidi.addEventListener('click', () => {
    currentInputMode = 'midi';
    tabMidi.classList.add('active');
    tabManual.classList.remove('active');
    manualInputArea.style.display = 'none';
    midiUploadArea.style.display = 'block';
    validateCurrentInput();
  });

  // ==========================================
  // Real-Time Synchronized Lyrics Engine (Karaoke)
  // ==========================================
  const SONG_LYRICS_SYNC = {
    mayadari: {
      title: "Mayadari Maisamma (30s Telangana Folk)",
      bpm: 112,
      lines: [
        { start_beat: 0.0, end_beat: 10.0, text: "మాయాదారీ మైసమ్మో మైసమ్మా...", roman: "Mayadari Maisammo Maisamma..." },
        { start_beat: 10.0, end_beat: 20.0, text: "మనం మైసారం పోదామే మైసమ్మా!", roman: "Manam Maisaram Podame Maisamma!" },
        { start_beat: 20.0, end_beat: 29.0, text: "గాబర బెట్టి మమ్ము గాబర బెట్టి... గయబు గాకే మైసమ్మా!", roman: "Gabara betti mammu... gayabu gaake maisamma!" },
        { start_beat: 29.0, end_beat: 37.0, text: "జర్ర పరేశానీ జెయ్యకే మైసమ్మో... ఓ మైసమ్మో!", roman: "Zara pareshani jeyyake maisammo... O Maisammo!" },
        { start_beat: 37.0, end_beat: 45.0, text: "స్కాములన్ని కామ్ చేసి సరదాగా బతుకుతున్నమే...", roman: "Scam-lanni calm chesi saradaaga bathukuthunname..." },
        { start_beat: 45.0, end_beat: 56.0, text: "మాయాదారీ మైసమ్మో మైసమ్మా... మనం మైసారం పోదామే!", roman: "Mayadari Maisammo Maisamma... Manam maisaram podame!" }
      ]
    },
    pedda_puli: {
      title: "Pedda Puli — Rahul Sipligunj (30s)",
      bpm: 120,
      lines: [
        { start_beat: 0.0, end_beat: 9.0, text: "అరేయ్ పొదుగలే బైలెళ్ళు... బోనం ఎత్తి బైలెళ్ళు!", roman: "Arey podugale bailellu... bonam yetti bailellu!" },
        { start_beat: 9.0, end_beat: 18.0, text: "గండి మైసకి మొక్కేళ్లు... గాలి మోటర్ ఎక్కిళ్ళు!", roman: "Gandi maisaki mokkellu... gaali motor yekkellu!" },
        { start_beat: 18.0, end_beat: 28.0, text: "నువ్వు పెద్దపులి... నువ్వు పెద్దపులి... నువ్వు పెద్దపులి!", roman: "Nuvvu peddapuli... nuvvu peddapuli... nuvvu peddapuli!" },
        { start_beat: 28.0, end_beat: 39.0, text: "నువ్వు పెద్దపులి లెక్క గోడితివిరో... బెమ్మాండం బద్దలు గొట్టెయ్రో!", roman: "Nuvvu peddapuli lekka goditiviro... bemmandam baddalu gotteyro!" },
        { start_beat: 39.0, end_beat: 50.0, text: "నువ్వు పెద్దపులి లెక్క గోడితివిరో... బెమ్మాండం బద్దలు గొట్టెయ్రో!", roman: "Nuvvu peddapuli lekka goditiviro... bemmandam baddalu gotteyro!" },
        { start_beat: 50.0, end_beat: 60.0, text: "హే రంగ చిందేయి... శివమెత్తు సుబ్బరంగా చల్ మోహన్ రంగ!", roman: "Hey ranga chindeyi... shivamettu subbaranga chal mohan ranga!" }
      ]
    },
    chhota_bheem: {
      title: "Chhota Bheem — Cartoon Title Track (30s)",
      bpm: 114,
      lines: [
        { start_beat: 0.0, end_beat: 10.5, text: "भीम... भीम की शक्ति धूम मचाए, सामने कोई टिक ना पाए!", roman: "Bheem... Bheem ki shakti dhoom machaye, saamne koi tik na paaye!" },
        { start_beat: 10.5, end_beat: 19.5, text: "छोटा भीम, छोटा भीम! छोटा भीम, छोटा भीम!", roman: "Chhota Bheem, Chhota Bheem! Chhota Bheem, Chhota Bheem!" },
        { start_beat: 19.5, end_beat: 28.5, text: "भीम, भीम, भीम... छोटा भीम छोटा भीम!", roman: "Bheem, Bheem, Bheem... Chhota Bheem Chhota Bheem!" },
        { start_beat: 28.5, end_beat: 38.5, text: "दिल का ये रंगीन, खाने की मशीन, लड्डू का शौक़ीन!", roman: "Dil ka ye rangeen, khaane ki machine, laddoo ka shaukeen!" },
        { start_beat: 38.5, end_beat: 47.5, text: "भीम, भीम, भीम... छोटा भीम छोटा भीम!", roman: "Bheem, Bheem, Bheem... Chhota Bheem Chhota Bheem!" },
        { start_beat: 47.5, end_beat: 57.0, text: "यारों का है यार, सबका मददगार... छोटा भीम छोटा भीम!", roman: "Yaaron ka hai yaar, sabka madadgaar... Chhota Bheem Chhota Bheem!" }
      ]
    },
    tu_mujhe_qubool: {
      title: "Tu Mujhe Qubool (30s Bollywood Classic — Khuda Gawah)",
      bpm: 96,
      lines: [
        { start_beat: 0.0, end_beat: 11.5, text: "तू मुझे क़ुबूल, मैं तुझे क़ुबूल...", roman: "Tu mujhe qubool, main tujhe qubool..." },
        { start_beat: 11.5, end_beat: 23.0, text: "तू मुझे क़ुबूल, मैं तुझे क़ुबूल...", roman: "Tu mujhe qubool, main tujhe qubool..." },
        { start_beat: 23.0, end_beat: 35.0, text: "इस बात का गवाह ख़ुदा, ख़ुदा गवाह, ख़ुदा गवाह!", roman: "Is baat ka gawah khuda, khuda gawah, khuda gawah!" },
        { start_beat: 35.0, end_beat: 49.5, text: "वाई वाई वाई... तेरे मेरे प्यार की... तेरे मेरे प्यार की!", roman: "Vai vai vai... tere mere pyaar ki... tere mere pyaar ki!" }
      ]
    }
  };

  let activeSongKey = null;

  function renderSyncedLyrics(songKey) {
    activeSongKey = songKey;
    if (!lyricsLinesContainer || !presetLyricsCard) return;

    const song = SONG_LYRICS_SYNC[songKey];
    if (!song) {
      presetLyricsCard.style.display = 'none';
      lyricsLinesContainer.innerHTML = '';
      return;
    }

    presetLyricsCard.style.display = 'flex';
    if (presetSongTitle) presetSongTitle.textContent = song.title;
    lyricsLinesContainer.innerHTML = '';

    song.lines.forEach((line, idx) => {
      const lineEl = document.createElement('div');
      lineEl.className = 'lyric-line';
      lineEl.id = `lyric-line-${idx}`;
      lineEl.setAttribute('data-start', line.start_beat);
      lineEl.setAttribute('data-end', line.end_beat);

      const startSec = Math.round((line.start_beat / song.bpm) * 60);
      const timeTag = `${String(Math.floor(startSec / 60)).padStart(2, '0')}:${String(startSec % 60).padStart(2, '0')}`;

      lineEl.innerHTML = `
        <span class="lyric-dot"></span>
        <span class="lyric-time">${timeTag}</span>
        <div class="lyric-text">
          <div style="font-weight:600;">${line.text}</div>
          <div style="font-size:11px; opacity:0.8; font-style:normal; margin-top:2px; color:#cbd5e1;">${line.roman}</div>
        </div>
      `;

      lyricsLinesContainer.appendChild(lineEl);
    });
  }

  function updateSyncedLyrics(currentBeat) {
    if (!lyricsLinesContainer || !activeSongKey) return;
    const lines = lyricsLinesContainer.querySelectorAll('.lyric-line');
    lines.forEach(lineEl => {
      const start = parseFloat(lineEl.getAttribute('data-start'));
      const end = parseFloat(lineEl.getAttribute('data-end'));
      if (currentBeat >= start && currentBeat < end) {
        if (!lineEl.classList.contains('active')) {
          lines.forEach(l => l.classList.remove('active'));
          lineEl.classList.add('active');
          lineEl.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }
      }
    });
  }

  function clearSyncedLyricsHighlight() {
    if (!lyricsLinesContainer) return;
    lyricsLinesContainer.querySelectorAll('.lyric-line.active').forEach(l => l.classList.remove('active'));
  }

  // ==========================================
  // 3. Preset Melodies
  // ==========================================
  presetPills.forEach(pill => {
    pill.addEventListener('click', async () => {
      // Stop any ongoing playback
      stopAllPlayback();

      if (currentInputMode !== 'manual') {
        tabManual.click();
      }
      melodyInput.value = pill.getAttribute('data-notes') || '';

      // Update BPM if specified in preset
      const presetBpm = pill.getAttribute('data-bpm');
      if (presetBpm) {
        sliderBpm.value = presetBpm;
        bpmValBadge.textContent = `${presetBpm} BPM`;
      }

      // Update Timbre if specified in preset
      const presetTimbre = pill.getAttribute('data-timbre');
      if (presetTimbre) {
        selectTimbre.value = presetTimbre;
        window.musicSynth.setTimbre(presetTimbre);
      }

      // Render Synchronized Karaoke Lyrics if available
      const songKey = pill.getAttribute('data-preset');
      renderSyncedLyrics(songKey);

      await validateCurrentInput();

      const presetName = pill.textContent.trim();
      setStatus('idle', `${presetName} loaded! Click "▶ Listen to Input" to hear the synchronized melody & lyrics, or "✨ Generate Continuation" to extend it.`);

      // Play a quick first-note audio hint
      if (validatedInputEvents.length > 0 && validatedInputEvents[0].midi != null) {
        const firstMidi = validatedInputEvents[0].midi;
        const freq = 440 * Math.pow(2, (firstMidi - 69) / 12);
        window.musicSynth.playPreviewNote(freq, 0.35);
      }
    });
  });

  // ==========================================
  // 4. Live Input Validation & Note Preview
  // ==========================================
  let typingTimer;
  melodyInput.addEventListener('input', () => {
    clearTimeout(typingTimer);
    typingTimer = setTimeout(validateCurrentInput, 300);
  });

  async function validateCurrentInput() {
    if (currentInputMode === 'manual') {
      const text = melodyInput.value.trim();
      if (!text) {
        inputPreviewBox.style.display = 'none';
        btnGenerate.disabled = true;
        validatedInputEvents = [];
        setStatus('idle', 'Enter notes or choose a preset to begin.');
        return;
      }

      try {
        const res = await fetch('/api/validate', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ melody: text })
        });
        const data = await res.json();

        if (data.success) {
          validatedInputEvents = data.data.events || [];
          inputPreviewBox.style.display = 'flex';
          inputPreviewNotes.textContent = data.data.preview_str;
          inputPreviewCount.textContent = `${data.data.count} notes (${data.data.total_beats} beats)`;
          btnGenerate.disabled = false;
          setStatus('idle', 'Melody valid. Ready to generate.');
        } else {
          validatedInputEvents = [];
          inputPreviewBox.style.display = 'none';
          btnGenerate.disabled = true;
          setStatus('error', data.error);
        }
      } catch (e) {
        console.error("Validation error:", e);
      }
    } else {
      // MIDI mode
      if (!uploadedMidiFile) {
        inputPreviewBox.style.display = 'none';
        btnGenerate.disabled = true;
        validatedInputEvents = [];
        setStatus('idle', 'Upload a .mid or .midi file to get started.');
        return;
      }

      const formData = new FormData();
      formData.append('file', uploadedMidiFile);

      try {
        const res = await fetch('/api/validate', {
          method: 'POST',
          body: formData
        });
        const data = await res.json();

        if (data.success) {
          validatedInputEvents = data.data.events || [];
          inputPreviewBox.style.display = 'flex';
          inputPreviewNotes.textContent = data.data.preview_str;
          inputPreviewCount.textContent = `${data.data.count} notes (${data.data.total_beats} beats)`;
          btnGenerate.disabled = false;
          setStatus('idle', `Loaded ${uploadedMidiFile.name}. Ready to generate.`);
        } else {
          validatedInputEvents = [];
          inputPreviewBox.style.display = 'none';
          btnGenerate.disabled = true;
          setStatus('error', data.error);
        }
      } catch (e) {
        console.error("MIDI validation error:", e);
      }
    }
  }

  // ==========================================
  // 5. Input Melody Playback (Step 1)
  // ==========================================
  if (btnPlayInput) {
    btnPlayInput.addEventListener('click', async () => {
      if (window.musicSynth.isPlaying) {
        stopAllPlayback();
        return;
      }

      if (!validatedInputEvents || validatedInputEvents.length === 0) {
        await validateCurrentInput();
      }

      if (!validatedInputEvents || validatedInputEvents.length === 0) {
        setStatus('error', 'Please enter some valid notes first to listen.');
        return;
      }

      try {
        const bpm = parseInt(sliderBpm.value, 10) || 120;
        window.musicSynth.setTimbre(selectTimbre.value);
        window.musicSynth.setVolume(parseFloat(volumeSlider.value));

        const schedule = computeSchedule(validatedInputEvents, bpm);

        btnPlayInput.innerHTML = `⏸️ Playing...`;
        if (btnStopInput) btnStopInput.style.display = 'inline-flex';
        isPlayingInput = true;

        window.musicSynth.onNoteStart = (idx, note) => {
          // Highlight key on piano if matching
          highlightPianoKeyByPitch(note.pitch);
          // Synchronize lyric highlight in real time
          const currentBeat = (note.start_time / 60) * bpm;
          updateSyncedLyrics(currentBeat);
        };

        window.musicSynth.onNoteEnd = () => {
          clearKeyHighlights();
        };

        window.musicSynth.onEnded = () => {
          stopAllPlayback();
        };

        await window.musicSynth.playSchedule(schedule);
      } catch (err) {
        console.error("Input playback error:", err);
        stopAllPlayback();
      }
    });
  }

  if (btnStopInput) {
    btnStopInput.addEventListener('click', stopAllPlayback);
  }

  function highlightPianoKeyByPitch(pitchStr) {
    clearKeyHighlights();
    if (!pitchStr) return;
    const clean = pitchStr.replace(/[0-9]/g, '');
    const keyEl = document.querySelector(`.piano-keys [data-note="${clean}"]`);
    if (keyEl) keyEl.classList.add('active-press');
  }

  function clearKeyHighlights() {
    document.querySelectorAll('.piano-keys .active-press').forEach(k => k.classList.remove('active-press'));
  }

  // ==========================================
  // 6. MIDI Upload & Drag-and-Drop
  // ==========================================
  dropzone.addEventListener('click', () => fileInput.click());

  dropzone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropzone.classList.add('dragover');
  });

  dropzone.addEventListener('dragleave', () => {
    dropzone.classList.remove('dragover');
  });

  dropzone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropzone.classList.remove('dragover');
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFileSelected(e.dataTransfer.files[0]);
    }
  });

  fileInput.addEventListener('change', () => {
    if (fileInput.files && fileInput.files.length > 0) {
      handleFileSelected(fileInput.files[0]);
    }
  });

  function handleFileSelected(file) {
    if (!file.name.toLowerCase().endsWith('.mid') && !file.name.toLowerCase().endsWith('.midi')) {
      setStatus('error', `This file type is not supported ('${file.name}'). Choose a compatible MIDI file (.mid or .midi).`);
      return;
    }
    uploadedMidiFile = file;
    selectedFileName.textContent = file.name;
    selectedFileInfo.style.display = 'flex';
    dropzone.style.display = 'none';
    validateCurrentInput();
  }

  removeFileBtn.addEventListener('click', () => {
    uploadedMidiFile = null;
    fileInput.value = '';
    selectedFileInfo.style.display = 'none';
    dropzone.style.display = 'block';
    validateCurrentInput();
  });

  // ==========================================
  // 7. Virtual Piano Keyboard & Sound Synthesis
  // ==========================================
  const noteFreqs = {
    'C': 261.63, 'C#': 277.18, 'D': 293.66, 'D#': 311.13,
    'E': 329.63, 'F': 349.23, 'F#': 369.99, 'G': 392.00,
    'G#': 415.30, 'A': 440.00, 'A#': 466.16, 'B': 493.88
  };

  // Computer keyboard to piano note mapping
  const pcKeyMap = {
    'a': 'C', 'w': 'C#', 's': 'D', 'e': 'D#', 'd': 'E',
    'f': 'F', 't': 'F#', 'g': 'G', 'y': 'G#', 'h': 'A',
    'u': 'A#', 'j': 'B'
  };

  octaveBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      octaveBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      currentOctave = parseInt(btn.getAttribute('data-octave'), 10) || 4;
      updateKeyboardLabels();
    });
  });

  function updateKeyboardLabels() {
    document.querySelectorAll('.piano-keys .white-key, .piano-keys .black-key').forEach(key => {
      const noteName = key.getAttribute('data-note');
      key.title = `${noteName}${currentOctave}`;
    });
  }

  // Play and append note
  function playAndInsertNote(noteLetter) {
    if (!noteLetter) return;
    const pitchStr = `${noteLetter}${currentOctave}`;

    // Visual key press animation
    const keyEl = document.querySelector(`.piano-keys [data-note="${noteLetter}"]`);
    if (keyEl) {
      keyEl.classList.add('active-press');
      setTimeout(() => keyEl.classList.remove('active-press'), 160);
    }

    // Play tone immediately
    const baseFreq = noteFreqs[noteLetter] || 261.63;
    const octaveShift = Math.pow(2, currentOctave - 4);
    const targetFreq = baseFreq * octaveShift;
    window.musicSynth.setTimbre(selectTimbre.value);
    window.musicSynth.playPreviewNote(targetFreq, 0.45);

    // Append to textarea
    const current = melodyInput.value.trim();
    melodyInput.value = current ? `${current} ${pitchStr}:1.0` : `${pitchStr}:1.0`;
    validateCurrentInput();
  }

  // On-screen key clicks
  document.querySelectorAll('.piano-keys .white-key, .piano-keys .black-key').forEach(key => {
    key.addEventListener('click', (e) => {
      e.preventDefault();
      const noteLetter = key.getAttribute('data-note');
      playAndInsertNote(noteLetter);
    });
  });

  // Physical PC keyboard listener
  window.addEventListener('keydown', (e) => {
    // If typing inside textarea or an input, don't intercept typing
    if (e.target === melodyInput || e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
      return;
    }
    const keyChar = e.key.toLowerCase();
    if (pcKeyMap[keyChar]) {
      e.preventDefault();
      playAndInsertNote(pcKeyMap[keyChar]);
    }
  });

  // ==========================================
  // 8. Settings & Controls Listeners
  // ==========================================
  sliderTemp.addEventListener('input', () => {
    const v = parseFloat(sliderTemp.value);
    let desc = 'Balanced';
    if (v < 0.6) desc = 'Cohesive';
    else if (v > 1.0) desc = 'Creative';
    tempValBadge.textContent = `${v.toFixed(2)} (${desc})`;
  });

  sliderBpm.addEventListener('input', () => {
    bpmValBadge.textContent = `${sliderBpm.value} BPM`;
  });

  selectTimbre.addEventListener('change', () => {
    const timbre = selectTimbre.value;
    window.musicSynth.setTimbre(timbre);
    // Audition sound with C4 note
    window.musicSynth.playPreviewNote(261.63, 0.35);
  });

  volumeSlider.addEventListener('input', () => {
    window.musicSynth.setVolume(parseFloat(volumeSlider.value));
  });

  // ==========================================
  // 9. Generate Continuation
  // ==========================================
  btnGenerate.addEventListener('click', triggerGeneration);
  btnRegenerate.addEventListener('click', triggerGeneration);

  async function triggerGeneration() {
    if (isGenerating) return; // Prevent duplicate requests (TC-12)

    stopAllPlayback();

    isGenerating = true;
    btnGenerate.disabled = true;
    btnRegenerate.disabled = true;
    btnGenerate.innerHTML = `<span class="spinner"></span> Generating continuation…`;
    setStatus('generating', 'Generating a continuation… This may take a few seconds.');

    const length = parseInt(selectLength.value, 10) || 16;
    const temperature = parseFloat(sliderTemp.value) || 0.85;
    const bpm = parseInt(sliderBpm.value, 10) || 120;

    try {
      let res;
      if (currentInputMode === 'midi' && uploadedMidiFile) {
        const formData = new FormData();
        formData.append('file', uploadedMidiFile);
        formData.append('length', length);
        formData.append('temperature', temperature);
        formData.append('bpm', bpm);

        res = await fetch('/api/generate', {
          method: 'POST',
          body: formData
        });
      } else {
        const text = melodyInput.value.trim();
        res = await fetch('/api/generate', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            melody: text,
            length: length,
            temperature: temperature,
            bpm: bpm
          })
        });
      }

      const data = await res.json();

      if (data.success) {
        activeMelodyData = data;
        displayResults(data);
        setStatus('success', `Continuation generated in ${data.metadata.generation_time_seconds}s. Review the notes below.`);
      } else {
        setStatus('error', data.error || 'Generation failed. Your input has been kept; please try again.');
      }
    } catch (err) {
      console.error("Generation error:", err);
      setStatus('error', `Connection error: ${err.message}. Your input has been kept.`);
    } finally {
      isGenerating = false;
      btnGenerate.disabled = false;
      btnRegenerate.disabled = false;
      btnGenerate.innerHTML = `✨ Generate Continuation`;
    }
  }

  // ==========================================
  // 10. Display Generated Results
  // ==========================================
  function displayResults(data) {
    resultSection.style.display = 'block';

    // Scroll smoothly to results
    resultSection.scrollIntoView({ behavior: 'smooth', block: 'nearest' });

    // Update note chips lists
    renderNoteChips(data.original_melody.events, origNotesContainer, 'orig');
    renderNoteChips(data.generated_continuation.events, contNotesContainer, 'cont');

    origCountBadge.textContent = `${data.original_melody.count} notes`;
    contCountBadge.textContent = `${data.generated_continuation.count} notes`;

    // Render Canvas Piano Roll
    const bpm = parseInt(sliderBpm.value, 10) || 120;
    pianoRoll.setMelody(data.combined_melody.events, bpm);
  }

  function renderNoteChips(events, container, typeClass) {
    container.innerHTML = '';
    events.forEach((ev, idx) => {
      const chip = document.createElement('div');
      chip.className = `note-chip ${typeClass}`;
      chip.setAttribute('data-index', idx);

      const label = ev.is_rest ? 'REST' : ev.pitch;
      const durText = `${ev.duration}b`;

      chip.innerHTML = `<span>${label}</span><span class="chip-dur">${durText}</span>`;

      // Click note chip to preview tone
      chip.addEventListener('click', () => {
        if (!ev.is_rest && ev.midi != null) {
          const freq = 440 * Math.pow(2, (ev.midi - 69) / 12);
          window.musicSynth.setTimbre(selectTimbre.value);
          window.musicSynth.playPreviewNote(freq, Math.min(0.5, (ev.duration || 1.0) * 0.45));
        }
      });

      container.appendChild(chip);
    });
  }

  // ==========================================
  // 11. Playback Control & Synchronization (Step 3)
  // ==========================================
  btnPlay.addEventListener('click', async () => {
    if (!activeMelodyData || !activeMelodyData.combined_melody) {
      setStatus('error', 'No melody available to play.');
      return;
    }

    if (window.musicSynth.isPlaying) {
      stopAllPlayback();
      return;
    }

    try {
      const bpm = parseInt(sliderBpm.value, 10) || 120;
      window.musicSynth.setTimbre(selectTimbre.value);
      window.musicSynth.setVolume(parseFloat(volumeSlider.value));

      // Synchronize visual note highlight and lyrics
      window.musicSynth.onNoteStart = (noteIdx, note) => {
        pianoRoll.setActiveNote(noteIdx);
        highlightActiveChip(noteIdx);
        highlightPianoKeyByPitch(note.pitch);
        const currentBeat = (note.start_time / 60) * bpm;
        updateSyncedLyrics(currentBeat);
      };

      window.musicSynth.onNoteEnd = () => {
        pianoRoll.setActiveNote(-1);
        clearKeyHighlights();
      };

      window.musicSynth.onEnded = () => {
        stopAllPlayback();
      };

      btnPlay.innerHTML = `⏸️ Pause`;
      btnPlay.classList.add('playing');

      // Compute schedule dynamically using active BPM and combined events
      const schedule = computeSchedule(activeMelodyData.combined_melody.events, bpm);
      const playInfo = await window.musicSynth.playSchedule(schedule);

      playbackStartTime = performance.now();
      totalPlaybackSec = playInfo.totalDuration;

      // Start Playhead cursor animation loop
      animatePlayhead();

    } catch (err) {
      console.error("Playback failed:", err);
      setStatus('error', `Playback unavailable: ${err.message}`);
      stopAllPlayback();
    }
  });

  btnStop.addEventListener('click', stopAllPlayback);

  function stopAllPlayback() {
    window.musicSynth.stop();
    if (playheadAnimId) {
      cancelAnimationFrame(playheadAnimId);
      playheadAnimId = null;
    }
    pianoRoll.setPlayheadTime(-1);
    pianoRoll.setActiveNote(-1);
    clearChipHighlights();
    clearKeyHighlights();
    clearSyncedLyricsHighlight();

    btnPlay.innerHTML = `▶ Play Full Melody`;
    btnPlay.classList.remove('playing');

    if (btnPlayInput) {
      btnPlayInput.innerHTML = `▶ Listen to Input`;
    }
    if (btnStopInput) {
      btnStopInput.style.display = 'none';
    }
    isPlayingInput = false;
  }

  function animatePlayhead() {
    if (!window.musicSynth.isPlaying) return;

    const elapsedSec = (performance.now() - playbackStartTime) / 1000;
    pianoRoll.setPlayheadTime(elapsedSec);

    if (elapsedSec <= totalPlaybackSec) {
      playheadAnimId = requestAnimationFrame(animatePlayhead);
    }
  }

  function highlightActiveChip(activeGlobalIdx) {
    clearChipHighlights();
    const origCount = (activeMelodyData && activeMelodyData.original_melody) ? activeMelodyData.original_melody.count : 0;
    
    if (activeGlobalIdx < origCount) {
      const chip = origNotesContainer.querySelector(`[data-index="${activeGlobalIdx}"]`);
      if (chip) chip.classList.add('playing');
    } else {
      const contIdx = activeGlobalIdx - origCount;
      const chip = contNotesContainer.querySelector(`[data-index="${contIdx}"]`);
      if (chip) chip.classList.add('playing');
    }
  }

  function clearChipHighlights() {
    document.querySelectorAll('.note-chip.playing').forEach(c => c.classList.remove('playing'));
  }

  // ==========================================
  // 12. MIDI Download & Copy Action
  // ==========================================
  btnDownloadMidi.addEventListener('click', async () => {
    if (!activeMelodyData || !activeMelodyData.combined_melody) {
      setStatus('error', 'No melody available to export.');
      return;
    }

    try {
      const bpm = parseInt(sliderBpm.value, 10) || 120;
      const res = await fetch('/api/export-midi', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          events: activeMelodyData.combined_melody.events,
          bpm: bpm,
          filename: 'melody_continuation.mid'
        })
      });

      if (!res.ok) {
        throw new Error("Server failed to generate MIDI file.");
      }

      const blob = await res.blob();
      const downloadUrl = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = downloadUrl;
      a.download = 'melody_continuation.mid';
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(downloadUrl);

      setStatus('success', 'MIDI file created and downloaded successfully.');
    } catch (err) {
      setStatus('error', `Failed to export MIDI: ${err.message}`);
    }
  });

  btnCopyNotes.addEventListener('click', () => {
    if (!activeMelodyData || !activeMelodyData.combined_melody) return;
    const noteStrings = activeMelodyData.combined_melody.events.map(e => e.is_rest ? `REST:${e.duration}` : `${e.pitch}:${e.duration}`).join(' ');
    navigator.clipboard.writeText(noteStrings).then(() => {
      const origText = btnCopyNotes.innerHTML;
      btnCopyNotes.innerHTML = `✓ Copied!`;
      setTimeout(() => btnCopyNotes.innerHTML = origText, 2000);
    });
  });

  // ==========================================
  // 13. Helper: Set Status Banner
  // ==========================================
  function setStatus(type, message) {
    statusBanner.className = `status-banner ${type}`;
    if (type === 'generating') {
      statusIcon.innerHTML = `<span class="spinner"></span>`;
    } else if (type === 'success') {
      statusIcon.innerHTML = `✓`;
    } else if (type === 'error') {
      statusIcon.innerHTML = `⚠️`;
    } else {
      statusIcon.innerHTML = `ℹ️`;
    }
    statusText.textContent = message;
  }

  // Pre-load default preview if text exists
  if (melodyInput.value.trim()) {
    validateCurrentInput();
  }
});
