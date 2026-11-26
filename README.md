# Ai-2 — 로컬 AI로 만드는 YouTube 영상 자동화

ComfyUI(로컬 RTX 5060 Ti 16GB)로 그림·영상·음악·목소리를 만들고, 스크립트로 합성·업로드 준비까지 자동화하는 프로젝트.

- **로파이 음악 채널** — 8090 레트로 서울 골목 루프 영상 + AI 음악 2시간 편성
- **야담·사연 스토리 영상** — 대본 → 인물·장면 그림 → 인물별 목소리 → 동작 클립 → 효과음·BGM → 자막 영상 (8분 상한)

전체 경과와 결정 근거: **[`docs/PROJECT_REPORT.md`](docs/PROJECT_REPORT.md)** · 문서 목록: [`docs/README.md`](docs/README.md)

## 폴더
- `prompts/` — Claude Code에 붙여넣을 작업 프롬프트 (`01-local-setup.md`부터)
- `docs/` — 전체 보고서, 날짜별 작업 보고(`reports/`), 모델 비교·시험(`experiments/`)
- `config/` — 모델 목록·라이선스(`models.yaml`), 로파이 테마, 목소리, 야담 그림체 기준(`style_bible_yadam.md`)
- `workflows/` — ComfyUI API 형식 워크플로 (스크립트가 호출)
- `scripts/` — 공통 도구(`ui_to_api.py`, `run_workflow.py`), 로파이(`build_long.py`, `theme_pipeline.py` 등), 스토리(`story_pipeline.py`와 `story_*.py`)
- `test_output/` — 생성물 (git 제외)

## 스토리 영상 한 편 만들기
```
python scripts/story_pipeline.py test_output/story/<편> --from chars --to preview
```
단계: 인물 → 장면 → GPT 핵심 그림 → 그림체 맞추기 → 검수 → LoRA 수집 → 목소리 → 낭독 → BGM → 효과음 → 동작 → Foley → 영상 → 썸네일 → 미리보기
