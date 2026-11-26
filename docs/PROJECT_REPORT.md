# Ai-2 전체 작업 보고서 (2026-11-23 → 2026-11-26)

로컬 PC(RTX 5060 Ti 16GB, RAM 64GB, Windows 11)의 ComfyUI로 YouTube 영상을 만드는 자동화 프로젝트.
두 갈래로 진행했다: **① 8090 레트로 로파이 음악 채널**, **② 50~60대 대상 야담·사연 스토리 영상**.
날짜별 상세는 [`reports/`](reports/), 모델 비교·시험은 [`experiments/`](experiments/)에 있다. 생성물(영상·음악·그림)은 `test_output/`(git 제외).

---

## 1. 타임라인

| 날짜 | 한 일 | 상세 |
|---|---|---|
| 11-23 | 로컬 셋업 작업 프롬프트 작성(ComfyUI·모델·스모크 테스트), LTX-2.5를 비교 후보로 추가 | `prompts/01-local-setup.md` |
| 11-24 오전 | ComfyUI 포터블 0.46 설치, 모델 약 98 GB(safetensors만), 템플릿→API 변환기, 스모크 테스트 11종 | [setup-log](reports/2026-11-24-setup-log.md), [smoke-test](experiments/2026-11-24-smoke-test.md) |
| 11-24 오전 | 결정: 루프 영상 **LTX-2.5 FLF2V**, 음악 **Stable Audio 3.0**(블라인드 13.3점 vs ACE-Step 4.0점), 빗소리 -4 dB | smoke-test |
| 11-24 오후 | 한글 간판 고치기: 깨진 글자 지우기 → 실제 폰트 합성 → Qwen-Edit 질감화 → 글자 획 대조 검사 | `sign_fix.py`, `glyph_check.py` |
| 11-24 밤 → 11-25 | 밤샘 로파이 파이프라인: 2시간 영상 5편(서울 1~3편, 사이버펑크, 디스토피아 45분), GPT 검수·전략 토의, 전환 품질 측정, 트루피크 리미터 | [overnight-lofi](reports/2026-11-25-overnight-lofi.md) |
| 11-25 | 채널 아트(프로필·배너), 업로드 팩, 에피소드 간 곡 중복 제거, 영어 우선 채널 문안 | `make_channel_art.py`, `make_upload_pack.py` |
| 11-25 밤 → 11-26 아침 | 스토리 영상 파이프라인 신설: 야담·사연 6편, 인물별 목소리, 장면 효과음, LTX 동작 클립, 표준 스토리 구성 과정 확정, 스타일 LoRA 시험 | [story-night](reports/2026-11-26-story-night.md) |
| 11-26 주간 | ep5c 검수 반영(정지 화면 56%→0%, 자막 정리), GPT 그림 + LoRA 자동 수집, 모델 4종 비교·청취 결정, Foley 효과음, 비공개 업로드 | [2026-11-26-day](reports/2026-11-26-day.md), [model-ab](experiments/2026-11-26-model-ab.md) |

---

## 2. 결과물 (test_output/, git 제외)

### ① 로파이 음악 (Night Alley Records 채널)
| 영상 | 길이 | 비고 |
|---|---|---|
| 서울 골목 라디오 1편 '레코드 가게' | 2:00:00 | 업로드됨 (Studio 기준 공개, 조회수 86) |
| 2편 '다방 창가', 3편 '막차 뒤 정류장' | 각 2:00:00 | Studio 콘텐츠 목록에 등록됨(공개 일정은 Studio에서 확인) |
| 사이버펑크 Neon Rain City | 2:00:00 | Studio 콘텐츠 목록에 등록됨 |
| 디스토피아 After the Fall 특집 | 0:45:00 | |
모든 편 -14 LUFS / 약 -1.5 dBTP, 곡 전환 품질 측정과 청취 팩 포함.

