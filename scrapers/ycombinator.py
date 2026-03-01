"""
HireTrace — Y Combinator Scraper
Scrapes startup jobs from workatastartup.com (YC's official job board)

Usage:
    python ycombinator.py                         # scrape all
    python ycombinator.py --keyword "fintech"     # filter by keyword
    python ycombinator.py --pages 5               # scrape more pages
    python ycombinator.py --format json           # export as JSON
    python ycombinator.py --no-deep               # skip email deep scrape (faster)
"""

import requests
from bs4 import BeautifulSoup
import csv
import json
import re
import time
import argparse
from datetime import datetime

# ── CONFIG ────────────────────────────────────────────────────────────────────

BASE_URL = "https://www.workatastartup.com"
JOBS_URL = "https://www.workatastartup.com/jobs"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


# ── HELPERS ───────────────────────────────────────────────────────────────────

def extract_emails(text):
    pattern = r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"
    found = re.findall(pattern, text)
    junk = {"example.com", "test.com", "sentry.io", "domain.com", "wixpress.com"}
    return list({e.lower() for e in found if e.split("@")[-1] not in junk})


def guess_email(domain):
    if not domain:
        return []
    domain = domain.replace("https://","").replace("http://","").strip("/").split("/")[0]
    return [f"founders@{domain}", f"hello@{domain}", f"careers@{domain}", f"hr@{domain}"]


def infer_stage_from_batch(batch):
    """
    YC batch codes: W16, S24, F25 etc.
    W = Winter, S = Summer, F = Fall (newer format)
    Recent batch = early stage. Older = more grown.
    """
    try:
        year = int("20" + batch[1:])
        age = datetime.now().year - year
        if age <= 1:   return "Early Stage"
        elif age <= 3: return "Growing"
        else:          return "Scaling Up"
    except Exception:
        return "Unknown"


def get_page(url, retries=3):
    for attempt in range(retries):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            resp.raise_for_status()
            return BeautifulSoup(resp.text, "html.parser")
        except requests.RequestException as e:
            print(f"  Attempt {attempt+1} failed: {e}")
            time.sleep(2 ** attempt)
    return None


# ── COMPANY PAGE DEEP SCRAPE ──────────────────────────────────────────────────

def get_company_data(slug):
    """
    Fetch company data from YC public JSON endpoint — no login needed.
    e.g. https://www.ycombinator.com/companies/mason.json
    """
    result = {"emails": [], "website": "", "description": "", "location": "", "team_size": "", "founders": []}
    try:
        url = f"https://www.ycombinator.com/companies/{slug}.json"
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        match = re.search(r'data-page="(.+?)"(?:\s|>)', resp.text)
        if not match:
            return result
        raw = match.group(1).replace('&quot;', '"').replace('&amp;', '&').replace('&#39;', "'")
        data = json.loads(raw)
        company = data.get("props", {}).get("company", {})
        result["website"]     = company.get("website", "").rstrip("/")
        result["description"] = company.get("one_liner", "")[:250]
        result["location"]    = company.get("location", "")
        result["team_size"]   = str(company.get("team_size", ""))
        for f in company.get("founders", []):
            name = f.get("full_name", "")
            if name:
                result["founders"].append(name)
    except Exception as e:
        print(f"  Could not fetch YC data: {e}")
    time.sleep(0.5)
    return result


def smart_email_guesses(founders, domain):
    """Generate smart email guesses from founder names + domain."""
    if not domain:
        return []
    domain = domain.replace("https://","").replace("http://","").strip("/").split("/")[0]
    domain = re.sub(r"^www\.", "", domain)  # strip www. so emails look clean
    guesses = set()
    for prefix in ["founders", "hello", "careers", "hr"]:
        guesses.add(f"{prefix}@{domain}")
    for full_name in founders:
        parts = full_name.lower().split()
        if len(parts) >= 2:
            first, last = parts[0], parts[-1]
            guesses.add(f"{first}@{domain}")
            guesses.add(f"{first}{last}@{domain}")
            guesses.add(f"{first}.{last}@{domain}")
            guesses.add(f"{first[0]}{last}@{domain}")
            guesses.add(f"{first[0]}.{last}@{domain}")
    return sorted(guesses)


