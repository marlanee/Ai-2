# 모델 비교 시험 보고 (2026-11-26) — MOSS-Image · Kandinsky 6 · LTX Foley · ACE-Step XL SFT

환경: RTX 5060 Ti 16GB, RAM 64GB, ComfyUI 0.46.0(업데이트 안 함). 시간은 `run_workflow.py` 측정값(warm = 모델 적재 후, cold = /free 직후 첫 장),
VRAM은 nvidia-smi 전체 GPU 최대치(바탕화면 약 1GB 포함). 생성물은 git 제외(test_output/).

---

## A. MOSS-Image vs Qwen-Image-2512 / Qwen-Edit-2511

### 준비 결과
| 항목 | 결과 |
|---|---|
| ComfyUI 버전 | 0.46.0 — MOSS 요구(t2i 0.42.0+, 편집 0.43.0+) 충족, **업데이트·백업 불필요**, 기존 워크플로 영향 없음 |
| 커스텀 노드 | **불필요.** CreateBoundingBoxes, MOSSImageLayoutPrompt, TextEncodeMOSSImageEdit, EmptyFlux2LatentImage 모두 내장. 공식 템플릿도 로컬에 동봉 |
| 라이선스 | OpenMOSS-Team/MOSS-Image-SFT·Base 저장소에 `LICENSE`(Apache 2.0 전문). 카드: "weights and bundled inference code ... Apache License 2.0". 비상업 조항 없음 → **상업 이용 가능**. Comfy-Org 재포장 저장소에는 LICENSE 파일 없이 apache-2.0 태그만 있음 |
| 편집 LoRA | 가중치에 명시 라이선스 없음(chinoll/Moss-Image-Edit, 코드는 GPLv3) → 시험용으로만 사용 |
| 받은 파일 | moss_image_sft_int8_convrot 5.41GB, qwen3.5_9b_w4a8_gptq 7.34GB, flux2-vae_small 250MB, moss_image_edit_lora_rank_64_bf16 297MB (safetensors만, Base·bf16·MoGe 안 받음) |
| 워크플로 | `scripts/make_moss_workflows.py` → `workflows/image_moss_{t2i,layout,edit}_api.json` (공식 템플릿 설정: 25 steps, CFG 2.5, er_sde/simple, SLG 22층; 편집 30 steps CFG 4) |
| 주의점 | API 형식에서 bbox 목록은 `{"__value__": [...]}`로 감싸야 함(그냥 목록이면 노드 연결로 해석돼 400 오류) |
| 핵심 제약 | MOSS t2i 모델에는 **이미지 입력이 없음** → 인물 시트로 얼굴을 고정할 수 없음. 얼굴은 편집 LoRA(최대 4장)나 Qwen-Edit 후처리로만 가능 |

### 시험 구성
`scripts/moss_ab.py` — 6장면 × 시드 2 × {Qwen t2i, Qwen-Edit+인물시트(현행), MOSS t2i, MOSS 레이아웃}, 참조 편집 2종(MOSS 편집 LoRA+시트, MOSS 레이아웃→Qwen-Edit) 장면 4개.
1664×928(16:9, 1.54MP — MOSS 권장 1~2MP 범위), 그림체는 style_bible_yadam 요약을 모든 프롬프트에 동일하게.
비교표: `test_output/story/moss_ab/_ab.jpg`(전체), `_ab_<장면>.jpg`(장면별 확대).

### 시간·VRAM
| 방식 | 장당(warm) | cold 첫 장 | 모델 적재 | 최대 VRAM |
|---|---|---|---|---|
| Qwen-2512 t2i | 14~16초 | 95초 | 약 80초 | 15.8GB |
| Qwen-Edit+시트 | 17~31초 | 109초 | 약 80초 | 15.8GB |
| **MOSS t2i / 레이아웃** | **34~37초** | 40~63초 | **약 5~27초** | **12.0~12.3GB** |
| MOSS 편집 LoRA | 40~76초(참조 수에 비례) | 56초 | — | 15.9GB |
| MOSS→Qwen-Edit | 37초 | 104초 | 약 65초 | 15.7GB |