### ② 야담·사연 스토리
| 편 | 길이 | 비고 |
|---|---|---|
| 1편 국밥과 짚신 v2 | 6:12 | 초기 정지 그림 버전 |
| 2편 빈 상여를 멘 딸 | 8:06 | GPT 대본 |
| 3편 딱, 딱, 끌 (현대 사연) | 6:36 | |
| 4편 그 문을 닫은 건 접니다 | 22:48 / 8분판 8:06 | 8분 상한 도입 계기 |
| 5편 덫을 거둔 포수 (GPT 대본) | 8:06 | |
| **5편 Claude 대본판 v2 (`yadam_ep5c`)** | **7:18** | 오늘 완성본. Night Alley Records 채널에 **비공개** 업로드 |

---

## 3. 파이프라인 구조

### 공통 도구
| 파일 | 역할 |
|---|---|
| `scripts/ui_to_api.py` | ComfyUI 템플릿(UI JSON) → API JSON (서브그래프·동적 콤보 처리) |
| `scripts/run_workflow.py` | API 워크플로 실행 + 시간·최대 VRAM 기록(`test_output/runs.jsonl`) |
| `scripts/download_models.py` | 승인된 모델 이어받기·크기 검증 |
| `scripts/audio_qc.py` | 음량(LUFS)·트루피크·전환 평가 |
| `workflows/*_api.json` | 실제로 쓰는 API 워크플로 |
| `config/models.yaml` | 모델 목록·경로·라이선스·상업 이용 여부 |

### ① 로파이 영상
키아트(`theme_pipeline.py`, Qwen-Image-2512) → 한글 간판 수정(`sign_fix.py`, `integrate_text.py`, `glyph_check.py`) → LTX-2.5 루프(`ltx_variants.py`, 간판 영역 고정 `freeze_regions.py`) → 음악 풀(Stable Audio 3.0, MiniMax Music 3, 헤드룸) → 2시간 편집표 합성(`build_long.py`, 전환 곡선 선택·리미터) → 썸네일(`make_thumbnail.py`) → 업로드 팩(`make_upload_pack.py`).

### ② 스토리 영상 — `scripts/story_pipeline.py` 한 명령
```
script_review → chars → scenes → gptimg → stylize → qa → lora_collect → voices → tts → bgm → sfx
→ motion → foley → video → thumb → preview → review
```
| 단계 | 파일 | 핵심 |
|---|---|---|
| 대본 | `story_gpt.py` | GPT 집필 → Claude 첫 청취자 검수 → GPT 수정 (오늘은 Claude 집필·검수) |
| 인물·장면 그림 | `story_images.py` | Qwen 인물 시트, Qwen-Edit 참조 장면, MOSS 레이아웃 엔진, stylize, 소품 문구 교정 |
| GPT 그림·LoRA | `story_gptimg.py` | 썸네일·도입·다인물 장면만 GPT, 승인한 원본 자동 수집 |
| 목소리 | `story_voices.py`, `story_tts.py` | Qwen3-TTS 인물별 목소리 설계·복제, 화자별 낭독 |
| 동작 | `story_motion.py` | LTX-2.5 클립, 이어 붙이는 클립(beats), 어두운 꼬리 자르기, Kandinsky 선택 |
| 효과음 | `story_foley.py` + Stable Audio 바닥 | 사건 소리 Foley, 휘파람은 박자 합성 |
| 영상 | `story_video.py` | 한 문장 자막, 대사 색 구분, BGM 덕킹, 효과음, 멈춤 방지 |
| 썸네일 | `story_thumbnail.py` | 폰트로 쓴 제목(글자 깨짐 없음) |

---

## 4. 모델 선택과 근거

| 용도 | 채택 | 근거 | 대안·보류 |
|---|---|---|---|
| 루프 영상 | LTX-2.5 22B distilled int8 (FLF2V) | 1080p 테스트, 이음새 수치 | Wan 2.2 (느림) |
| 스토리 동작 | LTX-2.5 (640×352) | 이야기 충실도 4.2 vs Kandinsky 3.3 | Kandinsky 6: 동물·자연 장면만 |
| 음악(로파이) | Stable Audio 3.0 Medium | 블라인드 13.3 vs ACE-Step 4.0 | MiniMax Music 3 교차 사용 |
| BGM(야담) | 긴장·엔딩 SA3, 따뜻함 ACE-Step XL SFT | 11-26 블라인드 | ACE turbo 제외 |
| 장면 그림 | GPT 핵심 장면 + Qwen-Edit 1~2인 + MOSS 레이아웃 다인물 | 11-26 A/B | MOSS 편집 LoRA 실패 |
| 효과음 | Foley(LTX-2.5, 긴 소리 2.3 dev) + SA3 바닥 + 합성 휘파람 | 11-26 블라인드 2회 | |
| 목소리 | Qwen3-TTS 클론 | 인물별 고정 목소리 | |

