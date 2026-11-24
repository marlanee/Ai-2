# 스모크 테스트 결과 (2026-11-24, RTX 5060 Ti 16GB)

- 측정: `scripts/run_workflow.py`. 시간은 프롬프트 제출부터 완료까지. 최대 VRAM은 `nvidia-smi`를 0.5초 간격으로 샘플링한 **GPU 전체 사용량**이며, 데스크톱 기본 사용량 약 1.4GB가 포함된다.
- 각 실행 전에 `/free`로 모델을 내렸지만, 시스템 RAM(64GB)에 캐시가 남아 2번째 실행부터는 로딩이 빠르다. 첫 실행(콜드) 시간은 따로 표시했다.
- 원본 기록: `test_output/runs.jsonl`. 출력물: `test_output/smoke/` (git 제외)

## 요약

| # | 테스트 | 설정 | 시간 | 최대 VRAM | 결과 |
|---|---|---|---|---|---|
| 1a | ACE-Step 1.5 Turbo ×3 | 120초, 8스텝, 75 BPM, F major, `[Instrumental]`, seed 101/202/303 | 13.0~13.2초/곡 (콜드 약 21초) | 13.4 GB | ✅ |
| 1b | Stable Audio 3.0 Medium ×3 | 120초, 8스텝 lcm, 프롬프트 확장(Qwen3.5) 끔, seed 101/202/303 | 6.0초/곡 (콜드 22.1초) | 14.1 GB | ✅ |
| 1c | ACE-Step 1.5 Turbo + 로파이 LoRA | 1a + `roti-l0f1y` 트리거, strength 1.0 | 33.1초 (LoRA 로딩 포함) | 13.4 GB | ✅ |
| 1d | ACE-Step 1.5 **XL** Turbo | 1a와 같은 설정, LM 4B | 42.1초 | 15.1 GB | ✅ 16GB에서 OOM 없음 |
| 2 | Z-Image Turbo int8 | 1344×768, 8스텝 res_multistep, seed 1980 | 19.1초 | 14.1 GB | ✅ |
| 3a | Wan 2.2 FLF2V 14B fp8 + LightX2V | 832×480, 81프레임(16fps, 5.06초), 4스텝, 첫 프레임 = 마지막 프레임 | 184.1초 | 14.2 GB | ✅ |
| 3b | Wan 2.2 TI2V 5B fp16 (비교) | 832×480, 121프레임(24fps, 5.04초), 20스텝, I2V(첫 프레임만) | 213.5초 | 15.8 GB | ✅ 생성 성공, 루프용으로는 부적합 |
| 3c | LTX-2.5 22B distilled int8 FLF2V | 832×480, 121프레임(24fps, 5.04초), 8스텝 distilled, 첫 프레임 = 마지막 프레임, 프롬프트 확장 끔, 빗소리 오디오 동시 생성 | 97.5초 | 15.5 GB | ✅ |
| 4a | RIFE v4.26 ×2 (내장 노드) | 3a 클립, 16→32fps, 81→161프레임 | 6.1초 | 측정 불가(샘플링 간격보다 짧음) | ✅ |
| 4b | RealESRGAN x4plus | 3a 클립, 832×480 → 3328×1920, 81프레임 | 184.3초 | 6.0 GB | ✅ |
| 5 | ffmpeg 합성 | 4a 클립을 루프 단위로 만들어 60초 반복 + ACE 2곡 8초 크로스페이드, -14 LUFS | 수 초 | - | ✅ `test_output/smoke_test.mp4` |

OOM은 한 번도 나지 않았다. 해상도·길이·양자화를 낮춰 재시도한 테스트도 없다.

## 1. 음악

- 7곡 모두 길이 120.0초, 48kHz 스테레오 FLAC.
- 라우드니스: ACE -11.9~-13.8 LUFS, Stable Audio -12.5~-13.1 LUFS. 피크가 모두 0dBFS에 닿아 있다 → 합성 단계에서 `loudnorm`(-14 LUFS / -1 dBTP)으로 정규화한다.
- 공정한 비교를 위해 Stable Audio 템플릿의 프롬프트 확장 LLM(Qwen3.5 2B)은 껐다(`52:35.value=false`). 켜면 품질이 달라질 수 있다.
- ACE-Step의 `TextEncodeAceStepAudio1.5`에는 bpm, keyscale, 가사 필드가 따로 있어서 BPM과 키를 프롬프트 밖에서 고정할 수 있다. 채널 운영(일관된 BPM/키 플레이리스트)에 유리하다.
- 음질 비교는 사람이 직접 들어봐야 한다 → `test_output/blind/A1~A6.flac` 블라인드 테스트 (정답: `answer.txt`, 채점 페이지: `index.html`).

