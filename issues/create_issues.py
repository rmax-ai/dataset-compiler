#!/usr/bin/env python3
"""Create the native GitHub issue graph for rmax-ai/dataset-compiler from issues/graph.yaml.

Two passes:
  1) create labels + milestones + issues (capturing numbers into issues/map.json);
  2) patch bodies: resolve dependency links + epic/parent checklists to live issue numbers.

Re-runnable: keys already present in map.json (and alive) are skipped.
Requires: ~/bin/gh (bot shim) authenticated for the target repo; run from the repo root.

Usage:
  python3 issues/create_issues.py --dry-run          # validate + render, no network
  python3 issues/create_issues.py                    # execute
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

import yaml

REPO = "rmax-ai/dataset-compiler"
HERE = Path(__file__).resolve().parent
GRAPH = HERE / "graph.yaml"
MAP = HERE / "map.json"
GH = str(Path.home() / "bin" / "gh")

LABELS = {
    "type:epic": "5319e7",
    "type:task": "0e8a16",
    "type:subtask": "c2e0c6",
    "planning": "ededed",
}
PLANNING_NOTE = (
    "Planning state only — execution requires a central trigger in "
    "`rmax-ai/delegation-queue`."
)


def gh(*args: str, input_text: str | None = None) -> str:
    cmd = [GH, *args]
    res = subprocess.run(
        cmd, capture_output=True, text=True, input=input_text, timeout=120,
        env={**os.environ, "GH_PROMPT_DISABLED": "1"},
    )
    if res.returncode != 0:
        raise SystemExit(f"gh failed ({res.returncode}): {' '.join(cmd)}\n{res.stderr.strip()}")
    return res.stdout.strip()


def children_of(key: str, issues: dict) -> list[str]:
    """Child keys: project -> epics; epic -> tasks/subtasks; task -> subtasks."""
    if key == "project":
        return [k for k in ("E1", "E2", "E3", "E4", "E5", "E6") if k in issues]
    kids = [
        k for k, v in issues.items()
        if k != key and v["type"] != "epic" and (
            k.startswith(key + ".") or (v["type"] == "subtask" and k.startswith(key))
        )
    ]
    return sorted(kids)



def load_graph() -> dict:
    return yaml.safe_load(GRAPH.read_text())


def load_map() -> dict:
    if MAP.exists():
        return json.loads(MAP.read_text())
    return {}


def save_map(mapping: dict) -> None:
    MAP.write_text(json.dumps(mapping, indent=2, sort_keys=True) + "\n")


def render_body(
    iss: dict, milestone: str, num_of: dict, *, deps: list[str], children: list[str]
) -> str:
    parts: list[str] = []
    if iss.get("scope"):
        parts.append(f"## Scope\n\n{iss['scope'].strip()}\n")
    if iss.get("deliverables"):
        items = "\n".join(f"- {d}" for d in iss["deliverables"])
        parts.append(f"## Deliverables\n\n{items}\n")
    if iss.get("acceptance"):
        items = "\n".join(f"- [ ] {a}" for a in iss["acceptance"])
        parts.append(f"## Acceptance (deterministic)\n\n{items}\n")
    if children and iss["type"] == "epic":
        label = "Child epics" if iss["key"] == "project" else "Child tasks"
        items = "\n".join(f"- [ ] #{num_of[c]} — {c}" for c in children)
        parts.append(f"## {label}\n\n{items}\n")
    dep_lines = []
    if deps:
        dep_lines.append("**blocked by:** " + ", ".join(f"#{num_of[d]}" for d in deps))
    else:
        dep_lines.append("**blocked by:** —")
    unblocks = sorted(k for k, v in NUM_DEPS.items() if iss["key"] in v)
    dep_lines.append(
        "**unblocks:** " + (", ".join(f"#{num_of[k]}" for k in unblocks) if unblocks else "—")
    )
    parts.append("## Dependencies\n\n" + "\n".join(dep_lines) + "\n")
    parts.append(
        f"---\nMilestone: {milestone}. {PLANNING_NOTE}\n"
        "Origin: PLAN.md §7 (bootstrap corpus: `issues/graph.yaml`).\n"
    )
    return "\n".join(parts)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    graph = load_graph()
    issues = {i["key"]: i for i in graph["issues"]}
    milestones = graph["milestones"]

    global NUM_DEPS
    NUM_DEPS = {k: v.get("deps") or [] for k, v in issues.items()}

    order = ["project"] + [k for k in ("E1", "E2", "E3", "E4", "E5", "E6")] + sorted(
        k for k in issues if k not in ("project", "E1", "E2", "E3", "E4", "E5", "E6")
    )

    if args.dry_run:
        fake = {k: idx + 1 for idx, k in enumerate(order)}
        for k in order:
            iss = issues[k]
            body = render_body(
                iss, iss["milestone"], fake, deps=NUM_DEPS[k], children=children_of(k, issues)
            )
            print(f"=== {k} :: {iss['title']} [{iss['type']}] ms={iss['milestone']} ===")
            print(body)
        print(f"dry-run ok: {len(order)} issues", file=sys.stderr)
        return 0

    mapping = load_map()
    # milestone + label bootstrap
    for name, desc in milestones.items():
        existing = json.loads(gh("api", f"repos/{REPO}/milestones", "--jq", "[.[].title]"))
        if name not in existing:
            gh(
                "api", f"repos/{REPO}/milestones",
                "-f", f"title={name}", "-f", f"description={desc}",
            )
            print(f"milestone created: {name}")
    existing_labels = json.loads(gh("api", f"repos/{REPO}/labels", "--jq", "[.[].name]"))
    for name, color in LABELS.items():
        if name not in existing_labels:
            gh("api", f"repos/{REPO}/labels", "-f", f"name={name}", "-f", f"color={color}")
            print(f"label created: {name}")

    # pass 1: create
    for k in order:
        if k in mapping and mapping[k]:
            continue
        iss = issues[k]
        body = (
            f"# {iss['title']}\n\n"
            f"Bootstrap issue from the frozen planning corpus. {PLANNING_NOTE}\n\n"
            + "PLACEHOLDER-BODY (pass 2 fills scope/acceptance/deps)\n"
        )
        tmp = HERE / f".body-{k}.md"
        tmp.write_text(body)
        out = gh(
            "issue", "create", "-R", REPO,
            "--title", iss["title"],
            "--body-file", str(tmp),
            "--label", f"type:{iss['type']}",
            "--label", "planning",
            "--milestone", iss["milestone"],
        )
        tmp.unlink()
        num = int(out.rstrip("/").split("/")[-1])
        mapping[k] = num
        save_map(mapping)
        print(f"created #{num} [{k}] {iss['title']}")

    # pass 2: patch bodies with scope/acceptance/deps/children
    for k in order:
        iss = issues[k]
        body = render_body(
            iss, iss["milestone"], mapping, deps=NUM_DEPS[k], children=children_of(k, issues)
        )
        tmp = HERE / f".body-{k}.md"
        tmp.write_text(body)
        gh("api", "--method", "PATCH", f"repos/{REPO}/issues/{mapping[k]}",
           "-F", f"body=@{tmp}", "--jq", ".number")
        tmp.unlink()
        print(f"patched #{mapping[k]} [{k}]")

    print(f"done: {len(mapping)} issues; map at {MAP}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
