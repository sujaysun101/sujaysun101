import os, sys, re, datetime, requests
from dateutil import tz  # reserved for future timezone formatting

GH_TOKEN = os.environ.get("GH_TOKEN")
GH_USER  = os.environ.get("GH_USER")

if not GH_TOKEN or not GH_USER:
    print("Missing GH_TOKEN or GH_USER env vars.", file=sys.stderr)
    sys.exit(1)

CURRENT_YEAR = datetime.datetime.utcnow().year
TARGET_YEARS = [CURRENT_YEAR, CURRENT_YEAR - 1]

GRAPHQL_URL = "https://api.github.com/graphql"

QUERY = """
query($login:String!, $from:DateTime!, $to:DateTime!) {
  user(login:$login) {
    contributionsCollection(from:$from, to:$to) {
      totalCommitContributions
      totalPullRequestContributions
      totalPullRequestReviewContributions
      totalIssueContributions
      totalRepositoryContributions
      contributionCalendar { totalContributions }
    }
  }
}
"""

def fetch_year_stats(year: int):
    start = datetime.datetime(year,1,1,0,0,0)
    end   = datetime.datetime(year+1,1,1,0,0,0) - datetime.timedelta(seconds=1)
    payload = {
        "query": QUERY,
        "variables": {
            "login": GH_USER,
            "from": start.isoformat() + "Z",
            "to":   end.isoformat() + "Z"
        }
    }
    r = requests.post(GRAPHQL_URL, json=payload, headers={"Authorization": f"Bearer {GH_TOKEN}"})
    if r.status_code != 200:
        raise RuntimeError(f"GraphQL error {r.status_code}: {r.text}")
    data = r.json()
    if "errors" in data:
        raise RuntimeError(f"GraphQL returned errors: {data['errors']}")
    cc = data["data"]["user"]["contributionsCollection"]
    return {
        "year": year,
        "total_contributions": cc["contributionCalendar"]["totalContributions"],
        "commits": cc["totalCommitContributions"],
        "prs": cc["totalPullRequestContributions"],
        "issues": cc["totalIssueContributions"],
        "reviews": cc["totalPullRequestReviewContributions"],
        "repos": cc["totalRepositoryContributions"],
    }

def format_line(stats, ytd=False):
    label = f"{stats['year']} ({'YTD' if ytd else 'Full Year'})"
    return (f"{label}: {stats['total_contributions']} total contributions "
            f"(Commits: {stats['commits']} | PRs: {stats['prs']} | Issues: {stats['issues']} | Reviews: {stats['reviews']})")

def main():
    year_stats = {y: fetch_year_stats(y) for y in TARGET_YEARS}

    current_stats = year_stats[CURRENT_YEAR]
    last_year_stats = year_stats[CURRENT_YEAR - 1]

    current_line = format_line(current_stats, ytd=True)
    last_year_line = format_line(last_year_stats, ytd=False)

    updated_at = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    block = [
        "### 🗓 Yearly Contribution Snapshot",
        current_line,
        last_year_line,
        f"Last updated: {updated_at}",
    ]
    replacement = "\n".join(block)

    with open("README.md", "r", encoding="utf-8") as f:
        readme = f.read()

    pattern = r"(<!-- YEARLY_CONTRIBUTIONS_START -->)(.*?)(<!-- YEARLY_CONTRIBUTIONS_END -->)"
    if not re.search(pattern, readme, flags=re.DOTALL):
        print("Markers not found in README.md", file=sys.stderr)
        sys.exit(1)

    new_readme = re.sub(
        pattern,
        f"<!-- YEARLY_CONTRIBUTIONS_START -->\n{replacement}\n<!-- YEARLY_CONTRIBUTIONS_END -->",
        readme,
        flags=re.DOTALL,
    )

    if new_readme != readme:
        with open("README.md", "w", encoding="utf-8") as f:
            f.write(new_readme)
        print("README.md updated.")
    else:
        print("No change detected.")

if __name__ == "__main__":
    main()