#!/usr/bin/env python3
"""
Synthesizes a 14.0-second 48kHz stereo soundtrack + frame-synced Foley SFX
matching the playful hand-drawn paper-craft studio aesthetic of the Gemini 4 Neon promo.
Pure Python standard library (zero external dependencies).
"""
import math
import random
import struct
import wave

SR = 48000
DURATION = 14.0
N_SAMPLES = int(SR * DURATION)
BPM = 128.0
BEAT_S = 60.0 / BPM  # 0.46875s

left = [0.0] * N_SAMPLES
right = [0.0] * N_SAMPLES

def midi_to_hz(m):
    return 440.0 * (2.0 ** ((m - 69) / 12.0))

def add_sample(idx, l_val, r_val):
    if 0 <= idx < N_SAMPLES:
        left[idx] += l_val
        right[idx] += r_val

def add_rhodes_note(start_s, dur_s, midi, amp=0.12, pan=0.0):
    """Warm electric-piano / lo-fi Rhodes tone with soft bell attack."""
    hz = midi_to_hz(midi)
    i0 = int(start_s * SR)
    n = int(dur_s * SR)
    pan_l = math.cos((pan + 1) * math.pi / 4)
    pan_r = math.sin((pan + 1) * math.pi / 4)
    for k in range(n):
        idx = i0 + k
        if idx >= N_SAMPLES:
            break
        t = k / SR
        att = min(1.0, t / 0.012)
        rel = math.exp(-t * 3.1)
        tail = min(1.0, (dur_s - t) / 0.04) if dur_s - t < 0.04 else 1.0
        env = att * rel * max(0.0, tail)
        # Warm fundamental + subtle 2nd + soft bell 4th
        sig = (
            math.sin(2 * math.pi * hz * t)
            + 0.28 * math.sin(2 * math.pi * hz * 2.0 * t) * math.exp(-t * 5.0)
            + 0.10 * math.sin(2 * math.pi * hz * 4.0 * t) * math.exp(-t * 14.0)
        )
        v = sig * env * amp
        left[idx] += v * pan_l
        right[idx] += v * pan_r

def add_marimba_pop(start_s, midi, amp=0.22, pan=0.0):
    """Playful wooden UI pop / marimba bloop."""
    hz = midi_to_hz(midi)
    i0 = int(start_s * SR)
    n = int(0.18 * SR)
    pan_l = math.cos((pan + 1) * math.pi / 4)
    pan_r = math.sin((pan + 1) * math.pi / 4)
    for k in range(n):
        idx = i0 + k
        if idx >= N_SAMPLES:
            break
        t = k / SR
        env = min(1.0, t / 0.004) * math.exp(-t * 24.0)
        pitch_bend = 1.0 + 0.14 * math.exp(-t * 45.0)
        sig = math.sin(2 * math.pi * hz * pitch_bend * t) + 0.25 * math.sin(2 * math.pi * hz * 3.98 * t) * math.exp(-t * 45.0)
        v = sig * env * amp
        left[idx] += v * pan_l
        right[idx] += v * pan_r

def add_kick(start_s, amp=0.34):
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

def add_hat(start_s, amp=0.08, open_hat=False, pan=0.15):
    rng = random.Random(int(start_s * 10000))
    i0 = int(start_s * SR)
    dur = 0.12 if open_hat else 0.045
    n = int(dur * SR)
    decay = 24.0 if open_hat else 78.0
    prev = 0.0
    pan_l = math.cos((pan + 1) * math.pi / 4)
    pan_r = math.sin((pan + 1) * math.pi / 4)
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

def add_clap_snare(start_s, amp=0.20):
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

def add_pencil_sketch(start_s, dur_s, amp=0.07):
    """Subtle paper-pencil tactile scratch during 0.16..1.05s intro drawing."""
    rng = random.Random(42)
    i0 = int(start_s * SR)
    n = int(dur_s * SR)
    lp = 0.0
    for k in range(n):
        idx = i0 + k
        if idx >= N_SAMPLES:
            break
        t = k / SR
        white = rng.uniform(-1.0, 1.0)
        lp = lp * 0.78 + white * 0.22
        bp = white - lp
        # Rhythmic stroke pressure modulation
        mod = 0.55 + 0.45 * math.sin(t * 26.0) * math.sin(t * 7.5)
        env = min(1.0, t / 0.08) * min(1.0, (dur_s - t) / 0.12)
        v = bp * mod * env * amp
        left[idx] += v * 0.85
        right[idx] += v * 1.10

