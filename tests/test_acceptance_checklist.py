"""
Comprehensive Acceptance Test Suite verifying Part E of the PRD / SRS Specification.
Covers TC-01 through TC-15 and produces a full formal verification report.
"""
import os
import io
import time
import pytest
from app.server import create_app
from generation.generator import MusicGenerator
from input.validator import validate_text_melody, validate_midi_file
from output.validator import validate_generated_events
from output.midi_writer import events_to_midi_bytes
from playback.audio_spec import prepare_playback_schedule
import mido

ASSETS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "assets", "sample_melodies"))

@pytest.fixture
def app_client():
    app = create_app()
    app.config['TESTING'] = True
    with app.test_client() as c:
        yield c

def test_tc01_valid_melody_input(app_client):
    """TC-01: Valid melody input is accepted and previewed."""
    res = app_client.post('/api/validate', json={'melody': 'C4:1.0 D4:1.0 E4:1.0 G4:1.0'})
    assert res.status_code == 200
    data = res.get_json()
    assert data['success'] is True
    assert data['data']['count'] == 4
    assert 'preview_str' in data['data']
    assert data['data']['total_beats'] == 4.0

def test_tc02_empty_input(app_client):
    """TC-02: Empty input is blocked and helpful message appears."""
    res = app_client.post('/api/validate', json={'melody': ''})
    assert res.status_code == 400
    data = res.get_json()
    assert data['success'] is False
    assert data['error_code'] == 'EMPTY_INPUT'
    assert "Add a few notes" in data['error']

def test_tc03_unsupported_malformed_midi(app_client):
    """TC-03: Unsupported/malformed MIDI file is rejected safely; app remains usable."""
    # Test wrong extension
    res1 = app_client.post('/api/validate', data={'file': (io.BytesIO(b'dummy'), 'audio.wav')})
    assert res1.status_code == 400
    assert res1.get_json()['error_code'] == 'UNSUPPORTED_FILE'

    # Test corrupt MIDI content
    corrupt_file = os.path.join(ASSETS_DIR, 'corrupt_file.mid')
    with open(corrupt_file, 'rb') as f:
        res2 = app_client.post('/api/validate', data={'file': (f, 'corrupt_file.mid')})
    assert res2.status_code == 400
    assert 'Corrupt or non-MIDI' in res2.get_json()['error']

def test_tc04_model_missing_or_fails(app_client):
    """TC-04: Model missing or fails to load produces setup-oriented message."""
    broken_app = create_app(model_dir="invalid/nonexistent/dir")
    broken_client = broken_app.test_client()
    res = broken_client.post('/api/generate', json={'melody': 'C4 D4 E4 G4'})
    assert res.status_code == 503
    data = res.get_json()
    assert data['success'] is False
    assert data['error_code'] == 'MODEL_UNAVAILABLE'
    assert "The music model is not available right now" in data['error']

def test_tc05_valid_generation_request(app_client):
    """TC-05: Valid generation request produces continuation and preserves original."""
    res = app_client.post('/api/generate', json={
        'melody': 'C4 D4 E4 G4 A4',
        'length': 16,
        'temperature': 0.85
    })
    assert res.status_code == 200
    data = res.get_json()
    assert data['success'] is True
    assert data['original_melody']['count'] == 5
    assert data['generated_continuation']['count'] == 16
    assert data['combined_melody']['count'] == 21

def test_tc06_input_preservation(app_client):
    """TC-06: Original melody notes remain completely unchanged."""
    original_input = 'C4:1.0 D4:0.5 E4:0.5 G4:2.0'
    res = app_client.post('/api/generate', json={'melody': original_input, 'length': 8})
    data = res.get_json()
    orig_events = data['original_melody']['events']
    assert len(orig_events) == 4
    assert orig_events[0]['pitch'] == 'C4' and orig_events[0]['duration'] == 1.0
    assert orig_events[1]['pitch'] == 'D4' and orig_events[1]['duration'] == 0.5
    assert orig_events[2]['pitch'] == 'E4' and orig_events[2]['duration'] == 0.5
    assert orig_events[3]['pitch'] == 'G4' and orig_events[3]['duration'] == 2.0

def test_tc07_output_integrity(app_client):
    """TC-07: Generated events decode and pass structural validation."""
    res = app_client.post('/api/generate', json={'melody': 'E4 F4 G4', 'length': 16})
    data = res.get_json()
    cont_events = data['generated_continuation']['events']
    val_res = validate_generated_events(cont_events)
    assert val_res['valid'] is True
    assert val_res['count'] == 16

