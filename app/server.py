"""
Flask Application Server for the Music Continuation Tool.
Provides RESTful API endpoints for input validation, conditioned continuation generation,
audio playback scheduling, MIDI export, and health telemetry.
"""
import os
import sys
import io
import time
from typing import Dict, Any, List

# Add project root to sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from flask import Flask, request, jsonify, render_template, send_file
from flask_cors import CORS

from input.validator import validate_text_melody, validate_midi_file, validate_melody_events
from generation.generator import MusicGenerator
from output.validator import validate_generated_events
from output.midi_writer import events_to_midi_bytes
from output.decoder import analyze_melody_sequence
from playback.audio_spec import prepare_playback_schedule

def create_app(model_dir: str = None) -> Flask:
    app = Flask(
        __name__,
        template_folder=os.path.join(PROJECT_ROOT, "app", "templates"),
        static_folder=os.path.join(PROJECT_ROOT, "app", "static")
    )
    CORS(app)

    if model_dir is None:
        model_dir = os.path.join(PROJECT_ROOT, "models", "weights")

    # Initialize generator
    generator = MusicGenerator(model_dir=model_dir)

    # Preset sample melodies for quick testing
    PRESET_SAMPLES = [
        {
            "id": "mayadari_maisamma",
            "name": "Mayadari Maisamma (30s Telangana Folk)",
            "category": "Telangana / Folk",
            "bpm": 112,
            "lyrics": "మాయాదారీ మైసమ్మో మైసమ్మా... మనం మైసారం పోదామే మైసమ్మా!\nగాబర బెట్టి మమ్ము గాబర బెట్టి... గయబు గాకే మైసమ్మా!\nజర్ర పరేశానీ జెయ్యకే మైసమ్మో... ఓ మైసమ్మో మైసమ్మా!\nస్కాములన్ని కామ్ చేసి సరదాగా బతుకుతున్నమే...\nసచ్చి సగం అవుతున్నమే మైసమ్మో... ఎక్కడుందో చిక్కదాయె మైసమ్మా!\nమాయాదారీ మైసమ్మో మైసమ్మా... మనం మైసారం పోదామే!",
            "lyrics_lines": [
                {"start_beat": 0.0, "end_beat": 10.0, "text": "మాయాదారీ మైసమ్మో మైసమ్మా... (Mayadari Maisammo Maisamma...)"},
                {"start_beat": 10.0, "end_beat": 20.0, "text": "మనం మైసారం పోదామే మైసమ్మా! (Manam Maisaram Podame Maisamma!)"},
                {"start_beat": 20.0, "end_beat": 29.0, "text": "గాబర బెట్టి మమ్ము గాబర బెట్టి... గయబు గాకే మైసమ్మా! (Gabara betti mammu...)"},
                {"start_beat": 29.0, "end_beat": 37.0, "text": "జర్ర పరేశానీ జెయ్యకే మైసమ్మో... ఓ మైసమ్మో! (Zara pareshani jeyyake maisammo!)"},
                {"start_beat": 37.0, "end_beat": 45.0, "text": "స్కాములన్ని కామ్ చేసి సరదాగా బతుకుతున్నమే... (Scam-lanni calm chesi...)"},
                {"start_beat": 45.0, "end_beat": 56.0, "text": "మాయాదారీ మైసమ్మో మైసమ్మా... మనం మైసారం పోదామే! (Mayadari Maisammo Maisamma!)"}
            ],
            "notes": "C4:1.0 C4:0.5 E4:1.0 E4:0.5 E4:0.5 D4:1.0 D4:0.5 E4:1.0 E4:0.5 D4:1.0 D4:1.0 C4:1.5 B3:1.0 D4:0.5 D4:1.0 E4:1.0 E4:1.0 E4:0.5 D4:1.0 C4:0.5 D4:0.5 E4:1.0 D4:0.5 C4:1.5 F4:1.0 F4:0.5 F4:1.0 F4:0.5 F4:0.5 G4:1.0 F4:0.5 E4:1.0 E4:0.5 E4:0.5 D4:0.5 C4:1.5 D4:1.0 D4:0.5 E4:1.0 E4:0.5 D4:1.0 C4:1.0 B3:1.0 C4:2.0 E4:1.0 E4:0.5 G4:1.0 G4:0.5 A4:1.0 G4:0.5 E4:1.0 D4:1.0 C4:1.5 C4:1.0 C4:0.5 E4:1.0 E4:0.5 E4:0.5 D4:1.0 D4:0.5 E4:1.0 E4:0.5 D4:1.0 D4:1.0 C4:2.5"
        },
        {
            "id": "pedda_puli",
            "name": "Pedda Puli — Rahul Sipligunj (30s)",
            "category": "Telangana / Folk",
            "bpm": 120,
            "lyrics": "అరేయ్ పొదుగలే బైలెళ్ళు... బోనం ఎత్తి బైలెళ్ళు!\nగండి మైసకి మొక్కేళ్లు... గాలి మోటర్ ఎక్కిళ్ళు!\nనువ్వు పెద్దపులి... నువ్వు పెద్దపులి... నువ్వు పెద్దపులి!\nనువ్వు పెద్దపులి లెక్క గోడితివిరో... బెమ్మాండం బద్దలు గొట్టెయ్రో!\nనువ్వు పెద్దపులి లెక్క గోడితివిరో... బెమ్మాండం బద్దలు గొట్టెయ్రో!\nహే రంగ చిందేయి... శివమెత్తు సుబ్బరంగా చల్ మోహన్ రంగ!",
            "lyrics_lines": [
                {"start_beat": 0.0, "end_beat": 9.0, "text": "అరేయ్ పొదుగలే బైలెళ్ళు... బోనం ఎత్తి బైలెళ్ళు! (Arey podugale bailellu... bonam yetti bailellu!)"},
                {"start_beat": 9.0, "end_beat": 18.0, "text": "గండి మైసకి మొక్కేళ్లు... గాలి మోటర్ ఎక్కిళ్ళు! (Gandi maisaki mokkellu... gaali motor yekkellu!)"},
                {"start_beat": 18.0, "end_beat": 28.0, "text": "నువ్వు పెద్దపులి... నువ్వు పెద్దపులి... నువ్వు పెద్దపులి! (Nuvvu peddapuli... nuvvu peddapuli!)"},
                {"start_beat": 28.0, "end_beat": 39.0, "text": "నువ్వు పెద్దపులి లెక్క గోడితివిరో... బెమ్మాండం బద్దలు గొట్టెయ్రో! (Nuvvu peddapuli lekka goditiviro...)"},
                {"start_beat": 39.0, "end_beat": 50.0, "text": "నువ్వు పెద్దపులి లెక్క గోడితివిరో... బెమ్మాండం బద్దలు గొట్టెయ్రో! (Nuvvu peddapuli lekka goditiviro...)"},
                {"start_beat": 50.0, "end_beat": 60.0, "text": "హే రంగ చిందేయి... శివమెత్తు సుబ్బరంగా చల్ మోహన్ రంగ! (Hey ranga chindeyi... chal mohan ranga!)"}
            ],
            "notes": "G4:0.5 G4:0.5 G4:0.5 A4:0.5 Bb4:0.5 A4:0.5 G4:1.0 G4:0.5 G4:0.5 G4:0.5 A4:0.5 Bb4:0.5 A4:0.5 G4:2.0 D5:0.5 D5:0.5 D5:0.5 C5:0.5 Bb4:0.5 C5:0.5 D5:1.0 D5:0.5 D5:0.5 D5:0.5 C5:0.5 Bb4:0.5 C5:0.5 D5:2.0 D5:1.0 Bb4:0.5 G4:1.5 D5:1.0 Bb4:0.5 G4:1.5 D5:1.0 Bb4:0.5 G4:1.5 G4:1.0 Bb4:0.5 Bb4:0.5 Bb4:0.5 C5:0.5 D5:1.0 D5:1.0 C5:0.5 C5:0.5 C5:0.5 D5:0.5 Bb4:1.0 G4:1.0 Bb4:1.0 G4:2.0 Bb4:0.5 Bb4:0.5 Bb4:0.5 C5:0.5 D5:1.0 D5:1.0 C5:0.5 C5:0.5 C5:0.5 D5:0.5 Bb4:1.0 G4:1.0 Bb4:1.0 G4:2.0 D5:0.5 D5:0.5 C5:0.5 Bb4:0.5 G4:1.0 G4:1.0 F4:0.5 G4:0.5 Bb4:0.5 C5:0.5 D5:1.0 C5:1.0 G4:2.0"
        },
        {
            "id": "chhota_bheem",
            "name": "Chhota Bheem — Cartoon Title Track (30s)",
            "category": "Animation / Theme",
            "bpm": 114,
            "lyrics": "भीम... भीम की शक्ति धूम मचाए, सामने कोई टिक ना पाए!\nछोटा भीम, छोटा भीम! छोटा भीम, छोटा भीम!\nभीम, भीम, भीम... छोटा भीम छोटा भीम!\nदिल का ये रंगीन, खाने की मशीन, लड्डू का शौक़ीन!\nभीम, भीम, भीम... छोटा भीम छोटा भीम!\nयारों का है यार, सबका मददगार... छोटा भीम छोटा भीम!",
            "lyrics_lines": [
                {"start_beat": 0.0, "end_beat": 10.5, "text": "भीम... भीम की शक्ति धूम मचाए, सामने कोई टिक ना पाए! (Bheem ki shakti dhoom machaye...)"},
                {"start_beat": 10.5, "end_beat": 19.5, "text": "छोटा भीम, छोटा भीम! छोटा भीम, छोटा भीम! (Chhota Bheem, Chhota Bheem!)"},
                {"start_beat": 19.5, "end_beat": 28.5, "text": "भीम, भीम, भीम... छोटा भीम छोटा भीम! (Bheem, Bheem, Bheem... Chhota Bheem Chhota Bheem!)"},
                {"start_beat": 28.5, "end_beat": 38.5, "text": "दिल का ये रंगीन, खाने की मशीन, लड्डू का शौक़ीन! (Dil ka ye rangeen, khaane ki machine...)"},
                {"start_beat": 38.5, "end_beat": 47.5, "text": "भीम, भीम, भीम... छोटा भीम छोटा भीम! (Bheem, Bheem, Bheem... Chhota Bheem Chhota Bheem!)"},
                {"start_beat": 47.5, "end_beat": 57.0, "text": "यारों का है यार, सबका मददगार... छोटा भीम छोटा भीम! (Yaaron ka hai yaar, sabka madadgaar...)"}
            ],
            "notes": "C4:1.5 C4:0.5 C4:0.5 E4:0.5 G4:0.5 G4:0.5 A4:0.5 G4:1.0 F4:0.5 F4:0.5 E4:0.5 D4:0.5 C4:1.0 C4:2.0 E4:0.5 E4:0.5 E4:1.0 G4:0.5 G4:0.5 G4:1.0 E4:0.5 E4:0.5 E4:1.0 G4:0.5 G4:0.5 G4:2.0 C4:0.5 C4:0.5 C4:1.0 E4:0.5 E4:0.5 E4:1.0 G4:0.5 G4:0.5 G4:1.0 C5:1.0 C5:2.0 G4:0.5 G4:0.5 A4:0.5 G4:1.0 A4:0.5 A4:0.5 B4:0.5 A4:1.0 C5:0.5 C5:0.5 B4:0.5 A4:0.5 G4:2.0 G4:1.0 C4:0.5 C4:0.5 C4:1.0 E4:0.5 E4:0.5 E4:1.0 G4:0.5 G4:0.5 G4:1.0 C5:1.0 C5:2.0 F4:0.5 F4:0.5 G4:0.5 A4:1.0 G4:0.5 F4:0.5 E4:0.5 D4:1.0 E4:0.5 E4:0.5 G4:1.0 C5:2.5"
        },
        {
            "id": "tu_mujhe_qubool",
            "name": "Tu Mujhe Qubool — Khuda Gawah (30s)",
            "category": "Bollywood Classic",
            "bpm": 96,
            "lyrics": "तू मुझे क़ुबूल, मैं तुझे क़ुबूल... इस बात का गवाह ख़ुदा, ख़ुदा गवाह, ख़ुदा गवाह!\nवाई वाई वाई... तेरे मेरे प्यार की... तेरे मेरे प्यार की!",
            "lyrics_lines": [
                {"start_beat": 0.0, "end_beat": 11.5, "text": "तू मुझे क़ुबूल, मैं तुझे क़ुबूल... (Tu mujhe qubool, main tujhe qubool...)"},
                {"start_beat": 11.5, "end_beat": 23.0, "text": "तू मुझे क़ुबूल, मैं तुझे क़ुबूल... (Tu mujhe qubool, main tujhe qubool...)"},
                {"start_beat": 23.0, "end_beat": 35.0, "text": "इस बात का गवाह ख़ुदा, ख़ुदा गवाह, ख़ुदा गवाह! (Is baat ka gawah khuda...)"},
                {"start_beat": 35.0, "end_beat": 49.5, "text": "वाई वाई वाई... तेरे मेरे प्यार की... (Vai vai vai... tere mere pyaar ki...)"}
            ],
            "notes": "G4:0.5 G4:0.5 A4:0.5 A4:0.5 C5:1.0 Bb4:1.5 C5:0.5 Bb4:0.5 C5:0.5 Bb4:1.0 Bb4:0.5 A4:1.0 A4:1.5 G4:0.5 G4:0.5 A4:0.5 A4:0.5 C5:1.0 Bb4:1.5 C5:0.5 Bb4:0.5 C5:0.5 Bb4:1.0 Bb4:0.5 A4:1.0 A4:2.0 E5:0.5 D5:0.5 C5:0.5 D5:0.5 E5:0.5 D5:0.5 C5:0.5 Bb4:0.5 Bb4:0.5 A4:0.5 Bb4:0.5 A4:0.5 G4:2.0 G4:0.5 C5:1.0 Bb4:0.5 A4:1.5 G4:0.5 C5:1.0 Bb4:0.5 A4:2.0 A4:0.5 A4:0.5 A4:1.0 G4:0.5 G4:0.5 G4:0.5 G4:0.5 A4:0.5 A4:0.5 C5:1.0 Bb4:1.5 C5:0.5 Bb4:0.5 C5:0.5 Bb4:1.0 Bb4:0.5 A4:1.0 A4:2.0"
        },
        {
            "id": "ode_to_joy",
            "name": "Beethoven — Ode to Joy",
            "category": "Classical",
            "bpm": 120,
            "lyrics": "Freude, schöner Götterfunken, Tochter aus Elysium...",
            "notes": "E4:1.0 E4:1.0 F4:1.0 G4:1.0 G4:1.0 F4:1.0 E4:1.0 D4:1.0 C4:1.0 C4:1.0 D4:1.0 E4:1.0 E4:1.5 D4:0.5 D4:2.0"
        },
        {
            "id": "twinkle",
            "name": "Mozart — Twinkle Twinkle",
            "category": "Classical",
            "bpm": 120,
            "lyrics": "Twinkle, twinkle, little star, how I wonder what you are...",
            "notes": "C4:1.0 C4:1.0 G4:1.0 G4:1.0 A4:1.0 A4:1.0 G4:2.0 F4:1.0 F4:1.0 E4:1.0 E4:1.0 D4:1.0 D4:1.0 C4:2.0"
        },
        {
            "id": "fur_elise",
            "name": "Beethoven — Für Elise",
            "category": "Classical",
            "bpm": 130,
            "lyrics": "Theme in A minor (Bagatelle No. 25)",
            "notes": "E5:0.5 D#5:0.5 E5:0.5 D#5:0.5 E5:0.5 B4:0.5 D5:0.5 C5:0.5 A4:1.0"
        },
        {
            "id": "blues_riff",
            "name": "Pentatonic & Blues Riff",
            "category": "Jazz / Blues",
            "bpm": 110,
            "lyrics": "Swing & Blue note motif",
            "notes": "C4:0.5 Eb4:0.5 F4:0.5 F#4:0.5 G4:1.0 Bb4:0.5 C5:1.5"
        },
        {
            "id": "lydian_dream",
            "name": "Lydian Flight (Modern)",
            "category": "Contemporary",
            "bpm": 125,
            "lyrics": "Uplifting Lydian #4 progression",
            "notes": "C4:1.0 E4:1.0 F#4:1.0 G4:1.0 B4:1.0 C5:1.5 D5:0.5 C5:2.0"
        }
    ]

    @app.route('/')
    def index():
        return render_template('index.html')

    @app.route('/api/health', methods=['GET'])
    def health_check():
        model_status = generator.check_availability()
        return jsonify({
            'status': 'healthy' if model_status['available'] else 'degraded',
            'model': model_status,
            'api_version': '2.0.0',
            'supported_inputs': ['manual_text', 'midi_upload'],
            'supported_outputs': ['visual_piano_roll', 'audio_playback', 'midi_download']
        })

    @app.route('/api/samples', methods=['GET'])
    def get_samples():
        return jsonify({
            'success': True,
            'samples': PRESET_SAMPLES
        })

    @app.route('/api/validate', methods=['POST'])
    def validate_input_route():
        """
        Validates manual text input or uploaded MIDI file without triggering generation.
        """
        # 1. Check for MIDI file upload
        if 'file' in request.files:
            uploaded_file = request.files['file']
            filename = uploaded_file.filename or "upload.mid"
            file_bytes = uploaded_file.read()
            result = validate_midi_file(file_bytes, filename)
            if not result['valid']:
                return jsonify({
                    'success': False,
                    'error': result['error'],
                    'error_code': result.get('error_code', 'INVALID_INPUT')
                }), 400
            return jsonify({'success': True, 'data': result})

        # 2. Check for JSON text payload
        data = request.get_json(silent=True) or {}
        melody_str = data.get('melody', '')
        result = validate_text_melody(melody_str)
        if not result['valid']:
            return jsonify({
                'success': False,
                'error': result['error'],
                'error_code': result.get('error_code', 'INVALID_INPUT')
            }), 400

        return jsonify({'success': True, 'data': result})

    @app.route('/api/generate', methods=['POST'])
    def generate_route():
        """
        Generates continuation conditioned on input melody.
        """
        # Step 1: Check model availability (FR-05, TC-04)
        if not generator.is_loaded:
            return jsonify({
                'success': False,
                'error_code': 'MODEL_UNAVAILABLE',
                'error': "The music model is not available right now. Check the model setup and try again.",
                'details': generator.load_error
            }), 503

        # Step 2: Extract & validate input (text or file or parsed events)
        input_events = None
        source_label = "manual"
        filename = None
        continuation_length = 16
        temperature = 0.85
        bpm = 120

        if 'file' in request.files:
            uploaded_file = request.files['file']
            filename = uploaded_file.filename or "upload.mid"
            file_bytes = uploaded_file.read()
            val_res = validate_midi_file(file_bytes, filename)
            if not val_res['valid']:
                return jsonify({
                    'success': False,
                    'error_code': val_res.get('error_code', 'INVALID_INPUT'),
                    'error': val_res['error']
                }), 400
            input_events = val_res['events']
            source_label = "midi"
            continuation_length = int(request.form.get('length', 16))
            temperature = float(request.form.get('temperature', 0.85))
            bpm = int(request.form.get('bpm', 120))
        else:
            payload = request.get_json(silent=True) or {}
            continuation_length = int(payload.get('length', 16))
            temperature = float(payload.get('temperature', 0.85))
            bpm = int(payload.get('bpm', 120))

            if 'events' in payload and isinstance(payload['events'], list):
                val_res = validate_melody_events(payload['events'])
                if not val_res['valid']:
                    return jsonify({
                        'success': False,
                        'error_code': val_res.get('error_code', 'INVALID_INPUT'),
                        'error': val_res['error']
                    }), 400
                input_events = val_res['events']
            else:
                melody_str = payload.get('melody', '')
                val_res = validate_text_melody(melody_str)
                if not val_res['valid']:
                    return jsonify({
                        'success': False,
                        'error_code': val_res.get('error_code', 'INVALID_INPUT'),
                        'error': val_res['error']
                    }), 400
                input_events = val_res['events']

        # Ensure parameters are safely clamped
        continuation_length = max(4, min(64, continuation_length))
        temperature = max(0.1, min(2.0, temperature))
        bpm = max(40, min(240, bpm))

        # Step 3: Run inference
        try:
            gen_result = generator.generate(
                input_events=input_events,
                num_events=continuation_length,
                temperature=temperature
            )
        except Exception as err:
            return jsonify({
                'success': False,
                'error_code': 'GENERATION_FAILED',
                'error': f"Generation failed: {str(err)}. Your input has been preserved.",
                'original_input_preserved': True
            }), 500

        # Step 4: Validate output structural integrity (TC-07)
        val_cont = validate_generated_events(gen_result['continuation_events'])
        if not val_cont['valid']:
            return jsonify({
                'success': False,
                'error_code': 'OUTPUT_VALIDATION_FAILED',
                'error': f"Generated continuation failed structural check: {val_cont['error']}"
            }), 500

        # Step 5: Musical analysis and audio playback scheduling (FR-09, TC-08)
        analysis_orig = analyze_melody_sequence(gen_result['original_events'], bpm=bpm)
        analysis_cont = analyze_melody_sequence(gen_result['continuation_events'], bpm=bpm)
        analysis_all = analyze_melody_sequence(gen_result['combined_events'], bpm=bpm)

        playback_schedule = prepare_playback_schedule(gen_result['combined_events'], bpm=bpm)

        return jsonify({
            'success': True,
            'message': 'Continuation generated. Review the new notes below.',
            'original_melody': {
                'events': gen_result['original_events'],
                'count': gen_result['original_count'],
                'analysis': analysis_orig,
                'source': source_label,
                'filename': filename
            },
            'generated_continuation': {
                'events': gen_result['continuation_events'],
                'count': gen_result['continuation_count'],
                'analysis': analysis_cont
            },
            'combined_melody': {
                'events': gen_result['combined_events'],
                'count': gen_result['total_count'],
                'analysis': analysis_all,
                'playback_schedule': playback_schedule
            },
            'metadata': {
                'generation_time_seconds': gen_result['generation_time_seconds'],
                'temperature': temperature,
                'bpm': bpm,
                'length': continuation_length,
                'model_type': 'MelodyLSTM'
            }
        })

    @app.route('/api/export-midi', methods=['POST'])
    def export_midi_route():
        """
        Exports the combined melody (original + continuation) to a Standard MIDI File (.mid).
        """
        payload = request.get_json(silent=True) or {}
        events = payload.get('events', [])
        bpm = int(payload.get('bpm', 120))
        filename = payload.get('filename', 'melody_continuation.mid')

        if not filename.lower().endswith('.mid'):
            filename += '.mid'

        if not events or not isinstance(events, list):
            return jsonify({
                'success': False,
                'error_code': 'EMPTY_EVENTS',
                'error': "No melody events provided for MIDI export."
            }), 400

        try:
            midi_bytes = events_to_midi_bytes(events, bpm=bpm, track_name="Melody Continuation")
        except Exception as err:
            return jsonify({
                'success': False,
                'error_code': 'EXPORT_FAILED',
                'error': f"Failed to create MIDI file: {str(err)}"
            }), 500

        return send_file(
            io.BytesIO(midi_bytes),
            mimetype='audio/midi',
            as_attachment=True,
            download_name=filename
        )

    # 404 & 500 handlers
    @app.errorhandler(404)
    def not_found(e):
        return jsonify({'success': False, 'error': 'Endpoint not found.'}), 404

    @app.errorhandler(500)
    def server_error(e):
        return jsonify({'success': False, 'error': 'Internal server error. Your input has been preserved.'}), 500

    return app

# Top-level Flask instance for Vercel serverless deployment and WSGI servers
app = create_app()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"Starting Music Continuation Tool on http://127.0.0.1:{port}")
    app.run(host='127.0.0.1', port=port, debug=True)
