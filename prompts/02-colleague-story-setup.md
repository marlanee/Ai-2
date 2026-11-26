# 02. 동료용 셋업 프롬프트 — 스토리형 AI 영상 제작 환경 복제 (20~30대 타깃)

> 사용법: 같은 사양 PC(RTX 5060 Ti 16GB, RAM 64GB, Windows 11)에서 이 저장소를 clone하고 `setup/local-comfyui` 브랜치를 체크아웃한 폴더에서 Claude Code를 연 뒤, 아래 `---` 사이 내용을 그대로 붙여넣으세요.
> 50~60대 야담 채널을 만들며 검증한 환경·모델·파이프라인을 그대로 깔고, 20~30대 타깃 파일럿 1편까지 직접 만들어 보는 프롬프트입니다.

---

너는 내 PC(RTX 5060 Ti 16GB, RAM 64GB, Windows 11)에 **스토리형 AI 영상 제작 환경**을 세팅하고, 20~30대 타깃 파일럿 영상 1편을 스스로 만든다.
이 저장소는 동료가 50~60대 야담 채널용으로 시행착오를 거쳐 만든 것이다. 경로·모델·설정을 **동료 PC와 똑같이** 맞추는 게 원칙이다 (스크립트에 `C:\AI\...` 경로가 하드코딩되어 있음).
처음부터 끝까지 직접 실행하되, 아래 "멈추고 물어볼 것"에 해당하면 반드시 멈추고 나에게 물어봐. 답은 한국어로.

## 0. 먼저 읽을 것
- `docs/story-night-report.md` — 결과물, 표준 스토리 구성 과정, 파이프라인, 그림 품질 교훈, 한계
- `config/models.yaml` — 모델 목록·라이선스·출처 URL
- `docs/setup-log.md` — ComfyUI 셋업 때 겪은 문제와 해결법
- `scripts/story_*.py` 각 파일 상단 docstring

## 1. 사전 점검 (결과를 표로)
- `nvidia-smi`(드라이버, CUDA, VRAM), RAM, C: 남은 용량 (**최소 250GB** 필요: ComfyUI 모델 약 190GB + 학습용 53GB + TTS 약 10GB. 부족하면 멈추고 물어봐)
- git, Python 3.12, Node.js(24 이상), codex CLI 설치 여부와 버전
- 드라이버가 Blackwell(sm_120)을 지원하지 않으면 **직접 업데이트하지 말고** 알려만 줘.

## 2. 폴더 구조 (동료 PC와 동일하게)
```
C:\AI\ComfyUI\            ComfyUI 포터블 (NVIDIA)
C:\AI\tools\ffmpeg\bin\   ffmpeg.exe / ffprobe.exe
C:\AI\tools\fonts\        한글 OFL 폰트 (BlackHanSans, DoHyeon, Jua, SongMyung, YeonSung, Gaegu, Gugi, EastSeaDokdo, BlackAndWhitePicture)
C:\AI\tts\venv\           Qwen3-TTS 전용 venv
C:\AI\tts\models\         Qwen3-TTS 모델 3종
C:\AI\skills_eval\baoyu-skills\   GPT 이미지 생성 래퍼
C:\AI\train\              musubi-tuner (LoRA 학습, 선택)
```

