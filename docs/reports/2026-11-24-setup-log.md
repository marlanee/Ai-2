# 로컬 셋업 로그 (2026-11-24)

`prompts/01-local-setup.md` 기준으로 진행한 기록.

## 0. 사전 점검

| 항목 | 결과 | 판정 |
|---|---|---|
| OS | Windows 11 Enterprise 10.0.26200 | - |
| GPU | NVIDIA GeForce RTX 5060 Ti, 16,311 MiB, compute capability 12.0 (sm_120) | - |
| 드라이버 / CUDA | 610.88 / CUDA UMD 13.3 | Blackwell 지원, 업데이트 불필요 |
| 시스템 RAM | 63.6 GB | - |
| C: 남은 용량 | 689.5 GB / 930.4 GB | 필요량 120GB 이상 → 통과 |
| git | 2.54.0.windows.1 | 설치됨 |
| Python (시스템) | 3.12.10 | 설치됨 (ComfyUI는 포터블 내장 Python 사용) |
| ffmpeg | 없음 | 포터블로 설치 (아래) |

## 1. 설치 경로와 버전

| 구성 | 경로 / 버전 |
|---|---|
| ComfyUI 포터블 (NVIDIA) | `C:\AI\ComfyUI` — v0.46.0 (GitHub Releases `ComfyUI_windows_portable_nvidia.7z`) |
| 내장 Python | 3.13.14 (`C:\AI\ComfyUI\python_embeded`) |
| PyTorch | 2.14.1+cu130 (CUDA 13.0 빌드, 요구치 12.8 이상 충족) |
| 프런트엔드 / 템플릿 | comfyui-frontend-package 1.59.6 / comfyui-workflow-templates 0.11.111 |
| ComfyUI-Manager | 4.2.2 (포터블에 pip 패키지로 기본 포함, `--enable-manager`로 활성화) |
| ffmpeg | 9.1 essentials (gyan.dev), `C:\AI\tools\ffmpeg\bin` — 시스템 PATH 변경 없음 |
| 모델 | `C:\AI\ComfyUI\ComfyUI\models` 아래 약 97.9GB (목록은 `config/models.yaml`) |

PyTorch 확인 결과:

```
2.14.1+cu130 13.0 True NVIDIA GeForce RTX 5060 Ti ['sm_75', 'sm_80', 'sm_86', 'sm_90', 'sm_100', 'sm_120']
```
→ `is_available=True`, `sm_120` 포함 → 통과.

### 실행 방법

`C:\AI\ComfyUI\run_local.bat` (저장소 사본: `scripts/run_comfyui_local.bat`)

```
python_embeded\python.exe -s ComfyUI\main.py --windows-standalone-build --listen 127.0.0.1 --port 8188 --enable-manager
```

- `127.0.0.1`에만 바인딩. 외부 포트 개방 없음. `http://127.0.0.1:8188/system_stats` 응답 확인.

### 커스텀 노드

설치한 커스텀 노드 없음. 프레임 보간은 ComfyUI 0.46 내장 노드(`FrameInterpolationModelLoader`, `FrameInterpolate`)와 공식 safetensors RIFE 모델로 처리했다.
`ComfyUI-Frame-Interpolation` 커스텀 노드는 모델을 `.pth`(pickle)로 받기 때문에 사용하지 않았다(사용자 승인).

## 2. 모델 다운로드

- 저장소 이름과 파일명은 ComfyUI 내장 템플릿 JSON(`comfyui_workflow_templates_json/templates/*.json`)의 `models[].url`에서 추출했다.
- 전부 `.safetensors`. `scripts/download_models.py`(curl 이어받기, 크기 검증)로 받았다. 평균 속도는 약 35~57MB/s.
- 라이선스는 각 원문을 열어 확인했다. 요약은 `config/models.yaml`.
- 사용자 결정 사항:
  - 로파이 LoRA(라이선스 표기 없음)도 받음 → 상업 이용 전에 제작자 확인 필요
  - 업스케일러: 4x-UltraSharp(CC BY-NC-SA, 비상업) 대신 RealESRGAN_x4plus(BSD-3)
  - 프레임 보간: 내장 RIFE 노드