- MOSS는 장당 약 2.3배 느리지만 적재가 빠르고 VRAM이 3.5GB 적음 → LTX·TTS와 번갈아 쓸 때 전환 비용은 MOSS가 작음.
- Qwen t2i에서 한 번 93.7초(warm)가 나옴 — 16GB가 거의 찬 상태에서 공유 메모리로 넘친 것으로 보임. MOSS는 여유 4GB라 이런 튐이 없었음.

### 채점 (Claude, 1~5, 시드 2개 평균. GPT 채점은 사용자 결정으로 생략 — 토큰 절약)
기준: 배치 = 문장대로의 인물 위치·동선 / 인원 = 복제·누락 없음 / 그림체 = style bible(굵은 잉크선 망화) 일치 / 고증 = 시대·소품 / 글자 = 가짜 글자 없음, 요청 글자 정확

| 장면 | Qwen t2i | Qwen-Edit+시트 | MOSS t2i | **MOSS 레이아웃** | MOSS→Qwen-Edit | MOSS 편집+시트 |
|---|---|---|---|---|---|---|
| 범과 대치(복잡) | 배치2 인원5 | 배치2 인원4(범 꼬리가 아이를 관통) | 배치3.5 인원5 | **배치4.5 인원5** (s1: 아이가 등 뒤에서 내다봄, 범은 개울 건너) | 배치4.5 | 붕괴(거대한 얼굴 합성) |
| 품삯(복잡) | 배치3 **인원2(노인 복제 ×2)** | 배치3 인원5(칠복이 문간이 아닌 오른쪽) | **배치5 인원5** | **배치5 인원5** | 배치5 | 붕괴(얼굴 합성) |
| 바위 밑 연이(1인) | 배치4 인원3(s2 복제) | 배치4 인원5 | 배치4 | **배치5**(바위 아래 은신 정확) | 배치5 | 붕괴(다른 소녀) |
| 덫 거두는 손(1인) | 배치3 고증2(덫 속 범 머리) | **배치4 고증5**(올바른 발덫) | 배치3 고증2(덫 속 범 머리) | 배치3 고증2(바구니형 덫) | 고증2 | 붕괴(현대 재킷 남성) |
| 썸네일 덫(도입) | **고증5**(발판 있는 발덫) | — | 고증3(이빨 그릇 모양) | 고증3, 연이 자주 저고리 정확 | — | — |
| 썸네일 휘파람 + "짧게 두 번" | **글자1**("정게 두번") | **글자1**("장저 두 번") | **글자5**("짧게 두 번") | 글자4("짧게 두번", 띄어쓰기 1곳) | — | — |
| 그림체(전체) | 4 (굵은 잉크선) | 4 | 3 (부드러운 반실사·수채) | 3 | 3.5 | 1 |

요약 점수(5점, 배치·인원·그림체·고증·글자 평균): Qwen t2i 3.5 · Qwen-Edit+시트 3.9 · MOSS t2i 3.8 · **MOSS 레이아웃 4.1** · MOSS→Qwen 4.0 · MOSS 편집 1.2

### 판단
- **MOSS가 확실히 나은 것**: 여러 인물 동선(레이아웃 상자대로 위치가 잡힘), 인물 복제 없음(24장 중 0장, Qwen t2i는 12장 중 3장), **한글 글자**(Qwen은 전부 틀림).
- **Qwen이 나은 것**: 그림체(우리 망화 잉크선), 소품 고증(발덫), 인물 시트로 얼굴 고정(MOSS는 이미지 입력이 없음).
- **MOSS 편집 LoRA는 실패**(4/4 붕괴) — 장면+인물 시트 조합을 이해하지 못함. 쓰지 않음.
- MOSS→Qwen-Edit(denoise 0.75)은 배치를 지키지만 얼굴·그림체 변화가 작음 — 그림체 정리는 오늘 만든 `stylize`(GPT 그림을 기준으로)로 따로 해야 함.
- "tiger trap"이라는 말 때문에 두 모델 모두 덫 안에 범 머리를 그림 → 프롬프트를 "iron leg-hold trap(발덫), no animal"로 바꾸면 해결될 문제(모델 차이 아님).

