# 스토리 영상 워크플로 — 동작 클립 규칙

`scripts/story_pipeline.py`의 단계 순서와 파일은 [`PROJECT_REPORT.md` §3](PROJECT_REPORT.md#3-파이프라인-구조)에 있다.
이 문서는 동작 클립(`motion` 단계, `scripts/story_motion.py`)을 만들 때 지킬 규칙이다. 결함이 나오면 원인과 대처를 여기에 더한다.

---

## 1. 얼굴이 일그러지는 문제 (2026-11-27, ep5c)

### 증상
초반 클립 5개에서 표정이 상황과 맞지 않게 바뀌고 얼굴이 뭉개졌다.

| 클립 | 영상 위치 | 증상 |
|---|---|---|
| s02_1 | 0:34 | 카메라가 얼굴 클로즈업까지 파고들고, 표정이 찌푸려지거나 비웃는 얼굴이 됨 |
| s02_3 | 0:48 | 웃음이 사라져야 할 장면에서 오히려 과장된 웃음이 먼저 나옴 |
| s04_2 | 1:28 | 입을 크게 벌리고 눈이 튀어나오는 만화식 놀란 얼굴 |
| s04_3 | 1:34 | 고개가 뒤통수 쪽으로 돌았다가 다시 돌아옴 |
| s05_3 | 1:58 | 소리치는 얼굴로 순간 뭉개짐 |

### 원인
1. **표정을 바꾸라는 동작 지시.** 장면 `"beats"`에 "eyes widen", "smiles fade", "face goes pale", "speaks urgently"를 썼다.
   LTX는 표정 변화를 크게 과장하고, 처음 얼굴과 끝 얼굴 사이를 이으면서 얼굴을 변형시킨다.
2. **과장된 끝 그림.** 이어 붙이는 클립의 끝 그림은 Qwen-Edit가 beat의 `"end"` 문장대로 그린다.
   "eyes wide with shock"을 주자 입을 크게 벌리고 눈이 튀어나온 만화 표정을 그렸고, LTX는 그 그림에 도달하려고 얼굴을 바꿨다.
3. **머리 방향이 다른 첫·끝 프레임.** s04_2는 앞 클립 끝에서 칠복이 고개를 돌려 뒤통수가 보이는 상태로 시작했고, 끝 그림은 정면에 가까운 얼굴이었다.
   LTX가 그 사이 얼굴을 새로 지어내면서 뭉개졌다.
4. **지시 없는 기본 확대.** 장면에 `"motion"`이 없으면 기본 지시 "slow camera push-in"이 쓰인다.
   s02_1에서는 이것이 얼굴 클로즈업까지 과하게 들어가면서 표정도 함께 바뀌었다.
5. **검수 간격.** 6프레임 띠는 5초 클립에서 1초 간격이라 0.5초 안에 지나가는 눈·입 결함을 놓쳤다.

### 뭉개지지 않게 하는 방법

**동작 지시(`motion`, `beats[].motion`)**
- 표정을 *바꾸라는* 말을 쓰지 않는다. 쓰지 말 것: eyes widen, smile fades, face goes pale, shocked, screams, speaks urgently.
- 대신 작은 변화로 쓴다: "brows tighten slightly, mouth closed", "faces slowly become quiet and serious", "lips moving only slightly".
- 머리 방향을 한 클립 안에서 크게 바꾸지 않는다(옆얼굴이면 옆얼굴 유지). 뒤통수 → 얼굴로 도는 동작 금지.
- 카메라는 "static camera" 또는 "nearly static camera"로 쓴다. 확대가 필요하면 배경·소품 쪽으로만 쓴다.
- 장면마다 `"motion"`을 직접 쓴다. 기본값에 맡기지 않는다.

**끝 그림(`beats[].end`)**
- 처음 그림과 같은 머리 방향, 같은 구도, 조용한 표정으로 쓴다. 예: "in the same profile, brows slightly furrowed, mouth closed, tense".
- 끝 그림을 만든 뒤 LTX를 돌리기 전에 눈으로 확인한다(`--keyframes-only`로 먼저 만들고 `/free` 후 LTX).

**코드에 들어간 것 (`story_motion.py`)**
| 항목 | 내용 |
|---|---|
| 금지어 `LTX_NEG_ADD` | distorted face, morphing face, rolling eyes, crossed eyes, bulging eyes, exaggerated expression, grimace, gaping mouth, head spinning, sudden zoom |
| 공통 꼬리 `TAIL` | "faces stay stable with calm, subtle expressions" |
| 끝 그림 지시 `EDIT_KEEP` | "Keep facial expressions subtle and natural, no exaggerated cartoon expression (no gaping mouth, no bulging eyes)" |
| 기본 동작 | "slow camera push-in" → "nearly static camera" |
| 장면 `"seed_offset"` | 그 장면 모든 클립의 시드를 옮김. 시드가 장면 번호로 고정이라, 같은 지시로 다시 돌리면 같은 결함이 나온다 |
| 장면 `"anchor_end": true` | 장면 클립의 끝 프레임도 같은 그림으로 고정(강도 0.8). 확대·웃음이 점점 커지는 클립에 쓴다 |

**검수**
- 얼굴이 나오는 클립은 얼굴 부분만 잘라 5~6프레임 간격(클립당 약 24장)으로 띠를 만들어 본다.
- 볼 것: 눈동자 위치가 튀는지, 입이 갑자기 열리는지, 머리가 도는지, 확대가 얼굴을 자르는지, 표정이 대사와 맞는지.

**고칠 때 순서**
1. 지시와 끝 그림을 위 규칙대로 고친다. `"seed_offset"`을 준다.
2. 이어 붙이는 클립은 사슬 구조다(다음 클립의 첫 프레임 = 앞 클립 마지막 프레임). 장면의 앞 클립을 바꾸면 그 뒤 클립을 모두 지우고 순서대로 다시 만든다.
3. 다시 만들어도 확대·표정이 흘러가면 `"anchor_end": true`.
4. 그래도 결함이면 그 클립을 뺀다(장면 클립 수를 줄임). 클립이 슬롯보다 짧으면 story_video가 0.5배 재생과 느린 확대로 채운다.

### ep5c 적용 결과
- s02: `motion` 직접 지정, 둘째 beat 문구 완화, `anchor_end`, `seed_offset` 200. 1차(끝 고정 없음)에서도 웃음이 커져 2차에서 해결.
- s04: `motion` 직접 지정, 첫 beat를 옆얼굴 유지·입 다문 표정으로, 셋째 클립(s04_3) 삭제. `seed_offset` 100.
- s05: 셋째 beat를 "낮은 목소리, 입술만 조금" + 조용한 끝 그림. `seed_offset` 100.
- 클립 9개 재생성(LTX 클립당 66~215초), 끝 그림 2장(Qwen-Edit 약 3분), 영상 7:15로 재렌더.
- 비교: `test_output/story/yadam_ep5c/review/facefix_compare.jpg`, 미리보기 `review/facefix_0030-0215.mp4`. 이전 영상 `_backup_v1/yadam_ep5c_before_facefix.mp4`.