### 블라인드 테스트 결과 (2026-11-24)

항목: 8090 시티팝·로파이 분위기 / 음질 / 오래 틀어둬도 편안함 / 종합 선호 (각 1~5점, 합계 20점)

| 곡 | 모델 (seed) | 점수 |
|---|---|---|
| A1 | Stable Audio 3.0 Medium (202) | 5/5/5/5 = **20** |
| A5 | Stable Audio 3.0 Medium (303) | 4/4/4/4 = **16** |
| A6 | Stable Audio 3.0 Medium (101) | 1/1/1/1 = 4 |
| A2 | ACE-Step 1.5 Turbo (202) | 1/1/1/1 = 4 |
| A3 | ACE-Step 1.5 Turbo (101) | 1/1/1/1 = 4 |
| A4 | ACE-Step 1.5 Turbo (303) | 1/1/1/1 = 4 |

- 모델별 평균: **Stable Audio 13.3점**, ACE-Step 4.0점. 상위 2곡이 모두 Stable Audio였다.
- Stable Audio는 시드에 따라 편차가 크다(20 / 16 / 4). 곡을 여러 개 뽑아 고르는 방식이 필요하다.
- 1점 곡(ACE 3곡 + SA3 seed 101)에 대한 평가: "노래가 매끄럽지 않고 듣기 싫음. 불협화음처럼 들림."
  ACE-Step Turbo는 3곡 모두 이렇게 들렸으므로 시드 문제가 아니라 모델이나 설정 문제로 본다(가능성: keyscale 고정 F major, 8스텝 Turbo, LM 1.7B).
- 이번 블라인드에는 ACE-Step XL Turbo와 로파이 LoRA 버전이 들어가지 않았다.
- **결정: 음악 기본 모델은 Stable Audio 3.0 Medium.** 시드마다 편차가 있으므로 여러 곡을 뽑아 고르는 방식으로 운영한다.
- 라이선스 주의: Stable Audio 3.0은 Stability AI Community License다(연매출 $1M 미만 무료, 상업 이용 시 Stability AI 등록 필요). 수익화 전에 등록해야 한다.

## 2. 이미지

- 비 오는 1980년대 서울 골목, 큰 네온 간판의 한글("학산" 계열)은 또렷하다.
- 작은 간판의 한글은 뭉개졌고, 오른쪽 문에 한자(囍)가 들어갔다. 키 아트에 글자가 중요하면 간판 문구를 프롬프트에 명시하거나 후편집이 필요하다.

## 3. 루프 영상

### 비교 표

| 항목 | Wan 2.2 FLF2V 14B (4스텝) | Wan 2.2 TI2V 5B | LTX-2.5 FLF2V int8 |
|---|---|---|---|
| 생성 시간 (5초 클립) | 184초 | 214초 | **97.5초** |
| 최대 VRAM | 14.2 GB | 15.8 GB | 15.5 GB (여유 적음) |
| 첫/끝 프레임 고정 | 가능 (FLF) | 불가 (첫 프레임만) | 가능 (FLF, guide strength 0.7) |
| 프레임 수 / fps | 81 / 16 | 121 / 24 | 121 / 24 |
| 프레임 간 평균 변화량 (최대) | 0.69 (2.38) | 8.09 (26.99) | 0.50 (0.92) |
| 원본 이음새(끝→처음) | 4.30 | 14.23 | **2.08** |
| 이음새 0.5초 보정 후 / 평소 최대 | 1.74 / 1.08 (RIFE 32fps) | - | **1.23 / 0.86** |
| 첫 프레임 vs 끝 프레임 SSIM | 0.995 | 0.876 | 0.998 |
| 디테일 유지 | 간판 글자·창문 유지. 빗줄기 뭉개짐 없음 | 중간에 파란 조명이 튀고 카메라가 흔들림 | 간판 글자·창문 유지. 빗줄기는 Wan보다 약하게 보임 |
| OOM | 없음 | 없음 | 없음 |
| 오디오 생성 | 없음 | 없음 | ✅ 빗소리 앰비언스 (-29.7 LUFS, 48kHz) |

