# 🔍 HireTrace

> Open source startup intelligence tool — find emails, open roles, and funding signals from startups worldwide.

Built by students, for students. Interns, job seekers, and developers welcome.

---

## What is HireTrace?

HireTrace scrapes publicly available startup data so you don't have to spend hours hunting for it manually. Enter a keyword or niche, and HireTrace pulls out:

- 📧 **Emails** — founder and team contact emails
- 💼 **Open Roles** — active job and internship vacancies
- 💰 **Budget Signals** — funding rounds, salary ranges, and hiring budget hints
- 🏢 **Startup Info** — company name, website, location, and stage

Focused heavily on **Indian startups** (Tracxn, Inc42, YourStory, Startup India) but works globally too.

---

## Why HireTrace?

Most tools like this are expensive, closed source, or locked behind paywalls. HireTrace is free, open, and community powered. If a scraper breaks, anyone can fix it. If a new source needs to be added, anyone can build it.

---

## Supported Sources

| Source | Region | Status |
|--------|--------|--------|
| Y Combinator Jobs | Global | ✅ Active |
| Wellfound (AngelList) | Global | ✅ Active |
| Inc42 | India | 🔧 In Progress |
| Tracxn | India | 🔧 In Progress |
| YourStory | India | 🔧 In Progress |
| Startup India Portal | India | 🔧 In Progress |
| IIT/IIM Incubator Pages | India | 📋 Planned |

---

## Tech Stack

- **Backend** — Python + FastAPI
- **Scraping** — Playwright + BeautifulSoup
- **Frontend** — Next.js
- **Database** — PostgreSQL
- **Export** — CSV, JSON, Google Sheets

---

## Project Structure

```
hiretrace/
├── README.md
├── LICENSE
├── requirements.txt
│
├── scrapers/           # One file per source
│   ├── ycombinator.py
│   ├── wellfound.py
│   ├── inc42.py
│   └── tracxn.py
│
├── core/               # Shared logic
│   ├── email_extractor.py
│   ├── budget_parser.py
│   └── exporter.py
│
├── api/                # FastAPI backend
│   └── main.py
│
├── frontend/           # Next.js dashboard
│
└── data/output/        # Scraped results land here
```

---

## Getting Started

```bash
# Clone the repo
git clone https://github.com/YOURUSERNAME/hiretrace.git
cd hiretrace

# Install dependencies
pip install -r requirements.txt

# Run your first scrape
python scrapers/ycombinator.py --keyword "fintech"

# Start the API
uvicorn api.main:app --reload
```

---

## Contributing

HireTrace lives and grows through contributors. Here's how you can help:

- 🐛 **Fix a broken scraper** — sites change their HTML all the time
- ➕ **Add a new source** — know a good startup directory? Build a scraper for it
- 🎨 **Improve the frontend** — make the dashboard cleaner and faster
- 📖 **Improve the docs** — help other students get started faster

To contribute, fork the repo, make your changes, and open a pull request. See [CONTRIBUTING.md](CONTRIBUTING.md) for details.

---

## Who is this for?

- 🎓 College students looking for startup internships
- 🔍 Job seekers targeting early stage companies
- 📬 Founders doing outreach and competitor research
- 🛠️ Developers who want to build on top of startup data

---

## License

MIT — free to use, modify, and distribute.

---

## Star the repo ⭐

If HireTrace helps you land an opportunity or saves you time, give it a star. It helps more students find the tool.

---

*Made with curiosity and too many cups of chai ☕*