라이선스 주의: Stable Audio 3.0(연매출 $1M 미만 무료, 상업 이용 시 등록), LTX-2(연매출 $10M 미만 무료), MOSS-Image(Apache 2.0), Kandinsky 6 노드(MIT), MOSS 편집 LoRA(가중치 라이선스 없음 → 시험용). 상세는 `config/models.yaml`과 각 실험 보고서.

---

## 5. 확정된 운영 원칙
- 스토리 영상은 **8분 상한**(낭독 3,000~3,300자, 16~18장면).
- 스토리 구성: 집필 → **첫 청취자 검수**(첫 세 문장에 언제·어디서·누가·무엇 / 수수께끼 하나 / 시간 순서 / 장면당 새 정보 하나 / 관계를 붙인 인물 소개) → 수정 → 재검수.
- **결함이 없고 상황에 맞는 장면이 동작보다 우선**(11-26). 그림을 대사와 먼저 대조, 동작은 잔잔하게, 클립마다 프레임 검수.
- 모델 파일은 safetensors만, 다운로드·커스텀 노드 설치·업데이트는 사용자 승인 후. ComfyUI는 127.0.0.1에서만.
- GPU 작업은 한 번에 하나, 모델 전환 전 `/free`.
- 사람이 판단해야 하는 소리·음악은 블라인드 파일 + 정답표로.

---

## 6. 배운 것
- **수치보다 청취**: 작은 Foley 소리를 수치로 "거의 무음"이라 낮게 봤지만 청취에서 3짝 모두 이겼다. 소리·음악은 블라인드 청취가 최종 판정.
- **정지 화면은 숨은 최대 문제**였다: 장면 20~37초에 5초 클립 1개 → 영상의 56%가 멈춰 있었다. 장면 길이에 맞춰 클립 수를 정하고 프레임 단위로 이어 붙인다.
- **GPT 그림은 확실히 좋다**(동선·얼굴·가짜 글자 없음)지만 할당량이 한계 → 핵심 장면에만 쓰고, 끝 그림 같은 변형은 로컬 편집으로.
- 같은 로컬 모델이 그린 그림으로 LoRA를 학습하면 효과가 작다 → GPT 승인 그림을 모아 재학습(진행 중, 9장).
- 16GB에서 모델이 남은 채 다른 모델을 올리면 공유 메모리로 넘쳐 30분씩 멈춘다.
- 한글 글자는 모델 단독으로 부족하다 → 폰트 합성 + 편집 모델 질감화(로파이), 썸네일은 폰트로(스토리). MOSS는 한글 제목을 맞게 썼다.

---

## 7. 남은 일
1. 스토리 영상 화질: 동작 클립 640×352 → 960×544 생성 또는 업스케일러 시험(11-27 예정).
2. BGM 분위기별 엔진 코드 반영, 렌더 비트레이트 상향.
3. GPT 승인 그림이 충분히 모이면 스타일 LoRA 재학습.
4. ep5c 13·15장 같은 그림 교체.
5. 야담 전용 채널 여부 결정, 공개 일정.
6. 정리 대기: 다른 세션의 `docs/model-scouting-2026-11.md`(로컬 브랜치 `setup/local-comfyui`, 미푸시), `prompts/02-colleague-story-setup.md`(문서 경로가 옛 위치).

## 8. 브랜치
| 브랜치 | 내용 |
|---|---|
| `claude/eloquent-hamilton-z6uxch` | 원격 기본 브랜치 |
| `setup/local-comfyui` | 셋업 → 로파이 → 스토리 밤샘까지 |
| `story/gpt-image-lora-collect` | 11-26 주간 작업 전체 + 이 보고서. 기본 브랜치 내용은 모두 포함, `setup/local-comfyui`의 다른 세션 커밋 2개(`a842731` 동료 안내 프롬프트, `a0528ca` 모델 스카우팅)는 미포함 |