## 3. ComfyUI
- 공식 GitHub Releases 최신 **포터블(NVIDIA)** 을 `C:\AI\ComfyUI`에 설치. PyTorch가 CUDA 12.8 이상이고 `torch.cuda.get_arch_list()`에 `sm_120`이 있어야 통과.
- 실행은 저장소의 `scripts/run_comfyui_local.bat`을 `C:\AI\ComfyUI\`에 복사해서 사용 (`--listen 127.0.0.1 --port 8188 --enable-manager`). **외부에 포트를 열지 마.**
- 커스텀 노드는 설치하지 않는다 (내장 노드만 사용).

## 4. 모델 다운로드
원칙: `.safetensors`(또는 GGUF)만. 받기 전에 **목록·용량·라이선스 표를 보여주고 내 승인 후** 다운로드.

### 4-1. ComfyUI 모델 (`scripts/download_models.py` 사용, 이어받기 지원)
`python scripts/download_models.py C:\AI\ComfyUI\ComfyUI\models`
- 스토리 영상에 **꼭 필요한 것**: Qwen-Image-2512 fp8 + Lightning 4-step LoRA, Qwen-Image-Edit-2511 int8 + Lightning LoRA, Qwen2.5-VL 7B fp8 텍스트 인코더, Qwen-Image VAE, Stable Audio 3.0 Medium + T5Gemma (BGM·효과음)
- 음악 채널용(ACE-Step, MiniMax Music 3, Wan 2.2, Z-Image)은 스토리 영상엔 안 쓴다. 용량을 아끼려면 목록에서 빼도 되는지 나에게 물어봐.
- **LTX-2.5 (동작 클립, 필수)**: Hugging Face 게이트 모델이라 `download_models.py`에 없다. `config/models.yaml`의 LTX-2.5 항목 4개(22B distilled int8, Gemma4 12B int8 텍스트 인코더, video VAE, audio VAE) + Gemma 4 E2B int8. HF 페이지에서 라이선스 동의 + `hf auth login`이 필요하니 **이 단계에서 멈추고 나에게 요청해.** 로그인 후 `hf download`로 받아 각 폴더에 넣어.

### 4-2. Qwen3-TTS (내레이션·인물 목소리)
- `C:\AI\tts\venv` 생성 (Python 3.12). 동료 PC 기준 버전: torch 2.11.0+cu128, torchaudio 2.11.0+cu128, transformers 4.57.3, accelerate 1.12.0, qwen-tts 0.1.1, librosa, soundfile, numpy, pillow
- 모델 3종을 `C:\AI\tts\models\<폴더명>`에 받기 (HF `Qwen/` 조직, 폴더명은 아래와 정확히 같게):
  - `Qwen3-TTS-12Hz-1.7B-VoiceDesign` (목소리 설계)
  - `Qwen3-TTS-12Hz-1.7B-CustomVoice`
  - `Qwen3-TTS-12Hz-0.6B-Base` (설계한 목소리 복제 낭독)
- 영상 합성(`story_video.py`)과 TTS는 **이 venv의 python으로 실행**한다 (시스템 Python엔 soundfile이 없음).

### 4-3. 도구
- ffmpeg: gyan.dev 공식 release essentials 빌드 → `C:\AI\tools\ffmpeg\bin\`
- 폰트: Google Fonts의 위 9종 (OFL) → `C:\AI\tools\fonts\`, 라이선스 txt 함께
- baoyu-skills: `git clone https://github.com/JimLiu/baoyu-skills.git C:\AI\skills_eval\baoyu-skills` (실행은 `npx -y bun …` — 일반 node로 돌리면 TypeScript 오류남)
- codex CLI: `npm i -g @openai/codex` → **로그인은 내가 직접 한다** (`codex login`). 모델은 `gpt-6.2-sol`, reasoning high (`scripts/story_gpt.py`에 고정됨)

### 4-4. LoRA 학습 (선택 — 나중에 해도 됨, 받기 전에 물어봐)
- `git clone https://github.com/kohya-ss/musubi-tuner.git C:\AI\train\musubi-tuner` + 자체 venv
- 학습용 bf16 원본: Comfy-Org/Qwen-Image_ComfyUI의 `split_files/diffusion_models/qwen_image_2512_bf16.safetensors`(38GB), `split_files/text_encoders/qwen_2.5_vl_7b.safetensors`(15GB) → `C:\AI\train\models\split_files\...`
- 설정: `--fp8_base --fp8_scaled --blocks_to_swap 40`, network_dim 16, adamw8bit, lr 1e-4. 텍스트 인코더 캐시에 `--fp8_vl`을 쓰면 "Promotion for Float8 Types" 오류가 나니 빼.
- 교훈: 로컬 모델이 그린 그림으로 학습하면 효과가 거의 없다. **승인된 GPT 이미지로** 데이터를 모아야 의미가 있다.

## 5. 스모크 테스트 (각각 시간·VRAM·출력 경로 기록)
1. Qwen-Image-2512로 16:9 장면 1장 (`scripts/run_workflow.py` + `workflows/image_qwen2512_api.json`)
2. Qwen-Image-Edit-2511로 인물 참조 1장 편집 (`workflows/image_qwen_edit_2511_1ref_api.json`)
3. LTX-2.5 I2V 5초 클립 640×352 (`scripts/story_motion.py`, 클립당 약 1.8~3분이 정상)
4. Qwen3-TTS: VoiceDesign으로 목소리 1개 설계 → Base로 복제 낭독 2문장
5. Stable Audio 3.0 BGM 30초
6. `codex exec -m gpt-6.2-sol -c model_reasoning_effort=high -s read-only "한 줄로 자기소개"` 응답 확인
7. GPT 이미지 1장 (baoyu codex-imagegen, 약 2.5분)