- **LTX-2.5** (게이트 모델): 사용자가 HF에서 라이선스에 동의하고, 별도 PowerShell 창에서 `hf auth login`을 실행했다. 그 뒤 `hf download Lightricks/LTX-2.5 <파일...> --local-dir C:\AI\ComfyUI\ComfyUI\models`로 받았다(약 41GB). 저장소 폴더 구조가 ComfyUI `models` 하위 폴더 이름과 같아서 그대로 맞는 위치에 들어간다. `models\.cache\huggingface`에 메타데이터만 남는다.

## 3. 겪은 문제와 해결

| 문제 | 원인 | 해결 |
|---|---|---|
| 템플릿은 UI 형식이라 API로 바로 실행 불가 | ComfyUI 템플릿은 litegraph UI JSON | `scripts/ui_to_api.py` 작성. `/object_info`로 widgets_values를 입력 이름에 매핑하고 서브그래프·PrimitiveNode·바이패스를 펼침 |
| `SaveAudioAdvanced.execute() missing 'format'` | `format`이 `COMFY_DYNAMICCOMBO_V3` 타입. API에서는 `format` + `format.quality`로 나뉨 | 변환기에 동적 콤보 하위 위젯 처리 추가 |
| Wan FLF2V 템플릿의 기본 경로가 20스텝 | LightX2V 4스텝 경로는 바이패스 상태로 들어 있음 | 두 경로의 mode를 뒤집은 4스텝 변형을 만들어 사용 (`workflows/video_wan22_flf2v_14b_4step_api.json`) |
| Wan 5B 템플릿에서 시작 이미지 노드가 꺼져 있음 | 템플릿 기본값이 T2V | API JSON에 `LoadImage`를 추가해 `start_image`에 연결 |
| `hf auth login` 2회 실패 (`Invalid user token`, `Bad request`) | 앱 내장 터미널에서 숨김 입력에 붙여넣을 때 토큰이 깨진 것으로 추정 | `Start-Process powershell`로 띄운 별도 창에서 성공 |
| LTX 템플릿 변환 시 로더에 엉뚱한 값(`VAELoader vae_name=24` 등) | 서브그래프 바깥 노드의 promoted widget 값 순서가 입력 순서와 다름 | 바깥에서 연결되지 않은 입력은 안쪽 노드의 위젯 값을 쓰도록 변경 |
| `LTXVEmptyLatentAudio` batch_size=25 → 텐서 크기 오류 | `frame_rate` 타입이 `"FLOAT,INT"`(widgetType으로 위젯 표시)라 위젯으로 인식하지 못함 | `widgetType` 옵션도 위젯으로 인식하도록 수정. 기존 워크플로는 다시 변환해 결과가 같은지 확인 |
| ffprobe 경로 계산 버그 (`ffmpeg\bin\ffmpeg.exe` 전체 치환) | 문자열 replace가 폴더 이름까지 바꿈 | 파일 이름만 치환하도록 수정 |
| Python `-I` 실행 시 콘솔 cp949 인코딩 오류 | `-I`가 `PYTHONIOENCODING`을 무시 | `sys.stdout.reconfigure(encoding="utf-8")` |

## 4. 저장소에 추가한 것

- `scripts/ui_to_api.py` — 템플릿(UI) → API JSON 변환
- `scripts/run_workflow.py` — API JSON 실행 + 시간·최대 VRAM·출력 경로를 `test_output/runs.jsonl`에 기록
- `scripts/compose.py` — 루프 이음새 크로스페이드 + `-stream_loop` + 음악 크로스페이드 + 라우드니스 정규화
- `scripts/loop_check.py` — 루프 이음새 수치 점검
- `scripts/download_models.py`, `scripts/run_comfyui_local.bat`
- `workflows/*_api.json` — 스모크 테스트에 실제로 쓴 API 형식 워크플로