# ── PAGE PARSER ───────────────────────────────────────────────────────────────

def parse_page(soup):
    """
    Parse job listings from workatastartup.com

    Confirmed HTML structure:
      <div class="w-full bg-beige-lighter ... flex">          ← company block
        <a href="/companies/mason">...</a>                    ← logo link
        <div class="ml-5 my-auto grow">
          <div class="company-details text-lg">
            <a href="/companies/mason">
              <span class="font-bold">Mason (W16)</span>      ← company name + batch
              <span class="text-gray-600 ...">description</span>
            </a>
          </div>
          <div class="flex-none sm:flex mt-2 flex-wrap">
            <div class="job-name ...">
              <a data-jobid="..." href="...">Job Title</a>    ← role
            </div>
            <p class="job-details ...">
              <span>fulltime</span>
              <span>Seattle, WA</span>                        ← location
              <span>Backend</span>                            ← category
            </p>
          </div>
        </div>
      </div>
    """
    results = []

    # Each company block is a flex div with bg-beige-lighter
    company_blocks = soup.find_all("div", class_=re.compile(r"bg-beige-lighter"))

    for block in company_blocks:
        try:
            startup = {
                "company_name": "",
                "company_url":  "",
                "website":      "",
                "emails":       [],
                "email_guesses":[],
                "roles":        [],
                "job_urls":     [],
                "batch":        "",
                "funding_stage":"Unknown",
                "location":     "",
                "job_type":     "",
                "description":  "",
                "founders":     [],
                "source":       "Y Combinator",
                "scraped_at":   datetime.now().strftime("%Y-%m-%d %H:%M"),
            }

            # ── Company URL ───────────────────────────────────────────────
            company_link = block.find("a", href=re.compile(r"/companies/"))
            if company_link:
                href = company_link.get("href", "")
                startup["company_url"] = BASE_URL + href if href.startswith("/") else href

            # ── Company name + batch from font-bold span ──────────────────
            # e.g. "Mason (W16) " — we split out the batch
            bold_span = block.find("span", class_="font-bold")
            if bold_span:
                raw_name = bold_span.get_text(strip=True)
                # Extract batch like W16, S24 from name string
                batch_match = re.search(r"\(([WSF]\d{2})\)", raw_name)
                if batch_match:
                    startup["batch"] = batch_match.group(1)
                    startup["funding_stage"] = infer_stage_from_batch(startup["batch"])
                    # Clean company name — remove batch part
                    startup["company_name"] = re.sub(r"\s*\([WSF]\d{2}\)\s*", "", raw_name).strip()
                else:
                    startup["company_name"] = raw_name

            # ── Description ───────────────────────────────────────────────
            desc_span = block.find("span", class_=re.compile(r"text-gray-600"))
            if desc_span:
                startup["description"] = desc_span.get_text(strip=True)

            # ── All roles in this block ───────────────────────────────────
            job_divs = block.find_all("div", class_="job-name")
            for jd in job_divs:
                job_link = jd.find("a", attrs={"data-jobid": True})
                if job_link:
                    startup["roles"].append(job_link.get_text(strip=True))
                    startup["job_urls"].append(job_link.get("href", ""))

            # ── Location + job type from job-details ──────────────────────
            job_details = block.find("p", class_=re.compile(r"job-details"))
            if job_details:
                spans = job_details.find_all("span")
                texts = [s.get_text(strip=True) for s in spans if s.get_text(strip=True)]
                if texts:
                    startup["job_type"] = texts[0]           # e.g. "fulltime"
                if len(texts) > 1:
                    startup["location"] = texts[1]           # e.g. "Seattle, WA"

            # Skip blocks with no useful data
            if not startup["company_name"]:
                continue

            results.append(startup)

        except Exception as e:
            print(f"  Parse error: {e}")
            continue

    return results


# ── SCRAPE FLOW ───────────────────────────────────────────────────────────────

