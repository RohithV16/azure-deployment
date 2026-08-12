#!/usr/bin/env python3
"""
Scan a sitemap and report all resources (images, scripts, etc.) that return 4xx or 5xx status codes.
Uses Playwright to capture network activity during page load.
"""

import asyncio
import json
import os
import shutil
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import requests
from playwright.async_api import async_playwright

class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    CYAN = "\033[96m"
    SOFT_GREEN = "\033[32m"
    SOFT_RED = "\033[31m"
    DIM = "\033[2m"
    BOLD = "\033[1m"
    RESET = "\033[0m"

def format_duration(seconds: float) -> str:
    seconds = max(0, seconds)
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours > 0:
        return f"{int(hours):02d}:{int(minutes):02d}:{secs:06.3f}"
    return f"{int(minutes):02d}:{secs:06.3f}"

def render_progress(stats: dict, start_time: float):
    # Rate limit updates to 10Hz (once every 100ms) to prevent terminal flickering/glitching
    now = time.monotonic()
    last_update = stats.get("_last_render_time", 0)
    if now - last_update < 0.1:
        return
    stats["_last_render_time"] = now

    completed = stats.get("completed", 0)
    total = stats.get("total", 0)
    elapsed = now - start_time
    pct = (completed / total) if total else 0.0
    remaining = total - completed

    samples = stats.setdefault("_samples", [])
    samples.append((now, completed))
    window_seconds = 30.0
    while len(samples) > 2 and (now - samples[0][0]) > window_seconds:
        samples.pop(0)

    rate_per_sec = 0.0
    if len(samples) >= 2:
        delta_count = samples[-1][1] - samples[0][1]
        delta_time = samples[-1][0] - samples[0][0]
        if delta_count > 0 and delta_time > 0:
            rate_per_sec = delta_count / delta_time
    elif completed > 0 and elapsed > 0:
        rate_per_sec = completed / elapsed

    eta_text = "--:--"
    if rate_per_sec > 0:
        eta_text = format_duration(remaining / rate_per_sec)
    
    # Text segments
    info = f"LIVE {completed}/{total} ({pct*100:4.1f}%)"
    times = f"{format_duration(elapsed)} (ETA {eta_text})"
    
    codes = [f"2xx {stats.get('2xx', 0)}"]
    if stats.get("3xx", 0) > 0: codes.append(f"3xx {stats['3xx']}")
    if stats.get("4xx", 0) > 0 or stats.get("404", 0) > 0:
        codes.append(f"4xx {stats.get('4xx', 0) + stats.get('404', 0)}")
    if stats.get("5xx", 0) > 0: codes.append(f"5xx {stats['5xx']}")
    if stats.get("failed", 0) > 0: codes.append(f"FAIL {stats['failed']}")
    codes_str = " ".join(codes)

    # Calculate available width (with a safety margin of 5 chars)
    term_width = shutil.get_terminal_size((100, 20)).columns - 5
    text_len = len(info) + len(times) + len(codes_str) + 10 
    bar_width = max(5, term_width - text_len)
    
    filled = int(bar_width * pct)
    bar = f"[{'█' * filled}{'░' * (bar_width - filled)}]"
    
    # Assemble with colors
    colored_codes = codes_str.replace("2xx", f"{Colors.SOFT_GREEN}2xx").replace("3xx", f"{Colors.CYAN}3xx").replace("4xx", f"{Colors.SOFT_RED}4xx").replace("5xx", f"{Colors.SOFT_RED}5xx").replace("FAIL", f"{Colors.SOFT_RED}FAIL")
    colored_codes = colored_codes.replace(" ", f"{Colors.RESET} ") + Colors.RESET

    output = f"\r\x1b[2K{info} {Colors.DIM}{bar}{Colors.RESET} {times} | {colored_codes}"
    print(output, end="", file=sys.stderr, flush=True)

