# 문서 안내

| 위치 | 내용 |
|---|---|
| [`PROJECT_REPORT.md`](PROJECT_REPORT.md) | **전체 작업 보고서** — 타임라인, 결과물, 파이프라인 구조, 모델 선택 근거, 운영 원칙, 남은 일 |
| [`reports/`](reports/) | 날짜별 작업 보고 (`YYYY-MM-DD-주제.md`) |
| [`experiments/`](experiments/) | 모델 비교·스모크 테스트·블라인드 청취 결과 |

## 작업 보고 (reports/)
| 날짜 | 문서 |
|---|---|
| 2026-11-24 | [로컬 셋업 로그](reports/2026-11-24-setup-log.md) — ComfyUI 설치, 모델 다운로드, 겪은 문제와 해결 |
| 2026-11-25 | [밤샘 로파이 작업](reports/2026-11-25-overnight-lofi.md) — 2시간 영상 5편, 음악·전환 품질, GPT 검수 |
| 2026-11-26 | [스토리 영상 밤샘 작업](reports/2026-11-26-story-night.md) — 야담·사연 6편, 표준 스토리 구성 과정 |
| 2026-11-26 | [주간 작업](reports/2026-11-26-day.md) — ep5c 개선, GPT 그림 + LoRA 수집, 모델 4종 결정, 비공개 업로드 |

## 실험 (experiments/)
| 날짜 | 문서 |
|---|---|
| 2026-11-24 | [스모크 테스트](experiments/2026-11-24-smoke-test.md) — 음악·이미지·영상 모델 11종, 음악 블라인드 |
| 2026-11-26 | [모델 비교](experiments/2026-11-26-model-ab.md) — MOSS-Image, Kandinsky 6, LTX Foley, ACE-Step XL SFT |

새 문서 규칙: 날짜별 작업은 `reports/`, 비교·측정은 `experiments/`, 파일명은 `YYYY-MM-DD-주제.md`. 생성물은 `test_output/`(git 제외)을 가리키기만 한다.
