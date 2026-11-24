# Ai-2 — YouTube 음악 채널 자동화 (한국 8090 레트로 로파이)

ComfyUI(로컬 RTX 5060 Ti 16GB)로 루프 영상과 AI 음악을 만들고, 스크립트로 합성·업로드까지 자동화하는 프로젝트.

- `prompts/` — Claude Code에 붙여넣을 작업 프롬프트 (`01-local-setup.md`부터)
- `docs/` — 셋업 로그(`setup-log.md`), 스모크 테스트 결과(`smoke-test.md`)
- `config/models.yaml` — 받은 모델 목록, 경로, 라이선스, 상업 이용 가능 여부
- `workflows/` — ComfyUI API 형식 워크플로 (자동화 스크립트가 호출)
- `scripts/` — 템플릿 변환(`ui_to_api.py`), 실행·측정(`run_workflow.py`), 합성(`compose.py`), 루프 점검(`loop_check.py`)