async def parse_sitemap(url: str, headers: dict = None, cookies: list = None, auth: dict = None) -> list[str]:
    """Fetch and parse a sitemap, recursing in parallel if it's a sitemapindex."""
    if headers is None:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
    
    # Convert Playwright-style cookies to requests-style if needed
    req_cookies = {}
    if cookies:
        for c in cookies:
            req_cookies[c['name']] = c['value']
            
    # Basic Auth
    req_auth = None
    if auth:
        req_auth = (auth.get("username"), auth.get("password"))

    print(f"{Colors.CYAN}Fetching sitemap: {url}{Colors.RESET}")
    try:
        # Fetch using a thread to avoid blocking the event loop
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None, 
            lambda: requests.get(url, headers=headers, cookies=req_cookies, auth=req_auth, timeout=30)
        )
        response.raise_for_status()
        root = ET.fromstring(response.content)
        
        ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        
        # Check if it's a sitemapindex
        if "sitemapindex" in root.tag:
            print(f"{Colors.YELLOW}Found sitemap index, parsing children in parallel...{Colors.RESET}")
            tasks = []
            for sitemap in root.findall('.//{http://www.sitemaps.org/schemas/sitemap/0.9}sitemap'):
                loc = sitemap.find('{http://www.sitemaps.org/schemas/sitemap/0.9}loc')
                if loc is not None:
                    tasks.append(parse_sitemap(loc.text.strip(), headers, cookies, auth))
            results = await asyncio.gather(*tasks)
            
            all_urls = []
            for sublist in results:
                all_urls.extend(sublist)
            return all_urls

        # Otherwise parse as a normal sitemap
        urls = []
        for loc in root.findall(".//sm:loc", ns) or root.findall(".//loc"):
            if loc.text:
                urls.append(loc.text.strip())
                    
        return urls
    except requests.exceptions.HTTPError as e:
        print(f"{Colors.RED}Failed to fetch sitemap {url}: {e}{Colors.RESET}")
        if e.response is not None:
            print(f"{Colors.DIM}Response Body: {e.response.text[:200]}...{Colors.RESET}")
        return []
    except Exception as e:
        print(f"{Colors.RED}Failed to parse sitemap {url}: {e}{Colors.RESET}")
        return []

async def worker(queue, context, semaphore, stats, start_time, all_results, slow_threshold):
    """Persistent worker that processes URLs from the queue."""
    while True:
        url = await queue.get()
        try:
            stats["current_page_requests"] = 0
            result = await check_page_resources(context, url, semaphore, stats, start_time, slow_threshold)
            all_results.append(result)
            
            stats["completed"] += 1
            if not result["success"]:
                stats["failed"] += 1
                
            render_progress(stats, start_time)
        except Exception as e:
            print(f"{Colors.RED}Worker error on {url}: {e}{Colors.RESET}")
        finally:
            queue.task_done()

