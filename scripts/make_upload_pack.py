"""Build test_output/upload_pack/<NN_name>/ {title.txt, title_en.txt, description.txt, tags.txt, thumbnail.jpg}
from each video's .youtube.md, applying the GPT pre-upload review fixes (test_output/upload_pack/gpt_final_review.md)."""
import json, pathlib, re, shutil

ROOT = pathlib.Path(__file__).resolve().parent.parent
T = ROOT / "test_output"
OUT = T / "upload_pack"
SEOUL_TAGS = ("lofi, city pop, korean city pop, 시티팝, 로파이, 80s, 레트로, 서울, 비 오는 날, 공부 음악, 작업 음악, "
              "playlist, 플레이리스트, rain, study music, Night Alley Records")
KO_CREDIT = "음악은 MiniMax-Music3와 Stable Audio 3.0 (Powered by Stability AI)로 생성했으며, Night Alley Records가 곡을 선별하고 믹싱했습니다."
KO_AI = "이 영상의 음악·영상·그림은 AI로 생성했습니다. 곡 선별·편성·전환·환경음 믹스는 Night Alley Records가 직접 편집했습니다."
EN_AI = ("The music, visuals and artwork were AI-generated. Night Alley Records selected and sequenced the tracks, "
         "edited the transitions, and mixed the ambience.")
th = json.load(open(ROOT / "config/themes.json", encoding="utf-8"))
V = [
    dict(key="01_seoul_ep1", md=T / "release/long_2h_final_v3.youtube.md", thumb=T / "release/thumb_title_A.jpg", lang="ko",
         title="[Playlist] 비 오는 밤, 80년대 서울 레코드 가게 앞에서 🌧 시티팝 로파이 2시간 | 공부·작업할 때",
         title_en="80's Seoul Lofi City ☔ Rainy Record Shop City Pop to Study / Relax 🎧 2 Hours",
         intro=["80년대 서울을 모티브로 만든 가상의 레코드 가게 골목에서 듣는 시티팝 로파이.",
                "공부·작업·휴식할 때 틀어 두세요. 🌧️☕  |  서울 골목 라디오 1편"], tags=SEOUL_TAGS + ", 레코드 가게"),
    dict(key="02_seoul_ep2", md=T / "themes/seoul_ep2/long_2h_ep2.youtube.md", thumb=T / "themes/seoul_ep2/thumb_ep2_v2.jpg", lang="ko",
         title="[Playlist] 비 오는 다방 창가에 앉아 ☕ 80년대 서울 시티팝 로파이 2시간 | 공부·작업할 때",
         title_en="80's Seoul Lofi Café ☕ Rainy Window City Pop to Study / Relax 🌧 2 Hours",
         intro=["80년대 서울을 모티브로 만든 가상의 다방 창가에서 듣는 시티팝 로파이.",
                "공부·작업·휴식할 때 틀어 두세요.  |  서울 골목 라디오 2편"], tags=SEOUL_TAGS + ", 다방, 카페"),
    dict(key="03_seoul_ep3", md=T / "themes/seoul_ep3/long_2h_ep3.youtube.md", thumb=T / "themes/seoul_ep3/thumb_ep3.jpg", lang="ko",
         title="[Playlist] 막차가 떠난 비 오는 정류장 🚏 80년대 서울 시티팝 로파이 2시간 | 새벽 작업할 때",
         title_en="80's Seoul Lofi Night 🚏 After the Last Bus, Rainy City Pop to Study 🌧 2 Hours",
         intro=["80년대 서울을 모티브로 만든 가상의 골목 정류장. 막차가 떠난 뒤 듣는 시티팝 로파이.",
                "공부·작업·휴식할 때 틀어 두세요.  |  서울 골목 라디오 3편"], tags=SEOUL_TAGS + ", 버스 정류장, 새벽"),
    dict(key="04_cyberpunk", md=T / "themes/cyberpunk/long_2h_cyberpunk.youtube.md", thumb=T / "themes/cyberpunk/thumb_cp_A.jpg", lang="en",
         title="Cyberpunk Lofi City 🌃 Neon Rain Beats for Night Coding / Focus ☔ 2 Hours", title_en=None,
         intro=["Two hours of mellow cyberpunk instrumentals and rain ambience for late-night coding.",
                "Dark synthwave, chillwave and downtempo beats over a rainy neon megacity.  |  Neon Rain Sessions"],
         tags=th["cyberpunk"]["tags"] + ", Night Alley Records"),
    dict(key="05_dystopia", md=T / "themes/dystopia/special_45min_dystopia.youtube.md", thumb=T / "themes/dystopia/thumb_dys_B.jpg", lang="en",
         title="Quiet Focus After the Fall 🕯 Dystopian Ambient Lofi for Writing & Reading | 45 min", title_en=None,
         intro=["Melancholic but peaceful ambient lofi from a quiet city after the fall.",
                "Soft ash, a warm lantern and an old radio. For deep focus, reading and late-night thinking.  |  After the Fall"],
         tags=th["dystopia"]["tags"] + ", Night Alley Records"),
]


