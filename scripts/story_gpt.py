"""GPT (codex exec, read-only) helpers for the story-video pipeline.

  python scripts/story_gpt.py ideate <out.md> [--brief "..."]
  python scripts/story_gpt.py review_script <story_dir>
  python scripts/story_gpt.py scene_qa <story_dir> [--only 3,7]
  python scripts/story_gpt.py review_video <story_dir> [--video name.mp4]

Outputs go to <story_dir>/review/. scene_qa writes scene_qa.json: [{"id", "text", "dup", "issue", "ok"}].
"""
import argparse, json, pathlib, re, subprocess, sys
from PIL import Image, ImageDraw, ImageFont

ROOT = pathlib.Path(__file__).resolve().parent.parent
FF = r"C:\AI\tools\ffmpeg\bin\ffmpeg.exe"
PD = ("당신은 50~60대 시청자 대상 한국 유튜브 '야담·옛날이야기·시니어 사연 오디오북' 채널의 수석 PD입니다. "
      "인기 영상 트렌드(최근 1년, 10만+ 조회 172개 분석): 평균 87분, 70~120분이 최다, 키워드 며느리·회장·남편·시어머니·재벌·"
      "정체·버려진·은혜, 제목은 '상황 + 의외의 행동 + 이유/정체' 구조, 태그 오디오북·감동사연·노후사연·야담. "
      "작은 채널도 100만+ 조회가 흔함. YouTube는 반복적 AI 양산 콘텐츠를 채널 단위로 수익화 제외하므로 독창성이 중요합니다.")


BENCH = ("경쟁 영상(최근 인기, 우리가 반드시 넘어야 할 기준): ① 조선야담록 '몰락한 아씨를 따라 도망친 머슴의 놀라운 정체' 58분 60만회 "
         "(누명·몰락·반쪽 손수건·숨겨진 정체) ② '가난한 집이라 거절한 언니 대신 시집간 서희, 첫날밤 신랑이 꺼낸 붉은 주머니' 55분 10만회 "
         "③ 억만금야담 '혼례날 소박 맞은 새색시를 데려온 떡집 할매, 하루아침에 벼락부자 되다' 102분 46만회 ④ 야담동화 '새댁, 사흘 안에 혼인을 "
         "파하고 이름을 지우시오' 94분 91만회(대사 인용형 제목). 공통점: 첫 장면이 대립의 클로즈업(뺨, 찢긴 손수건, 경고의 말), 억울한 "
         "약자 주인공, 숨겨진 정체/물건의 반쪽, 신분 역전과 통쾌한 응징, 가족·혼인 갈등, 따뜻한 보상.")
WRITE_SPEC = """요구사항(몰입도와 중독성 최우선):
- 길이(상한 8분, 사용자 규칙): 내레이션 총 3,000~3,300자(약 7~8분). 장면 16~18개, 장면당 2~5줄, 한 줄은 60자 이내.
- 도입(사용자 규칙, 반드시): 첫 세 문장 안에 '언제·어디서·누가·무슨 일'을 모두 말할 것. 그다음 갈등 대사 한마디와
  수수께끼는 단 하나만(그 수수께끼가 가리키는 시점·대상을 명시). 처음 듣는 사람이 첫 30초에 상황을 한 문장으로 요약할 수 있어야 함.
- 구조: 시간 순서대로(회상은 결말의 고백 한 번만). 한 장면에 새 정보 하나. 2~3분마다 작은 반전이나 새 의문.
  후반에 귀로 기억되는 소리·말·물건으로 비밀 회수. 통쾌한 응징 + 따뜻한 보상.
- 인물은 처음 등장할 때 관계를 붙여 소개(시어머니 복례, 시아주버니 무겸 등).
- 귀로만 들어도 따라갈 수 있게: 인물 4~5명, 이름은 서로 소리가 겹치지 않게, 시간표(며칠 뒤/몇 년 전)를 명확히, 증거와 인과를 대사로.
- 고증: 조선 후기, 상중 혼인 금지 등 기본 예법 지키기. 실존 인물 사용 금지. 유리 램프 같은 시대착오 금지.
- 문체: '~했습니다/~했지요' 이야기꾼 말투, 대사는 따옴표. 50~60대가 듣기 편한 쉬운 말.
- 각 장면에 그림 지시(영어 1~2문장, 등장인물 키, 구도: wide/medium/close-up 중 하나, 감정과 동작이 보이게)와 shot 목록 2개.
- 제목 후보 5개(대사 인용형 2개 포함, 45자 안팎, 끝에 '| 조선 야담'), 썸네일 문구 후보 3개(한 줄 12자 이내).
- 인물 외형 묘사(영어, 나이·얼굴·머리·옷)를 고정해 줄 것.
출력: 먼저 한국어로 3~5줄 기획 의도, 그다음 아래 형식의 JSON 하나를 ```json 코드블록으로:
{"titles":[...],"thumb_lines":[...],"logline":"...","characters":{"key":"english description",...},
 "scenes":[{"id":1,"chars":["key"],"shot":"close-up","image":"english scene description","shots":["english alt shot 1","english alt shot 2"],
 "lines":["...","..."]}, ...]}"""


