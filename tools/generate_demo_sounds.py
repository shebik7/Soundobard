#!/usr/bin/env python3
"""Synthesizes the demo sounds bundled in sounds/ (all original, generated from scratch).

Usage: python3 tools/generate_demo_sounds.py [output_dir]
Requires numpy and ffmpeg with libmp3lame.
"""
import math
import os
import subprocess
import sys

import numpy as np

SR = 44100
rng = np.random.default_rng(7)


# ---------------------------------------------------------------- primitives

def t_axis(dur):
    return np.arange(int(SR * dur)) / SR


def const(value, dur):
    return np.full(int(SR * dur), float(value))


def glide(f0, f1, dur, curve=1.0):
    x = np.linspace(0, 1, int(SR * dur)) ** curve
    return f0 * (f1 / f0) ** x


def phase(freq):
    return np.cumsum(freq) / SR


def sine(freq):
    return np.sin(2 * np.pi * phase(freq))


def saw(freq):
    p = phase(freq)
    return 2 * (p % 1.0) - 1


def pulse(freq, duty=0.5):
    p = phase(freq) % 1.0
    return np.where(p < duty, 1.0, -1.0)


def noise(dur):
    return rng.uniform(-1, 1, int(SR * dur))


def midi(n):
    return 440.0 * 2 ** ((n - 69) / 12)


def adsr(n, a=0.01, d=0.1, s=0.7, r=0.1):
    a_n, d_n, r_n = int(a * SR), int(d * SR), int(r * SR)
    s_n = max(n - a_n - d_n - r_n, 0)
    e = np.concatenate([
        np.linspace(0, 1, a_n, endpoint=False),
        np.linspace(1, s, d_n, endpoint=False),
        np.full(s_n, s),
        np.linspace(s, 0, r_n),
    ])
    return np.pad(e, (0, max(n - len(e), 0)))[:n]


def decay(n, tau, attack=0.002):
    t = np.arange(n) / SR
    e = np.exp(-t / tau)
    a_n = max(int(attack * SR), 1)
    e[:a_n] *= np.linspace(0, 1, a_n)
    return e


def match_len(values, n):
    """Scalar or per-sample parameter -> array of exactly n samples."""
    v = np.atleast_1d(np.asarray(values, dtype=float))
    if len(v) == 1:
        return np.full(n, v[0])
    return np.pad(v[:n], (0, max(n - len(v), 0)), mode="edge")


def lowpass(x, fc):
    fc = match_len(fc, len(x))
    a = np.exp(-2 * np.pi * fc / SR)
    y = np.empty_like(x)
    prev = 0.0
    for i in range(len(x)):
        prev = (1 - a[i]) * x[i] + a[i] * prev
        y[i] = prev
    return y


def highpass(x, fc):
    return x - lowpass(x, fc)


def bandpass(x, fc, q=2.0):
    """State-variable band-pass with (optionally time-varying) centre frequency."""
    fc = match_len(fc, len(x))
    f = 2 * np.sin(np.pi * np.minimum(fc, SR / 6) / SR)
    damp = 1.0 / q
    low = band = 0.0
    y = np.empty_like(x)
    for i in range(len(x)):
        high = x[i] - low - damp * band
        band += f[i] * high
        low += f[i] * band
        y[i] = band
    return y


def reverb(x, size=1.4, wet=0.25, tau=0.35):
    ir_t = t_axis(size)
    ir = rng.normal(0, 1, len(ir_t)) * np.exp(-ir_t / tau)
    ir = lowpass(ir, 5000)
    ir /= np.sqrt(np.sum(ir ** 2))
    n = len(x) + len(ir)
    size_fft = 1 << (n - 1).bit_length()
    wet_sig = np.fft.irfft(np.fft.rfft(x, size_fft) * np.fft.rfft(ir, size_fft), size_fft)[:n]
    out = np.pad(x, (0, len(ir)))
    return out * (1 - wet) + wet_sig * wet * 0.9


def place(buf, sig, at, gain=1.0):
    i = int(at * SR)
    end = min(i + len(sig), len(buf))
    if end > i:
        buf[i:end] += sig[: end - i] * gain


def silence(dur):
    return np.zeros(int(SR * dur))


def trim_tail(x, threshold=1e-3):
    idx = np.nonzero(np.abs(x) > threshold * np.max(np.abs(x)))[0]
    return x[: idx[-1] + int(0.05 * SR)] if len(idx) else x


