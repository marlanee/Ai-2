# 01. 로컬 PC 셋업 프롬프트 (ComfyUI + 모델 다운로드 + 스모크 테스트)

> 사용법: 5060 Ti PC에서 이 저장소를 clone한 폴더에서 Claude Code를 열고, 아래 `---` 사이 내용을 그대로 붙여넣으세요.
> (또는 "prompts/01-local-setup.md 읽고 그대로 진행해줘" 라고만 해도 됩니다.)

---

너는 내 PC(RTX 5060 Ti 16GB)에 YouTube 음악 채널(한국 8090 레트로 로파이 + 루프 영상) 제작 환경을 세팅한다.
목표: ComfyUI 설치 → 필요한 모델 다운로드 → 각 파이프라인 단계별 스모크 테스트 → 결과 보고.
처음부터 끝까지 직접 실행하되, 아래 "멈추고 물어볼 것"에 해당하면 반드시 멈추고 나에게 물어봐.

## 0. 사전 점검 (먼저 실행하고 결과를 표로 보여줘)
- OS 종류/버전, `nvidia-smi`(드라이버 버전, CUDA 버전, VRAM), 시스템 RAM
- 설치 예정 드라이브의 남은 용량 (모델 포함 **최소 120GB** 필요. 부족하면 멈추고 물어봐)
- git, Python, ffmpeg 설치 여부와 버전
- 드라이버가 5060 Ti(Blackwell, sm_120)를 지원하기에 너무 오래됐으면 **직접 업데이트하지 말고** 알려만 줘.

## 1. ComfyUI 설치
- 설치 위치: 이 저장소 **밖** (예: Windows `C:\AI\ComfyUI`, Linux `~/AI/ComfyUI`). 위치는 정하기 전에 나에게 확인받아.
- Windows면 ComfyUI 공식 GitHub Releases의 최신 **포터블(NVIDIA)** 버전, Linux면 git clone + venv.
- PyTorch는 **CUDA 12.8 이상 빌드**여야 한다. 설치 후 아래를 실행해서 확인:
  `python -c "import torch;print(torch.__version__, torch.version.cuda, torch.cuda.is_available(), torch.cuda.get_device_name(0), torch.cuda.get_arch_list())"`
  → `is_available=True`이고 arch 목록에 `sm_120`이 있어야 통과.
- ComfyUI-Manager 설치.
- ComfyUI를 `--listen 127.0.0.1`(기본값)로 띄우고 `http://127.0.0.1:8188` 응답 확인. 외부에 포트를 열지 마.

## 2. 모델 다운로드
원칙:
- 최신 저장소 이름과 파일명은 기억에 의존하지 말고, **ComfyUI 내장 워크플로 템플릿(Workflow → Browse Templates)에 적힌 공식 다운로드 링크**나 공식 Hugging Face 조직(Comfy-Org, 각 모델 개발사)에서 확인해서 받아.
- `.safetensors`(또는 GGUF)만 받는다. 출처 불명 `.ckpt/.pt/.bin` pickle 파일은 받지 마.
- 받기 전에 **목록(모델명 / 파일 / 용량 / 라이선스 / 저장 경로)을 표로 보여주고 내 승인 후** 다운로드.
- 각 모델의 **LICENSE를 직접 열어 확인**하고, YouTube 수익화(상업 이용)가 가능한지 표에 적어. 불가하거나 애매하면 표시하고 대안 제시.
- 각 파일은 ComfyUI의 올바른 폴더(`models/diffusion_models`, `text_encoders`, `vae`, `loras`, `upscale_models`, `checkpoints` 등)에 넣어.

받을 것 (우선순위 순):
1. **음악**: ACE-Step 1.5 (ComfyUI 템플릿 기준, MIT 라이선스). 16GB면 XL도 가능한지 확인.
   - 선택: 로파이 LoRA `ryanontheinside/lo_fi-acestep1.5-v1` (라이선스 확인 후)
2. **음악(비교용)**: Stable Audio 3.0 Medium 또는 Small (Stability AI Community License, 텍스트 인코더로 쓰는 Gemma 약관도 확인).
3. **루프 영상**: Wan 2.2 (Apache 2.0)
   - **First-Last-Frame to Video** 템플릿이 쓰는 모델 세트 (14B는 16GB에 맞게 fp8 또는 GGUF Q4~Q5)
   - 속도용 Lightning/LightX2V LoRA가 템플릿에 있으면 함께
   - 대안으로 Wan 2.2 TI2V 5B도 받아서 속도·품질 비교