→ **두 FLF2V 모두 루프용으로 쓸 수 있다.** LTX-2.5는 2배 가까이 빠르고, 이음새가 작고, 빗소리까지 만들어 준다. 반면 VRAM 여유가 적고(15.5/16GB), 라이선스에 연매출 $10M 조건이 붙는다. Wan은 빗줄기 움직임이 더 뚜렷하다. **5B는 루프용으로 부적합하다.**
→ 둘 다 `smoke_test.mp4`(Wan) / `smoke_test_ltx.mp4`(LTX)로 만들어 두었다.

**결정 (2026-11-24): 루프 영상 기본 모델은 LTX-2.5 FLF2V int8.** 결과물을 직접 비교해 보고 가장 마음에 든다고 판단했다. Wan 2.2 FLF2V 14B는 예비로 남겨 둔다 (VRAM이 부족하거나 비를 더 뚜렷하게 보여야 할 때).

### LTX-2.5 해상도 테스트 (5초, 121프레임 24fps, 같은 시드·프롬프트)

| 해상도 | 실제 출력 | 생성 시간 | 최대 VRAM | 이음새(끝→처음) | 프레임 간 평균 / 최대 | 결과 |
|---|---|---|---|---|---|---|
| 480p | 832×480 | 97.5초 | 15.5 GB | 2.08 | 0.50 / 0.92 | ✅ |
| 720p | 1280×704 | 196.2초 | 15.8 GB | 1.61 | 0.38 / 1.43 | ✅ |
| 1080p | 1920×1088 | 472.1초 | 15.6 GB | **1.32** | 0.44 / 1.41 | ✅ OOM 없음 |
| 480p → RealESRGAN 4x → 1920×1080 | 1920×1080 | 97.5 + 269.6 = **367초** | 6.1 GB (업스케일) | - | - | ✅ |

- 1080p에서도 OOM이 나지 않았다. ComfyUI가 텍스트 인코더와 VAE를 CPU로 내렸다가 올리면서 16GB 안에서 처리한다. 대신 시간이 해상도에 비례해 늘어난다.
- 해상도가 높을수록 원본 이음새가 오히려 작아졌다(2.08 → 1.61 → 1.32).
- 같은 영역(간판·빗줄기)을 잘라 비교했다:
  - **네이티브 1080p**: 빗줄기가 가늘고 또렷하게 살아 있다. 간판 글자와 벽 질감이 가장 선명하다.
  - **480p + ESRGAN**: 깔끔하지만 가는 빗줄기를 대부분 지워 버려 그림처럼 매끈해진다. 비 오는 장면의 핵심 디테일이 사라진다.
  - **720p 확대**: 빗줄기는 보이지만 전체적으로 약간 부드럽다.
- **추천: 최종본은 네이티브 1080p(5초 클립 1개에 약 8분).** 루프 영상은 클립 하나를 몇 시간씩 반복하므로 8분은 충분히 감수할 만하다. 시안이나 프롬프트 테스트는 480p(약 1.5분)로 빠르게 돌린다. RealESRGAN 업스케일은 빗줄기를 지우므로 이 채널에는 맞지 않는다.

LTX-2.5 메모:
- 템플릿 기본값은 Gemma 4 E2B로 프롬프트를 자동 확장(`TextGenerateLTX2Prompt`)한다. 비교를 위해 껐다(`251:250.value=false`).
- 오디오는 같은 프롬프트의 `Audio:` 문장으로 지정했다. 추출본: `test_output/smoke/ltx25_rain_ambience.flac`. 음량이 작아서(-29.7 LUFS) 음악 아래 깔 앰비언스로 쓰기에 알맞다.

### 루프 이음새 (`scripts/loop_check.py`, 256px 회색조 평균 절대 차)

| 루프 단위 | 프레임 간 평균 | 프레임 간 최대 | 이음새(끝→처음) | 판정 |
|---|---|---|---|---|
| RIFE 클립 그대로 반복 | 0.35 | 1.39 | **4.69** | 평소 최대치의 3.4배 → 빗줄기가 순간적으로 "툭" 튈 가능성 큼 |
| 이음새 0.5초 크로스페이드 (`--seam 0.5`) | 0.32 | 1.08 | **1.74** | 평소 최대치의 1.6배 → 크게 줄었지만 완전히 없어지지는 않음 |
| 이음새 1.0초 크로스페이드 | 0.31 | 1.20 | 1.58 | 0.5초와 차이가 작음 |

