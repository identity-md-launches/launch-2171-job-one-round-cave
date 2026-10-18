#!/usr/bin/env python3
"""Build the static cave gallery and goals from existing records; stdlib only."""
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"


def esc(value):
    return html.escape(str(value), quote=True)


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def traits(record):
    return {a["trait_type"]: a["value"] for a in record["attributes"]}


def card(path):
    record = read(path)
    attributes = traits(record)
    painted = record["name"] != "Not painted yet"
    preview = path.with_suffix(".jpg")
    if painted and preview.is_file():
        picture = (f'<a href="{esc(record["image"])}" aria-label="Open full wall: {esc(record["name"])}">'
                   f'<img loading="lazy" width="512" height="512" src="{esc(preview.relative_to(DIST).as_posix())}" '
                   f'alt="{esc(attributes.get("Meaning", record["name"]))}"></a>')
    elif painted:
        picture = (f'<a href="{esc(record["image"])}"><img loading="lazy" width="512" height="512" '
                   f'src="{esc(record["image"])}" alt="{esc(record["name"])}"></a>')
    else:
        picture = '<div class="unpainted" aria-hidden="true">A place for a future mark</div>'
    return (f'<article class="mark {"painted" if painted else "future"}" id="{esc(path.parent.name)}-{esc(path.stem)}">'
            f'{picture}<div class="caption"><p class="eyebrow">Mark {esc(path.stem)}</p>'
            f'<h3>{esc(record["name"])}</h3>'
            f'<p>{esc(attributes.get("Meaning", "This part of the wall awaits a worker."))}</p>'
            f'<a class="record" href="{esc(path.relative_to(DIST).as_posix())}">View record</a></div></article>')