def scrape_jobs(keyword="", max_pages=3, deep=True):
    all_results = []
    seen = set()

    print(f"\nHireTrace - Scraping Y Combinator jobs...")
    if keyword:
        print(f"Filter: '{keyword}'")
    print()

    for page_num in range(1, max_pages + 1):
        url = f"{JOBS_URL}?page={page_num}"
        if keyword:
            url += f"&q={keyword.replace(' ', '+')}"

        print(f"Page {page_num}: {url}")
        soup = get_page(url)
        if not soup:
            break

        page_results = parse_page(soup)
        print(f"  Found {len(page_results)} companies")

        if not page_results:
            print("  No more results.")
            break

        for startup in page_results:
            cname = startup["company_name"]

            # Keyword filter
            if keyword:
                searchable = (cname + " " + startup["description"] + " " + " ".join(startup["roles"])).lower()
                if keyword.lower() not in searchable:
                    continue

            # Deduplicate
            if cname in seen:
                continue
            seen.add(cname)

            # Fetch company data from YC public JSON API
            if deep and startup["company_url"]:
                slug = startup["company_url"].rstrip("/").split("/")[-1]
                print(f"  Fetching: {startup['company_name']} (/{slug})...")
                yc_data = get_company_data(slug)
                startup["website"]   = yc_data["website"]
                startup["founders"]  = yc_data["founders"]
                if not startup["location"]:
                    startup["location"] = yc_data["location"]
                if not startup["description"]:
                    startup["description"] = yc_data["description"]

            # Smart email guesses from founder names + domain
            if startup.get("website"):
                domain = startup["website"].replace("https://","").replace("http://","").split("/")[0]
                startup["email_guesses"] = smart_email_guesses(startup.get("founders", []), domain)

            email_info = (
                f"{len(startup['emails'])} email(s)" if startup["emails"]
                else f"{len(startup['email_guesses'])} guess(es)"
            )
            roles_preview = ", ".join(startup["roles"][:2])
            print(f"  OK: {startup['company_name']} ({startup['batch']}) | {roles_preview} | {startup['funding_stage']} | {email_info}")
            all_results.append(startup)

        time.sleep(2)

    print(f"\nDone! {len(all_results)} unique startups.\n")
    return all_results


# ── EXPORT ───────────────────────────────────────────────────────────────────

def export_csv(data, filename):
    if not data:
        print("Nothing to export.")
        return
    import os; os.makedirs(os.path.dirname(filename), exist_ok=True) if os.path.dirname(filename) else None
    fields = ["company_name","website","emails","email_guesses","roles",
              "funding_stage","batch","location","job_type","description",
              "company_url","source","scraped_at"]
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in data:
            row = row.copy()
            row["emails"]        = ", ".join(row.get("emails", []))
            row["email_guesses"] = ", ".join(row.get("email_guesses", []))
            row["roles"]         = ", ".join(row.get("roles", []))
            row["job_urls"]      = ", ".join(row.get("job_urls", []))
            writer.writerow(row)
    print(f"Saved to {filename}")


def export_json(data, filename):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"Saved to {filename}")


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="HireTrace - YC Scraper")
    parser.add_argument("--keyword", type=str,  default="",           help="Filter keyword e.g. 'fintech'")
    parser.add_argument("--pages",   type=int,  default=3,            help="Pages to scrape (default: 3)")
    parser.add_argument("--output",  type=str,  default="../data/output/yc_results", help="Output filename (no extension)")
    parser.add_argument("--format",  choices=["csv","json","both"],    default="csv")
    parser.add_argument("--no-deep", action="store_true",             help="Skip deep scraping (faster, no emails)")
    args = parser.parse_args()

    results = scrape_jobs(keyword=args.keyword, max_pages=args.pages, deep=not args.no_deep)

    if not results:
        print("No results. Try without --keyword first.")
        return

    if args.format in ("csv","both"):
        export_csv(results, f"{args.output}.csv")
    if args.format in ("json","both"):
        export_json(results, f"{args.output}.json")

    print("── SUMMARY ──────────────────────────")
    print(f"  Startups       : {len(results)}")
    print(f"  Real emails    : {sum(1 for r in results if r['emails'])}")
    print(f"  Email guesses  : {sum(1 for r in results if r['email_guesses'])}")
    print(f"  Total roles    : {sum(len(r['roles']) for r in results)}")
    print("─────────────────────────────────────\n")


if __name__ == "__main__":
    main()