def codex(prompt, images=()):
    # user (19:55): storylines/titles by gpt-6.2-sol at high reasoning (also the codex default; pinned here)
    args = ["codex.cmd" if sys.platform == "win32" else "codex", "exec", "--skip-git-repo-check", "-s", "read-only",
            "-m", "gpt-6.2-sol", "-c", "model_reasoning_effort=high"]
    for i in images:
        args += ["-i", str(i)]
    r = subprocess.run(args, input=prompt, capture_output=True, text=True, encoding="utf-8")
    out = r.stdout
    k = out.rfind("\ncodex\n")
    out = out[k + 7:] if k >= 0 else out
    k = out.rfind("\ntokens used")
    return (out[:k] if k >= 0 else out).strip()


def load(d):
    return json.load(open(pathlib.Path(d) / "story.json", encoding="utf-8-sig"))


def script_text(s):
    out = []
    for sc in s["scenes"]:
        out.append(f"[장면 {sc['id']}] " + " ".join(sc["lines"]))
    return "\n".join(out)


def contact(d, ids, path):
    f = ImageFont.truetype(r"C:\Windows\Fonts\malgunbd.ttf", 40)
    ims = [(i, Image.open(pathlib.Path(d) / "scenes" / f"s{i:02d}.png").convert("RGB").resize((640, 357))) for i in ids]
    cols = 3; rows = (len(ims) + cols - 1) // cols
    c = Image.new("RGB", (cols * 640, rows * 357), "black"); dr = ImageDraw.Draw(c)
    for k, (i, im) in enumerate(ims):
        x, y = (k % cols) * 640, (k // cols) * 357
        c.paste(im, (x, y)); dr.rectangle([x, y, x + 70, y + 50], fill="black"); dr.text((x + 8, y + 2), str(i), font=f, fill="yellow")
    c.save(path, quality=88)
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd"); ap.add_argument("target"); ap.add_argument("--brief", default="")
    ap.add_argument("--only", default=""); ap.add_argument("--video", default="")
    a = ap.parse_args()
    if a.brief.startswith("@"):   # --brief @file.md (PowerShell mangles quotes in long inline arguments)
        a.brief = pathlib.Path(a.brief[1:]).read_text(encoding="utf-8")

    if a.cmd == "ideate":
        p = (PD + "\n\n새 채널의 다음 에피소드 기획안이 필요합니다. " + a.brief +
             "\n\n로그라인 12개를 제안하세요: 조선 야담 8개, 현대 시니어 사연 4개. 각 항목에 (1) 가제(유튜브 제목 형식) "
             "(2) 3문장 줄거리(위기-단서-반전) (3) 귀로 기억되는 핵심 물건/말 한 가지 (4) 첫 30초 후킹 장면 "
             "(5) 독창성 위험(흔한 클리셰와 겹치는 점)을 쓰세요. 마지막에 야담 TOP2와 현대 사연 TOP1을 이유와 함께 고르고, "
             "마지막 줄은 정확히: PICK: yadam=<번호>,<번호> modern=<번호>")
        pathlib.Path(a.target).write_text(codex(p), encoding="utf-8")
        print("wrote", a.target)
        return

    if a.cmd == "write":   # GPT writes storyline + titles + full narration as story.json draft; Claude reviews it after
        d = pathlib.Path(a.target); d.mkdir(parents=True, exist_ok=True)
        p = (PD + "\n\n" + BENCH + "\n\n" + a.brief + "\n\n" + WRITE_SPEC)
        out = codex(p)
        (d / "gpt_draft.md").write_text(out, encoding="utf-8")
        m = re.search(r"```json\s*(\{.*\})\s*```", out, re.S) or re.search(r"(\{\s*\"titles\".*\})", out, re.S)
        if not m:
            print("NO JSON in GPT output; see gpt_draft.md"); return
        j = json.loads(m.group(1))
        (d / "gpt_draft.json").write_text(json.dumps(j, ensure_ascii=False, indent=1), encoding="utf-8")
        n = sum(len(l) for sc in j["scenes"] for l in sc["lines"])
        print(f"titles {len(j.get('titles', []))}, scenes {len(j['scenes'])}, chars {n} (~{n / 8.3 / 60:.1f} min)")
        return

    if a.cmd == "revise":   # GPT rewrites its draft from Claude's review notes (--brief = notes); same JSON + per-scene motion
        d = pathlib.Path(a.target)
        draft = (d / "gpt_draft.json").read_text(encoding="utf-8")
        p = (PD + "\n\n당신이 쓴 초안을 편집자(Claude)가 검수했습니다. 검수 의견을 모두 반영해 다시 쓰세요.\n\n[검수 의견]\n" + a.brief +
             "\n\n[초안 JSON]\n" + draft + "\n\n" + WRITE_SPEC +
             "\n추가: 각 장면에 \"motion\": [\"...\"] (영어 1문장, 그 장면 그림의 시작 상태에서 이어지는 인물의 구체적 동작과 표정, "
             "카메라 움직임. 대사 내용과 정확히 맞을 것)을 넣고, \"chars\"는 그림에 크게 나오는 인물 최대 2명만.")
        out = codex(p)
        (d / "gpt_rev.md").write_text(out, encoding="utf-8")
        m = re.search(r"```json\s*(\{.*\})\s*```", out, re.S)
        if not m:
            print("NO JSON; see gpt_rev.md"); return
        j = json.loads(m.group(1))
        (d / "gpt_rev.json").write_text(json.dumps(j, ensure_ascii=False, indent=1), encoding="utf-8")
        n = sum(len(l) for sc in j["scenes"] for l in sc["lines"])
        print(f"titles {len(j.get('titles', []))}, scenes {len(j['scenes'])}, chars {n}")
        return

    if a.cmd == "condense":   # shorten an existing story to the 8-min cap, reusing its scene images (--brief = rules)
        d = pathlib.Path(a.target); s = load(d)
        scenes = [{"id": sc["id"], "image": sc.get("image", "")[:160], "lines": sc["lines"]} for sc in s["scenes"]]
        out = codex(PD + "\n\n" + a.brief + "\n\n[기존 장면 JSON]\n" + json.dumps(scenes, ensure_ascii=False))
        (d / "condense.md").write_text(out, encoding="utf-8")
        m = re.search(r"```json\s*(\{.*\})\s*```", out, re.S)
        j = json.loads(m.group(1))
        (d / "condense.json").write_text(json.dumps(j, ensure_ascii=False, indent=1), encoding="utf-8")
        n = sum(len(l) for sc in j["scenes"] for l in sc["lines"])
        print(f"scenes {len(j['scenes'])}, chars {n} (~{n / 420:.1f} min)")
        return

    if a.cmd == "motion":   # per-scene I2V motion prompt from the scene's lines + its existing image (start state)
        d = pathlib.Path(a.target); s = load(d)
        res = {}
        for k in range(0, len(s["scenes"]), 9):
            chunk = [sc for sc in s["scenes"][k:k + 9] if (d / "scenes" / f"s{sc['id']:02d}.png").exists()]
            sheet = contact(d, [sc["id"] for sc in chunk], d / "review" / f"_mo_{k // 9}.jpg") if (d / "review").mkdir(exist_ok=True) is None else None
            p = ("첨부 이미지는 오디오북 영상의 장면들이고 왼쪽 위 노란 숫자가 장면 번호입니다. 각 장면을 이미지→동영상(5초)으로 움직이려 합니다. "
                 "장면마다 영어 1문장 motion 프롬프트를 쓰세요: 그 그림의 현재 상태에서 자연스럽게 이어지는 인물의 구체적 동작·표정 변화와 "
                 "카메라 움직임, 그리고 그 장면 대사/내레이션의 감정과 정확히 맞을 것. 그림에 없는 인물·물건을 새로 등장시키지 말 것. "
                 "JSON만 출력: {\"1\": \"...\", ...}\n\n" +
                 "\n".join(f"{sc['id']}: " + " ".join(sc["lines"]) for sc in chunk))
            out = codex(p, [sheet])
            m = re.search(r"\{.*\}", out, re.S)
            res.update(json.loads(m.group(0)) if m else {})
        for sc in s["scenes"]:
            if str(sc["id"]) in res:
                sc["motion"] = [res[str(sc["id"])]]
        json.dump(s, open(d / "story.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"motion prompts for {len(res)}/{len(s['scenes'])} scenes")
        return

    if a.cmd == "annotate":   # speakers per line + ambience/SFX prompt per scene + voice design per character
        d = pathlib.Path(a.target); s = load(d)
        p = ("아래 오디오북 대본의 각 장면에 대해 JSON만 출력하세요.\n"
             "1) speakers: 각 줄(lines와 같은 순서·같은 개수)을 누가 소리 내 말하는지. 따옴표 대사는 그 대사를 하는 인물 키, "
             "나머지(서술, 소리 묘사)는 \"narrator\". 한 줄에 서술과 대사가 섞이면 대사 주인 키.\n"
             "2) sfx: 그 장면 배경에 깔 환경음·효과음 설명(영어, Stable Audio 프롬프트용 1문장, 음악·목소리 금지. 예: 'gentle rain on a "
             "thatched roof, distant thunder, no music, no voices').\n"
             "3) voices: 인물별 목소리 설계(한국어 1문장: 나이·성별·음색·말투). narrator 제외.\n"
             f"인물 키: {list(s['characters'])}\n형식: {{\"voices\":{{\"key\":\"...\"}},\"scenes\":[{{\"id\":1,\"speakers\":[...],\"sfx\":\"...\"}}]}}\n\n"
             + json.dumps([{"id": sc["id"], "lines": sc["lines"]} for sc in s["scenes"]], ensure_ascii=False))
        out = codex(p)
        m = re.search(r"\{.*\}", out, re.S)
        j = json.loads(m.group(0))
        (d / "annotate.json").write_text(json.dumps(j, ensure_ascii=False, indent=1), encoding="utf-8")
        bad = [x["id"] for x, sc in zip(j["scenes"], s["scenes"]) if len(x["speakers"]) != len(sc["lines"])]
        print(f"voices {list(j['voices'])}, scenes {len(j['scenes'])}, speaker-count mismatches {bad}")
        return

    d = pathlib.Path(a.target); (d / "review").mkdir(exist_ok=True); s = load(d)

    if a.cmd == "review_script":
        p = (PD + "\n\n녹음 전 대본 검수입니다. 화면 없이 귀로만 들어도 따라갈 수 있어야 합니다.\n\n[제목] " + s["title"] +
             "\n[대본]\n" + script_text(s) +
             "\n\n한국어로 냉정하게: 1) 첫 30초 후킹 2) 시간표·인과·증거의 빈틈(누가 언제 무엇을 알았나) 3) 감정선과 반전 "
             "4) 어색하거나 50~60대에게 낯선 문장 → 수정안 표 5) 고증 오류 6) 반드시 고칠 TOP5(구체적 문장 단위). "
             "마지막 줄은 정확히: SCORES: hook=<n> story=<n> clarity=<n>")
        out = codex(p); (d / "review" / "script_review.md").write_text(out, encoding="utf-8")
        print(out.strip().splitlines()[-1] if out.strip() else "?")

    elif a.cmd == "scene_qa":
        ids = [int(x) for x in a.only.split(",") if x] or [sc["id"] for sc in s["scenes"] if (d / "scenes" / f"s{sc['id']:02d}.png").exists()]
        res = []
        for k in range(0, len(ids), 9):
            chunk = ids[k:k + 9]
            sheet = contact(d, chunk, d / "review" / f"_qa_{k // 9}.jpg")
            desc = "\n".join(f"{sc['id']}: {sc.get('image', '(재사용 장면) ' + ' '.join(sc['lines'])[:120])}"
                             for sc in s["scenes"] if sc["id"] in chunk)
            p = ("첨부 이미지는 조선/한국 배경 웹툰풍 영상의 장면들이며 왼쪽 위 노란 숫자가 장면 번호입니다. 각 장면의 의도:\n" + desc +
                 "\n\n장면마다 검사하세요: text=간판·종이·현판 등에 글자/가짜 글자가 보이나, dup=같은 인물이 한 화면에 두 번 그려졌나, "
                 "issue=의도와 다른 점/시대에 안 맞는 물건(유리 램프 등)/신체 기형/인원 오류(없으면 빈 문자열), "
                 "severe=시청자가 휴대폰 화면에서 바로 알아챌 정도로 심각한가(신체 기형, 시대착오 물건이 크게 보임, 내레이션과 정반대의 "
                 "상황, 주인공 얼굴이 딴사람). 소품 위치·시선 방향·구도 취향 같은 사소한 차이는 severe=false. "
                 "설명 없이 JSON 배열만 출력: [{\"id\":1,\"text\":false,\"dup\":false,\"severe\":false,\"issue\":\"\"}, ...]")
            out = codex(p, [sheet])
            m = re.search(r"\[.*\]", out, re.S)
            try:
                res += json.loads(m.group(0)) if m else []
            except json.JSONDecodeError:
                print("QA parse failed:", out[-300:])
        for r in res:   # minor issues are logged but not auto-fixed
            r["ok"] = not (r.get("text") or r.get("dup") or r.get("severe"))
        json.dump(res, open(d / "review" / "scene_qa.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(json.dumps([r for r in res if not r["ok"]], ensure_ascii=False))

    elif a.cmd == "review_video":
        v = d / (a.video or f"{d.name}.mp4")
        tl = json.load(open(d / "timeline.json", encoding="utf-8"))
        total = tl[-1]["end"]
        frames = []
        for i, t in enumerate([3, total * 0.1, total * 0.3, total * 0.5, total * 0.7, total * 0.9]):
            p = d / "review" / f"f{i}.jpg"
            subprocess.run([FF, "-v", "error", "-y", "-ss", f"{t:.1f}", "-i", str(v), "-frames:v", "1", "-vf", "scale=960:-1", str(p)], check=True)
            frames.append(p)
        th = d / "thumb.jpg"
        up = (d / "upload.md").read_text(encoding="utf-8") if (d / "upload.md").exists() else ""
        p = (PD + f"\n\n완성 영상({total / 60:.1f}분) 검수입니다. 첨부: 영상 프레임 6장" + (" + 썸네일(마지막 이미지)" if th.exists() else "") +
             ".\n[대본]\n" + script_text(s) + "\n[업로드 정보]\n" + up +
             "\n\n한국어로 냉정하게: 1) 첫 30초 이탈 위험 2) 이야기 완성도 3) 화면(그림체 일관성·장면 일치·자막 가독성) "
             "4) 썸네일·제목 클릭 유도력과 대안 2개 5) 업로드 전 꼭 고칠 TOP3(구체적으로). "
             "마지막 줄은 정확히: SCORES: hook=<n> story=<n> visual=<n> thumb=<n>")
        out = codex(p, frames + ([th] if th.exists() else []))
        (d / "review" / "video_review.md").write_text(out, encoding="utf-8")
        print(out.strip().splitlines()[-1] if out.strip() else "?")


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
