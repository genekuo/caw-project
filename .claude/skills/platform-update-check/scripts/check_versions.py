#!/usr/bin/env python3
"""Check the platforms in docs/platform/versions.md for new releases.

Subcommands
  check         Fetch each item's check.url, compare with its `notified` record,
                print JSON {"updates": [...], "manual": [...], "errors": [...]}.
  render        Turn a check JSON (possibly edited by the agent) into a Slack mrkdwn message.
  record        Rewrite the `notified:` line of the listed items in versions.md.
  send-webhook  Post a message file to the Slack incoming webhook in $SLACK_WEBHOOK_URL.

Needs Python 3.9+ and PyYAML (pip install pyyaml). Set GITHUB_TOKEN to avoid
GitHub's 60 requests/hour anonymous limit.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.exit("PyYAML is required: pip install pyyaml")

PRERELEASE = re.compile(r"(alpha|beta|rc|preview|snapshot|milestone|[.-]m\d+\b|-ea\b|nightly|dev)", re.I)
DOC_CANDIDATES = ["docs/platform/versions.md", "../docs/platform/versions.md"]


# ---------------------------------------------------------------- doc I/O

def find_doc(explicit: str | None) -> Path:
    if explicit:
        return Path(explicit)
    here = Path.cwd()
    for base in [here, *here.parents]:
        for cand in DOC_CANDIDATES:
            p = (base / cand).resolve()
            if p.is_file():
                return p
    sys.exit("versions.md not found; pass --doc PATH")


def load_inventory(doc: Path) -> dict:
    m = re.search(r"```yaml\n(.*?)```", doc.read_text(encoding="utf-8"), re.S)
    if not m:
        sys.exit(f"No ```yaml block in {doc}")
    return yaml.safe_load(m.group(1))


# ---------------------------------------------------------------- versions

def vkey(v: str) -> tuple:
    return tuple(int(x) for x in re.findall(r"\d+", v))


def clean(tag: str) -> str:
    """'v1.2.3' / 'chart-v2.2.18' / 'helm-chart-2.13.0' -> '1.2.3'."""
    m = re.search(r"\d.*", tag or "")
    return m.group(0) if m else ""


def is_pre(v: str) -> bool:
    return bool(PRERELEASE.search(v))


def on_line(v: str, line) -> bool:
    if not line:
        return False
    line = str(line)
    if line.endswith(".x"):
        line = line[:-2]
    return v == line or any(v.startswith(line + sep) for sep in ".-+")


def newer(found, seen) -> bool:
    if not found:
        return False
    if not seen:
        return True
    return vkey(found) > vkey(str(seen))


def pick(cands, line):
    """cands: [(version, link)]. Returns (track, newest), each (version, link) or None."""
    cands = [c for c in cands if c[0] and not is_pre(c[0])]
    if not cands:
        return None, None
    newest = max(cands, key=lambda c: vkey(c[0]))
    tracked = [c for c in cands if on_line(c[0], line)]
    track = max(tracked, key=lambda c: vkey(c[0])) if tracked else None
    return track, newest


# ---------------------------------------------------------------- fetchers

def http_get(url: str) -> str:
    headers = {"User-Agent": "platform-update-check/1", "Accept": "application/json"}
    if "api.github.com" in url and os.environ.get("GITHUB_TOKEN"):
        headers["Authorization"] = f"Bearer {os.environ['GITHUB_TOKEN']}"
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30) as r:
        return r.read().decode("utf-8")


def fetch_endoflife(check, get):
    data = json.loads(get(check["url"]))
    data = data.get("result", data)
    out = []
    for rel in data.get("releases", []):
        if rel.get("isEol"):
            continue
        lat = rel.get("latest") or {}
        if lat.get("name"):
            out.append((lat["name"], lat.get("link")))
    return out


def fetch_github(check, get):
    url = check["url"]
    if url.endswith("/releases/latest"):  # list instead, so patch releases on older lines are seen
        url = url[: -len("/latest")] + "?per_page=100"
    rels = json.loads(get(url))
    if isinstance(rels, dict):
        rels = [rels]
    flt = re.compile(check["filter"]) if check.get("filter") else None
    out = []
    for r in rels:
        if r.get("draft") or r.get("prerelease"):
            continue
        tag = r.get("tag_name", "")
        if flt and not flt.search(tag):
            continue
        out.append((clean(tag), r.get("html_url")))
    return out


def fetch_maven(check, get):
    xml = get(check["url"])
    flt = re.compile(check["filter"]) if check.get("filter") else None
    return [(v, None) for v in re.findall(r"<version>([^<]+)</version>", xml) if not flt or flt.search(v)]


def fetch_artifacthub(check, get):
    data = json.loads(get(check["url"]))
    v = data.get(check.get("field", "app_version")) or data.get("version")
    repo = (data.get("repository") or {}).get("name", "")
    return [(clean(str(v)), f"https://artifacthub.io/packages/helm/{repo}/{data.get('name', '')}")]


FETCHERS = {
    "endoflife": fetch_endoflife,
    "github_release": fetch_github,
    "maven_metadata": fetch_maven,
    "artifacthub": fetch_artifacthub,
}


# ---------------------------------------------------------------- commands

def run_check(doc: Path, get=http_get) -> dict:
    inv = load_inventory(doc)
    updates, manual, errors = [], [], []
    for item in inv["platforms"]:
        check = item.get("check") or {}
        notified = item.get("notified") or {}
        base = {
            "id": item["id"],
            "name": item["name"],
            "owner": item.get("owner"),
            "track_line": item.get("track_line"),
            "design_pin": item.get("design_pin"),
            "notified": {"track": notified.get("track"), "newest": notified.get("newest")},
        }
        fetch = FETCHERS.get(check.get("kind"))
        if not fetch:
            manual.append({**base, "kind": check.get("kind"), "url": check.get("url"),
                           "check_alt": item.get("check_alt")})
            continue
        try:
            track, newest = pick(fetch(check, get), item.get("track_line"))
        except Exception as e:  # network, parse, rate limit
            errors.append({**base, "url": check.get("url"), "check_alt": item.get("check_alt"),
                           "error": f"{type(e).__name__}: {e}"})
            continue
        if newest is None:
            errors.append({**base, "url": check.get("url"), "check_alt": item.get("check_alt"),
                           "error": "no stable versions parsed"})
            continue
        t_ver, n_ver = (track[0] if track else None), newest[0]
        new_track = bool(item.get("track_line")) and newer(t_ver, base["notified"]["track"])
        new_newest = newer(n_ver, base["notified"]["newest"]) and n_ver != t_ver
        if new_track or new_newest:
            updates.append({
                **base,
                "found": {"track": t_ver, "newest": n_ver},
                "new_track": new_track,
                "new_newest": new_newest,
                "link": (track[1] if new_track and track else newest[1]) or check.get("url"),
            })
    return {"doc": str(doc), "run_date": dt.date.today().isoformat(),
            "updates": updates, "manual": manual, "errors": errors}


def cmd_check(args):
    json.dump(run_check(find_doc(args.doc)), sys.stdout, indent=2, default=str, ensure_ascii=False)
    print()


def render(data: dict) -> str:
    ups = data.get("updates", [])
    if not ups:
        return ""
    lines = [f"*Platform updates — {data.get('run_date') or dt.date.today().isoformat()}*", ""]
    for owner, title in [("app", "App-owned (this repo)"), ("platform", "Platform team")]:
        rows = [u for u in ups if (u.get("owner") or "app") == owner]
        if not rows:
            continue
        lines.append(f"*{title}*")
        for u in rows:
            f, n = u["found"], u["notified"]
            parts = []
            if u.get("new_track"):
                parts.append(f"`{n.get('track') or '—'}` → `{f['track']}` ({u.get('track_line')} line)")
            if u.get("new_newest"):
                parts.append(f"newer release `{f['newest']}` (last notified `{n.get('newest') or '—'}`)")
            note = f" — {u['note']}" if u.get("note") else ""
            link = f" <{u['link']}|release>" if u.get("link") else ""
            lines.append(f"• *{u['name']}*: " + "; ".join(parts) + note + link)
        lines.append("")
    lines.append("Details: `docs/platform/versions.md`")
    return "\n".join(lines).rstrip()


def cmd_render(args):
    out = render(json.loads(Path(args.input).read_text(encoding="utf-8")))
    if out:
        print(out)


def fmt_notified(track, newest, date) -> str:
    q = lambda v: "null" if v in (None, "") else json.dumps(str(v))
    return f"notified: {{ track: {q(track)}, newest: {q(newest)}, date: {date} }}"


def record(doc: Path, entries: list, date: str) -> list:
    original = doc.read_text(encoding="utf-8")
    lines = original.splitlines(keepends=True)
    inv = {i["id"]: i for i in load_inventory(doc)["platforms"]}
    changed = []
    for e in entries:
        pid = e["id"]
        if pid not in inv:
            sys.exit(f"unknown id: {pid}")
        prev = inv[pid].get("notified") or {}
        found = e.get("found") or e
        track = found.get("track") or prev.get("track")
        newest = found.get("newest") or prev.get("newest")
        start = next(i for i, l in enumerate(lines) if re.match(rf"\s*- id: {re.escape(pid)}\s*$", l))
        end = next((i for i in range(start + 1, len(lines))
                    if re.match(r"\s*- id: ", lines[i]) or lines[i].startswith("```")), len(lines))
        idx = next((i for i in range(start, end) if re.match(r"\s+notified:", lines[i])), None)
        if idx is None:
            sys.exit(f"{pid}: no notified: line to update")
        indent = re.match(r"(\s*)", lines[idx]).group(1)
        lines[idx] = indent + fmt_notified(track, newest, date) + "\n"
        changed.append(pid)
    doc.write_text("".join(lines), encoding="utf-8")
    try:
        load_inventory(doc)  # the YAML must still parse
    except Exception:
        doc.write_text(original, encoding="utf-8")
        raise
    return changed


def cmd_record(args):
    doc = find_doc(args.doc)
    entries = json.loads(Path(args.input).read_text(encoding="utf-8"))
    if isinstance(entries, dict):
        entries = entries.get("updates", [])
    date = args.date or dt.date.today().isoformat()
    print(json.dumps({"recorded": record(doc, entries, date), "date": date}))


def cmd_send_webhook(args):
    url = os.environ.get("SLACK_WEBHOOK_URL")
    if not url:
        sys.exit("SLACK_WEBHOOK_URL is not set")
    body = json.dumps({"text": Path(args.text_file).read_text(encoding="utf-8")}).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        resp = r.read().decode()
    if resp.strip() != "ok":
        sys.exit(f"Slack webhook returned: {resp}")
    print("sent")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check").add_argument("--doc")
    sub.add_parser("render").add_argument("--input", required=True)
    rec = sub.add_parser("record")
    rec.add_argument("--doc"); rec.add_argument("--input", required=True); rec.add_argument("--date")
    sub.add_parser("send-webhook").add_argument("--text-file", required=True)
    args = ap.parse_args()
    {"check": cmd_check, "render": cmd_render, "record": cmd_record,
     "send-webhook": cmd_send_webhook}[args.cmd](args)


if __name__ == "__main__":
    main()
