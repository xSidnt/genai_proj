# CroissantDough public benchmark

The preset under test used GuitarProFX TabCNN with Basic Pitch attack refinement, a Demucs guitar stem, single-note lead, and fixed fretboard calibration. The main GuiFiR-Vid run used the app’s per-clip tempo estimate. An additional GuiFiR-Vid run forced 89 BPM across the sample. The full Realiti comparison used a 115 BPM override.

## Audio-only · EGSet12

All 12 electric-guitar recordings, 1,567 annotated note events. A correct onset is within 50 ms of the reference. Pitch F1 requires the correct pitch and onset. Tab F1 also requires the exact string and fret. Both metrics penalize missed notes and extra detections. The published GuitarProFX study used this dataset for evaluation. [EGSet12](https://zenodo.org/records/11406378)

| Pipeline | Pitch F1 | Exact tab F1 |
| --- | ---: | ---: |
| Original TabCNN checkpoint, original audio | 43.3% | 28.5% |
| Raw GuitarProFX TabCNN, original audio | 52.2% | 36.6% |
| CroissantDough TabCNN, original audio, polyphonic | 58.6% | **42.5%** |
| CroissantDough Basic Pitch with playable fingering, original audio, polyphonic | **76.4%** | 42.4% |
| CroissantDough TabCNN, isolated guitar, polyphonic | 54.6% | 37.3% |
| CroissantDough TabCNN, isolated guitar, single-note lead | 44.4% | 28.1% |

The last row evaluates the isolated lead preset’s audio path. EGSet12 provides audio and tablature annotations, so fixed vision is unavailable. On the local CPU, the isolated lead path took 137 seconds across the corpus. The polyphonic original-audio path took 18 seconds. The GuitarProFX authors’ published **58.5%** Tab F1 is reported on a frame-level metric. This benchmark scores note attacks. [GuitarProFX paper](https://www.dafx.de/paper-archive/2024/papers/DAFx24_paper_99.pdf)

## Audio-only · Guitar-TECHS

All 12 amplifier-microphone recordings from the `P3_music` archive, with 1,941 reference notes from the per-string MIDI channels. The dataset authors report possible synchronization offsets of up to 100 ms, so results include both tolerances. Vision is unavailable for this audio subset. [Guitar-TECHS](https://zenodo.org/records/14963133)

| Pipeline | Pitch F1, 50 ms | Exact tab F1, 50 ms | Exact tab F1, 100 ms |
| --- | ---: | ---: | ---: |
| Raw GuitarProFX TabCNN, original audio | 36.8% | 22.8% | 30.4% |
| CroissantDough TabCNN, original audio, polyphonic | 38.7% | 24.0% | 30.9% |
| CroissantDough Basic Pitch with playable fingering, original audio, polyphonic | **59.9%** | **30.6%** | **31.8%** |
| CroissantDough TabCNN, isolated guitar, polyphonic | 38.2% | 23.0% | 28.5% |
| CroissantDough TabCNN, isolated guitar, single-note lead | 36.0% | 18.6% | 23.5% |

## Audio and video · GuiFiR-Vid

Ten available no-capo clips from the released test split, covering six performance titles. Each clip used the nut and fret-20 corners from its first annotated frame as the fixed calibration. That frame was excluded from scoring. The remaining labels contain 275 manually annotated string/fret attacks. We assume standard tuning and use the filenames’ one-based source frame indices on a 30 FPS annotation timeline. Several delivered MP4s are encoded at 25 FPS.

Scores report recall on labeled attacks. The annotations cover selected frames, so precision for the full clip would require additional note labels. The 50 ms column is stricter and the 100 ms column shows sensitivity to temporal alignment. [GuiFiR-Vid release](https://github.com/kmu-ee-ailab/guifir_dataset) · [Dataset paper](https://doi.org/10.1109/ACCESS.2026.3713562)

| CroissantDough TabCNN configuration | Pitch recall, 50 ms | Exact tab recall, 50 ms | Exact tab recall, 100 ms |
| --- | ---: | ---: | ---: |
| Original audio, polyphonic | **38.5%** | 28.7% | **36.7%** |
| Isolated guitar, polyphonic | 38.2% | **29.1%** | **36.7%** |
| Isolated guitar, single-note lead, vision off | 27.3% | 21.5% | 25.8% |
| Isolated guitar, single-note lead, fixed vision | 27.3% | 23.6% | 29.1% |

At 50 ms, fixed vision raised the exact placements from **59 to 65** among the same **75** pitch matches. At 100 ms it raised exact placements from **71 to 80** among the same **100** pitch matches. The local vision pass took **8.8 seconds total** for the ten 10-second clips. The app emitted 71 finger estimates among 407 notes. The released tablature labels do not identify which finger pressed each string, so that count measures coverage.

Forcing 89 BPM yielded **22.9%** exact-tab recall with fixed vision and **20.7%** with vision off at 50 ms. The per-clip estimated tempo performed slightly better across this sample. The ten clips are an availability-based pilot because the larger download timed out.

## Complete score references for three video excerpts

This follow-up scores the entire tab sequence inside three bounded excerpts. The reference captures score agreement. I spot-checked the fretting positions against the videos and could see the playing region, but the footage frequently hides the actual string contact. Exact performer fingering remains unverified for the full sequences.

| Excerpt | Window | Reference attacks | Reference method |
| --- | --- | ---: | --- |
| Mateusz Kowalski, Bach BWV 1006a | 9.00–24.00 s | 116 | GAPS aligned MIDI plus the released MusicXML tablature. [GAPS example](https://aim-qmul.github.io/GAPS/#demo-of-aligned-score) · [Performance](https://www.youtube.com/watch?v=foQ9dHbwLGo) |
| Aguado, Study in A Minor | 0.32–9.23 s | 40 | First five bars of the on-screen tablature, transcribed and timed using the moving score cursor and audio transients. [GuiFiR-Vid](https://github.com/kmu-ee-ailab/guifir_dataset) |
| Lizzie Skevington, Realiti | 0.78–9.13 s | 64 | First four bars of the supplied reference tab, timed from the opening attack and the 115 BPM score. CroissantDough used its 117 BPM playback grid. |

The GAPS video audio matched the release at a consistent 36.25 ms offset. Three MIDI attacks in the window lacked a reliable string/fret join. Pitch scoring includes all 116 attacks. Exact-tab scoring excludes those timing neighborhoods, leaving 110 reference attacks at 50 ms. The GAPS score credits a different arranger from the performance video, and the video cuts to a different view near the end of the tested window. [GAPS discussion of score vs. performer fingering](https://arxiv.org/html/2408.08653v2#S3.SS4)

| Excerpt and audio configuration | Pitch F1 | Tab F1, vision off | Tab F1, fixed vision | Exact matches, off → fixed |
| --- | ---: | ---: | ---: | ---: |
| Bach, original and polyphonic | 24.4% | 14.0% | 12.9% | 12 → 11 |
| Bach, isolated single-note lead | 34.1% | 22.6% | 25.2% | 18 → 20 |
| Study, original and polyphonic | 44.4% | 6.8% | 6.8% | 4 → 4 |
| Study, isolated single-note lead | 60.0% | 6.7% | 6.7% | 3 → 3 |
| Realiti, original and polyphonic | 31.4% | 3.5% | 29.1% | 3 → 25 |
| Realiti, isolated single-note lead | 76.7% | 38.3% | **75.0%** | **23 → 45** |

The table uses 50 ms onset tolerance with both missed and extra outputs counted. On Realiti, both isolated lead runs emitted 56 notes against 64 reference notes. Exact unmatched predictions fell from 33 to 11, and missed exact reference events fell from 41 to 19. The pitch matches stayed at 46. At 100 ms, exact-tab F1 on the same comparison rose from 43.3% to 80.0%. The fixed vision pass added about 1.1 seconds to this Realiti run. This three-excerpt pilot shows how much the benefit can vary by clip.

## Realiti · Complete user-supplied tab

The reference was transcribed from the published lead-guitar tablature across all 24 played measures. The reference has 295 numbered notes. Printed hammer-on, pull-off, and slide targets count as notes. Technique symbols, bend targets without a printed fret, tied continuations without a printed fret, and nine unpitched mute hits were omitted. Predictions in the mute slots were excluded from scoring. Timing was reconstructed from the printed rhythms at 115 BPM and the estimated first attack at 0.848 seconds. The 100 ms column shows sensitivity to timing uncertainty.

CroissantDough analyzed 0.78–50.94 seconds with TabCNN. The isolated lead used a 115 BPM grid. Fixed and tracked vision started from the same marks at fret wires 2 and 12 and reused the same audio detections as the vision-off run.

| Configuration | Exact string and fret within 50 ms | Tab F1 at 50 ms | Tab F1 at 100 ms |
| --- | ---: | ---: | ---: |
| Isolated lead, vision off | 63 / 295 | 21.1% | 25.1% |
| Isolated lead, fixed vision | **137 / 295** | **45.8%** | **54.2%** |
| Isolated lead, tracked vision | 133 / 295 | 44.5% | 52.8% |
| Original audio, polyphonic, vision off | 37 / 295 | 8.1% | 13.3% |
| Original audio, polyphonic, fixed vision | 94 / 295 | 20.5% | 28.5% |
| Original audio, polyphonic, tracked vision | 95 / 295 | 20.7% | 29.0% |

With isolated lead, all three runs produced 303 scored notes and 178 correct pitches within 50 ms. Fixed vision placed 137 of those on the reference string and fret, up from 63 with vision off. Measures 9–12 were the weakest fingering section. The app matched the pitch and timing for 38 of 58 notes there, but only seven matched the tab positions. The most common substitution was B-string fret 4 for the tab’s G-string fret 8.

## Reproduce

Run the commands from `backend/`. Download the datasets and model weights from their respective releases. Basic Pitch used its bundled ONNX runtime for these runs on macOS. The original TabCNN checkpoint was run with raw CQT magnitudes after waveform peak normalization, as specified in the export model card. [TabCNN ONNX model card](https://huggingface.co/cstr/tabcnn-onnx)

Add `--grid-bpm 89` to the GuiFiR command to reproduce the forced-tempo run.

```bash
.venv/bin/python -m scripts.benchmark_egset12 /path/to/EGSet12 \
  --include-isolated --original-tabcnn-weights /path/to/tabcnn.onnx

.venv/bin/python -m scripts.benchmark_guifir /path/to/GuiFiR/raw_clips \
  /path/to/GuiFiR/annotations/guifir_test_coco_anno_box.jsonl \
  --clips StudyInAMinor_1 StudyInAMinor_3 acoustic_Mephisto_2 \
  classic_BohemianRapsody_10 classic_BohemianRapsody_2 classic_BohemianRapsody_7 \
  classic_Chopin_4 classic_FutureBoy_5 classic_FutureBoy_8 classic_StarWars_11

.venv/bin/python -m scripts.benchmark_guitar_techs /path/to/P3_music.zip

.venv/bin/python -m scripts.benchmark_dense_av /path/to/manifest.json --output /path/to/results.json
```