### 추천: (c) 장면 유형별로 나눠 쓰기
| 장면 유형 | 쓸 모델 |
|---|---|
| 썸네일·도입·다인물 핵심 장면 | GPT 이미지(현행 유지) |
| GPT 한도가 모자랄 때의 다인물 동선 장면 | **MOSS 레이아웃 초안 → stylize(GPT 앵커)** |
| 1~2인 단순 장면, 소품이 중요한 장면 | Qwen-Edit+인물 시트(현행 유지) |
| 썸네일 한글 문구를 그림 안에 넣을 때 | MOSS t2i (지금은 story_thumbnail.py로 글자를 얹으므로 필수는 아님) |

### story_images.py 반영 계획 (승인 후 코드 변경)
1. story.json 장면에 `"engine": "moss_layout"`과 `"boxes": [{"x","y","w","h","desc","char"}...]`(1664×928 기준) 추가. 없으면 지금처럼 Qwen.
2. `render()`에서 engine이 moss_layout이면 `image_moss_layout_api.json`을 쓰고, boxes를 `{"__value__": ...}`로 넣고 char 표시된 상자 번호를 `character_boxes`로 넘김.
   인물 설명은 시트 그림 대신 story["characters"] 문장을 상자 desc에 넣음(이미지 입력 없음).
3. 결과는 `scenes/draft/`에 두고 `--stage stylize`로 GPT 앵커 그림체를 입힘(오늘 추가한 단계 재사용). 얼굴이 시트와 다르면 Qwen-Edit 1ref로 얼굴만 맞춤.
4. 상자 좌표는 Claude가 대본을 읽고 장면마다 작성(GPT 토큰 불필요).
5. 소품 프롬프트 사전: "tiger trap" → "iron leg-hold trap with a pressure plate, no animal inside".

---

## B. Kandinsky 6.0 Video Lite vs LTX-2.5
결과: `test_output/story/model_ab_2611/B_kandinsky/` (`<장면>_ltx.mp4`, `<장면>_k6.mp4`, `_cmp_<장면>.jpg` 6프레임 비교, results.jsonl)

### 준비
- 노드팩 **kandinsky6 v1.0.2만 설치**(사용자 승인, kandinsky6-sr 미설치). 코드는 MIT, 동봉 영상 코드는 Apache 2.0.
  설치 전 `C:\AI\_backup\pip_freeze_before_kandinsky6_*.txt` 백업, pip는 **추가만 16개**(librosa, numba, scikit-learn 등), 기존 패키지 버전 변경 없음.
  설치 후 Qwen-2512 1장(87.5초 cold, 성공), LTX-2.5 클립 1개(115초, 성공) 재확인. MOSS 워크플로는 설치 전에 끝남.
- 시작 시 네트워크 호출 없음(다운로드는 `POST /kandinsky6/download-models`를 직접 부를 때만), 예제 그림 4장을 input/에 복사함.
- **오디오는 시험 불가**: 오디오 VAE는 `torch.load`(.pth/.pt)만, 보코더는 `bigvgan_generator.pt`만 읽음 → safetensors판을 읽지 못함. 샘플링에는 오디오 VAE가 필요 없어 **영상만** 시험.
- **우리 TTS로 입모양 구동 불가**: 공식 팩에 외부 오디오 입력 노드가 없음. `<S>대사<E>`로 모델 자체 입모양만 평가(사용자 결정).
- 설정: 10 steps, CFG 1, euler/simple, 864×480, 121프레임(5초), Beautify 끔, MagCache 없음(Pro 전용), VAE 디코드는 타일.

### 시간·VRAM
| 모델 | 클립당 | cold 첫 클립 | 모델 적재(추정) | 최대 VRAM | 해상도 |
|---|---|---|---|---|---|
| LTX-2.5 (현행) | 110~127초 | — | — | 15.6~15.8GB | 640×352 |
| Kandinsky 6 Lite distill | **235~241초** | 273초 | 약 35초 | 15.3~15.8GB | 864×480 |

