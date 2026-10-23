#!/usr/bin/env python3
"""Fetch the live numbers shown on the profile and write data/stats.json.

Runs in the refresh workflow with GITHUB_TOKEN. Any value that cannot be
fetched keeps its previous value, so a failed request never blanks the page."""
import datetime as dt
import json
import os
import sys
import urllib.request
from pathlib import Path

USER = "ethany14"
FEATURED = ["Eregion-Job-Finding-Agent", "Cs2-Roundcrafter"]
DATA = Path(__file__).resolve().parent.parent / "data" / "stats.json"


def request(url, payload=None):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": f"{USER}-profile"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=body, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def owned_repos():
    repos, page = [], 1
    while True:
        batch = request(f"https://api.github.com/users/{USER}/repos?type=owner&per_page=100&page={page}")
        repos += batch
        if len(batch) < 100:
            return repos
        page += 1


def contributions(year):
    query = """query($login: String!, $from: DateTime!, $to: DateTime!) {
      user(login: $login) { contributionsCollection(from: $from, to: $to) {
        contributionCalendar { totalContributions } } } }"""
    variables = {"login": USER, "from": f"{year}-01-01T00:00:00Z", "to": f"{year}-12-31T23:59:59Z"}
    data = request("https://api.github.com/graphql", {"query": query, "variables": variables})
    return data["data"]["user"]["contributionsCollection"]["contributionCalendar"]["totalContributions"]


def main():
    stats = json.loads(DATA.read_text()) if DATA.exists() else {}
    now = dt.datetime.now(dt.timezone.utc)
    stats["year"] = now.year

    try:
        stats["account_created"] = request(f"https://api.github.com/users/{USER}")["created_at"]
    except Exception as exc:  # keep the previous value
        print(f"user: {exc}", file=sys.stderr)

    try:
        repos = owned_repos()
        stats["total_stars"] = sum(r["stargazers_count"] for r in repos if not r["fork"])
        stats["repos"] = {r["name"]: {"stars": r["stargazers_count"], "forks": r["forks_count"],
                                      "pushed_at": r["pushed_at"]}
                          for r in repos if r["name"] in FEATURED}
    except Exception as exc:
        print(f"repos: {exc}", file=sys.stderr)

    try:
        stats["contributions"] = contributions(now.year)
    except Exception as exc:
        print(f"contributions: {exc}", file=sys.stderr)

    # Date only, so hourly runs commit when a number changes or a new day starts, not every hour.
    stats["generated_at"] = now.strftime("%Y-%m-%d")
    DATA.parent.mkdir(parents=True, exist_ok=True)
    DATA.write_text(json.dumps(stats, indent=2, sort_keys=True) + "\n")
    print(json.dumps(stats, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
