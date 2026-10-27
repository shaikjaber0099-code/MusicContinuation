"""
Integration tests for Flask API endpoints.
Tests full pipeline through HTTP client.
"""
import io
import pytest
from app.server import create_app

@pytest.fixture
def client():
    app = create_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_health_endpoint(client):
    res = client.get('/api/health')
    assert res.status_code == 200
    data = res.get_json()
    assert data['status'] == 'healthy'
    assert data['model']['available'] is True

def test_samples_endpoint(client):
    res = client.get('/api/samples')
    assert res.status_code == 200
    data = res.get_json()
    assert data['success'] is True
    assert len(data['samples']) >= 3

def test_validate_route_success(client):
    res = client.post('/api/validate', json={'melody': 'C4 D4 E4 G4'})
    assert res.status_code == 200
    data = res.get_json()
    assert data['success'] is True
    assert data['data']['count'] == 4

def test_validate_route_empty(client):
    res = client.post('/api/validate', json={'melody': ''})
    assert res.status_code == 400
    data = res.get_json()
    assert data['success'] is False
    assert data['error_code'] == 'EMPTY_INPUT'

def test_generate_route_success(client):
    res = client.post('/api/generate', json={
        'melody': 'C4 D4 E4 G4',
        'length': 8,
        'temperature': 0.8,
        'bpm': 120
    })
    assert res.status_code == 200
    data = res.get_json()
    assert data['success'] is True
    assert data['original_melody']['count'] == 4
    assert data['generated_continuation']['count'] == 8
    assert data['combined_melody']['count'] == 12

    # Playback schedule verification (TC-08)
    schedule = data['combined_melody']['playback_schedule']
    assert len(schedule) == 12
    assert schedule[0]['pitch'] == 'C4'
    assert schedule[0]['frequency_hz'] == 261.626

def test_generate_route_midi_file(client):
    # Test generation from uploaded MIDI file
    import os
    sample_file = os.path.join(os.path.dirname(__file__), "..", "assets", "sample_melodies", "ode_to_joy.mid")
    with open(sample_file, 'rb') as f:
        file_bytes = f.read()

    res = client.post(
        '/api/generate',
        data={
            'file': (io.BytesIO(file_bytes), 'ode_to_joy.mid'),
            'length': '8',
            'temperature': '0.7'
        },
        content_type='multipart/form-data'
    )
    assert res.status_code == 200
    data = res.get_json()
    assert data['success'] is True
    assert data['original_melody']['source'] == 'midi'
    assert data['generated_continuation']['count'] == 8

def test_export_midi_route(client):
    events = [
        {'pitch': 'C4', 'midi': 60, 'duration': 1.0, 'is_rest': False, 'source': 'original'},
        {'pitch': 'D4', 'midi': 62, 'duration': 1.0, 'is_rest': False, 'source': 'continuation'}
    ]
    res = client.post('/api/export-midi', json={
        'events': events,
        'bpm': 120,
        'filename': 'my_melody.mid'
    })
    assert res.status_code == 200
    assert res.headers['Content-Type'].startswith('audio/midi')
    assert len(res.data) > 0
    assert res.data.startswith(b'MThd')