### 채점 (Claude, 1~5)
| 클립 | LTX 이야기/유지/깨짐 | Kandinsky 이야기/유지/깨짐 | 메모 |
|---|---|---|---|
| s01 덫·남매(도입) | 3 / 5 / 5 | 3 / 2 / **1** | K6: 아이 3~4명이 새로 생겨 서양식 옷차림으로 걸어옴 |
| s09 덫 여는 손 | 4 / 5 / 4 | 3 / 3 / 2 | K6: 손 클로즈업으로 들어가며 얼굴 사라짐, 덫 모양이 변함 |
| s10 발 낀 두만 | 3 / 5 / 4 | 3 / 4 / 2 | K6: 덫이 거북 등딱지처럼 녹아내림 |
| s11 범과 대치 | 2 / 5 / 5 | **5 / 5 / 5** | K6: 범이 일어나 개울로 내려옴 — 이번 시험 최고 컷 |
| s12 업고 돌아옴 | 3 / 5 / 5 | 3 / 3 / 2 | K6: 연이 손에 불빛이 생기고 끝에 새 인물 등장 |
| s16 품삯 | 3 / 5 / 4 | 4 / 5 / 5 | LTX는 끝 1.5초 어두워짐(잘라냄), K6는 밝기 유지 |
| **평균** | **3.0 / 5.0 / 4.5 → 4.2** | **3.5 / 3.7 / 2.8 → 3.3** | |
| 입모양 lip_s05, lip_s16 | — | 입이 열리고 닫히며 말하는 동작은 나옴(2/2). 다만 약 1.5~2초 뒤부터 움직여 우리 TTS(0초 시작)와 어긋남 → 2/5 | `*_k6_ourtts.mp4`로 확인 가능 |

GPT 채점: 요청했지만 실행이 자동 승인 단계에서 막힘(오늘 아침 "GPT 토큰 절약" 지시와 충돌). 비교 이미지와 프롬프트는 준비돼 있어 승인하면 1회 호출로 끝남.

### 판단
- Kandinsky는 **움직임이 크고 극적**(범 장면은 LTX보다 확실히 좋음)이지만 **새 인물 추가·소품 변형이 6개 중 4개**. "no new people"을 지키지 못함.
- 시간은 2배(5초 클립 약 4분), VRAM은 비슷. 해상도는 더 높음(864×480).
- 우리 TTS에 입모양을 맞추는 기능이 공식 팩에 없음 → 대사 장면 용도는 지금은 불가.
- **추천: LTX 유지, 동물·자연 동작 장면(범, 눈보라)만 Kandinsky를 선택적으로**(장면 유형별 나눠 쓰기). 인물 여럿 장면에는 쓰지 않음.

### story_motion.py 반영 계획 (승인 후)
- 장면 `"motion_engine": "k6"`일 때만 Kandinsky 워크플로(`scripts/kandinsky_ab.py`의 wf 재사용)로 생성, 나머지는 LTX.
- 프롬프트 끝에 "no new people"만으로는 부족 → 부정 프롬프트에 "extra people, children appearing, new characters" 추가, 시드 2개 생성 후 QA.
- LTX 클립 끝 어두워짐 문제: 클립마다 밝기를 재서 15% 이상 떨어지는 지점에서 자르는 단계를 story_motion에 추가(오늘 ep5c s02·s06·s16에서 수동으로 한 것).

## C. LTX Foley LoRA (영상→효과음)
결과: `test_output/story/model_ab_2611/C_foley/` (`<이름>_cfg1_foley.mp4`, 블라인드 `blind/A1~A10.mp4` + `answer.txt`)

