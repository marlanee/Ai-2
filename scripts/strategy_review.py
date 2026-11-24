"""YouTube strategy discussion with GPT (Codex CLI) about a finished output.

Round 1:  python scripts/strategy_review.py round1 <name> --images thumb.jpg frame.png --brief brief.md
Round 2:  python scripts/strategy_review.py round2 <name> --reply my_reply.md      (GPT sees round 1 + my reply)
Files go to test_output/strategy/<name>_round{1,2}.md
"""
import argparse, pathlib, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "test_output" / "strategy"

R1 = """You are a YouTube growth strategist for long-form lofi / ambient music channels (study, work, sleep).
Below is the brief of a finished video and its thumbnail/frame images. Discuss in Korean, concretely and honestly.

{brief}

Answer with:
1. 첫인상: 이 썸네일·제목이 피드에서 클릭될지 (CTR 관점), 무엇이 약한지.
2. 시청 지속(AVD/retention): 2시간 영상에서 사람들이 이탈하는 지점과 이유, 막을 구체적 방법 (영상·음악·구성).
3. 재방문·구독: 이 채널을 '매일 다시 트는 채널'로 만들 시리즈 설계, 업로드 주기, 길이, 세계관/브랜딩.
4. 퀄리티: 제작물에서 당장 고칠 3가지 (우선순위).
5. 실험 설계: 다음 2주 동안 A/B로 검증할 가설 3개 (측정 지표 포함).
6. 우리 파이프라인(로컬 생성: 이미지 Qwen-Image, 루프 영상 LTX 5초 루프, 음악 Stable Audio/MiniMax, ffmpeg 합성)으로
   자동화할 수 있는 것과 없는 것을 구분해서 제안.
Be specific (numbers, examples). No generic advice."""

R2 = """Continue the discussion. Here is your previous answer and the producer's reply (feasibility, disagreements,
data). Answer in Korean:
- 동의/반박: 상대 의견 중 틀렸거나 과한 부분은 이유와 함께 반박.
- 최종 합의 액션 리스트: 우선순위 순서로 최대 8개, 각 항목에 '자동화 가능/수동', '예상 효과(지표)', '난이도'.
- 다음 영상 1편의 구체적 스펙 (제목 2안, 썸네일 콘셉트, 길이, 구성 타임라인, 음악 흐름).

=== YOUR ROUND 1 ===
{r1}

=== PRODUCER REPLY ===
{reply}"""


def codex(prompt, images=()):
    args = ["codex.cmd", "exec", "--skip-git-repo-check", "-s", "read-only"]
    for i in images:
        args += ["-i", str(i)]
    r = subprocess.run(args, input=prompt, capture_output=True, text=True, encoding="utf-8")
    # codex prints the clean final message on stdout after the "tokens used" footer (stderr has the transcript);
    # fall back to everything after the last "codex" marker.
    lines = r.stdout.splitlines()
    if "tokens used" in lines:
        j = len(lines) - 1 - lines[::-1].index("tokens used")
        tail = lines[j + 2:]
        if sum(len(l) for l in tail) > 200:
            return "\n".join(tail).strip()
    if "codex" in lines:
        i = len(lines) - 1 - lines[::-1].index("codex")
        return "\n".join(l for l in lines[i + 1:] if not l.startswith(("hook:", "tokens used"))).strip()
    return r.stdout.strip() or r.stderr[-3000:]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("round", choices=["round1", "round2"]); ap.add_argument("name")
    ap.add_argument("--images", nargs="*", default=[]); ap.add_argument("--brief"); ap.add_argument("--reply")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if a.round == "round1":
        txt = codex(R1.format(brief=pathlib.Path(a.brief).read_text(encoding="utf-8")), a.images)
        p = OUT / f"{a.name}_round1.md"
    else:
        r1 = (OUT / f"{a.name}_round1.md").read_text(encoding="utf-8")
        txt = codex(R2.format(r1=r1, reply=pathlib.Path(a.reply).read_text(encoding="utf-8")))
        p = OUT / f"{a.name}_round2.md"
    p.write_text(txt, encoding="utf-8")
    print(txt)
    print("->", p)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
