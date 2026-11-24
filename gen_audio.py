#!/usr/bin/env python3
"""
Produces the 14.0-second 48kHz stereo soundtrack for the Gemini 4 Neon promo:
- Warm 128 BPM Rhodes / lo-fi pop groove + punchy beat-drop drums
- Real CC0 studio Foley & UI sound effects sourced via the vibe-motion/sound skill
  (trimmed to measured transient onsets, peak-normalized, stereo-panned, and frame-synced)
"""
import math
import os
import random
import struct
import subprocess
import wave

SR = 48000
DURATION = 14.0
N_SAMPLES = int(SR * DURATION)
BPM = 128.0
BEAT_S = 60.0 / BPM  # 0.46875s

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SFX_DIR = os.path.join(BASE_DIR, 'sfx')
FFMPEG = '/Users/mac/.local/lib/python3.13/site-packages/static_ffmpeg/bin/darwin/ffmpeg'

left = [0.0] * N_SAMPLES
right = [0.0] * N_SAMPLES


def midi_to_hz(m):
    return 440.0 * (2.0 ** ((m - 69) / 12.0))


def load_sfx(filename, start_s=0.0, end_s=None, pitch=1.0):
    """Decode an SFX clip to mono float samples [-1, 1], trimmed & peak-normalized."""
    path = os.path.join(SFX_DIR, filename)
    raw = subprocess.check_output([
        FFMPEG, '-v', 'error', '-i', path,
        '-ac', '1', '-ar', str(SR), '-f', 's16le', '-'
    ])
    n = len(raw) // 2
    samples = struct.unpack(f'<{n}h', raw)
    i0 = max(0, int(start_s * SR))
    i1 = n if end_s is None else min(n, int(end_s * SR))
    seg = [x / 32768.0 for x in samples[i0:i1]]
    if not seg:
        return []
    # Optional linear resampling for subtle musical pitch shift
    if abs(pitch - 1.0) > 1e-3:
        out_len = max(1, int(len(seg) / pitch))
        res = []
        for k in range(out_len):
            pos = k * pitch
            idx = int(pos)
            frac = pos - idx
            if idx + 1 < len(seg):
                res.append(seg[idx] * (1.0 - frac) + seg[idx + 1] * frac)
            elif idx < len(seg):
                res.append(seg[idx])
        seg = res
    # Peak normalize active slice + apply 6ms anti-click fade-in/out
    pk = max(abs(x) for x in seg) or 1.0
    seg = [x / pk for x in seg]
    fade_n = min(len(seg) // 4, int(0.006 * SR))
    for k in range(fade_n):
        w = k / max(1, fade_n)
        seg[k] *= w
        seg[-1 - k] *= w
    return seg


def place_sfx(samples, start_s, gain=0.45, pan=0.0, fade_out_s=0.03):
    """Mix a normalized mono SFX clip into the stereo bus at exact start_s."""
    if not samples:
        return
    i0 = int(start_s * SR)
    pan_l = math.cos((pan + 1.0) * math.pi / 4.0)
    pan_r = math.sin((pan + 1.0) * math.pi / 4.0)
    fo_n = min(len(samples) // 2, int(fade_out_s * SR))
    n = len(samples)
    for k, s in enumerate(samples):
        idx = i0 + k
        if idx < 0 or idx >= N_SAMPLES:
            continue
        env = 1.0
        if fo_n > 0 and k >= n - fo_n:
            env = (n - k) / fo_n
        v = s * gain * env
        left[idx] += v * pan_l
        right[idx] += v * pan_r


def add_rhodes_note(start_s, dur_s, midi, amp=0.10, pan=0.0):
    hz = midi_to_hz(midi)
    i0 = int(start_s * SR)
    n = int(dur_s * SR)
    pan_l = math.cos((pan + 1.0) * math.pi / 4.0)
    pan_r = math.sin((pan + 1.0) * math.pi / 4.0)
    for k in range(n):
        idx = i0 + k
        if idx >= N_SAMPLES:
            break
        t = k / SR
        att = min(1.0, t / 0.012)
        rel = math.exp(-t * 3.1)
        tail = min(1.0, (dur_s - t) / 0.04) if dur_s - t < 0.04 else 1.0
        env = att * rel * max(0.0, tail)
        sig = (
            math.sin(2 * math.pi * hz * t)
            + 0.26 * math.sin(2 * math.pi * hz * 2.0 * t) * math.exp(-t * 5.0)
            + 0.09 * math.sin(2 * math.pi * hz * 4.0 * t) * math.exp(-t * 14.0)
        )
        v = sig * env * amp
        left[idx] += v * pan_l
        right[idx] += v * pan_r


def add_marimba_spark(start_s, midi, amp=0.11, pan=0.0):
    hz = midi_to_hz(midi)
    i0 = int(start_s * SR)
    n = int(0.16 * SR)
    pan_l = math.cos((pan + 1.0) * math.pi / 4.0)
    pan_r = math.sin((pan + 1.0) * math.pi / 4.0)
    for k in range(n):
        idx = i0 + k
        if idx >= N_SAMPLES:
            break
        t = k / SR
        env = min(1.0, t / 0.004) * math.exp(-t * 25.0)
        sig = math.sin(2 * math.pi * hz * t) + 0.22 * math.sin(2 * math.pi * hz * 3.98 * t) * math.exp(-t * 45.0)
        v = sig * env * amp
        left[idx] += v * pan_l
        right[idx] += v * pan_r


def add_kick(start_s, amp=0.30):
    i0 = int(start_s * SR)
    n = int(0.22 * SR)
    phase = 0.0
    for k in range(n):
        idx = i0 + k
        if idx >= N_SAMPLES:
            break
        t = k / SR
        freq = 48.0 + 115.0 * math.exp(-t * 36.0)
        phase += 2 * math.pi * freq / SR
        env = min(1.0, t / 0.003) * math.exp(-t * 15.0)
        v = math.sin(phase) * env * amp
        left[idx] += v
        right[idx] += v


def add_hat(start_s, amp=0.065, open_hat=False, pan=0.15):
    rng = random.Random(int(start_s * 10000))
    i0 = int(start_s * SR)
    dur = 0.12 if open_hat else 0.045
    n = int(dur * SR)
    decay = 24.0 if open_hat else 78.0
    prev = 0.0
    pan_l = math.cos((pan + 1.0) * math.pi / 4.0)
    pan_r = math.sin((pan + 1.0) * math.pi / 4.0)
    for k in range(n):
        idx = i0 + k
        if idx >= N_SAMPLES:
            break
        t = k / SR
        white = rng.uniform(-1.0, 1.0)
        hp = white - 0.85 * prev
        prev = white
        v = hp * math.exp(-t * decay) * amp
        left[idx] += v * pan_l
        right[idx] += v * pan_r


def add_clap_snare(start_s, amp=0.17):
    rng = random.Random(int(start_s * 9999) + 7)
    i0 = int(start_s * SR)
    n = int(0.14 * SR)
    for k in range(n):
        idx = i0 + k
        if idx >= N_SAMPLES:
            break
        t = k / SR
        noise = rng.uniform(-1.0, 1.0) * math.exp(-t * 28.0)
        tone = math.sin(2 * math.pi * 195.0 * t) * math.exp(-t * 32.0) * 0.55
        v = (noise * 0.75 + tone) * amp
        left[idx] += v * 0.96
        right[idx] += v * 1.04


# =====================================================================
# 1. Warm 128 BPM Creative-Studio Music Bed (balanced beneath real SFX)
# =====================================================================
chords = [
    (0.00,   1.80, [53, 57, 60, 64, 67], 0.052),  # Fmaj9 (leaves space for pencil!)
    (1.875,  1.80, [55, 59, 62, 64, 67], 0.062),  # G6
    (3.75,   1.80, [52, 55, 59, 62, 67], 0.044),  # Em7 (ducks gently for scissors + stamp!)
    (5.625,  1.80, [57, 60, 64, 67, 71], 0.064),  # Am9
    (7.50,   0.90, [50, 57, 60, 64, 69], 0.070),  # Dm9
    (8.4375, 0.90, [55, 59, 62, 65, 69], 0.078),  # G13
    (9.375,  0.90, [53, 60, 64, 67, 72], 0.095),  # Fmaj9 (Beat drop!)
    (10.3125,0.90, [55, 62, 64, 67, 71], 0.095),  # G6/9
    (11.55,  2.35, [48, 55, 60, 64, 67, 71, 74], 0.088),  # Cmaj9 finale!
]
for st, dur, notes, amp in chords:
    for idx_n, m in enumerate(notes):
        add_rhodes_note(st + idx_n * 0.018, dur, m, amp=amp, pan=-0.28 + 0.11 * idx_n)

bass_events = [
    (0.00, 1.80, 41), (1.875, 1.80, 43), (3.75, 1.00, 40),
    (5.625, 1.80, 45), (7.50, 0.90, 38), (8.4375, 0.90, 43),
    (9.375, 0.45, 41), (9.84375, 0.45, 41), (10.3125, 0.45, 43), (10.78125, 0.45, 43),
    (11.55, 2.30, 36),
]
for st, dur, m in bass_events:
    add_rhodes_note(st, dur, m, amp=0.115, pan=0.0)

for b in range(28):
    bt = b * BEAT_S
    if bt >= 11.45:
        break
    if 3.80 <= bt <= 4.75:
        continue  # Dramatic musical pause for bloat gag + crisp scissors cut!
    is_drop = 9.30 <= bt <= 10.85
    if b >= 3:
        if b % 2 == 0 or is_drop:
            add_kick(bt, amp=0.35 if is_drop else 0.20)
        if b % 2 == 1:
            add_clap_snare(bt, amp=0.20 if is_drop else 0.11)
        add_hat(bt + BEAT_S * 0.5, amp=0.08 if is_drop else 0.045, open_hat=(is_drop and b % 2 == 1))
        if is_drop:
            add_hat(bt + BEAT_S * 0.25, amp=0.045)
            add_hat(bt + BEAT_S * 0.75, amp=0.045)

# Sparkling Beat-Drop Arpeggio (9.375..10.78s)
for i, m in enumerate([72, 76, 79, 84, 79, 76, 74, 79, 83, 86, 83, 79]):
    add_marimba_spark(9.375 + i * (BEAT_S * 0.25), m, amp=0.11, pan=-0.38 if i % 2 == 0 else 0.38)

# =====================================================================
# 2. Real Freesound CC0 Foley & UI SFX Layer (measured & frame-synced!)
# =====================================================================
# 0.15..1.08s: Real 0.5mm mechanical pencil drawing on stiff paper (fs:211247)
sfx_pencil = load_sfx('fs_211247_Scribble.mp3', start_s=0.02, end_s=1.02)
place_sfx(sfx_pencil, 0.15, gain=0.42, pan=-0.28, fade_out_s=0.10)

# 0.95s & 1.12s: Panels & Phone pop in (fs:439186 cartoon bubble pop)
place_sfx(load_sfx('fs_439186_Pop-5-ogg.mp3', 0.04, 0.13, pitch=0.92), 0.95, gain=0.34, pan=-0.25)
place_sfx(load_sfx('fs_439186_Pop-5-ogg.mp3', 0.04, 0.13, pitch=1.08), 1.12, gain=0.38, pan=0.0)

# 1.85, 2.33, 2.81, 3.29s: 4 capability cards drop onto timeline (fs:447910 Plop! + soft air swish)
for i, pitch in enumerate([0.92, 1.00, 1.08, 1.18]):
    t_drop = 1.85 + i * 0.48
    pan = -0.35 + i * 0.23
    place_sfx(load_sfx('fs_420668_Basic-Melee-Swing-Miss-Whoosh.mp3', 0.03, 0.16, pitch=1.15), t_drop - 0.10, gain=0.18, pan=pan)
    place_sfx(load_sfx('fs_447910_Plop.mp3', 0.00, 0.14, pitch=pitch), t_drop, gain=0.52, pan=pan)

# 3.32s: Audio waveform track enters (fs:59988 SWOSH-01)
place_sfx(load_sfx('fs_59988_SWOSH-01-44-1kHz.mp3', 0.02, 0.26, pitch=1.05), 3.32, gain=0.38, pan=0.0)

# 4.62s swing + 4.72s: Real metallic Scissors Snip on "咔嚓!" (fs:629513 snip #2 peak at 0.55s -> onset 0.53s)
place_sfx(load_sfx('fs_420668_Basic-Melee-Swing-Miss-Whoosh.mp3', 0.03, 0.16, pitch=1.25), 4.60, gain=0.28, pan=-0.08)
place_sfx(load_sfx('fs_629513_scissors-snips-wav.mp3', 0.53, 0.72, pitch=1.00), 4.70, gain=0.72, pan=0.0)

# 5.10s: Real Traditional Rubber Stamp slamming "省 60% Token" (fs:470710 onset=0.50s -> trimmed 0.49..0.85s)
place_sfx(load_sfx('fs_470710_traditional-stamp-wav.mp3', 0.49, 0.85, pitch=1.02), 5.09, gain=0.68, pan=0.18)

# 5.88s: Spin transition whoosh (fs:59988 SWOSH-01)
place_sfx(load_sfx('fs_59988_SWOSH-01-44-1kHz.mp3', 0.02, 0.27, pitch=0.96), 5.86, gain=0.50, pan=0.0)

# 6.38s: Neon glitch static zap (fs:456827 Quick static noise)
place_sfx(load_sfx('fs_456827_Quick-static-noise.mp3', 0.00, 0.15, pitch=1.05), 6.38, gain=0.46, pan=0.0)

# 6.78..7.40s: Real Mechanical Keyboard Typing for "XHigh 强推理!" (fs:331656 crisp 6-keystroke burst)
place_sfx(load_sfx('fs_331656_Keyboard-Typing.mp3', 0.14, 0.76, pitch=1.06), 6.78, gain=0.52, pan=-0.18, fade_out_s=0.05)

# 7.58..9.18s: Real mechanical switch flicks on 4 parameter sliders (fs:566176)
slider_cues = [
    (7.66, 0.96), (7.88, 1.06),  # 推理深度 -> XHigh
    (8.12, 1.04), (8.34, 1.15),  # 代码准确 -> 99%
    (8.56, 0.92), (8.76, 0.84),  # Token 消耗 -> -60% (playful downward pitch!)
    (8.98, 1.12), (9.16, 1.24),  # 霓虹亮度 -> 100%
]
for t_sl, p_sl in slider_cues:
    place_sfx(load_sfx('fs_566176_Flicking-a-Switch.mp3', 0.015, 0.075, pitch=p_sl), t_sl, gain=0.46, pan=0.40)

# 10.82s: Export button click + render swish -> 11.52s: Sparkling Blue Yeti Bell Ding ("完成 ✓")!
place_sfx(load_sfx('fs_566176_Flicking-a-Switch.mp3', 0.015, 0.075, pitch=1.22), 10.82, gain=0.52, pan=0.42)
place_sfx(load_sfx('fs_59988_SWOSH-01-44-1kHz.mp3', 0.02, 0.27, pitch=1.22), 11.30, gain=0.34, pan=0.22)
place_sfx(load_sfx('fs_611113_bell-ding-1-wav.mp3', 0.055, 1.90, pitch=1.04), 11.50, gain=0.58, pan=0.05, fade_out_s=0.25)

# 11.82s: Sticky note slide-in swish + 12.35/12.55/12.75s: 3 capability pill bubble pops!
place_sfx(load_sfx('fs_420668_Basic-Melee-Swing-Miss-Whoosh.mp3', 0.03, 0.16, pitch=0.88), 11.82, gain=0.24, pan=-0.35)
for i, (tp, pt) in enumerate([(12.35, 0.96), (12.55, 1.06), (12.75, 1.16)]):
    place_sfx(load_sfx('fs_439186_Pop-5-ogg.mp3', 0.04, 0.13, pitch=pt), tp, gain=0.34, pan=-0.30 + i * 0.08)

# =====================================================================
# 3. Clean Mastering & Soft Peak Limiter (target ~ -14 LUFS, zero clip)
# =====================================================================
peak = max(max(abs(x) for x in left), max(abs(x) for x in right), 1e-6)
gain = min(0.94 / peak, 1.32)
fade_samples = int(0.45 * SR)

frames = bytearray()
for i in range(N_SAMPLES):
    fade = 1.0
    if i > N_SAMPLES - fade_samples:
        fade = (N_SAMPLES - i) / fade_samples
    l = math.tanh(left[i] * gain * 1.12) * 0.93 * fade
    r = math.tanh(right[i] * gain * 1.12) * 0.93 * fade
    frames += struct.pack(
        '<hh',
        int(max(-32767, min(32767, l * 32767))),
        int(max(-32767, min(32767, r * 32767))),
    )

out_path = os.path.join(BASE_DIR, 'output', 'soundtrack.wav')
with wave.open(out_path, 'wb') as wf:
    wf.setnchannels(2)
    wf.setsampwidth(2)
    wf.setframerate(SR)
    wf.writeframes(frames)

print(f'Wrote {out_path} ({DURATION:.2f}s, {SR}Hz stereo, pre-master peak={peak:.3f})')