3-1. **루프 영상 (비교용)**: LTX-2.5 (Lightricks, LTX-2 Community License: 연매출 $10M 미만 상업 이용 무료)
   - Hugging Face **게이트 모델**이라 라이선스 동의 + 로그인 필요 → 이 단계에서 멈추고 나에게 요청해.
   - 16GB용 **양자화 버전**(fp8/int8/GGUF)만 받아. 풀 정밀도는 32GB급이라 안 맞음.
   - ComfyUI 공식 템플릿 또는 `ComfyUI-LTXVideo`의 **FLF2V(First-Last-Frame)** 워크플로 사용.
4. **키 아트 이미지**: 상업 이용 가능한 라이선스의 모델 하나 (후보: Z-Image Turbo, Qwen-Image GGUF, SDXL 계열). FLUX.1 [dev]는 라이선스가 까다로우니 고르기 전에 나에게 물어봐.
5. **후처리**: 업스케일러 `4x-UltraSharp` 또는 `RealESRGAN_x4plus`, 프레임 보간용 커스텀 노드 `ComfyUI-Frame-Interpolation`(RIFE).
   - 커스텀 노드는 ComfyUI-Manager로 설치하고, 설치한 노드 목록을 보고해.

## 3. 스모크 테스트 (단계별로 한 번씩, 작은 설정으로)
각 테스트마다 **소요 시간, 최대 VRAM 사용량, 출력 파일 경로**를 기록해. OOM이 나면 해상도/길이/양자화를 낮춰 재시도하고, 어떤 설정에서 통과했는지 적어.
1. 음악: ACE-Step 1.5로 2분짜리 곡 3개
   프롬프트 예: `80s Korean city pop lofi, instrumental, Rhodes piano, warm tape saturation, mellow bass, soft drums, 75 BPM`
   같은 프롬프트로 Stable Audio 3.0도 3개.
2. 이미지: 1344×768 한 장
   프롬프트 예: `1980s Seoul alley at night, rain, neon hangul signs, warm window light, retro anime illustration, cozy, highly detailed`
3. 루프 영상: 2번 이미지를 **첫 프레임 = 마지막 프레임**으로 넣고 Wan 2.2 FLF2V로 3~5초 클립 (먼저 저해상도 480p로).
   같은 이미지·같은 모션 프롬프트로 LTX-2.5 FLF2V도 생성해서 비교 표 작성: 생성 시간, VRAM, 루프 이음새 자연스러움, 디테일 유지(간판 글자·빗줄기 뭉개짐), OOM 여부.
   LTX-2.5가 오디오도 같이 만들 수 있으면 빗소리 앰비언스도 한 번 뽑아봐.
4. 후처리: 3번 클립을 RIFE로 프레임 보간, 4x 업스케일 1회.
5. ffmpeg로 3번 클립을 1분으로 반복(`-stream_loop`) + 1번 음악 2곡 크로스페이드 합성 → `test_output/smoke_test.mp4`. 루프 이음새가 튀는지 확인해서 알려줘.

결과물은 이 저장소의 `test_output/`에 저장하되 **git에는 올리지 마** (`.gitignore`에 포함돼 있음).

## 4. 기록 (저장소에 커밋)
- `docs/reports/2026-11-24-setup-log.md`: 사전 점검 결과, 설치 경로, 버전, 겪은 문제와 해결법
- `config/models.yaml`: 받은 모델 목록 (이름, 파일명, 용량, ComfyUI 내 경로, 라이선스, 상업 이용 가능 여부, 출처 URL)
- `docs/experiments/2026-11-24-smoke-test.md`: 테스트별 설정, 시간, VRAM, 통과/실패, 소감
- 사용한 ComfyUI 워크플로는 **API 형식 JSON으로 내보내서** `workflows/` 아래 저장 (나중에 자동화 스크립트가 호출할 것)
- 모델 파일, 생성물, 토큰은 절대 커밋하지 마.

## 멈추고 물어볼 것
- 디스크 부족, 설치 위치 결정, 다운로드 목록 승인
- GPU 드라이버·CUDA 툴킷 등 **시스템 전체** 설치/변경
- Hugging Face 로그인이나 라이선스 동의가 필요한 모델 (토큰은 내가 직접 `hf auth login`으로 넣는다. 채팅에 붙여넣으라고 하지 마)
- 라이선스상 상업 이용이 불가하거나 애매한 모델
- 같은 오류로 두 번 실패했을 때

## 마지막 보고
1. 설치/다운로드 요약 표 (모델, 용량, 라이선스, 상업 이용 가능 여부)
2. 스모크 테스트 결과 표 (시간, VRAM, 통과 여부)
3. 음악 블라인드 테스트 준비: ACE-Step / Stable Audio 결과 6곡을 `test_output/blind/`에 `A1~A6` 같은 무작위 이름으로 복사하고, 정답표는 `test_output/blind/answer.txt`에 따로 저장
4. 다음 단계로 추천하는 것

---