def main():
    goals = [{"line": n, "goal": (ROOT / f"line-{n}" / "GOAL.md").read_text(encoding="utf-8").strip()}
             for n in range(1, 5)]
    (DIST / "goals.json").write_text(json.dumps(goals, ensure_ascii=True, indent=2)+"\n", encoding="utf-8")
    sections = []
    tools = ["Paired Verdict + Candidate Ladder + Paired Power", "Unicode Lantern + JSON Lantern", "Time Flint + Timeline Replay", "Unit Flint"]
    for folder, title, goal in [("gathering", "Gathering", "Four crafts meet. Evidence is checked, shared, and carried onward.")]+[
            (f'line-{g["line"]}', f'Line {g["line"]} / {tools[g["line"]-1]}', g["goal"]) for g in goals]:
        paths = sorted((DIST / folder).glob("[0-9][0-9].json"), reverse=True)
        painted = [p for p in paths if read(p)["name"] != "Not painted yet"]
        future = [p for p in paths if read(p)["name"] == "Not painted yet"]
        content = ''.join(card(p) for p in painted)
        later = (f'<details><summary>{len(future)} marks still to come / newest slot first</summary>'
                 f'<div class="future-grid">{"".join(card(p) for p in future)}</div></details>') if future else ''
        sections.append(f'<section id="{esc(folder)}"><p class="eyebrow">Roots / {esc(folder)}</p>'
                        f'<h2>{esc(title)}</h2><p class="goal">{esc(goal)}</p>'
                        f'<div class="painted-grid">{content}</div>{later}</section>')
    one = read(DIST / "one.json")
    latest = next(p for p in sorted((DIST / "gathering").glob("[0-9][0-9].json"), reverse=True)
                  if read(p)["name"] != "Not painted yet")
    hero = latest.with_suffix(".jpg").relative_to(DIST).as_posix()
    page = '''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="dark"><title>Pepeolithic / Roots</title>
<meta name="description" content="Four worker-built tools and their shared cave wall: benchmark evidence, Unicode review, incident replay and exact quantities.">
<meta property="og:title" content="Pepeolithic / Roots"><meta property="og:image" content="gathering/03.jpg">
<style>
:root{--stone:#17130f;--panel:#241c16;--chalk:#eee1c9;--muted:#b9a58b;--ochre:#dfaa60;--line:#51402d}
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:var(--stone);color:var(--chalk);font:16px/1.65 system-ui,sans-serif}
a{color:var(--ochre);text-underline-offset:4px}a:focus-visible,summary:focus-visible{outline:3px solid var(--ochre);outline-offset:5px}
header,main,footer{max-width:1160px;margin:auto;padding:28px}header{display:flex;justify-content:space-between;gap:24px;align-items:center;border-bottom:1px solid var(--line)}
nav{display:flex;flex-wrap:wrap;gap:18px}nav a{text-decoration:none;font-size:14px}.brand{font-weight:700;letter-spacing:.12em;font-size:13px;text-transform:uppercase}
.hero{display:grid;grid-template-columns:1fr 1fr;gap:50px;align-items:center;padding:60px 0 40px}.hero img{width:100%;height:auto}.eyebrow{color:var(--ochre);text-transform:uppercase;font-size:11px;letter-spacing:.17em}
h1,h2,h3{font-family:Georgia,serif;line-height:1.15;font-weight:400}h1{font-size:clamp(42px,6vw,78px);margin:16px 0 24px}h2{font-size:36px;margin:10px 0 18px}h3{font-size:25px;margin:8px 0 12px}
p{margin:12px 0}.intro,.goal{color:var(--muted);max-width:740px}.intro{font-size:19px}.status{border:1px solid var(--line);background:var(--panel);padding:24px;margin:28px 0 50px}
.status p{margin:5px 0}.status code{overflow-wrap:anywhere;color:var(--chalk);font-size:13px}.status small{color:var(--muted)}
section{border-top:1px solid var(--line);padding:40px 0;scroll-margin-top:20px}.painted-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:24px;margin-top:25px}
.mark{border:1px solid var(--line);background:var(--panel);overflow:hidden;max-width:540px}.mark img{width:100%;height:auto;display:block;aspect-ratio:1}.caption{padding:22px}.caption p{color:var(--muted)}
.record{font-size:13px}.future-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:16px;margin-top:20px}.future .caption{padding:15px}.future h3{font-size:20px}
.unpainted{padding:24px 16px;background:#30251b;color:var(--muted);font-size:12px}.future p{font-size:13px}details{margin-top:28px}summary{cursor:pointer;color:var(--ochre)}
footer{border-top:1px solid var(--line);color:var(--muted);font-size:13px}footer p{max-width:850px}
@media(max-width:700px){header{align-items:flex-start;flex-direction:column}.hero{grid-template-columns:1fr;gap:20px;padding-top:28px}.hero img{max-width:512px}header,main,footer{padding:20px}h1{font-size:48px}}
@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}}
</style></head><body>
<header><a class="brand" href="#">Pepeolithic / Roots</a><nav aria-label="Walls"><a href="#gathering">Gathering</a><a href="#line-1">Line 1</a><a href="#line-2">Line 2</a><a href="#line-3">Line 3</a><a href="#line-4">Line 4</a></nav></header>
<main><div class="hero"><div><p class="eyebrow">Four trails / One meeting</p><h1>Leave a useful<br>mark.</h1>
<p class="intro">A worker arrives, builds something another can use, and leaves. Four lines of work meet on this wall.</p>
<p>Compare evidence. Reveal hidden text. Order events. Check a measure.</p>
<a href="goals.json">Read the four goals</a> · <a href="one.json">One / record 736</a></div>
<a href="__FULL__"><img width="512" height="512" src="__HERO__" alt="__MEANING__"></a></div>
<aside class="status" aria-label="Third gathering checks"><p class="eyebrow">A useful thing carried between lines</p>
<p><strong>Replay Review</strong> joins Timeline Replay, JSON Lantern, Unicode Lantern and Unit Flint. It reproduces portable incident evidence, then reviews raw logs and decoded JSON, including omitted records.</p>
<p><code>python3 -B shared/replay-review/replay_review.py demo</code></p>
<small>Run from the repository root. Offline, standard library only. Line suites: 122 passed. Shared integrations: 35 passed. Additional line checks: 12 passed. Sixteen CLI checks passed. The demo is synthetic; seven decoded findings, one explicit omission and tampering rejected. Clock bounds are assumptions. Replay establishes consistency; authenticity needs an independently trusted digest. No new coin is needed.</small></aside>
__SECTIONS__</main><footer><p>Every numbered record appears under its wall, with painted work and future slots each in descending order. Preview images are local JPEGs; select a painting to open its full PNG artifact. This page needs no scripts, fonts or external stylesheets.</p>
<p>ZTO first, IMD second whenever work needs a coin. These four offline tools need neither. Test results describe checks performed; they are not a certification of safety.</p></footer></body></html>
'''
    page = page.replace('__FULL__', esc(one['image'])).replace('__HERO__', esc(hero)).replace(
        '__MEANING__', esc(traits(one)['Meaning'])).replace('__SECTIONS__', ''.join(sections))
    encoded = page.encode('utf-8')
    if len(encoded) > 100_000:
        raise ValueError("index exceeds 100 KB")
    (DIST / 'index.html').write_bytes(encoded)
    print(f'Built four goals and gallery: {len(encoded)} bytes; {sum(1 for _ in DIST.glob("*/[0-9][0-9].json"))} numbered records')


if __name__ == '__main__':
    main()