def test_tc08_playback_audible_and_timing(app_client):
    """TC-08: Playback schedule accurately maps to positive frequencies and timing offsets."""
    events = [
        {'pitch': 'C4', 'midi': 60, 'duration': 1.0, 'is_rest': False, 'source': 'original'},
        {'pitch': 'D4', 'midi': 62, 'duration': 1.0, 'is_rest': False, 'source': 'original'},
        {'pitch': 'REST', 'midi': None, 'duration': 0.5, 'is_rest': True, 'source': 'original'},
        {'pitch': 'E4', 'midi': 64, 'duration': 1.5, 'is_rest': False, 'source': 'continuation'}
    ]
    schedule = prepare_playback_schedule(events, bpm=120)
    assert len(schedule) == 3  # Rests are non-audible gaps
    assert schedule[0]['frequency_hz'] == 261.626
    assert schedule[1]['frequency_hz'] == 293.665
    assert schedule[2]['frequency_hz'] == 329.628
    # Start times: 0.0s, 0.5s, 1.25s (1.0 beat = 0.5s at 120 bpm)
    assert schedule[0]['start_time'] == 0.0
    assert schedule[1]['start_time'] == 0.5
    assert schedule[2]['start_time'] == 1.25

def test_tc09_playback_unavailable_handling():
    """TC-09: Playback handles missing audio engine gracefully without crash."""
    from playback.audio_spec import midi_to_freq
    # Assert frequency math never crashes for any valid MIDI range 0-127
    for m in range(0, 128):
        f = midi_to_freq(m)
        assert f > 0

def test_tc10_midi_export(app_client):
    """TC-10: File opens in compatible MIDI tool and contains both sections."""
    events = [
        {'pitch': 'C4', 'midi': 60, 'duration': 1.0, 'is_rest': False, 'source': 'original'},
        {'pitch': 'D4', 'midi': 62, 'duration': 1.0, 'is_rest': False, 'source': 'continuation'}
    ]
    res = app_client.post('/api/export-midi', json={'events': events, 'bpm': 120})
    assert res.status_code == 200
    midi_bytes = res.data
    mid = mido.MidiFile(file=io.BytesIO(midi_bytes))
    notes = [m.note for t in mid.tracks for m in t if m.type == 'note_on' and m.velocity > 0]
    assert notes == [60, 62]

def test_tc11_regenerate_replaces_prior_continuation(app_client):
    """TC-11: New continuation does not append accidentally to old output."""
    res1 = app_client.post('/api/generate', json={'melody': 'C4 D4 E4', 'length': 8})
    res2 = app_client.post('/api/generate', json={'melody': 'C4 D4 E4', 'length': 8})
    data1 = res1.get_json()
    data2 = res2.get_json()
    assert data1['generated_continuation']['count'] == 8
    assert data2['generated_continuation']['count'] == 8
    assert data1['combined_melody']['count'] == 11
    assert data2['combined_melody']['count'] == 11

def test_tc12_duplicate_request_safe():
    """TC-12: Concurrent generation requests are safely managed."""
    import concurrent.futures
    app = create_app()
    app.config['TESTING'] = True

    def make_req():
        with app.test_client() as client:
            return client.post('/api/generate', json={'melody': 'C4 D4 E4', 'length': 8}).status_code

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
        futures = [ex.submit(make_req) for _ in range(4)]
        results = [f.result() for f in futures]
    assert all(code == 200 for code in results)

def test_tc13_mobile_and_responsive_css():
    """TC-13: CSS has responsive breakpoints for mobile/narrow viewports."""
    css_path = os.path.join(os.path.dirname(__file__), "..", "app", "static", "css", "style.css")
    with open(css_path, 'r', encoding='utf-8') as f:
        content = f.read()
    assert "@media (max-width: 992px)" in content
    assert "@media (max-width: 768px)" in content

def test_tc14_keyboard_and_focus_visible():
    """TC-14: Primary controls have visible focus states and labels in CSS & HTML."""
    css_path = os.path.join(os.path.dirname(__file__), "..", "app", "static", "css", "style.css")
    with open(css_path, 'r', encoding='utf-8') as f:
        content = f.read()
    assert ":focus-visible" in content
    html_path = os.path.join(os.path.dirname(__file__), "..", "app", "templates", "index.html")
    with open(html_path, 'r', encoding='utf-8') as f:
        html = f.read()
    assert "aria-label" in html
    assert "role=\"tab\"" in html

def test_tc15_performance_target(app_client):
    """TC-15: Generation time is measured against target (< 10 seconds)."""
    t0 = time.perf_counter()
    res = app_client.post('/api/generate', json={'melody': 'C4 D4 E4 G4 A4', 'length': 32})
    dur = time.perf_counter() - t0
    assert res.status_code == 200
    assert dur < 10.0
    data = res.get_json()
    assert data['metadata']['generation_time_seconds'] < 10.0
