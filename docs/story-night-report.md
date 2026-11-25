# 50~60대 스토리 영상 — 밤샘 작업 보고 (2026-11-25 18:00 → 2026-11-26 07:30)

## 한 줄 요약
야담·사연 영상 6편(8분 상한 기준 5편 + 22분 대표작 원본)을 만들었고, **GPT가 쓰고 Claude가 첫 청취자 입장에서 검수하는**
스토리 구성 과정을 표준으로 확정했습니다. 모든 장면이 이야기에 맞게 움직이고(LTX 동작 클립), 인물마다 목소리가 다르며, 장면별 효과음이 깔립니다.

## 결과물 (test_output/story/, git 제외)
| 편 | 폴더 | 길이 | 특징 |
|---|---|---|---|
| 1편 국밥과 짚신 v2 | yadam_ep1_v2 | 6:12 | 정지 그림(초기 버전) |
| 2편 빈 상여를 멘 딸 | yadam_ep2 | 8:06 | GPT 대본·완성본 검수 반영, 동작 클립 24 |
| 3편 딱, 딱, 끌 (현대 사연) | saveon_ep1 | 6:36 | 현대 웹툰체, 동작 클립 20 |
| 4편 그 문을 닫은 건 접니다 | yadam_ep4 | 22:48 | GPT 집필 대표작 원본, 동작 클립 80, 인물 목소리 5, 효과음 40 |
| **4편 8분판** | yadam_ep4_8min | 8:06 | 도입 재작성(사용자 지적 반영), 그림·클립 재사용 |
| **5편 덫을 거둔 포수** | yadam_ep5 | 8:06 | 승인된 구성 과정 첫 적용, 동작 클립 18, 목소리 5, 효과음 18 |

각 폴더: 원본 mp4(1080p), _preview.mp4(휴대폰용), thumb.jpg, .srt, upload.md(제목·설명·목차·태그, 1·2·3·4편).

## 표준 스토리 구성 과정 (사용자 승인)
1. GPT(gpt-6.2-sol, high)가 `story_gpt.py write`로 대본·제목 작성 (8분 상한, 도입 규칙 내장)
2. Claude가 처음 듣는 청자로 검수: 첫 세 문장에 언제·어디서·누가·무엇 / 수수께끼 하나 / 시간 순서 / 장면당 새 정보 하나 / 관계 붙인 인물 소개
3. GPT가 `revise`·`condense`로 수정 → Claude 재검수 → 제작

## 파이프라인 (scripts/)
- story_gpt.py — ideate / write / revise / condense / review_script / annotate / motion / scene_qa / review_video
- story_pipeline.py — chars → scenes → qa(+검증) → voices → tts → bgm → sfx → motion → video → thumb → preview → review
- story_images.py — 인물 시트(상반신), 장면(1~2인 참조 / 복잡한 동선은 텍스트 전용), 추가 샷, 연속성 표(continuity)
- story_motion.py — LTX-2.5 이미지→동영상 (640×352, 5초, 클립당 약 1.8분)
- story_voices.py / story_tts.py — 인물별 목소리 설계·복제, 화자별 낭독
- story_video.py — 동작 클립 재생, 한 줄 자막, 대사 색 구분, BGM 덕킹, 장면 효과음, SRT
- story_thumbnail.py, story_channel_art.py

## 그림 품질 — 무엇을 배웠나
- **GPT 이미지(baoyu-comic 스킬의 codex-imagegen)가 로컬 Qwen보다 확실히 좋음**: 동선·관계를 정확히 그림, 얼굴이 참조와 일치, 가짜 글자 없음.
  이유: 로컬은 16GB에 맞춘 fp8/int8 압축 + Lightning 4단계 고속 모드. 대가: 장당 약 2.5분, codex 구독 한도 소모(이번에 03:57 한도 도달, 07:07 해제).
- 로컬 개선책: 인물 참조는 상반신, 복잡한 장면은 텍스트 초안 → 참조 편집(실험 A 채택), 겨울/소품 연속성 명시.
- **LoRA 시험**: musubi-tuner로 Qwen-Image-2512 스타일 LoRA 학습 성공(68장, 16GB에서 에폭당 약 9분). v1(3에폭)과 v2(+4에폭, lr 2e-4) 모두 효과가 작음(선이 약간 정돈되는 수준, 구도·얼굴 거의 동일). 원인 추정: 학습 이미지 대부분이 같은 로컬 모델이 그린 것이라 새로 배울 그림체가 적음 → GPT 이미지 승인 컷 위주로 데이터를 다시 모아야 의미가 있음. 비교: test_output/story/lora_ab/_ab.jpg, _ab_v2.jpg

## 정직한 한계
- 4편 원본 도입은 GPT가 쓰고 Claude가 통과시킨 검수 실패 → 8분판으로 재작성.
- 5편 그림 대부분과 화자 표시는 GPT 한도 때문에 로컬·Claude가 대신함. 5편 GPT 완성본 검수는 아직 못 함.
- 업로드·채널 생성은 하지 않음(사용자 결정 대기).

## 다음 단계 제안
1. 새 채널 개설(이름 후보: 밤마실 야담 / 처마 밑 야담) 후 4편 8분판·5편부터 업로드
2. 핵심 장면·썸네일은 GPT 이미지, 나머지는 로컬 — GPT 한도에 맞춰 편당 장수 배분
3. GPT 이미지 승인 컷을 모아 LoRA 데이터를 늘려 재학습