def add_scissor_snip(start_s, amp=0.36):
    """Crisp metallic '咔嚓!' scissor snip SFX."""
    rng = random.Random(1337)
    i0 = int(start_s * SR)
    n = int(0.16 * SR)
    for k in range(n):
        idx = i0 + k
        if idx >= N_SAMPLES:
            break
        t = k / SR
        # Metallic ringing sweep + transient snap
        ring = (
            math.sin(2 * math.pi * (2850.0 + 900.0 * math.exp(-t * 45.0)) * t) * 0.5
            + math.sin(2 * math.pi * 4320.0 * t) * 0.35
        ) * math.exp(-t * 34.0)
        snap = rng.uniform(-1.0, 1.0) * math.exp(-t * 85.0)
        v = (ring * 0.7 + snap * 0.65) * amp
        left[idx] += v
        right[idx] += v

def add_whoosh(start_s, dur_s, f_start, f_end, amp=0.14):
    rng = random.Random(int(start_s * 500) + 3)
    i0 = int(start_s * SR)
    n = int(dur_s * SR)
    lp = 0.0
    phase = 0.0
    for k in range(n):
        idx = i0 + k
        if idx >= N_SAMPLES:
            break
        t = k / SR
        u = t / dur_s
        env = math.sin(u * math.pi)
        freq = f_start + (f_end - f_start) * (u ** 1.5)
        phase += 2 * math.pi * freq / SR
        white = rng.uniform(-1.0, 1.0)
        lp = lp * 0.88 + white * 0.12
        v = (math.sin(phase) * 0.45 + (white - lp) * 0.55) * env * amp
        left[idx] += v * (1.0 - 0.25 * u)
        right[idx] += v * (0.75 + 0.25 * u)

def add_sparkle_chime(start_s, midis, step_s=0.055, amp=0.14):
    for j, m in enumerate(midis):
        add_rhodes_note(start_s + j * step_s, 0.75, m, amp=amp, pan=-0.35 + 0.22 * j)

# =====================================================================
# 1. Warm Upbeat 128 BPM Creative-Studio Groove (0.0s .. 14.0s)
# =====================================================================
# Chord progression in C major / uplifting pop-lofi:
# Bar 1 (0.00-1.875s): Fmaj7  | Bar 2 (1.875-3.75s): G6
# Bar 3 (3.75-5.625s): Em7    | Bar 4 (5.625-7.50s): Am9
# Bar 5 (7.50-9.375s): Dm9->G | Bar 6 (9.375-11.25s): Fmaj7->G13 (BEAT DROP!)
# Bar 7-8 (11.25-14.0s): Cmaj9 celebratory finale!
chords = [
    (0.00,  1.80, [53, 57, 60, 64, 67], 0.065), # Fmaj9
    (1.875, 1.80, [55, 59, 62, 64, 67], 0.075), # G6
    (3.75,  1.80, [52, 55, 59, 62, 67], 0.055), # Em7 (softer during bloat gag)
    (5.625, 1.80, [57, 60, 64, 67, 71], 0.080), # Am9
    (7.50,  0.90, [50, 57, 60, 64, 69], 0.085), # Dm9
    (8.4375,0.90, [55, 59, 62, 65, 69], 0.095), # G13
    (9.375, 0.90, [53, 60, 64, 67, 72], 0.105), # Fmaj9 (Beat drop!)
    (10.3125,0.90,[55, 62, 64, 67, 71], 0.105), # G6/9
    (11.55, 2.35, [48, 55, 60, 64, 67, 71, 74], 0.095), # Cmaj9 grand resolution!
]
for st, dur, notes, amp in chords:
    for idx_n, m in enumerate(notes):
        add_rhodes_note(st + idx_n * 0.018, dur, m, amp=amp, pan=-0.3 + 0.12 * idx_n)

# Subtle warm bassline
bass_events = [
    (0.00, 1.80, 41), (1.875, 1.80, 43), (3.75, 1.00, 40),
    (5.625, 1.80, 45), (7.50, 0.90, 38), (8.4375, 0.90, 43),
    (9.375, 0.45, 41), (9.84375, 0.45, 41), (10.3125, 0.45, 43), (10.78125, 0.45, 43),
    (11.55, 2.30, 36),
]
for st, dur, m in bass_events:
    add_rhodes_note(st, dur, m, amp=0.14, pan=0.0)

