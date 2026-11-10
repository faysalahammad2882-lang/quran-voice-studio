import io, re, wave, subprocess, tempfile
from pathlib import Path
import requests
import streamlit as st

st.set_page_config(page_title='Quran Voice Studio', page_icon='🎙️', layout='centered')
st.markdown('''<style>
.stApp{background:radial-gradient(circle at top,#19243a 0%,#090d18 55%,#070a12 100%);color:#f5edda}
.block-container{max-width:760px;padding-top:1.2rem}
.hero{background:linear-gradient(135deg,#1b2438,#111827);border:1px solid #66502c;padding:22px;border-radius:20px;margin-bottom:20px}
.gold{color:#d7b66c;letter-spacing:2px;font-size:12px;font-weight:800}
.stButton>button,.stDownloadButton>button{background:linear-gradient(90deg,#c69b48,#e0c47f);color:#111827;border:0;border-radius:12px;font-weight:800;min-height:46px}
</style>''', unsafe_allow_html=True)
st.markdown('<div class="hero"><div class="gold">AI-POWERED SUBTITLE AUDIO STUDIO</div><h1>QURAN VOICE STUDIO</h1><div style="color:#aab4c5">Turn translated SRT subtitles into synchronized audio.</div></div>', unsafe_allow_html=True)

CARTESIA_VERSION = '2026-08-14'
MODEL_ID = 'sonic-3.6'
RATE = 44100

def parse_srt(raw):
    raw = raw.replace('\ufeff', '').replace('\r\n', '\n').replace('\r', '\n')
    cues = []
    for block in re.split(r'\n\s*\n', raw.strip()):
        lines = [x for x in block.split('\n') if x.strip()]
        ti = next((i for i, x in enumerate(lines) if '-->' in x), None)
        if ti is None: continue
        m = re.match(r'\s*(\d{2}):(\d{2}):(\d{2})[,.](\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2})[,.](\d{3})', lines[ti])
        if not m: continue
        v = list(map(int, m.groups()))
        start = ((v[0]*3600 + v[1]*60 + v[2])*1000 + v[3])
        end = ((v[4]*3600 + v[5]*60 + v[6])*1000 + v[7])
        text = '\n'.join(lines[ti+1:]).strip()
        if text and end > start: cues.append({'start': start, 'end': end, 'text': text})
    return cues

def timecode(ms):
    h, r = divmod(ms, 3600000); m, r = divmod(r, 60000); s, milli = divmod(r, 1000)
    return f'{h:02}:{m:02}:{s:02},{milli:03}'

def cartesia_tts(api_key, voice_id, text, language):
    response = requests.post('https://api.cartesia.ai/tts/bytes',
        headers={'Authorization': f'Bearer {api_key}', 'Cartesia-Version': CARTESIA_VERSION, 'Content-Type': 'application/json'},
        json={'model_id': MODEL_ID, 'transcript': text, 'voice': voice_id, 'language': language,
              'output_format': {'container': 'wav', 'encoding': 'pcm_s16le', 'sample_rate': RATE}}, timeout=120)
    if not response.ok: raise RuntimeError(f'Cartesia API error {response.status_code}: {response.text[:600]}')
    with wave.open(io.BytesIO(response.content), 'rb') as wav:
        if (wav.getnchannels(), wav.getsampwidth(), wav.getframerate()) != (1, 2, RATE):
            raise RuntimeError('Unexpected WAV format returned by Cartesia.')
        frames = wav.readframes(wav.getnframes())
    return frames, round(len(frames) / 2 / RATE * 1000)

st.subheader('01 · Upload subtitle')
srt_file = st.file_uploader('Choose translated SRT file', type=['srt'])
st.subheader('02 · Cartesia voice')
api_key = st.text_input('Cartesia API Key', type='password')
voice_id = st.text_input('Cartesia Voice ID', placeholder='Paste your Cartesia Voice ID')
lang_label = st.radio('Translation language', ['বাংলা', 'English'], horizontal=True)
language = 'bn' if lang_label == 'বাংলা' else 'en'

if srt_file:
    raw = srt_file.getvalue().decode('utf-8-sig', errors='replace')
    cues = parse_srt(raw)
    if not cues: st.error('No valid SRT entries found. Please check the file format.')
    else:
        st.success(f'{len(cues)} subtitle entries loaded.')
        st.dataframe([{'#': i+1, 'Start': timecode(c['start']), 'End': timecode(c['end']), 'Text': c['text']} for i, c in enumerate(cues)], use_container_width=True, hide_index=True)
        st.info('Original start times are preserved. If speech is longer than its subtitle slot, export stops instead of cutting speech or shifting timing.')
        if st.button('✨ Generate synchronized MP3', use_container_width=True):
            if not api_key.strip() or not voice_id.strip(): st.error('Enter your Cartesia API key and Voice ID.')
            else:
                progress = st.progress(0); status = st.empty(); clips = []
                try:
                    for i, cue in enumerate(cues):
                        status.write(f'Generating voice {i+1}/{len(cues)}…')
                        frames, duration = cartesia_tts(api_key.strip(), voice_id.strip(), cue['text'], language)
                        available = cue['end'] - cue['start']
                        if duration > available:
                            raise RuntimeError(f'Subtitle {i+1}: speech is {duration/1000:.2f}s but its SRT slot is {available/1000:.2f}s. Shorten this subtitle or extend its SRT end time, then retry.')
                        clips.append((cue, frames)); progress.progress((i+1)/len(cues))
                    total_ms = max(c['end'] for c in cues) + 1200
                    mixed = bytearray(int(total_ms * RATE / 1000) * 2)
                    for cue, frames in clips:
                        offset = int(cue['start'] * RATE / 1000) * 2
                        mixed[offset:offset+len(frames)] = frames
                    wav_buffer = io.BytesIO()
                    with wave.open(wav_buffer, 'wb') as out_wav:
                        out_wav.setnchannels(1); out_wav.setsampwidth(2); out_wav.setframerate(RATE); out_wav.writeframes(mixed)
                    with tempfile.TemporaryDirectory() as tmp:
                        wav_path = Path(tmp) / 'voice.wav'; mp3_path = Path(tmp) / 'voice.mp3'
                        wav_path.write_bytes(wav_buffer.getvalue())
                        result = subprocess.run(['ffmpeg', '-y', '-i', str(wav_path), '-codec:a', 'libmp3lame', '-b:a', '192k', str(mp3_path)], capture_output=True, text=True)
                        if result.returncode: raise RuntimeError('MP3 conversion failed: ' + result.stderr[-500:])
                        mp3_data = mp3_path.read_bytes()
                    st.success('Your synchronized MP3 is ready.')
                    st.audio(mp3_data, format='audio/mp3')
                    st.download_button('⬇ Download MP3', mp3_data, 'quran_voice_studio.mp3', 'audio/mpeg', use_container_width=True)
                except FileNotFoundError: st.error('FFmpeg is missing. Check packages.txt and redeploy.')
                except Exception as error: st.error(str(error))
                finally: status.empty()
else:
    st.caption('Upload a translated .srt file to begin.')
st.divider()
st.caption('Prototype v0.1 · Voice cloning and saved Voice ID profiles are planned for the next version. Keep your API key private.')
