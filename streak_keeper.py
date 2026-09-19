#!/usr/bin/env python3
"""
GitHub streak keeper for ShrlGnwn.
Checks today's public events via gh api; if no commit-ish activity,
bumps the streak counter comment in README.md and pushes.
Exit 0 always; prints a status line for cron logging.
"""
import json, re, subprocess, sys, os
from datetime import datetime, timezone, timedelta

REPO_DIR = "/root/streak-keeper"
README = os.path.join(REPO_DIR, "README.md")
USER = "ShrlGnwn"
WIB = timezone(timedelta(hours=7))

# Activity types that count as a "commit" for streak purposes
COMMIT_EVENTS = {"PushEvent", "PullRequestEvent", "PullRequestReviewEvent",
                 "CreateEvent", "IssuesEvent", "IssueCommentEvent",
                 "CommitCommentEvent", "ReleaseEvent"}

def sh(cmd, cwd=REPO_DIR):
    return subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True)

def today_wib():
    return datetime.now(WIB).date()

def get_today_events():
    """Fetch recent public events; filter to today (WIB)."""
    r = subprocess.run(
        ["gh", "api", f"/users/{USER}/events", "--paginate", "-q", "."],
        capture_output=True, text=True, timeout=30)
    if r.returncode != 0:
        print("ERR gh api:", r.stderr[:200]); return None
    try:
        events = json.loads(r.stdout)
    except Exception:
        # --paginate may emit multiple arrays; try line-delimited
        events = []
        for chunk in re.findall(r'\[.*?\]', r.stdout, re.S):
            try: events += json.loads(chunk)
            except Exception: pass
    today = today_wib()
    hits = []
    for e in events:
        et = e.get("type", "")
        if et not in COMMIT_EVENTS:
            continue
        ts = e.get("created_at", "")
        try:
            d = datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(WIB).date()
        except Exception:
            continue
        if d == today:
            hits.append((et, e.get("repo", {}).get("name", "?"), ts))
    return hits

def bump_readme():
    now = datetime.now(WIB).strftime("%Y-%m-%d")
    src = open(README).read()
    marker = re.search(
        r"(<!-- STREAK-COUNTER -->)(.*?)(<!-- /STREAK-COUNTER -->)",
        src, re.S)
    if not marker:
        src += f"\n\n<!-- STREAK-COUNTER -->\n<!-- Streak 1 : {now} -->\n<!-- /STREAK-COUNTER -->\n"
    else:
        prev = marker.group(2)
        # extract last streak number
        m = re.search(r"Streak (\d+)", prev)
        n = int(m.group(1)) if m else 0
        src = (src[:marker.start(2)]
               + f"\n<!-- Streak {n+1} : {now} -->\n"
               + src[marker.end(2):])
    open(README, "w").write(src)

def git_push():
    sh("git add README.md")
    if "nothing to commit" in sh("git status --porcelain").stdout:
        return False
    now = datetime.now(WIB).strftime("%Y-%m-%d")
    sh(f'git commit -q -m "streak-keeper: heartbeat {now}"')
    p = sh("git push origin main")
    return p.returncode == 0

def main():
    os.chdir(REPO_DIR)
    sh("git pull -q origin main")
    events = get_today_events()
    if events is None:
        print("SKIP: could not fetch events"); return
    if events:
        print(f"OK: {len(events)} activity event(s) today — streak safe, no auto-commit")
        for t, repo, ts in events[:5]:
            print(f"  - {t} @ {repo}")
        return
    print("No activity today — bumping counter & pushing")
    bump_readme()
    if git_push():
        print("PUSHED: streak-keeper heartbeat")
    else:
        print("PUSH FAILED")

if __name__ == "__main__":
    main()
