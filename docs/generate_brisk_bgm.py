import numpy as np
import wave, math, struct, os

def generate_brisk_bgm(duration=42.0, output_path="brisk_bgm.wav"):
    sr = 44100
    bpm = 126
    beat_dur = 60.0 / bpm
    sixteenth_dur = beat_dur / 4.0
    total_samples = int(duration * sr)
    
    # 初始化左右声道
    left = np.zeros(total_samples, dtype=np.float32)
    right = np.zeros(total_samples, dtype=np.float32)
    
    # --- 辅助生成函数 ---
    
    # 1. 声音包络 (ADSR 简化版: 快速 attack, 指数 decay)
    def make_envelope(num_samples, attack=0.005, decay_rate=8.0):
        t = np.linspace(0, num_samples / sr, num_samples, endpoint=False)
        att_samples = int(attack * sr)
        env = np.ones(num_samples, dtype=np.float32)
        if att_samples > 0 and att_samples < num_samples:
            env[:att_samples] = np.linspace(0, 1, att_samples)
            env[att_samples:] = np.exp(-decay_rate * (t[att_samples:] - attack))
        else:
            env = np.exp(-decay_rate * t)
        return env

    # 2. 木琴/马林巴/清脆八音盒音色 (Marimba / Kalimba Pluck)
    def marimba_note(freq, dur=0.35, decay=9.0):
        num_s = int(dur * sr)
        t = np.linspace(0, dur, num_s, endpoint=False)
        # 基频 + 3次谐波 (木质乐器特征: 偶次谐波弱, 3次泛音适度)
        tone = (1.0 * np.sin(2 * np.pi * freq * t) +
                0.35 * np.sin(2 * np.pi * freq * 2.75 * t) +
                0.15 * np.sin(2 * np.pi * freq * 4.0 * t) +
                0.08 * np.sin(2 * np.pi * freq * 5.4 * t))
        env = make_envelope(num_s, attack=0.003, decay_rate=decay)
        return tone * env * 0.45

    # 3. 温暖和弦铺底音色 (Warm Electric Piano / Harp Pluck)
    def chord_note(freq, dur=0.8):
        num_s = int(dur * sr)
        t = np.linspace(0, dur, num_s, endpoint=False)
        tone = (0.7 * np.sin(2 * np.pi * freq * t) +
                0.25 * np.sin(2 * np.pi * freq * 2 * t) +
                0.1 * np.sin(2 * np.pi * freq * 3 * t))
        env = make_envelope(num_s, attack=0.015, decay_rate=4.5)
        return tone * env * 0.25

    # 4. 弹性贝斯音色 (Bouncy Sub/Synth Bass)
    def bass_note(freq, dur=0.4):
        num_s = int(dur * sr)
        t = np.linspace(0, dur, num_s, endpoint=False)
        # 饱满带一点温暖过载
        tone = np.sin(2 * np.pi * freq * t) + 0.3 * np.sin(2 * np.pi * freq * 2 * t)
        tone = np.tanh(tone * 1.4)
        env = make_envelope(num_s, attack=0.005, decay_rate=6.5)
        return tone * env * 0.55

    # 5. 打击乐: 软底鼓 (Kick)
    def make_kick():
        dur = 0.12
        num_s = int(dur * sr)
        t = np.linspace(0, dur, num_s, endpoint=False)
        # 快速俯冲频率从 140Hz 降到 45Hz
        pitch = 45 + (140 - 45) * np.exp(-40 * t)
        phase = 2 * np.pi * np.cumsum(pitch) / sr
        env = np.exp(-18 * t)
        return np.sin(phase) * env * 0.65

    # 6. 打击乐: 清脆沙锤/踩镲 (Hi-hat / Shaker)
    def make_hihat(open_hat=False):
        dur = 0.08 if open_hat else 0.035
        num_s = int(dur * sr)
        t = np.linspace(0, dur, num_s, endpoint=False)
        # 高频噪声
        noise = np.random.uniform(-1, 1, num_s)
        # 简单高通滤波
        noise = noise - np.roll(noise, 1)
        decay = 35 if open_hat else 90
        env = np.exp(-decay * t)
        return noise * env * 0.22

    # 7. 打击乐: 清脆木质响指/小军鼓 (Wood Rimshot / Snap)
    def make_rimshot():
        dur = 0.06
        num_s = int(dur * sr)
        t = np.linspace(0, dur, num_s, endpoint=False)
        tone = np.sin(2 * np.pi * 880 * t) * np.exp(-70 * t) * 0.4
        noise = np.random.uniform(-1, 1, num_s) * np.exp(-50 * t) * 0.25
        return (tone + noise) * 0.55

    # 音符频率表 (以 D Major / 东方五音宫商角徵羽为核心: D, E, F#, A, B)
    # D大调极具明媚感与上进朝气
    NOTES = {
        'D2': 73.42, 'E2': 82.41, 'F#2': 92.50, 'G2': 98.00, 'A2': 110.00, 'B2': 123.47, 'C#3': 138.59,
        'D3': 146.83, 'E3': 164.81, 'F#3': 185.00, 'G3': 196.00, 'A3': 220.00, 'B3': 246.94, 'C#4': 277.18,
        'D4': 293.66, 'E4': 329.63, 'F#4': 369.99, 'G4': 392.00, 'A4': 440.00, 'B4': 493.88, 'C#5': 554.37,
        'D5': 587.33, 'E5': 659.25, 'F#5': 739.99, 'A5': 880.00, 'B5': 987.77, 'D6': 1174.66
    }

    # 和弦进程 (每小节 4 拍, 4 小节循环):
    # Bar 1: Dmaj7 (D - F# - A - C#) -> 明媚展开
    # Bar 2: Bm7   (B - D - F# - A)  -> 灵动转折
    # Bar 3: Gmaj7 (G - B - D - F#)  -> 开阔舒展
    # Bar 4: Asus4 -> A (A - D - E -> A - C# - E) -> 欢快推进
    PROGRESSION = [
        # (Bass root, Chord notes, Arp scale)
        ('D2', ['D3', 'F#3', 'A3', 'C#4'], ['D4', 'F#4', 'A4', 'D5', 'C#5', 'A4', 'F#4', 'E4']),
        ('B2', ['B2', 'D3', 'F#3', 'A3'],  ['B3', 'D4', 'F#4', 'B4', 'A4', 'F#4', 'D4', 'E4']),
        ('G2', ['G2', 'B2', 'D3', 'F#3'],  ['G3', 'B3', 'D4', 'G4', 'F#4', 'D4', 'B3', 'D4']),
        ('A2', ['A2', 'C#3', 'E3', 'A3'],  ['A3', 'C#4', 'E4', 'A4', 'B4', 'A4', 'F#4', 'E4']),
    ]

    total_bars = int(np.ceil(duration / (4 * beat_dur)))
    
    def mix_into(target, sound, start_idx, pan=0.5):
        # pan: 0=left, 1=right
        end_idx = min(start_idx + len(sound), total_samples)
        part = sound[:end_idx - start_idx]
        left[start_idx:end_idx] += part * (1.0 - pan)
        right[start_idx:end_idx] += part * pan

    kick = make_kick()
    rim = make_rimshot()
    hihat = make_hihat(False)
    open_hihat = make_hihat(True)

    current_sample = 0

    for bar_i in range(total_bars):
        chord_info = PROGRESSION[bar_i % 4]
        bass_note_name, chord_note_names, melody_pool = chord_info
        
        # 1小节内 16 个十六分音符
        for step in range(16):
            time_offset = (bar_i * 16 + step) * sixteenth_dur
            idx = int(time_offset * sr)
            if idx >= total_samples:
                break
                
            beat_pos = step % 4  # 0, 1, 2, 3 在每拍里
            beat_num = step // 4 # 0, 1, 2, 3 在每小节里
            
            # --- 节奏轨道 (Brisk Beat) ---
            # 1. Kick: 每拍正拍 0, 或者切分节奏 (第 0, 6, 10 拍)
            if step in [0, 6, 10]:
                mix_into(left, kick, idx, 0.5)
                
            # 2. Rimshot (军鼓/响指): 落在第 2 拍和第 4 拍正拍 (step 4, 12)
            if step in [4, 12]:
                mix_into(left, rim, idx, 0.52)
                
            # 3. Hi-hat (轻快点缀): 每个奇数 16 分音符加反拍 (营造跳跃感)
            if step % 2 == 1:
                mix_into(left, hihat, idx, 0.35)
            elif step % 4 == 2:
                mix_into(left, open_hihat, idx, 0.65)
                
            # --- 贝斯轨道 (Bouncing Bass) ---
            # 弹性跳跃: 正拍根音，切分跳五度或八度
            if step == 0:
                b_sound = bass_note(NOTES[bass_note_name], dur=0.32)
                mix_into(left, b_sound, idx, 0.5)
            elif step == 6:
                # 弹跳到八度音
                oct_note = bass_note_name.replace('2', '3')
                b_sound = bass_note(NOTES.get(oct_note, NOTES[bass_note_name] * 2), dur=0.20)
                mix_into(left, b_sound, idx, 0.5)
            elif step == 10:
                b_sound = bass_note(NOTES[bass_note_name], dur=0.25)
                mix_into(left, b_sound, idx, 0.5)

            # --- 和弦轨道 (Syncopated Upbeat Plucks) ---
            # 轻快切分和弦 (在 step 2, 8, 14 处弹奏轻快跳跃的电钢琴/吉他分解)
            if step in [2, 8, 14]:
                for c_idx, c_name in enumerate(chord_note_names):
                    c_sound = chord_note(NOTES[c_name], dur=0.45)
                    pan_val = 0.3 + 0.15 * c_idx
                    mix_into(left, c_sound, idx, pan_val)

            # --- 主旋律木琴/风铃轨道 (Lively Marimba / Arpeggio) ---
            # 具有东方水墨灵韵的轻快五声音阶跳跃，音高跳荡、极富朝气
            melody_patterns = [
                # Bar 1
                [0, 2, 4, 7, 3, 5, 2, 0, 4, 7, 5, 3, 7, 5, 4, 2],
                # Bar 2
                [1, 3, 5, 7, 4, 6, 3, 1, 5, 7, 6, 4, 6, 4, 3, 1],
                # Bar 3
                [0, 2, 4, 6, 3, 5, 2, 0, 4, 6, 5, 3, 6, 4, 2, 0],
                # Bar 4
                [2, 4, 5, 7, 4, 6, 5, 3, 7, 8, 7, 5, 4, 3, 2, 1],
            ]
            pat = melody_patterns[bar_i % 4]
            note_idx = pat[step]
            # 选取音符
            freq = NOTES[melody_pool[note_idx % len(melody_pool)]]
            # 偶尔高八度跳动
            if step in [3, 7, 11, 15]:
                freq *= 1.5
            
            # 木琴声
            m_sound = marimba_note(freq, dur=0.25, decay=11.0)
            # 乒乓声场 (左右交替流动)
            pan_val = 0.25 if step % 2 == 0 else 0.75
            mix_into(left, m_sound, idx, pan_val)

    # 混音与后处理:
    # 1. 稍微加一点轻微空间混响 (Simple delay / reflections)
    delay_samples = int(0.18 * sr)
    decay_factor = 0.22
    left_wet = left.copy()
    right_wet = right.copy()
    left_wet[delay_samples:] += right[:-delay_samples] * decay_factor
    right_wet[delay_samples:] += left[:-delay_samples] * decay_factor

    # 2. 结尾轻微平滑淡出 (Fade out in last 1.2s)
    fade_samples = int(1.2 * sr)
    fade_curve = np.linspace(1.0, 0.0, fade_samples)
    left_wet[-fade_samples:] *= fade_curve
    right_wet[-fade_samples:] *= fade_curve

    # 3. 动态软压限器 (Soft Limiter)
    max_val = max(np.max(np.abs(left_wet)), np.max(np.abs(right_wet)))
    print("Peak amplitude before normalization:", max_val)
    if max_val > 0.01:
        left_norm = np.tanh(left_wet / max_val * 1.1) * 0.88
        right_norm = np.tanh(right_wet / max_val * 1.1) * 0.88
    else:
        left_norm = left_wet
        right_norm = right_wet

    # 4. 写入 16-bit PCM WAV
    left_int = (left_norm * 32767).astype(np.int16)
    right_int = (right_norm * 32767).astype(np.int16)
    
    # 交叉合并左右声道
    interleaved = np.empty((total_samples * 2,), dtype=np.int16)
    interleaved[0::2] = left_int
    interleaved[1::2] = right_int

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with wave.open(output_path, 'wb') as wav_file:
        wav_file.setnchannels(2)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sr)
        wav_file.writeframes(interleaved.tobytes())

    print(f"Generated brisk BGM successfully: {output_path} ({duration}s, {os.path.getsize(output_path)} bytes)")

if __name__ == '__main__':
    generate_brisk_bgm(41.8, "D:/english-multiple-choice-practice-machine/docs/video_record/brisk_cheerful_bgm.wav")