async def check_page_resources(browser_context, page_url: str, semaphore: asyncio.Semaphore, stats: dict, start_time: float, slow_threshold: float = 3.0):
    # The semaphore is now handled by the worker queue concurrency, but kept for compatibility
    results = {
        "page_url": page_url,
        "page_title": "Unknown",
        "page_status": 0,
        "violations": [],
        "total_resources": 0,
        "total_weight_bytes": 0,
        "load_time_ms": 0,
        "slow_resources": [],
        "success": False,
        "error": None
    }
    
    page = await browser_context.new_page()
    start_nav = time.monotonic()
    
    def handle_response(response):
        if page.is_closed():
            return
            
        results["total_resources"] += 1
        
        # Track Weight
        try:
            content_length = response.headers.get("content-length")
            if content_length:
                size = int(content_length)
                results["total_weight_bytes"] += size
                stats["total_bytes"] += size
        except:
            pass
        
        # Track Granular Status Codes
        code = response.status
        stats["codes"] = stats.get("codes", {})
        stats["codes"][code] = stats["codes"].get(code, 0) + 1
        stats["current_page_requests"] = stats.get("current_page_requests", 0) + 1
        
        if 200 <= code < 300:
            stats["2xx"] = stats.get("2xx", 0) + 1
        elif 300 <= code < 400:
            stats["3xx"] = stats.get("3xx", 0) + 1
        elif code == 404:
            stats["404"] = stats.get("404", 0) + 1
        elif 400 <= code < 500:
            stats["4xx"] = stats.get("4xx", 0) + 1
        elif code >= 500:
            stats["5xx"] = stats.get("5xx", 0) + 1
        
        # Track timing
        timing = response.request.timing
        duration = timing.get("responseEnd", 0) - timing.get("requestStart", 0)
        if duration > (slow_threshold * 1000):
            results["slow_resources"].append({
                "url": response.url,
                "duration_ms": duration
            })
        
        # Update UI for every resource response
        render_progress(stats, start_time)

        if code >= 300:
            results["violations"].append({
                "url": response.url,
                "status": code,
                "status_text": response.status_text,
                "resource_type": response.request.resource_type
            })
        elif code == 200 and response.request.resource_type == "image":
            # Check for images that return 200 OK but are actually HTML error pages
            ctype = response.headers.get("content-type", "").lower()
            if ctype and "text/html" in ctype:
                results["violations"].append({
                    "url": response.url,
                    "status": 200,
                    "status_text": "CONTENT TYPE MISMATCH (Expected Image, got HTML)",
                    "resource_type": "image"
                })

    def handle_failed_request(request):
        # Prevent errors if page is already closing
        if page.is_closed():
            return
            
        # Capture blocked or failed requests (CORS, DNS, etc.)
        error_msg = request.failure if request.failure else "Unknown Browser Error"
        results["violations"].append({
            "url": request.url,
            "status": 0,
            "status_text": f"FAILED: {error_msg}",
            "resource_type": request.resource_type
        })
        stats["failed"] = stats.get("failed", 0) + 1
        stats["codes"]["FAILED"] = stats["codes"].get("FAILED", 0) + 1
        render_progress(stats, start_time)

    page.on("response", handle_response)
    page.on("requestfailed", handle_failed_request)
    
    try:
        # Navigation with retry logic
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = await page.goto(page_url, wait_until="load", timeout=60000)
                results["page_status"] = response.status if response else 0
                
                if results["page_status"] >= 500 and attempt < max_retries - 1:
                    raise Exception(f"Server error {results['page_status']}")
                
                break # Success
            except Exception as e:
                if attempt == max_retries - 1:
                    raise e
                wait = (attempt + 1) * 2
                await asyncio.sleep(wait)

        results["load_time_ms"] = int((time.monotonic() - start_nav) * 1000)
        results["total_resources"] = stats.get("current_page_requests", 0)
        try:
            results["page_title"] = await page.title()
        except:
            pass
            
        # Check for visual rendering failures (naturalWidth === 0)
        # This catches images that return 200 OK but are technically broken/empty
        visual_broken_images = await page.evaluate("""() => {
            return Array.from(document.querySelectorAll('img'))
                .filter(img => {
                    // Filter out tiny tracking pixels (1x1) which are intentional
                    const isTracker = img.naturalWidth <= 1 && img.naturalHeight <= 1;
                    return img.complete && img.naturalWidth === 0 && !isTracker;
                })
                .map(img => img.src);
        }""")
        
        for img_src in visual_broken_images:
            # Avoid duplicate logs if already flagged by header check
            if not any(v["url"] == img_src for v in results["violations"]):
                results["violations"].append({
                    "url": img_src,
                    "status": 200,
                    "status_text": "VISUAL FAILURE (Rendered as 0px)",
                    "resource_type": "image"
                })

        results["success"] = True
        await asyncio.sleep(1)
    except Exception as e:
        results["error"] = str(e)
    finally:
        await page.close()
        
    return results