def finish(x, target_rms_db=-15.0, peak_db=-2.0):
    x = trim_tail(x - np.mean(x))
    fade = min(int(0.01 * SR), len(x) // 4)
    x[-fade:] *= np.linspace(1, 0, fade)
    rms = np.sqrt(np.mean(x ** 2)) + 1e-12
    peak = np.max(np.abs(x)) + 1e-12
    gain = min(10 ** (target_rms_db / 20) / rms, 10 ** (peak_db / 20) / peak)
    return x * gain


# ------------------------------------------------------------- instruments

def kick(dur=0.35):
    n = int(SR * dur)
    return sine(glide(150, 45, dur, 0.3)) * decay(n, 0.12)


def snare(dur=0.25, tone=190):
    n = int(SR * dur)
    body = sine(const(tone, dur)) * decay(n, 0.05)
    rattle = highpass(noise(dur), 1500) * decay(n, 0.08)
    return 0.5 * body + 0.8 * rattle


def hihat(dur=0.06, open_=False):
    n = int(SR * dur)
    metal = sum(pulse(const(f, dur)) for f in (205.3, 304.4, 369.6, 522.7, 540.0, 800.0))
    sig = highpass(metal / 6 + 0.5 * noise(dur), 7000)
    return sig * decay(n, 0.25 if open_ else 0.02)


def cymbal(dur=1.6):
    n = int(SR * dur)
    metal = sum(pulse(const(f, dur)) for f in (205.3, 304.4, 369.6, 522.7, 540.0, 800.0))
    sig = highpass(metal / 6 + noise(dur), 4500)
    return sig * decay(n, 0.45)


def brass(freq, dur, bright=3000):
    n = len(freq)
    env = adsr(n, 0.03, 0.15, 0.8, min(0.15, dur / 3))
    cutoff = 300 + bright * adsr(n, 0.06, 0.2, 0.6, 0.1)
    tone = saw(freq) + 0.5 * saw(freq * 1.004)
    return np.tanh(1.5 * lowpass(tone, cutoff)) * env


def rhodes(freq_hz, dur, vel=1.0):
    n = int(SR * dur)
    f = const(freq_hz, dur)
    tone = sine(f) + 0.25 * sine(2 * f) * decay(n, 0.3) + 0.15 * sine(7.1 * f) * decay(n, 0.02)
    trem = 1 + 0.25 * np.sin(2 * np.pi * 4.5 * t_axis(dur))
    return tone * decay(n, 1.4, 0.004) * trem * vel


def chord(notes, dur, vel=0.25):
    return sum(rhodes(midi(m), dur, vel) for m in notes)


def sax(notes, tempo_s, breathy=0.12):
    """notes: list of (midi, beats, slide_from_semitones)."""
    pieces = []
    for m, beats, slide in notes:
        dur = beats * tempo_s
        f_target = midi(m)
        n = int(SR * dur)
        f = np.full(n, f_target)
        if slide:
            k = min(int(0.12 * SR), n)
            f[:k] = midi(m + slide) * (f_target / midi(m + slide)) ** np.linspace(0, 1, k)
        vib_depth = np.clip((np.arange(n) / SR - 0.25) / 0.4, 0, 1) * 0.012
        f = f * (1 + vib_depth * np.sin(2 * np.pi * 5.2 * np.arange(n) / SR))
        tone = 0.6 * saw(f) + 0.4 * pulse(f, 0.3)
        tone = bandpass(tone, 650, 1.6) + 0.6 * bandpass(tone, 1700, 2.5) + 0.3 * bandpass(tone, 2900, 3.0)
        tone += breathy * bandpass(noise(dur), 2200, 1.5)
        pieces.append(np.tanh(2.0 * tone) * adsr(n, 0.04, 0.1, 0.85, min(0.12, dur / 3)))
    return np.concatenate(pieces)


def bell(freq_hz, dur, tau=0.6):
    n = int(SR * dur)
    partials = [(1, 1.0, 1.0), (2.76, 0.5, 0.6), (5.4, 0.3, 0.35), (8.93, 0.15, 0.2)]
    return sum(a * sine(const(freq_hz * r, dur)) * decay(n, tau * d) for r, a, d in partials)


# ------------------------------------------------------------------ sounds

def whip():
    out = silence(0.9)
    w_dur = 0.28
    whoosh = bandpass(noise(w_dur), glide(500, 4000, w_dur, 2.0), 3.0)
    whoosh *= np.linspace(0, 1, len(whoosh)) ** 3
    place(out, whoosh, 0.0, 0.5)
    crack_dur = 0.25
    n = int(crack_dur * SR)
    crack = highpass(noise(crack_dur), 2000) * decay(n, 0.012, 0.0003)
    crack[:30] += np.hanning(60)[:30] * 3
    place(out, crack, w_dur, 1.4)
    place(out, bandpass(noise(0.15), 900, 2) * decay(int(0.15 * SR), 0.02), w_dur, 0.6)
    out = reverb(out, 0.8, 0.2, 0.15)
    # A crack is one huge transient; saturate it so it is as loud as the other sounds.
    return np.tanh(6 * out / np.max(np.abs(out)))


def airhorn():
    out = silence(2.0)
    t = 0.0
    for dur in (0.14, 0.14, 0.14, 1.0):
        f = glide(400, 466, dur * 0.3)
        f = np.concatenate([f, const(466, dur - len(f) / SR)])
        tone = saw(f) + saw(f * 1.26) * 0.7 + saw(f * 1.5) * 0.5
        tone = np.tanh(3 * lowpass(tone, 3500)) * adsr(len(f), 0.01, 0.05, 0.9, 0.04)
        place(out, tone, t)
        t += dur + 0.06
    return reverb(out, 1.0, 0.18, 0.2)


def vine_boom():
    dur = 1.6
    n = int(SR * dur)
    f = glide(130, 42, dur, 0.15)
    boom = np.tanh(2.5 * (sine(f) + 0.4 * sine(2 * f))) * decay(n, 0.45)
    click = highpass(noise(0.03), 800) * decay(int(0.03 * SR), 0.005)
    out = boom.copy()
    place(out, click, 0, 0.6)
    return reverb(out, 1.5, 0.3, 0.45)


def badum_tss():
    out = silence(2.2)
    place(out, snare(0.25, 220), 0.0, 0.8)
    tom = lambda f0, f1: sine(glide(f0, f1, 0.4, 0.4)) * decay(int(0.4 * SR), 0.12)
    place(out, tom(200, 130), 0.16, 0.9)
    place(out, tom(150, 90), 0.36, 0.9)
    place(out, kick(), 0.6, 0.8)
    place(out, cymbal(1.6), 0.6, 0.55)
    return reverb(out, 1.0, 0.15, 0.25)


def sad_trombone():
    notes = [(70, 0.42), (69, 0.42), (68, 0.42), (67, 1.6)]
    pieces = []
    for i, (m, dur) in enumerate(notes):
        n = int(SR * dur)
        f = np.full(n, midi(m - 12))
        if i == len(notes) - 1:
            depth = np.clip(t_axis(dur) / 0.4, 0, 1) * 0.03
            f *= 1 + depth * np.sin(2 * np.pi * 5.5 * t_axis(dur))
            f *= glide(1.0, 0.94, dur, 3.0)
        tone = saw(f) + 0.6 * pulse(f, 0.35)
        wah = 300 + 1700 * adsr(n, 0.08, 0.15, 0.55, 0.12)
        pieces.append(np.tanh(2 * lowpass(tone, wah)) * adsr(n, 0.03, 0.1, 0.9, 0.12))
    return reverb(np.concatenate(pieces), 1.0, 0.2, 0.3)


def bow_chicka():
    beat = 0.6
    bars = 2
    out = silence(beat * 4 * bars + 1.0)
    em7 = [midi(m) for m in (52, 55, 59, 62)]

    def guitar(dur, sweep, scratch=False):
        n = int(SR * dur)
        tone = sum(saw(const(f * (1 + 0.002 * k), dur)) for k, f in enumerate(em7)) / 3
        if scratch:
            tone = 0.4 * tone + 0.8 * noise(dur)
            env = decay(n, 0.025)
        else:
            env = adsr(n, 0.01, 0.05, 0.85, 0.06)
        return np.tanh(2.5 * bandpass(tone, sweep, 4.0)) * env

    for bar in range(bars):
        b0 = bar * 4 * beat
        place(out, guitar(0.38, glide(350, 1900, 0.38, 0.7)), b0, 0.9)              # bow
        place(out, guitar(0.08, const(1600, 0.08), True), b0 + 0.75 * beat, 0.7)   # chic-
        place(out, guitar(0.08, const(1300, 0.08), True), b0 + 1.0 * beat, 0.7)    # -ka
        sweep = np.concatenate([glide(300, 2200, 0.25), glide(2200, 700, 0.35)])
        place(out, guitar(0.6, sweep), b0 + 1.5 * beat, 0.9)                       # wow
        sweep = np.concatenate([glide(300, 2400, 0.3), glide(2400, 500, 0.7)])
        place(out, guitar(1.0, sweep), b0 + 2.5 * beat, 0.9)                       # wow
        for k in range(8):
            place(out, hihat(0.06, k % 4 == 3), b0 + k * beat / 2, 0.25)
        place(out, kick(), b0, 0.7)
        place(out, kick(), b0 + 2 * beat, 0.7)
        place(out, snare(), b0 + beat, 0.35)
        place(out, snare(), b0 + 3 * beat, 0.35)
        bass = lambda m, d: lowpass(saw(const(midi(m), d)), 600) * adsr(int(d * SR), 0.01, 0.1, 0.7, 0.05)
        place(out, bass(28, 0.5), b0, 0.5)
        place(out, bass(28, 0.25), b0 + 1.5 * beat, 0.5)
        place(out, bass(31, 0.25), b0 + 2.5 * beat, 0.5)
        place(out, bass(33, 0.5), b0 + 3 * beat, 0.5)
    return reverb(out, 1.2, 0.18, 0.3)


def sexy_sax():
    beat = 0.8
    melody = [
        (64, 1.5, -2), (67, 0.5, 0), (69, 1.0, 0), (72, 1.0, -1),
        (71, 0.5, 0), (69, 0.5, 0), (67, 0.5, 0), (64, 2.5, 0),
    ]
    lead = sax(melody, beat)
    out = silence(len(lead) / SR + 1.5)
    place(out, lead, 0.1, 0.55)
    am9 = [45, 52, 55, 59, 60]
    dm9 = [50, 53, 57, 60, 64]
    for i, ch in enumerate([am9, dm9, am9, dm9]):
        place(out, chord(ch, beat * 2.2, 0.22), i * beat * 2)
        place(out, lowpass(sine(const(midi(ch[0] - 12), beat * 1.8)), 400) * adsr(int(beat * 1.8 * SR), 0.02, 0.2, 0.6, 0.2), i * beat * 2, 0.5)
    for k in range(int(len(out) / SR / (beat / 2))):
        place(out, hihat(0.05), k * beat / 2 + (0.08 if k % 2 else 0), 0.12)
    return reverb(out, 1.8, 0.28, 0.5)


def jazz_lounge():
    beat = 0.5
    out = silence(beat * 12 + 1.5)
    progression = [([50, 53, 57, 60, 64], [38, 41, 45, 48]),
                   ([43, 53, 57, 59, 64], [43, 47, 50, 53]),
                   ([48, 52, 55, 59, 62], [36, 40, 43, 47])]
    for i, (ch, walk) in enumerate(progression):
        t0 = i * 4 * beat
        place(out, chord(ch, beat * 1.4, 0.2), t0)
        place(out, chord(ch, beat * 2.4, 0.18), t0 + 1.66 * beat)
        for k, m in enumerate(walk):
            b = lowpass(saw(const(midi(m), beat * 0.9)), 500) * adsr(int(beat * 0.9 * SR), 0.01, 0.15, 0.5, 0.1)
            place(out, b, t0 + k * beat, 0.45)
        for k in range(4):
            place(out, hihat(0.25, True), t0 + k * beat, 0.12)
            place(out, hihat(0.05), t0 + k * beat + 0.66 * beat, 0.08)
    place(out, chord([48, 52, 55, 59, 62, 69], 3.0, 0.2), 12 * beat)
    return reverb(out, 1.5, 0.22, 0.4)


def dun_dun_dunnn():
    out = silence(3.2)
    for at, notes, dur in ((0.0, (48, 55), 0.3), (0.45, (51, 58), 0.3), (0.9, (47, 54, 60), 2.0)):
        for m in notes:
            place(out, brass(const(midi(m), dur), dur, 2500), at, 0.35)
        timp = sine(glide(midi(notes[0] - 12) * 1.1, midi(notes[0] - 12), dur, 0.2)) * decay(int(dur * SR), 0.5)
        place(out, timp, at, 0.7)
    roll = snare(0.12, 120)
    for k in range(int(1.6 / 0.05)):
        place(out, roll * 0.25 * (1 - k / 40), 0.95 + k * 0.05)
    return reverb(out, 1.6, 0.25, 0.45)


def crickets():
    dur = 4.0
    out = 0.01 * lowpass(noise(dur), 1000)
    for carrier, period, offset in ((4400, 0.62, 0.0), (4850, 0.71, 0.3)):
        t = offset
        while t < dur - 0.2:
            for p in range(3):
                n = int(0.018 * SR)
                chirp = sine(const(carrier, 0.018)) * np.hanning(n)
                place(out, chirp, t + p * 0.032, 0.35)
            t += period * rng.uniform(0.9, 1.1)
    return reverb(out, 1.0, 0.2, 0.3)


def bonk():
    dur = 0.5
    n = int(SR * dur)
    body = sine(glide(420, 160, dur, 0.15)) * decay(n, 0.07)
    wood = bandpass(noise(dur), 950, 6) * decay(n, 0.03)
    ring = sine(const(612, dur)) * decay(n, 0.09) * 0.3
    return reverb(np.tanh(2 * (body + 0.8 * wood + ring)), 0.6, 0.12, 0.12)


def fart():
    dur = 1.3
    n = int(SR * dur)
    jitter = lowpass(rng.normal(0, 1, n), 25) * 40
    f = np.clip(glide(95, 70, dur) + jitter + 25 * np.sin(2 * np.pi * 7 * t_axis(dur)), 40, 180)
    tone = pulse(f, 0.18) + 0.3 * noise(dur)
    tone = lowpass(lowpass(tone, 900), 1200)
    env = adsr(n, 0.02, 0.1, 0.8, 0.25) * (0.75 + 0.25 * np.sin(2 * np.pi * 11 * t_axis(dur)))
    out = np.tanh(2.2 * tone) * env
    tail_dur = 0.25
    tail = bandpass(noise(tail_dur), glide(500, 1600, tail_dur), 2) * decay(int(tail_dur * SR), 0.06)
    return np.concatenate([out, tail * 0.6])


def boing():
    dur = 1.0
    t = t_axis(dur)
    wobble = 1 + 0.35 * np.exp(-t / 0.3) * np.sin(2 * np.pi * 13 * t)
    f = glide(160, 260, dur, 0.5) * wobble
    tone = sine(f) + 0.4 * sine(2 * f) + 0.2 * saw(f)
    return tone * decay(len(t), 0.35, 0.003)


def ding_correct():
    out = silence(1.8)
    place(out, bell(midi(76), 1.5, 0.7), 0.0, 0.6)
    place(out, bell(midi(81), 1.6, 0.9), 0.14, 0.7)
    return reverb(out, 1.0, 0.18, 0.3)


def buzzer_wrong():
    out = silence(1.3)
    for at, dur in ((0.0, 0.28), (0.36, 0.75)):
        tone = pulse(const(148, dur)) + pulse(const(152.5, dur)) + 0.5 * saw(const(74, dur))
        place(out, np.tanh(1.5 * lowpass(tone, 2500)) * adsr(int(dur * SR), 0.005, 0.02, 0.9, 0.03), at, 0.5)
    return out


def tada():
    out = silence(2.6)
    for m in (55, 59, 62, 67):
        place(out, brass(const(midi(m), 0.13), 0.13, 3500), 0.0, 0.25)
    for m in (60, 64, 67, 72, 76):
        f = const(midi(m), 1.6) * (1 + 0.006 * np.sin(2 * np.pi * 5 * t_axis(1.6)))
        place(out, brass(f, 1.6, 4000), 0.2, 0.22)
    place(out, cymbal(1.8), 0.2, 0.35)
    place(out, kick(), 0.2, 0.6)
    return reverb(out, 1.4, 0.22, 0.35)


def fanfare():
    beat = 0.43
    trip = beat / 3
    seq = [(67, trip), (72, trip), (76, trip), (79, beat), (76, beat / 2), (79, beat * 3)]
    out = silence(sum(d for _, d in seq) + 1.5)
    t = 0.0
    for m, d in seq:
        f = const(midi(m), d * 0.95)
        place(out, brass(f, d * 0.95, 4000), t, 0.35)
        place(out, brass(f / 2, d * 0.95, 2000), t, 0.2)
        place(out, snare(0.15), t, 0.2)
        t += d
    end_at = t - beat * 3
    for m in (48, 60, 64, 67):
        place(out, brass(const(midi(m), beat * 3), beat * 3, 3000), end_at, 0.15)
    place(out, cymbal(2.0), end_at, 0.35)
    place(out, kick(), end_at, 0.6)
    return reverb(out, 1.5, 0.22, 0.4)


def applause():
    dur = 4.0
    out = silence(dur + 0.2)
    templates = []
    for _ in range(12):
        d = 0.04
        templates.append(bandpass(noise(d), rng.uniform(900, 2600), 1.8) * decay(int(d * SR), rng.uniform(0.006, 0.012), 0.0005))
    t = 0.0
    while t < dur:
        intensity = min(t / 0.5, 1.0) * min((dur - t) / 1.2, 1.0)
        rate = 15 + 110 * intensity
        t += rng.exponential(1 / rate)
        place(out, templates[rng.integers(len(templates))], t, rng.uniform(0.3, 1.0) * (0.3 + 0.7 * intensity))
    return reverb(out, 1.2, 0.3, 0.3)


def ka_ching():
    out = silence(2.0)
    place(out, highpass(noise(0.05), 1200) * decay(int(0.05 * SR), 0.01), 0.0, 0.8)
    place(out, bandpass(noise(0.08), 600, 3) * decay(int(0.08 * SR), 0.02), 0.07, 0.8)
    place(out, bell(2093, 1.6, 0.6), 0.16, 0.5)
    place(out, bell(2637, 1.4, 0.5), 0.16, 0.35)
    for _ in range(9):
        place(out, bell(rng.uniform(3500, 6000), 0.3, 0.05), 0.2 + rng.uniform(0, 0.5), 0.12)
    return reverb(out, 1.0, 0.2, 0.25)


def suspense():
    dur = 3.4
    t = t_axis(dur)
    crescendo = (t / dur) ** 2
    trem = 0.6 + 0.4 * np.sin(2 * np.pi * 11 * t)
    tone = sum(saw(const(midi(m), dur) * (1 + 0.003 * k)) for k, m in enumerate((45, 46, 52, 57, 58)))
    strings = lowpass(tone, 400 + 3500 * crescendo) * crescendo * trem / 3
    out = np.concatenate([strings, silence(1.8)])
    hit = sum(brass(const(midi(m), 1.2), 1.2, 3500) for m in (33, 45, 52, 58))
    place(out, hit, dur, 0.45)
    place(out, cymbal(1.6), dur, 0.4)
    place(out, kick(0.6), dur, 0.9)
    return reverb(out, 1.6, 0.25, 0.45)


def drumroll():
    out = silence(4.4)
    t, step = 0.0, 0.07
    while t < 2.6:
        vol = 0.25 + 0.6 * (t / 2.6) ** 1.5
        place(out, snare(0.1, 200) * rng.uniform(0.8, 1.0), t, vol)
        t += step
        step = max(0.035, step * 0.985)
    place(out, cymbal(1.8), 2.65, 0.6)
    place(out, kick(), 2.65, 1.0)
    return reverb(out, 1.4, 0.2, 0.35)


SOUNDS = [
    ("01_Bič_(whiplash)", whip),
    ("02_Airhorn", airhorn),
    ("03_Vine_boom", vine_boom),
    ("04_Ba-dum-tss", badum_tss),
    ("05_Sad_trombone", sad_trombone),
    ("06_Bow_chicka_wow_wow", bow_chicka),
    ("07_Sexy_saxofon", sexy_sax),
    ("08_Jazzový_podkres", jazz_lounge),
    ("09_Dun_dun_dunnn", dun_dun_dunnn),
    ("10_Cvrčci_(trapné_ticho)", crickets),
    ("11_Bonk", bonk),
    ("12_Prd", fart),
    ("13_Boing", boing),
    ("14_Ding_(správně)", ding_correct),
    ("15_Bzučák_(špatně)", buzzer_wrong),
    ("16_Tadá", tada),
    ("17_Fanfára", fanfare),
    ("18_Potlesk", applause),
    ("19_Ka-ching", ka_ching),
    ("20_Napětí", suspense),
    ("21_Vířivé_bubny", drumroll),
]


def encode(samples, path):
    pcm = np.clip(samples, -1, 1).astype("<f4").tobytes()
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "f32le", "-ar", str(SR), "-ac", "1", "-i", "-",
         "-codec:a", "libmp3lame", "-b:a", "128k", "-map_metadata", "-1", path],
        input=pcm, check=True,
    )


def main():
    out_dir = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "..", "sounds")
    only = set(sys.argv[2:])
    os.makedirs(out_dir, exist_ok=True)
    for name, fn in SOUNDS:
        if only and name not in only:
            continue
        audio = finish(fn())
        path = os.path.join(out_dir, name + ".mp3")
        encode(audio, path)
        print(f"{name}: {len(audio) / SR:.2f}s")


if __name__ == "__main__":
    main()