## 6. 파일럿 1편 (20~30대 타깃)
### 6-1. 기획
- 유튜브에서 20~30대가 많이 보는 스토리형 AI 영상 상위 조회수 사례를 조사해서 트렌드 표로 정리하고, 장르 후보 3개를 제안해서 **내가 고르게** 해.
- 그 장르에 맞게 `scripts/story_gpt.py`의 `PD`(타깃 페르소나·트렌드 프롬프트)와 `BENCH`(벤치마크 목록)를 20~30대용으로 바꿔. 50~60대 야담용 원본은 지우지 말고 옵션으로 고를 수 있게.
- 내레이션 목소리는 20~30대 취향으로 VoiceDesign 후보 3~4개를 만들어 **내가 고르게** 해. 고른 목소리를 `config/voices.json`에 새 키로 추가.

### 6-2. 반드시 지킬 표준 과정 (동료가 실패하며 확정한 것)
1. **영상 길이 8분 상한** (내레이션 3,000~3,300자, 장면 16~18개)
2. **대본: GPT가 쓰고 → Claude가 처음 듣는 청자로 검수 → GPT가 수정 → Claude 재검수**
   - 첫 세 문장에 언제·어디서·누가·무엇 / 수수께끼는 하나 / 시간 순서대로 / 장면당 새 정보 하나 / 인물은 첫 등장 때 관계를 붙여 소개
   - 검수를 통과시키기 전에 도입부를 소리 내어 읽듯 다시 확인해. (동료 4편은 도입이 이해 안 된다는 지적을 받았다 — GPT가 쓰고 Claude가 통과시킨 검수 실패)
3. **그림 분담**: 썸네일·도입 30초·인물 2명 이상 핵심 장면은 GPT 이미지, 나머지는 로컬 Qwen (GPT 그림을 스타일 기준·인물 참조로 넣고 편집). 로컬 검수에서 두 번 떨어진 장면만 GPT로 넘긴다.
4. 인물 참조 그림은 **상반신**(전신 시트는 콜라주·인물 복제를 일으킴). 1인 장면 프롬프트엔 "ONLY person in the whole image".
5. 모든 장면이 이야기에 맞게 움직여야 한다 (LTX 동작 클립). 고화질일 필요는 없다.
6. 동작 클립 전에 장면 QA (`story_gpt.py scene_qa`), 완성 후 GPT 완성본 검수(`review_video`) 반영.

### 6-3. 실행
`scripts/story_pipeline.py`로 chars → scenes → qa → voices → tts → bgm → sfx → motion → video → thumb → preview → review 순서. 결과는 `test_output/story/<폴더>/`.

## 알려진 함정 (동료가 겪은 것)
- PowerShell은 한글·따옴표·jq를 망가뜨린다 → Bash나 스크립트 파일 사용, 긴 지시는 `--brief @파일`
- PowerShell이 쓴 JSON엔 BOM이 붙는다 → `utf-8-sig`로 읽기
- ComfyUI에 LTX 모델이 올라간 채로 TTS를 돌리면 엄청 느려진다 → TTS 전에 `POST http://127.0.0.1:8188/free` (스크립트에 반영됨)
- VoiceDesign 출력 앞뒤에 1~3초 무음 → librosa trim (반영됨)
- 로컬 Qwen은 복잡한 동선(엿듣기, 구출)에 약하다 → 텍스트 전용 초안 후 참조 편집, 계절·소품 연속성은 프롬프트에 명시
- codex 구독 한도가 차면 몇 시간 멈춘다 → GPT 이미지는 하루 약 20장, 동시 실행 금지(lock_busy)

## 멈추고 물어볼 것
- 디스크 부족, 다운로드 목록 승인, 시스템 전체 설치(드라이버·CUDA)
- HF 로그인·라이선스 동의, codex 로그인 (토큰·비밀번호는 내가 직접 넣는다. 채팅에 붙여넣으라고 하지 마)
- 상업 이용이 불가하거나 애매한 라이선스
- 장르 선택, 내레이션 목소리 선택
- 같은 오류로 두 번 실패했을 때
- 유튜브 업로드·채널 생성은 하지 마 (내가 결정)

## 커밋 규칙
- 모델 파일, 생성물(`test_output/`), 토큰은 절대 커밋하지 마. `.omc/`도 커밋 금지.
- 작업은 새 브랜치(예: `story/young-pilot`)에서. 동료 브랜치(`setup/local-comfyui`)에 직접 커밋·푸시하지 마.

## 마지막 보고
1. 설치·다운로드 요약 표 (모델, 용량, 라이선스, 상업 이용)
2. 스모크 테스트 표 (시간, VRAM, 통과)
3. 파일럿 영상·썸네일·대본 검수 기록·GPT 완성본 검수 점수
4. 20~30대 타깃에 맞게 바꾼 것과, 동료 파이프라인에서 더 고치면 좋을 점

---
