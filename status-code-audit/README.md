# 🚦 Status Code & Performance Audit Tool

This tool scans sitemaps and uses Playwright to audit all network resources (images, scripts, styles, etc.) for broken links (4xx/5xx errors), redirects (3xx), and performance bottlenecks.

## 🚀 Key Features

- **Recursive Sitemap Indexing**: Automatically parses sitemap indexes to find all child URLs.
- **Deep Resource Audit**: Monitors every single network request made by the page, catching broken assets that standard crawlers miss.
- **Performance Metrics**: Reports average page weight, load times, and flags slow-loading individual resources.
- **Premium Live UI**: Real-time progress bar with ETA, page rates, and dynamic status code counters.
- **Smart Filtering**: Generates clean reports by only logging pages that actually have issues.
- **Advanced Auth**: Supports cookies and basic authentication for protected environments.

---

### 🛠️ Installation

1. **Ensure Playwright is installed**:
   ```bash
   pip3 install playwright requests
   playwright install chromium
   ```

---

## 📖 Usage Commands

Always run the commands from the root directory using the virtual environment.

### 1. Basic Scan (from CLI)
```bash
./venv/bin/python3 status-code-audit/scan_status_codes.py https://example.com/sitemap.xml
```

### 2. Using Configuration File
Modify `status-code-audit/config.json` and run:
```bash
./venv/bin/python3 status-code-audit/scan_status_codes.py
```

### 3. Limited Performance Audit
Scan the first 10 pages and flag resources taking longer than 5 seconds:
```bash
./venv/bin/python3 status-code-audit/scan_status_codes.py --limit 10 --slow 5.0
```

---

## ⚙️ Configuration (`config.json`)

| Key | Description |
|-----|-------------|
| `"sitemaps"` | List of sitemap or sitemap index URLs to crawl. |
| `"max_workers"` | Number of parallel pages to scan (Default: 5). |
| `"slow_resource_threshold"` | Threshold in seconds to flag slow resources (Default: 3.0). |
| `"cookies"` | List of cookie objects (name, value, domain, path). |
| `"auth"` | Basic authentication string (`user:pass`). |
| `"headers"` | Custom headers like `User-Agent`. |

---

## 📂 Output Structure

- **`reports/session_YYYYMMDD_HHMMSS/`**:
  - `summary.md`: Human-readable summary with performance stats and 4xx/5xx lists.
  - `results.json`: Machine-readable data including 3xx redirects and full resource timing.

---

## ⚡ Speed Optimization

- **Worker Count**: Increase `--workers` to 10 or 15 on powerful machines to speed up large sitemap scans.
- **Slow Threshold**: Increase `--slow` if the environment is naturally high-latency to reduce "noise" in the reports.