- 원인: 첫 프레임과 끝 프레임의 구도는 같지만(SSIM 0.99) 빗줄기 위치는 이어지지 않는다.
- `smoke_test.mp4`에는 0.5초 크로스페이드를 적용했다. 비교용으로 보정하지 않은 `smoke_test_noseamfix.mp4`도 남겼다. **최종 판단은 직접 보고 내려야 한다.**

## 4. 후처리

- RIFE v4.26 ×2: 6.1초. 81→161프레임, 32fps. 가볍고 빨라서 루프 영상에 상시 적용할 만하다.
- RealESRGAN x4: 5초 클립에 184초. 4x는 3328×1920(4K 수준)이 되어 유튜브 업로드에는 과하다. 1080p를 목표로 하면 2x 모델이나 4x 후 축소가 현실적이다.

## 5. 합성 (`test_output/smoke_test.mp4`)

- 60.0초, H.264 832×480 32fps + AAC 320k 48kHz, 13.5MB.
- 음악: ACE 곡 1과 2를 각각 34초로 잘라 8초 크로스페이드, 앞 2초 페이드인, 뒤 3초 페이드아웃.
- 라우드니스: -14.4 LUFS, True Peak -0.6 dBTP (AAC 인코딩 후 목표치 -1보다 약간 높음 → 다음에는 TP -1.5로 여유를 둘 것).
- 다시 만드는 명령:

```
python scripts/compose.py --clip <rife_clip.mp4> --music <a.flac> <b.flac> --duration 60 --seam 0.5 --xfade 8 --out test_output/smoke_test.mp4 --ffmpeg C:/AI/tools/ffmpeg/bin/ffmpeg.exe
```

## 6. 최종 조합 1분 영상 (`test_output/final_1min_ltx1080_sa3.mp4`)

- 영상: LTX-2.5 FLF2V 1080p 클립(1920×1088, 5.04초) → 이음새 0.5초 크로스페이드 → 1920×1080 중앙 크롭 → `-stream_loop` 반복
- 음악: 블라인드 1·2위 Stable Audio 3.0 곡(seed 202, 303)을 각각 34초로 잘라 8초 크로스페이드
- 앰비언스: LTX가 1080p 클립과 함께 만든 빗소리(+4dB)를 음악 밑에 반복해 깔기
- 결과: 60.0초, H.264 1920×1080 24fps, AAC 48kHz 스테레오, 33.3MB(4.4Mbps), **-13.3 LUFS / True Peak -1.1 dBTP**. 합성 8.5초.
- 루프 단위 이음새: **0.70** (프레임 간 평균 0.45, 최대 1.34). 처음으로 평소 변화 범위 안에 들어왔다 → 수치상 이음새가 보이지 않는 수준.

```
python scripts/compose.py --clip ltx25_flf_1080p.mp4 --music sa3_s202.flac sa3_s303.flac \
  --ambience ltx25_1080p_rain.flac --ambience-db 4 --size 1920x1080 \
  --duration 60 --seam 0.5 --xfade 8 --out test_output/final_1min_ltx1080_sa3.mp4
```

## 사용한 워크플로 (API 형식, `workflows/`)

| 파일 | 원본 템플릿 |
|---|---|
| `music_acestep15_turbo_api.json` | `audio_ace_step_1_5_split` |
| `music_acestep15_turbo_lofi_lora_api.json` | 위 + `LoraLoaderModelOnly` 추가 |
| `music_acestep15_xl_turbo_api.json` | `audio_ace_step1_5_xl_turbo` |
| `music_stableaudio3_medium_api.json` | `audio_stable_audio_3_medium` (서브그래프를 펼침) |
| `image_zimage_turbo_int8_api.json` | `image_z_image_turbo_int8` |
| `video_wan22_flf2v_14b_4step_api.json` | `video_wan2_2_14B_flf2v` (LightX2V 4스텝 경로 사용) |
| `video_wan22_ti2v_5b_api.json` | `video_wan2_2_5B_ti2v` (+ LoadImage) |
| `video_ltx25_flf2v_int8_api.json` | `video_ltx2_5_flf2v` (서브그래프를 펼침, 오디오 포함) |
| `post_rife_interpolate_api.json` | `utility_video_frame_interpolation` (RIFE v4.26) |
| `post_realesrgan_x4_api.json` | `utility-gan_upscaler` |

입력 파일 이름(`keyart.png`, `wan_loop.mp4`)은 `C:\AI\ComfyUI\ComfyUI\input\` 기준이다. 자동화에서는 `run_workflow.py --set NODE.INPUT=VALUE`로 바꿔 넣으면 된다.