def generate_reports(all_results: list[dict], stats: dict, output_dir: Path):
    # Filter: Only log pages with violations, slow resources, or errors
    results_to_log = [r for r in all_results if r["violations"] or r["slow_resources"] or not r["success"]]
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_dir = output_dir / f"session_{timestamp}"
    report_dir.mkdir(parents=True, exist_ok=True)
    
    # Global Issue Tracking (Deduplication)
    global_broken = {} # url -> {type, status, pages: [{title, url}]}
    for r in all_results:
        for v in r["violations"]:
            # Capture 4xx/5xx AND suspicious 200s (Visual/Content mismatch)
            is_suspicious_200 = (v["status"] == 200 and ("MISMATCH" in v["status_text"] or "VISUAL" in v["status_text"]))
            if v["status"] >= 400 or is_suspicious_200 or v["status"] == 0:
                url = v["url"]
                if url not in global_broken:
                    global_broken[url] = {"type": v["resource_type"], "status": v["status"], "pages": []}
                # Avoid duplicate pages for same asset on same page
                if not any(p["url"] == r["page_url"] for p in global_broken[url]["pages"]):
                    global_broken[url]["pages"].append({"title": r["page_title"], "url": r["page_url"]})

    # JSON Report
    with open(report_dir / "results.json", "w") as f:
        json.dump(results_to_log, f, indent=2)
        
    total_pages = len(all_results)
    failed_pages = [r for r in all_results if not r["success"]]
    
    def is_violation(v):
        return v["status"] >= 400 or v["status"] == 0 or "MISMATCH" in v["status_text"] or "VISUAL" in v["status_text"]
        
    pages_with_violations = [r for r in all_results if any(is_violation(v) for v in r["violations"])]
    total_violations_count = sum(len([v for v in r["violations"] if is_violation(v)]) for r in all_results)
    
    # Performance stats
    avg_weight = sum(r["total_weight_bytes"] for r in all_results) / total_pages / 1024 if total_pages else 0
    avg_load_time = sum(r["load_time_ms"] for r in all_results) / total_pages if total_pages else 0
    slow_pages = [r for r in all_results if r["slow_resources"]]
    
    health_score = 100.0
    if total_pages > 0:
        # Simple health score: pages without critical violations / total pages
        clean_pages = total_pages - len(pages_with_violations)
        health_score = (clean_pages / total_pages) * 100

    # --- Generate summary.md ---
    md_path = report_dir / "summary.md"
    with open(md_path, "w") as f:
        f.write(f"# 🚦 Status Code Audit Report\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        f.write("## 📊 Executive Summary\n\n")
        f.write(f"| Metric | Status | Value |\n|--------|:---:|-------|\n")
        f.write(f"| **Total Pages Scanned** | 🔍 | {total_pages} |\n")
        f.write(f"| **Broken Resources (4xx/5xx)** | ❌ | {total_violations_count} |\n")
        f.write(f"| **Unique Broken Assets** | 🧩 | {len(global_broken)} |\n")
        f.write(f"| **Failed Page Loads** | ⚠️ | {len(failed_pages)} |\n")
        f.write(f"| **Average Page Weight** | ⚖️ | {avg_weight:.1f} KB |\n")
        f.write(f"| **Health Score** | 📈 | **{health_score:.1f}%** |\n\n")
        
        if global_broken:
            f.write("--- \n\n")
            f.write("## 🛠️ Unique Errors (Grouped by Resource)\n")
            f.write("Each unique broken resource and the specific pages it affects.\n\n")
            
            # Sort by occurrence count
            sorted_broken = sorted(global_broken.items(), key=lambda x: len(x[1]["pages"]), reverse=True)
            for url, data in sorted_broken:
                status_label = f"[{data['status']}]" if data['status'] != 0 else "[FAILED]"
                icon = "❌" if data['status'] >= 400 or data['status'] == 0 else "🚫"
                f.write(f"### {icon} {status_label} {Path(urlparse(url).path).name or 'Asset'}\n")
                f.write(f"**Resource URL:** {url}\n\n")
                f.write(f"**Affected Pages ({len(data['pages'])}):**\n")
                for p in data['pages']:
                    f.write(f"- [{p['title']}]({p['url']})\n")
                f.write("\n---\n\n")

        # Detailed Page Breakdown
        md_results = [r for r in all_results if not r["success"] or any(is_violation(v) for v in r["violations"]) or r["slow_resources"]]

        if md_results:
            f.write("## 📄 Detailed Findings by Page\n\n")
            for r in md_results:
                status_icon = "❌" if not r["success"] else "⚠️"
                f.write(f"### {status_icon} {r['page_title']}\n")
                f.write(f"- **URL:** [{r['page_url']}]({r['page_url']})\n")
                
                if r["error"]:
                    f.write(f"- **Critical Error:** `{r['error']}`\n")
                
                # Group violations by type
                v_issues = [v for v in r["violations"] if is_violation(v)]
                if v_issues:
                    f.write("- **Broken Resources:**\n")
                    for v in v_issues:
                        status_display = f"[{v['status']}]" if "VISUAL" not in v['status_text'] else "[RENDER ERROR]"
                        f.write(f"  - `{status_display}` {v['url']}\n")

                if r["slow_resources"]:
                    f.write("- **Slow Resources (> {stats.get('slow_threshold', 3)}s):**\n")
                    for s in r["slow_resources"]:
                        f.write(f"  - `{s['duration_ms']/1000:.1f}s` {s['url']}\n")
                f.write("\n")
        else:
            f.write("No major issues detected across all scanned pages.\n")

    # --- Generate summary.txt ---
    txt_path = report_dir / "summary.txt"
    with open(txt_path, "w") as f:
        f.write(f"# 🚦 Status Code Audit Report\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        f.write("## 📊 Executive Summary\n\n")
        f.write(f"| Metric | Status | Value |\n")
        f.write(f"| :--- | :---: | :--- |\n")
        f.write(f"| Total Pages Scanned | 🔍 | {total_pages} |\n")
        f.write(f"| Broken Resources (4xx/5xx) | ❌ | {total_violations_count} |\n")
        f.write(f"| Unique Broken Assets | 🧩 | {len(global_broken)} |\n")
        f.write(f"| Failed Page Loads | ⚠️ | {len(failed_pages)} |\n")
        f.write(f"| Average Page Weight | ⚖️ | {avg_weight:.1f} KB |\n")
        f.write(f"| Health Score | 📈 | {health_score:.1f}% |\n\n")
        
        if global_broken:
            f.write("---\n\n")
            f.write("## 🛠️ Unique Errors (Grouped by Resource)\n\n")
            sorted_broken = sorted(global_broken.items(), key=lambda x: len(x[1]["pages"]), reverse=True)
            for url, data in sorted_broken:
                status_label = f"[{data['status']}]" if data['status'] != 0 else "[FAILED]"
                f.write(f"### {status_label} {Path(urlparse(url).path).name or 'Asset'}\n")
                f.write(f"Resource URL: {url}\n")
                f.write(f"Affected Pages ({len(data['pages'])}):\n")
                for p in data['pages']:
                    f.write(f"- {p['title']}: {p['url']}\n")
                f.write("\n---\n\n")

        if md_results:
            f.write("## 📄 Detailed Findings by Page\n\n")
            for r in md_results:
                f.write(f"### ⚠️ {r['page_title']}\n")
                f.write(f"- URL: {r['page_url']}\n")
                
                v_issues = [v for v in r["violations"] if is_violation(v)]
                if v_issues:
                    f.write("- Issues Found: {len(v_issues)} Errors\n")
                    for v in v_issues:
                        status_display = f"[{v['status']}]" if "VISUAL" not in v['status_text'] else "[RENDER ERROR]"
                        f.write(f"  - {status_display} {v['url']}\n")
                f.write("\n")

    print(f"\n\n{Colors.GREEN}Reports generated in: {report_dir}{Colors.RESET}")
    print(f"Summary (MD): {md_path}")
    print(f"Summary (TXT): {txt_path}")


async def main():
    import argparse
    parser = argparse.ArgumentParser(description="Scan sitemap for 4xx/5xx errors using Playwright.")
    parser.add_argument("sitemap_url", nargs="?", help="URL of the sitemap.xml")
    parser.add_argument("--workers", type=int, default=5, help="Number of concurrent pages to scan")
    parser.add_argument("--output", default="status-code-audit/reports", help="Output directory for reports")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of pages to scan (0 for all)")
    parser.add_argument("--cookies", help="Path to JSON file with cookies")
    parser.add_argument("--auth", help="Basic auth credentials (user:password)")
    parser.add_argument("--slow", type=float, default=3.0, help="Slow resource threshold in seconds")
    parser.add_argument("--config", default="status-code-audit/config.json", help="Path to config JSON file")
    
    args = parser.parse_args()
    
    # Load config if it exists
    config_data = {}
    if os.path.exists(args.config):
        try:
            with open(args.config, "r") as f:
                config_data = json.load(f)
        except Exception as e:
            print(f"{Colors.YELLOW}Warning: Could not read config file {args.config}: {e}{Colors.RESET}")

    # Merge CLI args with config (CLI takes precedence)
    sitemap_arg = args.sitemap_url
    sitemap_list = config_data.get("sitemaps", [])
    
    if sitemap_arg:
        # If CLI arg provided, use it as the primary sitemap
        target_sitemaps = [sitemap_arg]
    elif sitemap_list:
        # If no CLI arg but config has a list, use the list
        target_sitemaps = sitemap_list
    elif config_data.get("sitemap_url"):
        # Fallback to single sitemap_url in config
        target_sitemaps = [config_data["sitemap_url"]]
    else:
        print(f"{Colors.RED}Error: No sitemap URL provided (via CLI or config).{Colors.RESET}")
        sys.exit(1)
        
    worker_count = args.workers if args.workers != 5 else config_data.get("max_workers", 5)
    limit = args.limit if args.limit != 0 else config_data.get("limit", 0)
    slow_threshold = args.slow if args.slow != 3.0 else config_data.get("slow_resource_threshold", 3.0)
    output_dir = args.output if args.output != "status-code-audit/reports" else config_data.get("output_dir", "status-code-audit/reports")
    
    # Load cookies if provided
    cookies = []
    cookie_path = args.cookies or config_data.get("cookies_path")
    if cookie_path:
        try:
            with open(cookie_path, "r") as f:
                cookies = json.load(f)
        except Exception as e:
            if not isinstance(cookie_path, list): # Support inline list in config
                print(f"{Colors.RED}Failed to load cookies from {cookie_path}: {e}{Colors.RESET}")
    
    if not cookies and isinstance(config_data.get("cookies"), list):
        cookies = config_data["cookies"]

    # Basic Auth setup
    auth_str = args.auth or config_data.get("auth")
    http_credentials = None
    if auth_str and ":" in auth_str:
        user, password = auth_str.split(":", 1)
        http_credentials = {"username": user, "password": password}

    # Aggregate all URLs from all sitemaps (using cookies)
    urls = []
    config_headers = config_data.get("headers", {})
    for s_url in target_sitemaps:
        s_urls = await parse_sitemap(s_url, headers=config_headers, cookies=cookies, auth=http_credentials)
        urls.extend(s_urls)

    if not urls:
        print(f"{Colors.RED}No URLs found in sitemap. Exiting.{Colors.RESET}")
        return

    if limit > 0:
        urls = urls[:limit]
        print(f"{Colors.YELLOW}Limited scan to {limit} pages.{Colors.RESET}")

    total_urls = len(urls)
    print(f"{Colors.GREEN}Found {total_urls} URLs to scan.{Colors.RESET}")
    
    start_time = time.monotonic()
    
    stats = {
        "completed": 0,
        "total": total_urls,
        "2xx": 0,
        "3xx": 0,
        "404": 0,
        "4xx": 0,
        "5xx": 0,
        "failed": 0,
        "total_bytes": 0,
        "codes": {}, # Granular tracking: code -> count
        "current_page_requests": 0
    }

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=config_data.get("headers", {}).get("User-Agent", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"),
            http_credentials=http_credentials,
            # Performance optimizations
            service_workers="block",
            geolocation={"latitude": 0, "longitude": 0},
            permissions=[]
        )
        if cookies:
            await context.add_cookies(cookies)
        
        # Create URL queue
        queue = asyncio.Queue()
        for url in urls:
            await queue.put(url)
            
        all_results = []
        render_progress(stats, start_time)
        
        # Start worker tasks
        semaphore = asyncio.Semaphore(worker_count) 
        workers = [
            asyncio.create_task(worker(queue, context, semaphore, stats, start_time, all_results, slow_threshold))
            for _ in range(worker_count)
        ]
        
        # Wait for all URLs to be processed
        await queue.join()
        
        # Cancel worker tasks
        for w in workers:
            w.cancel()
        
        await asyncio.gather(*workers, return_exceptions=True)
        await browser.close()
        
    duration = time.monotonic() - start_time
    # Clear the progress line before showing final result
    print("\n", file=sys.stderr)
    print(f"{Colors.BOLD}Scan completed in {format_duration(duration)}{Colors.RESET}")
    
    generate_reports(all_results, stats, Path(args.output))

if __name__ == "__main__":
    asyncio.run(main())
