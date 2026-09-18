import numpy as np
import wave, math, struct, os

def compose_moti_showcase_bgm(duration=41.8, output_path="moti_showcase_104bpm.wav"):
    sr = 44100
    bpm = 104
    beat_dur = 60.0 / bpm          # ~0.5769s
    sixteenth_dur = beat_dur / 4.0 # ~0.1442s
    total_samples = int(duration * sr)

    left = np.zeros(total_samples, dtype=np.float32)
    right = np.zeros(total_samples, dtype=np.float32)

    # --- 1. 物理建模音色生成器 ---

    # (A) 古筝/琵琶拨弦 (Guzheng / Pipa Pluck) - 琴弦物理振动模型 (Karplus-Strong 与谐波加算混合)
    def guzheng_pluck(freq, dur=0.6, brightness=0.55):
        num_s = int(dur * sr)
        t = np.linspace(0, dur, num_s, endpoint=False)
        # 丝弦复音: 基频 + 丰富泛音 + 微弱弦音色不规则振动
        tone = (1.00 * np.sin(2 * np.pi * freq * t) +
                0.55 * np.sin(2 * np.pi * freq * 2.005 * t) * np.exp(-1.5 * t) +
                0.35 * np.sin(2 * np.pi * freq * 3.01 * t) * np.exp(-3.0 * t) +
                0.20 * np.sin(2 * np.pi * freq * 4.02 * t) * np.exp(-5.0 * t) +
                0.12 * np.sin(2 * np.pi * freq * 5.03 * t) * np.exp(-8.0 * t))
        # 拨片初触的高频瞬态 (Transient Pick Click)
        click = np.random.uniform(-1, 1, min(200, num_s)) * np.linspace(1, 0, min(200, num_s)) * 0.4
        tone[:len(click)] += click
        
        # 丝弦自然衰减包络
        env = np.exp(-5.5 * t)
        return tone * env * 0.48

    # (B) 竹笛/箫气息泛音 (Bamboo Flute / Dizi Harmonic)
    def flute_tone(freq, dur=1.2):
        num_s = int(dur * sr)
        t = np.linspace(0, dur, num_s, endpoint=False)
        # 竹管振动 + 颤音 (Vibrato 5Hz)
        vib = 1.0 + 0.008 * np.sin(2 * np.pi * 5.2 * t)
        phase = 2 * np.pi * np.cumsum(freq * vib) / sr
        # 奇次谐波为主 (笛膜开闭管特性)
        tone = (0.75 * np.sin(phase) +
                0.20 * np.sin(phase * 2) +
                0.35 * np.sin(phase * 3) +
                0.08 * np.sin(phase * 4))
        # 模拟气息杂音 (Breathy Air Noise)
        air = np.random.uniform(-1, 1, num_s) * 0.04
        # 吹奏包络 (软起音 0.06s，慢衰减)
        att_s = int(0.06 * sr)
        env = np.ones(num_s, dtype=np.float32)
        env[:att_s] = np.sin(np.linspace(0, np.pi/2, att_s))
        env[att_s:] = np.exp(-2.2 * (t[att_s:] - 0.06))
        return (tone + air) * env * 0.28

    # (C) 暖调 Rhodes 爵士电钢琴 (Warm Rhodes / Lofi Chords)
    def rhodes_chord_note(freq, dur=1.4):
        num_s = int(dur * sr)
        t = np.linspace(0, dur, num_s, endpoint=False)
        # 钟声感音叉 (Tine) + 暖管放大
        tone = (0.75 * np.sin(2 * np.pi * freq * t) +
                0.30 * np.sin(2 * np.pi * freq * 2 * t) * np.exp(-4 * t) +
                0.15 * np.sin(2 * np.pi * freq * 3 * t) * np.exp(-7 * t))
        att_s = int(0.012 * sr)
        env = np.ones(num_s, dtype=np.float32)
        env[:att_s] = np.linspace(0, 1, att_s)
        env[att_s:] = np.exp(-3.2 * (t[att_s:] - 0.012))
        return tone * env * 0.22

    # (D) 暖调深沉 Lo-Fi 贝斯 (Smooth Neo-Soul Sub Bass)
    def lofi_bass(freq, dur=0.6):
        num_s = int(dur * sr)
        t = np.linspace(0, dur, num_s, endpoint=False)
        tone = np.sin(2 * np.pi * freq * t) + 0.35 * np.sin(2 * np.pi * freq * 2 * t)
        # 软饱和温暖削峰
        tone = np.tanh(tone * 1.5)
        att_s = int(0.008 * sr)
        env = np.ones(num_s, dtype=np.float32)
        env[:att_s] = np.linspace(0, 1, att_s)
        env[att_s:] = np.exp(-4.2 * (t[att_s:] - 0.008))
        return tone * env * 0.58

    # (E) Chillhop 节奏组件: 软底鼓 (Soft Round Kick)
    def make_chill_kick():
        dur = 0.16
        num_s = int(dur * sr)
        t = np.linspace(0, dur, num_s, endpoint=False)
        pitch = 50 + (130 - 50) * np.exp(-35 * t)
        phase = 2 * np.pi * np.cumsum(pitch) / sr
        env = np.exp(-15 * t)
        return np.sin(phase) * env * 0.65

    # (F) Chillhop 节奏组件: 木质拍板/响指 (Wooden Rim / Snare)
    def make_wood_snap():
        dur = 0.07
        num_s = int(dur * sr)
        t = np.linspace(0, dur, num_s, endpoint=False)
        tone = (np.sin(2 * np.pi * 920 * t) + 0.5 * np.sin(2 * np.pi * 1450 * t)) * np.exp(-65 * t)
        noise = np.random.uniform(-1, 1, num_s) * np.exp(-45 * t) * 0.3
        return (tone + noise) * 0.50

    # (G) 纸墨细碎沙锤 (Paper Texture Shaker)
    def make_paper_shaker(accent=False):
        dur = 0.06 if accent else 0.035
        num_s = int(dur * sr)
        t = np.linspace(0, dur, num_s, endpoint=False)
        noise = np.random.uniform(-1, 1, num_s)
        # 高频带通
        noise = noise - np.roll(noise, 1)
        env = np.exp((-40 if accent else -85) * t)
        return noise * env * (0.22 if accent else 0.14)

    # --- 2. 调式音阶与和声走向 ---
    # G 宫调式 (G 宫 - A 商 - B 角 - D 徵 - E 羽)
    # 搭配现代 Gmaj7 - Em7 - Cmaj7 - Dadd9 和弦走向
    FREQ = {
        'G1': 49.00, 'A1': 55.00, 'B1': 61.74, 'C2': 65.41, 'D2': 73.42, 'E2': 82.41,
        'G2': 98.00, 'A2': 110.00, 'B2': 123.47, 'C3': 130.81, 'D3': 146.83, 'E3': 164.81, 'F#3': 185.00,
        'G3': 196.00, 'A3': 220.00, 'B3': 246.94, 'C4': 261.63, 'D4': 293.66, 'E4': 329.63, 'F#4': 369.99,
        'G4': 392.00, 'A4': 440.00, 'B4': 493.88, 'C5': 523.25, 'D5': 587.33, 'E5': 659.25, 'F#5': 739.99,
        'G5': 783.99, 'A5': 880.00, 'B5': 987.77, 'D6': 1174.66, 'E6': 1318.51
    }

    # 4小节循环和弦
    CHORDS = [
        # (Bass, Rhodes 和弦音, 古筝五音旋律池, 笛子长音)
        ('G2', ['G3', 'B3', 'D4', 'F#4'], ['G4', 'B4', 'D5', 'E5', 'G5'], 'B4'),
        ('E2', ['E3', 'G3', 'B3', 'D4'],  ['E4', 'G4', 'B4', 'D5', 'E5'], 'G4'),
        ('C2', ['C3', 'E3', 'G3', 'B3'],  ['C4', 'E4', 'G4', 'B4', 'D5'], 'E4'),
        ('D2', ['D3', 'F#3', 'A3', 'E4'], ['D4', 'F#4', 'A4', 'D5', 'E5'], 'F#4')
    ]

    total_bars = int(np.ceil(duration / (4 * beat_dur)))

    def mix_sound(sound, start_sample, pan=0.5):
        end_sample = min(start_sample + len(sound), total_samples)
        if start_sample >= total_samples or end_sample <= start_sample:
            return
        chunk = sound[:end_sample - start_sample]
        left[start_sample:end_sample] += chunk * (1.0 - pan)
        right[start_sample:end_sample] += chunk * pan

    kick = make_chill_kick()
    wood = make_wood_snap()
    shaker_soft = make_paper_shaker(False)
    shaker_accent = make_paper_shaker(True)

    # 模拟细微的宣纸/书斋温暖微粒白噪音 (Soft Vinyl / Paper ambience)
    paper_noise = np.random.normal(0, 0.006, total_samples).astype(np.float32)
    left += paper_noise
    right += paper_noise

    for bar in range(total_bars):
        chord_data = CHORDS[bar % 4]
        bass_key, rhodes_keys, guzheng_pool, flute_lead = chord_data

        # 每小节 16 个十六分音符步长
        for step in range(16):
            # 引入 Lo-Fi Chillhop 微妙的 Swing 摇摆微延迟 (Odd sixteenths delayed by 18ms)
            swing_offset = 0.016 if (step % 2 == 1) else 0.0
            t_sec = (bar * 16 + step) * sixteenth_dur + swing_offset
            idx = int(t_sec * sr)
            if idx >= total_samples:
                break

            # 1. 节拍层 (Chillhop Rhythm @ 104 BPM)
            # Kick: step 0 (强拍) 与 step 10 (切分推力)
            if step in [0, 10]:
                mix_sound(kick, idx, 0.5)
            # Wood Snap: step 4, 12 (反拍 2, 4)
            if step in [4, 12]:
                mix_sound(wood, idx, 0.52)
            # Paper Shaker: 每 16 分音符轻微点缀，step 6, 14 重音
            if step in [6, 14]:
                mix_sound(shaker_accent, idx, 0.62)
            else:
                mix_sound(shaker_soft, idx, 0.38)

            # 2. 贝斯层 (Warm Sub Bass)
            if step == 0:
                b_s = lofi_bass(FREQ[bass_key], dur=0.52)
                mix_sound(b_s, idx, 0.5)
            elif step == 8:
                # 八度/五度轻跃
                b_s = lofi_bass(FREQ[bass_key] * 1.5, dur=0.35)
                mix_sound(b_s, idx, 0.5)

            # 3. 伴奏和弦 (Warm Rhodes Jazz Chords) - 落在反拍 step 2 和 step 8
            if step in [2, 8]:
                for c_i, c_k in enumerate(rhodes_keys):
                    c_s = rhodes_chord_note(FREQ[c_k], dur=0.75)
                    pan_val = 0.32 + 0.12 * c_i
                    mix_sound(c_s, idx, pan_val)

            # 4. 主奏意象 (古筝灵动指尖流转 Guzheng Melody)
            # 采用具有盛唐文墨灵气的五音旋律织体 (如高山流水般的切分琶音)
            melody_matrix = [
                # Bar 1: G 宫调起笔
                [0, 2, 4, 2, 3, 1, 4, 2, 0, 3, 4, 2, 3, 4, 1, 2],
                # Bar 2: 羽音微转
                [1, 3, 2, 4, 2, 0, 3, 1, 4, 2, 1, 3, 2, 4, 3, 1],
                # Bar 3: 角音舒展
                [0, 1, 3, 2, 4, 1, 3, 0, 2, 4, 3, 1, 4, 2, 3, 0],
                # Bar 4: 徵音昂扬推进
                [2, 3, 4, 1, 3, 4, 2, 3, 4, 2, 3, 4, 2, 1, 0, 2]
            ]
            pat = melody_matrix[bar % 4]
            note_idx = pat[step]
            pitch_freq = FREQ[guzheng_pool[note_idx % len(guzheng_pool)]]
            # 偶数步位偶尔点缀高八度晶莹泛音
            if step in [4, 12]:
                pitch_freq *= 2.0

            g_sound = guzheng_pluck(pitch_freq, dur=0.42, brightness=0.6)
            # 声像流动 (如水墨左右晕染)
            pan_val = 0.22 if (step % 4 < 2) else 0.78
            mix_sound(g_sound, idx, pan_val)

        # 5. 竹笛气韵 (每 2 小节一次的轻柔长音呼应)
        if bar % 2 == 0:
            flute_idx = int((bar * 16 + 4) * sixteenth_dur * sr)
            flute_s = flute_tone(FREQ[flute_lead], dur=2.2)
            mix_sound(flute_s, flute_idx, 0.45)

    # --- 3. 混音后处理 (Mastering) ---
    # 空间回响 (Ambient Reverb / StereoSpatial)
    rev_samples = int(0.14 * sr)
    decay = 0.24
    left[rev_samples:] += right[:-rev_samples] * decay
    right[rev_samples:] += left[:-rev_samples] * decay

    # 结尾 1.5 秒平滑淡出
    fade_s = int(1.5 * sr)
    fade = np.linspace(1.0, 0.0, fade_s)
    left[-fade_s:] *= fade
    right[-fade_s:] *= fade

    # 动态软限幅器 (Limiter to prevent clipping)
    peak = max(np.max(np.abs(left)), np.max(np.abs(right)))
    print("Master peak before limiter:", peak)
    if peak > 0.01:
        left_norm = np.tanh(left / peak * 1.15) * 0.90
        right_norm = np.tanh(right / peak * 1.15) * 0.90
    else:
        left_norm = left
        right_norm = right

    # 导出 16-bit 44.1kHz WAV
    left_i16 = (left_norm * 32767).astype(np.int16)
    right_i16 = (right_norm * 32767).astype(np.int16)
    interleaved = np.empty((total_samples * 2,), dtype=np.int16)
    interleaved[0::2] = left_i16
    interleaved[1::2] = right_i16

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with wave.open(output_path, 'wb') as f:
        f.setnchannels(2)
        f.setsampwidth(2)
        f.setframerate(sr)
        f.writeframes(interleaved.tobytes())

    print(f"Generated 《墨染流光》 (104 BPM Neo-Chinoiserie Chillhop) successfully: {output_path} ({os.path.getsize(output_path)} bytes)")

if __name__ == '__main__':
    out = "D:/english-multiple-choice-practice-machine/docs/moti_showcase_104bpm.wav"
    compose_moti_showcase_bgm(41.8, out)