### 준비
- 공식 V2A 워크플로는 커스텀 노드 ComfyUI-LTXVideo + VideoHelperSuite를 씀. **내장 노드만으로 재구성**: LoadVideo → LTX 비디오 VAE 인코딩 → `LTXVFreezeLatent`(영상 고정 = 공식의 mask_video=false) + 빈 오디오 latent → Concat → LTX-2.5 distilled + Foley LoRA(1.0) → 오디오만 디코드. 커스텀 노드 설치 없음.
- 공식 문서: "LTX-2.3에서만 검증, 2.5 지원은 개발 중". 오류 없이 붙었고 로그에 "lora key not loaded" 경고 없음.

### 결과 (클립당 약 25~54초, cold 113초, 최대 VRAM 15.8GB)
| 소리 | Foley 결과 | 현행 Stable Audio 3 | 화면과 타이밍 |
|---|---|---|---|
| 눈길 발소리 | **거의 무음**(피크 -35 dBFS). LoRA 끈 대조군도 -36.5 dBFS로 같음 → LoRA 효과 없음 | 바람+발소리 바닥(피크 -14) | 판단 불가 |
| 덫 여는 소리 | 금속 충격음 1회(피크 -0.9) | 금속성 배경 | 소리 2.3초, 화면 최대 움직임 3.0~4.0초 → **0.7~1초 빠름** |
| 범 숨소리 | 저음 덩어리 2회(중심 593Hz, 2.0초·4.0초) | 바람 배경 | 2.0~3.0초 움직임과 **맞음** |
| 초롱 불꽃 | 거의 무음(피크 -41) | 바람 배경 | 판단 불가 |
| 휘파람 "짧게 두 번, 길게 한 번" | 0초에 0.7초짜리 소리 1번 — **박자 패턴 못 만듦** | (합성 휘파람 cue_track이 정확) | — |

- CFG 3: 발소리·불꽃은 완전 무음(-82 dBFS), 덫·범은 클릭 1~2개로 붕괴 → distilled 모델에서는 CFG 1만 쓸 수 있음(공식 권장 6~8은 dev 모델 기준).
- 채점(Claude, 소리 자체는 들을 수 없어 수치·파형 기준): Foley **2/5**, Stable Audio 현행 **3/5**. 최종 판단은 블라인드 청취로.
- **추천: 현행 유지**(장면 바닥 소리는 Stable Audio, 휘파람은 합성 cue). Foley는 LTX-2.3 dev 본체(`ltx-2.3-22b-dev`, Gemma-3 12B 인코더)로 공식 설정(CFG 6, 30 steps)을 써야 제대로 평가 가능 → **본체 다운로드가 필요하므로 여기서 멈춤**.

## D. BGM: ACE-Step 1.5 XL SFT / turbo / Stable Audio 3.0
결과: `test_output/story/model_ab_2611/D_bgm/` (`<분위기>_<모델>.flac`, `qc.md`, 블라인드 `blind/B1~B9.mp3` + `answer.txt`, 모두 -16 LUFS로 맞춤)
워크플로: `workflows/music_acestep15_xl_sft_api.json` (turbo 사본, 공식 템플릿 기준 50 steps · CFG 7). 분위기 3종 × 60초 × 3모델, 시드 7.

### 시간·VRAM (60초 곡)
| 모델 | 곡당(warm) | cold 첫 곡 | 최대 VRAM |
|---|---|---|---|
| ACE-Step XL SFT | 31초 | 74초 | 15.6GB |
| ACE-Step XL turbo | 13초 | 34초 | 15.6GB |
| Stable Audio 3.0 | 2초(warm)* | 20초 | 7.9GB |
\* 두 번째부터 2초 — 같은 그래프에서 모델이 적재된 상태라 생성만 걸린 시간. 이상하게 빠르지만 파일은 정상 길이·음량.