def section(lines, head):
    out, on = [], False
    for l in lines:
        if l.startswith("## "):
            on = l.strip() == head; continue
        if on:
            if l.startswith("🎵"):
                break
            out.append(l)
    return [l for l in out if l.strip()]


def main():
    OUT.mkdir(exist_ok=True)
    rows = []
    for v in V:
        md = v["md"].read_text(encoding="utf-8").splitlines()
        chapters = section(md, "## 챕터")
        if chapters and chapters[0].startswith("0:00 "):
            chapters[0] = "00:00 " + chapters[0][5:]
        start = md.index("🎵 Tracklist")
        tracks = []
        for l in md[start + 1:]:
            if not l.strip() or l.startswith("—"):
                break
            tracks.append(l)
        edit = json.load(open(str(v["md"]).replace(".youtube.md", ".edit.json"), encoding="utf-8"))
        mm = any("mm3" in pathlib.Path(x["file"]).name for x in edit["tracks"])
        if v["lang"] == "ko":
            credit = KO_CREDIT if mm else "음악은 Stable Audio 3.0 (Powered by Stability AI)로 생성했으며, Night Alley Records가 곡을 선별하고 믹싱했습니다."
            ai, ch_head, img = KO_AI, "📖 챕터", "Image: Qwen-Image-2512, Qwen-Image-Edit-2511"
        else:
            credit = "Music: " + ("MiniMax-Music3, " if mm else "") + "Stable Audio 3.0 (Powered by Stability AI)"
            ai, ch_head, img = EN_AI, "📖 Chapters", "Image: Qwen-Image-2512"
        desc = "\n".join([v["intro"][0], credit, *v["intro"][1:], "", ch_head, *chapters, "", "🎵 Tracklist", *tracks, "", "—", ai,
                          f"Video: LTX-2.5 (Lightricks) · {img}"])
        assert "no ads" not in desc.lower()
        d = OUT / v["key"]; d.mkdir(exist_ok=True)
        (d / "title.txt").write_text(v["title"], encoding="utf-8")
        if v["title_en"]:
            (d / "title_en.txt").write_text(v["title_en"], encoding="utf-8")
        elif (d / "title_en.txt").exists():
            (d / "title_en.txt").unlink()
        (d / "description.txt").write_text(desc, encoding="utf-8")
        (d / "tags.txt").write_text(v["tags"], encoding="utf-8")
        shutil.copy(v["thumb"], d / "thumbnail.jpg")
        rows.append(dict(key=v["key"], video=str(v["md"]).replace(".youtube.md", ".mp4"), title_chars=len(v["title"]),
                         desc_chars=len(desc), tags=len(v["tags"].split(",")), tags_chars=len(v["tags"]), chapters=len(chapters)))
        assert len(v["title"]) <= 100 and len(desc) <= 5000 and len(v["tags"]) <= 500
    json.dump(rows, open(OUT / "summary.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for r in rows:
        print(r)


if __name__ == "__main__":
    main()
