"""Polished editable songs bundled as product examples."""

from __future__ import annotations

from .models import Note, Song, Track

SHOWCASE_SONG_NAME = "01_霓虹远航"
CELTIC_SONG_NAME = "02_凯尔特晨雾"
PIXEL_SONG_NAME = "03_像素跃迁"
EASTERN_SONG_NAME = "04_东方月影"
SUSPENSE_SONG_NAME = "05_深海回声"
SHOWCASE_SONG_NAMES = (
    SHOWCASE_SONG_NAME,
    CELTIC_SONG_NAME,
    PIXEL_SONG_NAME,
    EASTERN_SONG_NAME,
    SUSPENSE_SONG_NAME,
)


def _add_notes(
    track: Track,
    events: list[tuple[float, int, float, int]],
) -> None:
    track.notes.extend(
        Note(start=start, pitch=pitch, duration=duration, velocity=velocity)
        for start, pitch, duration, velocity in events
    )


def create_showcase_song() -> Song:
    """Create an original 16-bar A-minor synth-pop loop."""
    melody = Track(
        name="01 主题旋律",
        instrument="Rhodes Electric Piano",
        volume=0.78,
        color="#006CFF",
    )
    harmony = Track(
        name="02 弦乐和声",
        instrument="Strings Ensemble",
        volume=0.52,
        color="#18A57A",
    )
    arpeggio = Track(
        name="03 钟琴琶音",
        instrument="Music Box",
        volume=0.36,
        color="#8B5CF6",
    )
    bass = Track(
        name="04 低音",
        instrument="Triangle Bass",
        volume=0.68,
        color="#B66B18",
    )
    kick = Track(
        name="05 底鼓",
        instrument="Triangle Mellow",
        volume=0.48,
        color="#D84A4A",
    )
    snare = Track(
        name="06 军鼓",
        instrument="Noise Snare",
        volume=0.34,
        color="#D96C93",
    )
    hats = Track(
        name="07 踩镲",
        instrument="Noise Hi-Hat",
        volume=0.2,
        color="#5D6B82",
    )

    phrase = [
        (0.0, 69, 0.75, 86),
        (0.75, 72, 0.5, 78),
        (1.5, 76, 0.75, 92),
        (2.5, 74, 0.5, 80),
        (3.0, 72, 0.75, 84),
        (4.0, 69, 0.5, 82),
        (4.5, 67, 0.5, 74),
        (5.0, 69, 1.0, 88),
        (6.25, 72, 0.5, 82),
        (7.0, 69, 0.75, 78),
        (8.0, 67, 0.75, 84),
        (8.75, 64, 0.5, 74),
        (9.5, 67, 0.5, 80),
        (10.0, 76, 1.0, 94),
        (11.25, 74, 0.5, 82),
        (12.0, 71, 0.5, 82),
        (12.5, 74, 0.5, 86),
        (13.0, 79, 1.0, 96),
        (14.25, 76, 0.5, 86),
        (15.0, 71, 0.75, 80),
    ]
    melody_events = list(phrase)
    melody_events.extend(
        (
            start + 16.0,
            min(81, pitch + (12 if index in {2, 8, 13, 17} else 0)),
            duration,
            min(108, velocity + 5),
        )
        for index, (start, pitch, duration, velocity) in enumerate(phrase)
    )
    melody_events.extend(
        (
            start + 32.0,
            pitch + (2 if index % 5 == 0 else 0),
            duration,
            min(112, velocity + 8),
        )
        for index, (start, pitch, duration, velocity) in enumerate(phrase)
    )
    melody_events.extend(
        (
            start + 48.0,
            pitch + (12 if index in {0, 2, 9, 17} and pitch < 72 else 0),
            duration,
            min(116, velocity + 10),
        )
        for index, (start, pitch, duration, velocity) in enumerate(phrase)
    )
    final_start, final_pitch, _final_duration, final_velocity = melody_events[-1]
    melody_events[-1] = (final_start, final_pitch, 0.35, final_velocity)
    _add_notes(melody, melody_events)

    progression = [
        (57, 60, 64, 71),
        (53, 57, 60, 64),
        (48, 52, 55, 59),
        (55, 59, 62, 67),
        (50, 53, 57, 60),
        (48, 52, 57, 64),
        (53, 57, 60, 64),
        (52, 56, 59, 62),
    ]
    progression *= 2
    for bar, chord in enumerate(progression):
        start = bar * 4.0
        velocity = 54 + (bar // 4) * 3
        for pitch in chord:
            harmony.notes.append(
                Note(
                    start=start,
                    pitch=pitch,
                    duration=3.1 if bar == 15 else 3.85,
                    velocity=velocity,
                )
            )

        arp_pattern = (
            chord[0],
            chord[2],
            chord[1],
            chord[2],
            chord[3],
            chord[2],
            chord[1],
            chord[2],
        )
        arp_steps = arp_pattern[:-1] if bar == 15 else arp_pattern
        for step, pitch in enumerate(arp_steps):
            arpeggio.notes.append(
                Note(
                    start=start + step * 0.5,
                    pitch=pitch + 12,
                    duration=0.1 if bar == 15 and step == 6 else 0.38,
                    velocity=56 + (8 if step in (0, 4) else 0),
                )
            )

    bass_roots = (45, 41, 36, 43, 38, 36, 41, 40) * 2
    for bar, root in enumerate(bass_roots):
        start = bar * 4.0
        _add_notes(
            bass,
            [
                (start, root, 1.45, 88),
                (start + 2.0, root + 7, 0.7, 76),
                (start + 3.0, root + 12, 0.4 if bar == 15 else 0.7, 82),
            ],
        )

    for bar in range(16):
        start = bar * 4.0
        if bar >= 2:
            kick_beats = (0.0, 2.0, 3.25) if bar % 4 == 3 else (0.0, 2.0)
            for beat in kick_beats:
                kick.notes.append(
                    Note(
                        start=start + beat,
                        pitch=36,
                        duration=0.2,
                        velocity=92 if beat == 0 else 80,
                    )
                )
            for beat in (1.0, 3.0):
                snare.notes.append(
                    Note(
                        start=start + beat,
                        pitch=38,
                        duration=0.16,
                        velocity=74 if beat == 1.0 else 84,
                    )
                )
        if bar >= 4:
            for step in range(8):
                hats.notes.append(
                    Note(
                        start=start + step * 0.5,
                        pitch=42,
                        duration=0.1,
                        velocity=40 + (12 if step % 2 == 0 else 0),
                    )
                )

    return Song(
        name=SHOWCASE_SONG_NAME,
        bpm=108,
        time_signature="4/4",
        key="A",
        scale="Natural Minor",
        bars=16,
        loop_start=0.0,
        loop_end=64.0,
        tracks=[melody, harmony, arpeggio, bass, kick, snare, hats],
    )


def create_celtic_song() -> Song:
    """Create an original Celtic reel in D Mixolydian."""
    whistle = Track("01 哨笛主旋律", "Flute", 0.74, color="#1B8A72")
    fiddle = Track("02 提琴回应", "Solo Violin", 0.5, color="#3D7FB8")
    harp = Track("03 竖琴分解", "Harp", 0.48, color="#9A6BC7")
    guitar = Track("04 木吉他节奏", "Acoustic Guitar", 0.34, color="#B8782A")
    drone = Track("05 大提琴持续音", "Cello", 0.32, color="#65758B")
    bodhran = Track("06 手鼓", "Triangle Mellow", 0.42, color="#C45151")
    clap = Track("07 拍击", "Noise Snare", 0.2, color="#D47D91")

    reel_bars = (
        (74, 78, 81, 78, 76, 74, 71, 74),
        (72, 76, 79, 76, 74, 72, 69, 72),
        (71, 74, 79, 81, 79, 74, 71, 69),
        (74, 76, 78, 81, 78, 76, 74, 71),
        (74, 81, 78, 76, 74, 71, 69, 71),
        (72, 79, 76, 74, 72, 69, 67, 69),
        (71, 74, 79, 74, 71, 69, 67, 69),
        (74, 78, 81, 84, 81, 78, 76, 74),
    )
    for bar in range(16):
        pitches = reel_bars[bar % 8]
        steps = 7 if bar == 15 else 8
        for step, pitch in enumerate(pitches[:steps]):
            whistle.notes.append(
                Note(
                    start=bar * 4.0 + step * 0.5,
                    pitch=pitch,
                    duration=0.32 if step % 4 else 0.42,
                    velocity=78 + (10 if step in (0, 4) else 0) + (4 if bar >= 8 else 0),
                )
            )

    chords = (
        (50, 54, 57),
        (48, 52, 55),
        (43, 47, 50),
        (50, 54, 57),
        (45, 49, 52),
        (48, 52, 55),
        (43, 47, 50),
        (50, 54, 57),
    ) * 2
    for bar, chord in enumerate(chords):
        start = bar * 4.0
        pattern = (chord[0], chord[2], chord[1], chord[2]) * 2
        steps = 7 if bar == 15 else 8
        for step, pitch in enumerate(pattern[:steps]):
            harp.notes.append(
                Note(start=start + step * 0.5, pitch=pitch + 12, duration=0.28, velocity=58)
            )
        for beat in (0.0, 2.0):
            for pitch in chord:
                guitar.notes.append(
                    Note(
                        start=start + beat,
                        pitch=pitch + 12,
                        duration=1.45 if bar < 15 or beat == 0.0 else 1.0,
                        velocity=48 + (6 if beat == 0 else 0),
                    )
                )
        drone_pitch = 38 if bar % 4 in (0, 3) else 36 if bar % 4 == 1 else 43
        drone.notes.append(
            Note(
                start=start,
                pitch=drone_pitch,
                duration=3.0 if bar == 15 else 3.75,
                velocity=46,
            )
        )

        if bar >= 2:
            response = reel_bars[(bar + 2) % 8]
            for step in (0, 2, 4):
                fiddle.notes.append(
                    Note(
                        start=start + step * 0.5 + 0.25,
                        pitch=response[step] - 12,
                        duration=0.65,
                        velocity=60 + (6 if bar >= 8 else 0),
                    )
                )
            drum_beats = (0.0, 1.5, 2.0) if bar == 15 else (0.0, 1.5, 2.0, 3.5)
            for beat in drum_beats:
                bodhran.notes.append(
                    Note(
                        start=start + beat,
                        pitch=38,
                        duration=0.12,
                        velocity=78 if beat in (0.0, 2.0) else 58,
                    )
                )
            for beat in (1.0, 3.0):
                clap.notes.append(
                    Note(start=start + beat, pitch=42, duration=0.1, velocity=52)
                )

    return Song(
        name=CELTIC_SONG_NAME,
        bpm=126,
        key="D",
        scale="Mixolydian",
        bars=16,
        loop_end=64.0,
        tracks=[whistle, fiddle, harp, guitar, drone, bodhran, clap],
    )


def create_pixel_song() -> Song:
    """Create an original fast chiptune stage theme."""
    lead = Track("01 芯片主旋律", "NES Lead", 0.68, color="#006CFF")
    counter = Track("02 对位旋律", "GB Wave", 0.42, color="#16A085")
    arp = Track("03 方波琶音", "Square Arp", 0.34, color="#8B5CF6")
    bass = Track("04 掌机低音", "GB Bass", 0.58, color="#B66B18")
    snare = Track("05 芯片军鼓", "Noise Snare", 0.28, color="#D84A4A")
    hats = Track("06 芯片踩镲", "GB Noise", 0.16, color="#607089")

    motifs = (
        (72, 75, 79, 80, 79, 75, 72, 70),
        (68, 72, 75, 77, 75, 72, 68, 67),
        (63, 67, 70, 75, 72, 70, 67, 63),
        (70, 74, 77, 79, 77, 74, 72, 70),
    )
    for bar in range(16):
        motif = motifs[bar % 4]
        steps = 7 if bar == 15 else 8
        for step, pitch in enumerate(motif[:steps]):
            lead.notes.append(
                Note(
                    start=bar * 4.0 + step * 0.5,
                    pitch=min(84, pitch + (12 if bar in (7, 15) and step < 2 else 0)),
                    duration=0.28,
                    velocity=82 + (10 if step in (0, 4) else 0),
                )
            )

    chord_roots = (48, 44, 39, 46) * 4
    chord_types = ((0, 3, 7), (0, 4, 7), (0, 4, 7), (0, 4, 7))
    for bar, root in enumerate(chord_roots):
        start = bar * 4.0
        chord = tuple(root + interval for interval in chord_types[bar % 4])
        arp_pattern = (chord[0], chord[2], chord[1], chord[2]) * 2
        for step, pitch in enumerate(arp_pattern[: 7 if bar == 15 else 8]):
            arp.notes.append(
                Note(start=start + step * 0.5, pitch=pitch + 12, duration=0.24, velocity=54)
            )
        _add_notes(
            bass,
            [
                (start, max(36, root - 12), 0.7, 84),
                (start + 1.5, max(36, root - 5), 0.35, 68),
                (start + 2.0, max(36, root - 12), 0.7, 78),
                (start + 3.0, root, 0.35, 72),
            ],
        )
        if bar >= 4:
            counter_pattern = (chord[1] + 12, chord[2] + 12, chord[1] + 12, chord[0] + 12)
            for step, pitch in enumerate(counter_pattern):
                counter.notes.append(
                    Note(start=start + step, pitch=pitch, duration=0.55, velocity=54)
                )
        for beat in (1.0, 3.0):
            snare.notes.append(Note(start=start + beat, pitch=38, duration=0.1, velocity=68))
        for step in range(8):
            hats.notes.append(
                Note(
                    start=start + step * 0.5,
                    pitch=42,
                    duration=0.08,
                    velocity=34 + (10 if step % 2 == 0 else 0),
                )
            )

    return Song(
        name=PIXEL_SONG_NAME,
        bpm=148,
        key="C",
        scale="Natural Minor",
        bars=16,
        loop_end=64.0,
        tracks=[lead, counter, arp, bass, snare, hats],
    )


def create_eastern_song() -> Song:
    """Create an original D-pentatonic fantasy theme."""
    dizi = Track("01 笛子主旋律", "Dizi", 0.7, color="#159A86")
    guzheng = Track("02 古筝流水", "Guzheng", 0.5, color="#8B5CF6")
    erhu = Track("03 二胡回应", "Erhu", 0.42, color="#3D7FB8")
    pipa = Track("04 琵琶节奏", "Pipa", 0.4, color="#B8782A")
    cello = Track("05 大提琴低音", "Cello", 0.32, color="#65758B")
    drum = Track("06 鼓点", "Triangle Mellow", 0.34, color="#C45151")

    phrases = (
        ((74, 76, 78, 81, 78), (0.0, 0.75, 1.25, 2.0, 3.0)),
        ((76, 78, 81, 83, 81), (0.0, 0.5, 1.0, 2.0, 3.0)),
        ((69, 74, 76, 78, 76), (0.0, 0.75, 1.5, 2.25, 3.0)),
        ((71, 69, 66, 69, 74), (0.0, 0.5, 1.25, 2.0, 3.0)),
    )
    for bar in range(16):
        pitches, starts = phrases[bar % 4]
        count = 4 if bar == 15 else 5
        for index in range(count):
            dizi.notes.append(
                Note(
                    start=bar * 4.0 + starts[index],
                    pitch=min(
                        84,
                        pitches[index] + (12 if bar == 12 and index == 3 else 0),
                    ),
                    duration=0.4 if index < count - 1 else (0.45 if bar == 15 else 0.75),
                    velocity=76 + (8 if index in (0, 3) else 0),
                )
            )

    chords = (
        (50, 57, 62),
        (47, 54, 59),
        (45, 52, 57),
        (50, 57, 62),
    ) * 4
    for bar, chord in enumerate(chords):
        start = bar * 4.0
        plucks = (chord[0], chord[2], chord[1], chord[2]) * 2
        for step, pitch in enumerate(plucks[: 7 if bar == 15 else 8]):
            guzheng.notes.append(
                Note(start=start + step * 0.5, pitch=pitch + 12, duration=0.24, velocity=56)
            )
        for beat, pitch in zip((0.0, 1.0, 2.0, 3.0), plucks[:4], strict=True):
            pipa.notes.append(
                Note(start=start + beat, pitch=pitch + 12, duration=0.32, velocity=50)
            )
        cello.notes.append(
            Note(
                start=start,
                pitch=max(36, chord[0] - 12),
                duration=3.2 if bar == 15 else 3.7,
                velocity=48,
            )
        )
        if bar >= 4:
            erhu.notes.append(
                Note(
                    start=start + 1.0,
                    pitch=chord[1] + 12,
                    duration=2.1 if bar < 15 else 1.6,
                    velocity=58,
                )
            )
        drum_beats = (0.0, 2.0) if bar == 15 else (0.0, 2.0, 3.5)
        for beat in drum_beats:
            drum.notes.append(
                Note(
                    start=start + beat,
                    pitch=36,
                    duration=0.12,
                    velocity=70 if beat in (0.0, 2.0) else 48,
                )
            )

    return Song(
        name=EASTERN_SONG_NAME,
        bpm=92,
        key="D",
        scale="Major Pentatonic",
        bars=16,
        loop_end=64.0,
        tracks=[dizi, guzheng, erhu, pipa, cello, drum],
    )


def create_suspense_song() -> Song:
    """Create an original restrained suspense underscore."""
    motif = Track("01 钟琴动机", "Music Box", 0.42, color="#8B5CF6")
    strings = Track("02 暗色弦乐", "Strings Slow Attack", 0.68, color="#3D7FB8")
    cello = Track("03 大提琴脉冲", "Cello", 0.56, color="#65758B")
    bassoon = Track("04 低音管回应", "Bassoon", 0.44, color="#92704D")
    pulse = Track("05 低频脉冲", "Triangle Hollow", 0.5, color="#B66B18")
    impact = Track("06 远处冲击", "Noise Snare", 0.26, color="#C45151")

    chord_cycle = (
        (50, 53, 57),
        (49, 52, 57),
        (46, 50, 53),
        (45, 49, 52),
    ) * 4
    for bar, chord in enumerate(chord_cycle):
        start = bar * 4.0
        for pitch in chord:
            strings.notes.append(
                Note(
                    start=start,
                    pitch=pitch,
                    duration=3.0 if bar == 15 else 3.7,
                    velocity=42 + (5 if bar >= 8 else 0),
                )
            )
        for beat in (0.0, 2.0):
            cello.notes.append(
                Note(
                    start=start + beat,
                    pitch=max(36, chord[0] - 12),
                    duration=0.8,
                    velocity=58,
                )
            )
            pulse.notes.append(
                Note(start=start + beat + 0.5, pitch=chord[0], duration=0.35, velocity=46)
            )
        motif_pitches = (chord[1] + 12, chord[2] + 12, chord[1] + 13)
        for offset, pitch in zip((0.5, 1.25, 3.0), motif_pitches, strict=True):
            if bar == 15 and offset == 3.0:
                continue
            motif.notes.append(
                Note(start=start + offset, pitch=pitch, duration=0.28, velocity=48)
            )
        if bar % 2 == 1:
            bassoon.notes.append(
                Note(start=start + 1.0, pitch=chord[0], duration=1.6, velocity=50)
            )
        if bar in (3, 7, 11, 15):
            impact.notes.append(
                Note(start=start, pitch=38, duration=0.16, velocity=60 + bar)
            )

    return Song(
        name=SUSPENSE_SONG_NAME,
        bpm=72,
        key="D",
        scale="Natural Minor",
        bars=16,
        loop_end=64.0,
        tracks=[motif, strings, cello, bassoon, pulse, impact],
    )


def create_showcase_songs() -> list[Song]:
    return [
        create_showcase_song(),
        create_celtic_song(),
        create_pixel_song(),
        create_eastern_song(),
        create_suspense_song(),
    ]