### QC (audio_qc.py: 통합 음량, true peak, M < -45 LUFS 1.5초 이상 무음)
| 곡 | 음량(LUFS) | True peak | 클리핑 | 무음 구간 |
|---|---|---|---|---|
| 긴장 ACE SFT | -12.2 | 0.0 | **있음** | 없음 |
| 긴장 ACE turbo | -11.7 | +0.5 | **있음** | 없음 |
| 긴장 SA3 | -21.1 | -5.3 | 없음 | 없음 |
| 따뜻함 ACE SFT | -11.0 | -0.7 | 없음 | 56.3초~끝(꼬리) |
| 따뜻함 ACE turbo | -20.7 | -5.8 | 없음 | 51.6초~끝 |
| 따뜻함 SA3 | -22.1 | -10.8 | 없음 | 57.9초~끝(꼬리) |
| 엔딩 ACE SFT | -17.0 | -3.9 | 없음 | **8.4초~끝 — 곡이 8초 만에 끝남** |
| 엔딩 ACE turbo | -25.5 | -7.2 | 없음 | **30.1초~끝 — 절반이 무음** |
| 엔딩 SA3 | -22.5 | -5.1 | 없음 | 없음 |

### 판단 (Claude, 수치 기준. 음악 자체는 블라인드 청취로 판단 필요)
- ACE-Step은 60초를 채우지 못하는 경우가 있음(엔딩 2곡). 곡 구조를 스스로 끝내는 성향 → 루프용 BGM에는 꼬리 자르기·이어 붙이기 처리가 필요.
- ACE 긴장곡 2개는 클리핑 → 쓰려면 리미터 필요(story_video의 loudnorm이 어느 정도 흡수하지만 원본 단계에서 막는 편이 안전).
- SA3는 3곡 모두 구멍·클리핑 없이 60초를 채움, VRAM 절반, 가장 빠름.
- **추천: Stable Audio 3 유지.** ACE-Step XL SFT는 블라인드 청취에서 음악성이 확실히 좋다고 판단될 때만 "긴장" 계열에 리미터를 붙여 추가 후보로. turbo는 엔딩 무음이 커서 제외.

---

## 들어볼 블라인드 파일
| 시험 | 파일 | 정답표 |
|---|---|---|
| C 효과음 | `test_output/story/model_ab_2611/C_foley/blind/A1.mp4` ~ `A10.mp4` (화면+소리, -20 LUFS 맞춤) | `C_foley/blind/answer.txt` |
| D BGM | `test_output/story/model_ab_2611/D_bgm/blind/B1.mp3` ~ `B9.mp3` (분위기별 3개씩 묶음, -16 LUFS 맞춤) | `D_bgm/blind/answer.txt` |
| B 입모양 | `B_kandinsky/lip_s05_k6_ourtts.mp4`, `lip_s16_k6_ourtts.mp4` (Kandinsky 입모양 + 우리 TTS) | — |
| ep5c v2 휘파람 음량 | `yadam_ep5c/yadam_ep5c_preview.mp4` 0:20, 1:28, 2:39, 2:52, 3:00, 6:59, 7:00 | — |

## 종합 추천
| 영역 | 추천 | 이유 |
|---|---|---|
| 장면 그림 | **(c) 나눠 쓰기** — 다인물 동선은 MOSS 레이아웃 초안→stylize, 1~2인·소품 장면은 Qwen-Edit+시트, 핵심 장면은 GPT | MOSS: 배치·인원·한글 우수 / Qwen: 그림체·소품·얼굴 고정 우수 |
| 동작 클립 | **LTX 유지**, 동물·자연 장면만 Kandinsky 선택 사용 검토 | Kandinsky는 새 인물·변형이 잦고 2배 느림 |
| 효과음 | **현행 유지**(Stable Audio 바닥 + 합성 휘파람) | Foley는 2.5에서 조용한 소리 무음, 박자 패턴 불가. 2.3 본체로 재시험은 다운로드 승인 필요 |
| BGM | **Stable Audio 3 유지** | ACE는 무음 구간·클리핑. 청취 결과로 재판단 |

## 승인이 필요한 것
1. GPT 채점(B·D) 실행 여부 — 비교 이미지 준비됨, 1회 호출씩.
2. story_images.py(MOSS 레이아웃 엔진) / story_motion.py(밝기 자르기, k6 선택 엔진) 코드 변경.
3. Foley 재시험용 LTX-2.3 dev 본체 + Gemma-3 12B 인코더 다운로드 여부.
