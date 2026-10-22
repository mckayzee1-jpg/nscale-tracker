#!/usr/bin/env python3
"""Check Nscale's Greenhouse board for new roles matching config.json and push to ntfy."""
import json, os, sys, urllib.request, pathlib

ROOT = pathlib.Path(__file__).parent
CFG = json.loads((ROOT / "config.json").read_text())
SEEN_FILE = ROOT / "seen_jobs.json"
TOPIC = os.environ.get("NTFY_TOPIC", "").strip()
TOKEN = CFG["board_token"]

# Nscale's board is on Greenhouse's EU instance; try both API hosts.
API_HOSTS = ["https://boards-api.greenhouse.io", "https://boards-api.eu.greenhouse.io"]


def http(url, data=None, headers=None):
    req = urllib.request.Request(url, data=data, headers=headers or {})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def fetch_jobs():
    last_err = None
    for host in API_HOSTS:
        try:
            raw = http(f"{host}/v1/boards/{TOKEN}/jobs")
            return json.loads(raw)["jobs"]
        except Exception as e:  # try next host
            last_err = e
    sys.exit(f"Could not fetch board '{TOKEN}': {last_err}")


def matches(job):
    title = job["title"].lower()
    loc = (job.get("location") or {}).get("name", "").lower()
    inc = [k.lower() for k in CFG["title_include_any"]]
    exc = [k.lower() for k in CFG["title_exclude_any"]]
    locs = [k.lower() for k in CFG["location_include_any"]]
    if inc and not any(k in title for k in inc):
        return False
    if any(k in title for k in exc):
        return False
    if locs and not any(k in loc for k in locs):
        return False
    return True


def notify(job):
    if not TOPIC:
        print("NTFY_TOPIC not set; would notify:", job["title"], job["absolute_url"])
        return
    payload = {
        "topic": TOPIC,
        "title": "New Nscale role",
        "message": f'{job["title"]}\n{(job.get("location") or {}).get("name", "")}',
        "click": job["absolute_url"],
        "tags": ["briefcase"],
        "priority": 4,
        "actions": [{"action": "view", "label": "Open job", "url": job["absolute_url"]}],
    }
    http(CFG["ntfy_server"], json.dumps(payload).encode(), {"Content-Type": "application/json"})


def main():
    jobs = [j for j in fetch_jobs() if matches(j)]
    first_run = not SEEN_FILE.exists()
    seen = set(json.loads(SEEN_FILE.read_text())) if not first_run else set()

    new = [j for j in jobs if str(j["id"]) not in seen]
    print(f"{len(jobs)} matching roles, {len(new)} new (first_run={first_run})")

    # First run just records what exists so you aren't flooded with old roles.
    if not first_run:
        for j in new:
            notify(j)

    SEEN_FILE.write_text(json.dumps(sorted(seen | {str(j["id"]) for j in jobs}), indent=1))


if __name__ == "__main__":
    main()