# Rhythmic drums (kick + snare + crisp hi-hats)
for b in range(28):
    bt = b * BEAT_S
    if bt >= 11.45:
        break
    # Pause drums briefly during the comedic bloat pause (3.85..4.75s)
    if 3.85 <= bt <= 4.70:
        continue
    is_drop = 9.30 <= bt <= 10.85
    if b >= 3:
        if b % 2 == 0 or is_drop:
            add_kick(bt, amp=0.38 if is_drop else 0.24)
        if b % 2 == 1:
            add_clap_snare(bt, amp=0.22 if is_drop else 0.13)
        add_hat(bt + BEAT_S * 0.5, amp=0.09 if is_drop else 0.055, open_hat=(is_drop and b % 2 == 1))
        if is_drop:
            add_hat(bt + BEAT_S * 0.25, amp=0.05)
            add_hat(bt + BEAT_S * 0.75, amp=0.05)

# Playful synth sparkle arpeggio during Beat Drop (9.375..10.78s)
drop_notes = [72, 76, 79, 84, 79, 76, 74, 79, 83, 86, 83, 79]
for i, m in enumerate(drop_notes):
    add_marimba_pop(9.375 + i * (BEAT_S * 0.25), m, amp=0.13, pan=-0.4 if i % 2 == 0 else 0.4)

# =====================================================================
# 2. Frame-Synced Foley SFX matching index.html exact timestamps!
# =====================================================================
# 0.16..1.05s: Pencil drawing sidebar outline
add_pencil_sketch(0.16, 0.90, amp=0.085)
# 0.95..1.35s: Panels & phone pop in
add_marimba_pop(0.95, 67, amp=0.12, pan=-0.3)
add_marimba_pop(1.12, 72, amp=0.14, pan=0.0)

# 1.85, 2.33, 2.81, 3.29s: 4 capability cards drop onto timeline!
for i, m in enumerate([64, 67, 71, 76]):
    add_marimba_pop(1.85 + i * 0.48, m, amp=0.20, pan=-0.35 + i * 0.22)
# 3.38s: Audio track whoosh in
add_whoosh(3.32, 0.28, 320, 880, amp=0.10)

# 4.72s: Crisp scissor snip ("咔嚓!") + 5.10s rubber stamp thud!
add_scissor_snip(4.72, amp=0.38)
add_kick(5.10, amp=0.25)
add_marimba_pop(5.12, 79, amp=0.18, pan=0.2)

# 5.95s & 6.45s: Spin & Glitch transition swooshes
add_whoosh(5.88, 0.34, 280, 1250, amp=0.14)
add_whoosh(6.38, 0.24, 1400, 420, amp=0.15)

# 6.80..7.32s: Soft typewriter clicks for "XHigh 强推理!"
for i in range(8):
    add_marimba_pop(6.80 + i * 0.068, 84 + (i % 3) * 2, amp=0.085, pan=-0.2)

# 7.55..9.25s: Slider pulls (ascending ticks + playful dip for -60% Token!)
for t_tick, midi in [(7.68, 72), (7.86, 76), (8.15, 79), (8.34, 83), (8.56, 76), (8.74, 71), (8.98, 81), (9.16, 86)]:
    add_marimba_pop(t_tick, midi, amp=0.14, pan=0.35)

# 10.82s: Export click + rising crystal render sweep -> 11.52s "完成 ✓" chime!
add_marimba_pop(10.82, 79, amp=0.20, pan=0.4)
add_whoosh(10.88, 0.62, 400, 1950, amp=0.13)
add_sparkle_chime(11.52, [72, 76, 79, 84, 88], step_s=0.048, amp=0.13)

# 12.35, 12.55, 12.75s: Gentle soft pops for the 3 capability pills
add_marimba_pop(12.35, 76, amp=0.09, pan=-0.35)
add_marimba_pop(12.55, 79, amp=0.09, pan=-0.25)
add_marimba_pop(12.75, 84, amp=0.11, pan=-0.15)

# Soft master limiter + clean fade-out on last 0.45s
peak = max(max(abs(x) for x in left), max(abs(x) for x in right), 1e-6)
gain = min(0.92 / peak, 1.35)
fade_samples = int(0.45 * SR)

frames = bytearray()
for i in range(N_SAMPLES):
    fade = 1.0
    if i > N_SAMPLES - fade_samples:
        fade = (N_SAMPLES - i) / fade_samples
    l = math.tanh(left[i] * gain * 1.1) * 0.92 * fade
    r = math.tanh(right[i] * gain * 1.1) * 0.92 * fade
    frames += struct.pack('<hh', int(max(-32767, min(32767, l * 32767))), int(max(-32767, min(32767, r * 32767))))

out_path = '/Users/mac/gemini-neon-promo/output/soundtrack.wav'
with wave.open(out_path, 'wb') as wf:
    wf.setnchannels(2)
    wf.setsampwidth(2)
    wf.setframerate(SR)
    wf.writeframes(frames)

print(f'Wrote {out_path} ({DURATION:.2f}s, {SR}Hz stereo, peak={peak:.3f})')
