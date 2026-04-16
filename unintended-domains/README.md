# 🕵️ AEM Unintended Domains Audit Tool

This tool is designed to scan large Adobe Experience Manager (AEM) sites for "domain leaks"—instances where URLs from unexpected environments (like DevX or Stage) appear in the rendered markup of another environment (like Production or Preview).

## 🚀 Key Features

- **Client-Side Rendering**: Uses Playwright (Chromium) to ensure it catches leaks inside dynamic components like the Adobe Data Layer.
- **Cache-Aware Scanning**: Stores rendered HTML locally to allow near-instant re-scans when regex patterns are updated.
- **Smart Component Detection**: Pinpoints the exact AEM component (ID/Class) containing a leak.
- **Smart Screenshots**: Only takes visual screenshots for pages where a leak is actually found, saving time and disk space.
- **Sitemap Crawling**: Automatically discovers pages via standard AEM sitemaps with environment-domain replacement support.

---

## 🛠️ Installation

1. **Install Python dependencies**:
```bash
pip3 install playwright requests
```

2. **Install Chromium browser**:
```bash
playwright install chromium
```

---

## 📖 Usage Commands

Always run the commands from within the `unintended-domains/` folder.

### 1. Basic Scan
Runs a fresh scan against all URLs in the config/sitemaps.
```bash
python3 check_unintended_domains.py
```

### 2. Full Audit with Caching (Recommended)
Saves the rendered HTML so you can re-run analysis later without hitting the network.
```bash
python3 check_unintended_domains.py --cache
```

### 3. Fast Mode (Maximum Speed)
Blocks images, fonts, CSS, and heavy media to speed up the rendering process. Ideal for identifying leaks in markup and data layers.
```bash
python3 check_unintended_domains.py --fast --cache
```

### 4. Verbose Analysis
Shows real-time status symbols (✓ for clean, ✗ for leaks) and detailed redirect chains.
```bash
python3 check_unintended_domains.py --verbose --cache
```

---

## ⚙️ Configuration (`config.json`)

The `config.json` is the brain of the tool. Here is how to configure it:

| Key | Description |
|-----|-------------|
| `"sitemaps"` | List of AEM sitemap URLs to crawl. |
| `"urls"` | Specific individual URLs to scan regardless of sitemaps. |
| `"blacklisted_domains"` | Fragments of URLs that should NOT appear on the page (e.g., `www-devx.mandg.com`). |
| `"capture_screenshots"` | Enable (`true`) or Disable (`false`) visual evidence capture to save time/disk. |
| `"max_workers"` | Parallel chrome instances (Default: 15). Increase for faster scans on powerful machines. |
| `"timeouts.network_idle"` | Wait time for JS (Adobe Data Layer) to finish rendering (Default: 3s). Decrease for speed. |
| `"rate_limit.delay_ms"` | Delay between worker tasks. Set to `0` for maximum speed. |
| `"headers"` | Custom HTTP headers (API keys, Authorization, bypassing cache). |
| `"cookies"` | Specific cookies required to access the environment (e.g., `aemaacs-traffic`). |
| `"sitemap_domain_replace"` | Map internal sitemap URLs to a different testing domain. |

---

## ⚡ Speed Optimization Tips

- **Check network_idle**: If the environment is fast, reducing `timeouts.network_idle` in `config.json` to `1` or `2` seconds can shave minutes off the total runtime.
- **Use --fast**: This blocks non-essential resources like CSS and images, ensuring the browser only processes what is needed for domain detection.
- **Disable Screenshots**: Set `"capture_screenshots": false` if you only need the text report.
- **Persistent Cache**: Always use the `--cache` flag. Re-running a scan with updated blacklists takes seconds rather than hours if the HTML is already cached.

---

## 📂 Output Structure

- **`reports/session_YYYYMMDD_HHMMSS/`**: Contains the Markdown audit report.
- **`reports/.../screenshots/`**: Visual evidence of leaks with red banners and highlighted elements.
- **`cache/`**: (Ignored by Git) Stores MD5-hashed HTML files for super-fast re-scans.

---

## 💡 Troubleshooting Tips

- **Leaking JSON**: If a leak is found inside a JSON blob (like `data-cmp-data-layer`), the tool will report the specific attribute name.
- **404 Errors**: These are documented in a separate "Broken Links" section of the final report.
- **Scanning Local**: To apply new regex updates to old data without using the internet, simply run with `--cache`. It will process 1000+ pages from the disk in seconds.
