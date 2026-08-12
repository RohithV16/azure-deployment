#!/usr/bin/env python3
"""
Check HTML markup for unintended domains after client-side rendering.
Parses sitemap URLs, loads pages with Playwright, and detects blacklisted domains.
"""

import asyncio
import hashlib
import json
import re
import shutil
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse, quote

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
    seconds = max(0, int(seconds))
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def escape_md(value: str) -> str:
    if value is None:
        return ""
    safe = str(value).replace("\\", "\\\\").replace("|", "\\|").replace("`", "\\`")
    return safe.replace("\n", " ").replace("\r", " ").strip()


def truncate_text(value: str, max_len: int = 160) -> str:
    if value is None:
        return ""
    text = str(value)
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def render_progress(stats: dict, start_time: float):
    completed = stats.get("completed", 0)
    total = stats.get("total", 0)
    elapsed = time.monotonic() - start_time
    pct = (completed / total) if total else 0.0
    remaining = total - completed

    # Smooth ETA using a sliding rate window instead of point-in-time averages.
    now = time.monotonic()
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
    rate_per_min = rate_per_sec * 60
    if completed < 2 or elapsed < 1.0:
        rate_display = "--.-"
    elif rate_per_min > 9999:
        rate_display = "9999+"
    else:
        rate_display = f"{rate_per_min:5.1f}"

    term_width = shutil.get_terminal_size((120, 20)).columns
    bar_width = max(20, term_width)
    filled = int(bar_width * pct)
    bar = f"{'█' * filled}{'░' * (bar_width - filled)}"

    stats_line_plain = (
        f"LIVE {completed}/{total} ({pct * 100:5.1f}%)  "
        f"ELAPSED {format_duration(elapsed)}  ETA {eta_text}  "
        f"RATE {rate_display}/MIN  "
        f"OK {stats.get('ok', 0)}  FOUND {stats.get('found', 0)}  "
        f"FAILED {stats.get('failed', 0)}  404 {stats.get('not_found', 0)}  "
        f"CACHE {stats.get('cache_hits', 0)}"
    )
    if len(stats_line_plain) > term_width:
        stats_line_plain = stats_line_plain[: max(0, term_width - 3)] + "..."

    # Two-line layout:
    # 1) full-width bar
    # 2) telemetry text below
    # Keep cursor pinned to telemetry line for in-place redraw.
    if stats.get("_rendered_once"):
        prefix = "\x1b[1A\r"  # Move cursor up to bar line start
    else:
        prefix = "\r"
        stats["_rendered_once"] = True

    bar_line = f"{Colors.DIM}{bar}{Colors.RESET}"
    stats_line = (
        f"LIVE {completed}/{total} ({pct * 100:5.1f}%)  "
        f"ELAPSED {format_duration(elapsed)}  ETA {eta_text}  "
        f"RATE {rate_display}/MIN  "
        f"{Colors.SOFT_GREEN}OK {stats.get('ok', 0)}{Colors.RESET}  "
        f"{Colors.SOFT_RED}FOUND {stats.get('found', 0)}{Colors.RESET}  "
        f"{Colors.SOFT_RED}FAILED {stats.get('failed', 0)}{Colors.RESET}  "
        f"404 {stats.get('not_found', 0)}  CACHE {stats.get('cache_hits', 0)}"
    )

    if len(stats_line_plain) > term_width:
        stats_line = stats_line_plain

    output = f"{prefix}\x1b[2K{bar_line}\n\x1b[2K{stats_line}"
    print(output, end="", file=sys.stderr, flush=True)


def load_config(config_path: str, verbose: bool = False) -> dict:
    try:
        with open(config_path, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        print(
            f"{Colors.RED}Config file not found: {config_path}{Colors.RESET}",
            file=sys.stderr,
        )
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(
            f"{Colors.RED}Invalid JSON in config file: {e}{Colors.RESET}",
            file=sys.stderr,
        )
        sys.exit(1)


def parse_sitemap(url: str, config: dict, verbose: bool = False) -> list[str]:
    timeouts = config.get("timeouts", {})
    timeout = timeouts.get("sitemap_fetch", 30)
    headers = config.get("headers", {})

    cookies_config = config.get("cookies", [])

    try:
        session = requests.Session()
        session.headers.update(headers)
        for cookie in cookies_config:
            session.cookies.set(
                cookie["name"], cookie["value"], domain=cookie.get("domain")
            )

        response = session.get(url, timeout=timeout, allow_redirects=True)
        if verbose and len(response.history) > 0:
            print(
                f"{Colors.YELLOW}  -> Redirect chain: {Colors.RESET}",
                end="",
                file=sys.stderr,
            )
            for r in response.history:
                print(f" {r.status_code} ", end="", file=sys.stderr)
            print(f"-> {response.url}", file=sys.stderr)
        response.raise_for_status()
    except requests.RequestException as e:
        print(
            f"{Colors.RED}Failed to fetch sitemap {url}: {e}{Colors.RESET}",
            file=sys.stderr,
        )
        return []

    try:
        root = ET.fromstring(response.content)
        ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        urls = []
        mapping = config.get("sitemap_domain_replace", {})
        replace_from = mapping.get("from")
        replace_to = mapping.get("to")

        for loc in root.findall(".//sm:loc", ns):
            if loc.text:
                url_text = loc.text
                if replace_from and replace_to:
                    url_text = url_text.replace(replace_from, replace_to)
                urls.append(url_text)
        if not urls:
            for loc in root.findall(".//loc"):
                if loc.text:
                    url_text = loc.text
                    if replace_from and replace_to:
                        url_text = url_text.replace(replace_from, replace_to)
                    urls.append(url_text)
        return urls
    except ET.ParseError as e:
        print(
            f"{Colors.RED}Failed to parse sitemap {url}: {e}{Colors.RESET}",
            file=sys.stderr,
        )
        return []


async def get_rendered_html(
    page_url: str, page, config: dict, verbose: bool = False, cache_dir: Path = None, use_cache: bool = False
) -> tuple[str, bool, int, bool]:
    status_code = 0
    if use_cache and cache_dir:
        url_hash = hashlib.md5(page_url.encode()).hexdigest()
        cache_file = cache_dir / f"{url_hash}.html"
        meta_file = cache_dir / f"{url_hash}.json"
        
        # Check if cache is fresh (e.g., less than 24 hours old)
        if cache_file.exists() and meta_file.exists():
            try:
                with open(meta_file, "r") as f:
                    meta = json.load(f)
                    cached_at = datetime.fromisoformat(meta.get("timestamp", ""))
                    if datetime.now() - cached_at < timedelta(hours=24):
                        if verbose:
                            print(f"{Colors.CYAN}  -> Using cached HTML for {page_url}{Colors.RESET}", file=sys.stderr)
                        with open(cache_file, "r", encoding="utf-8") as f:
                            return f.read(), True, meta.get("status_code", 200), True
            except Exception as e:
                if verbose:
                    print(f"{Colors.YELLOW}  -> Cache read error: {e}{Colors.RESET}", file=sys.stderr)

    timeouts = config.get("timeouts", {})
    page_timeout = timeouts.get("page_load", 60) * 1000
    network_timeout = timeouts.get("network_idle", 30) * 1000

    max_retries = config.get("max_retries", 3)

    for attempt in range(max_retries):
        try:
            # Wait for DOM content to be loaded (faster than 'load' or 'networkidle')
            response = await page.goto(page_url, wait_until="domcontentloaded", timeout=page_timeout)
            status_code = response.status if response else 0

            # If it's a 404, we don't need to scroll or wait for stabilization
            if status_code == 404:
                html = await page.content()
                # Save to cache even for 404 (only if cache is enabled)
                if use_cache and cache_dir:
                    url_hash = hashlib.md5(page_url.encode()).hexdigest()
                    cache_dir.mkdir(parents=True, exist_ok=True)
                    with open(cache_dir / f"{url_hash}.html", "w", encoding="utf-8") as f:
                        f.write(html)
                    with open(cache_dir / f"{url_hash}.json", "w") as f:
                        json.dump({"url": page_url, "timestamp": datetime.now().isoformat(), "hash": url_hash, "status_code": 404}, f)
                return html, True, 404, False

            # Scroll to the bottom to trigger lazy loading of assets/components
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")

            # Allow additional time for client-side JS to finish
            # Using the 'network_idle' value from config as the delay in seconds
            # Cap it at 10s for sanity if not specified
            extra_wait = config.get("timeouts", {}).get("network_idle", 3)
            if extra_wait > 0:
                await asyncio.sleep(extra_wait)

            html = await page.content()
            
            # Save to cache if enabled
            if use_cache and cache_dir:
                try:
                    url_hash = hashlib.md5(page_url.encode()).hexdigest()
                    cache_dir.mkdir(parents=True, exist_ok=True)
                    with open(cache_dir / f"{url_hash}.html", "w", encoding="utf-8") as f:
                        f.write(html)
                    with open(cache_dir / f"{url_hash}.json", "w") as f:
                        json.dump({
                            "url": page_url,
                            "timestamp": datetime.now().isoformat(),
                            "hash": url_hash,
                            "status_code": status_code
                        }, f)
                except Exception as e:
                    if verbose:
                        print(f"{Colors.YELLOW}  -> Failed to save cache: {e}{Colors.RESET}", file=sys.stderr)

            if verbose and attempt > 0:
                print(
                    f"{Colors.GREEN}  -> Retry succeeded on attempt {attempt + 1}{Colors.RESET}",
                    file=sys.stderr,
                )
            return html, True, status_code, False
        except Exception as e:
            if verbose and attempt < max_retries - 1:
                wait_time = 2**attempt
                print(
                    f"{Colors.YELLOW}  -> Failed: {e}, retrying in {wait_time}s...{Colors.RESET}",
                    file=sys.stderr,
                )
                await asyncio.sleep(wait_time)
            elif attempt == max_retries - 1:
                print(
                    f"{Colors.RED}Failed to load {page_url} after {max_retries} attempts: {e}{Colors.RESET}",
                    file=sys.stderr,
                )

    return "", False, status_code, False


def find_unintended_domains(
    html: str, blacklist: list[str], page_url: str
) -> list[dict]:
    if not html:
        return []

    import re

    # Robust attribute value regex helper: handles quotes and spaces
    def attr_val_pattern(name):
        return re.compile(rf'{name}\s*=\s*(?:"([^"]*)"|\'([^\']*)\'|([^\s>]+))', re.IGNORECASE)

    patterns = {
        "src": attr_val_pattern("src"),
        "href": attr_val_pattern("href"),
        "xlink:href": attr_val_pattern("xlink:href"),
        "srcset": attr_val_pattern("srcset"),
        "data-src": attr_val_pattern("data-src"),
        "data-srcset": attr_val_pattern("data-srcset"),
        "data-href": attr_val_pattern("data-href"),
        "data-url": attr_val_pattern("data-url"),
        "data-cmp-data-layer": attr_val_pattern("data-cmp-data-layer"),
        "data-cmp-filereference": attr_val_pattern("data-cmp-filereference"),
        "data-cmp-src": attr_val_pattern("data-cmp-src"),
        "data-cmp-link": attr_val_pattern("data-cmp-link"),
        "data-content": attr_val_pattern("data-content"),
        "data-article": attr_val_pattern("data-article"),
        "data-config": attr_val_pattern("data-config"),
        "data-options": attr_val_pattern("data-options"),
        "data-dtm-data": attr_val_pattern("data-dtm-data"),
        "data-asset-id": attr_val_pattern("data-asset-id"),
        "data-asset-path": attr_val_pattern("data-asset-path"),
        "data-video-src": attr_val_pattern("data-video-src"),
        "action": attr_val_pattern("action"),
        "formaction": attr_val_pattern("formaction"),
        "content": attr_val_pattern("content"),
        "poster": attr_val_pattern("poster"),
        "data-poster": attr_val_pattern("data-poster"),
        "style": re.compile(r'url\(["\']?([^"\'\)]*)["\']?\)', re.IGNORECASE),
    }

    findings = []
    checked_values = set()
    captured_offsets = []  # Track found segments to avoid overlap

    for attr_name, pattern in patterns.items():
        for match in pattern.finditer(html):
            # Capture from any of the three possible matching groups (double/single/no quote)
            value = next((g for g in match.groups() if g is not None), "")
            
            if value in checked_values:
                continue
            checked_values.add(value)

            display_attr = attr_name
            # If it's a meta tag content attribute, try to get the property/name for clarity
            if attr_name == "content":
                tag_start = html.rfind('<', 0, match.start())
                if tag_start != -1:
                    next_gt = html.find('>', tag_start)
                    if next_gt != -1 and next_gt >= match.start():
                        tag_markup = html[tag_start : next_gt + 1]
                        if tag_markup.lower().startswith("<meta"):
                            meta_id_match = re.search(
                                r'(?:property|name|itemprop)\s*=\s*["\']?([^"\'\s>]+)["\']?',
                                tag_markup,
                                re.IGNORECASE,
                            )
                            if meta_id_match:
                                display_attr = f"meta[{meta_id_match.group(1)}]"

            for domain in blacklist:
                if domain.lower() in value.lower():
                    start = max(0, match.start() - 100)
                    end = min(len(html), match.end() + 100)
                    snippet = html[start:end].replace("\n", " ").strip()
                    findings.append(
                        {
                            "page_url": page_url,
                            "domain": domain,
                            "attribute": display_attr,
                            "url": value,
                            "snippet": snippet,
                        }
                    )
                    captured_offsets.append((match.start(), match.end()))
                    break

    # Final pass: check for any hardcoded domain matches in raw text/content
    # that weren't inside the attributes we checked
    for domain in blacklist:
        # Use a simpler regex for raw text search
        text_pattern = re.compile(re.escape(domain), re.IGNORECASE)
        for match in text_pattern.finditer(html):
            # Only add if this specific match wasn't already caught by an attribute check
            is_new = True
            for start, end in captured_offsets:
                if start <= match.start() <= end:
                    is_new = False
                    break

            if is_new:
                # context search for TEXT_CONTENT
                # Search backwards for the nearest tag start
                tag_context = "Unknown Component"
                tag_search_start = max(0, match.start() - 1000)
                preceding_html = html[tag_search_start : match.start()]
                
                # Look for last opening tag before the match
                last_tag_match = list(re.finditer(r'<([a-z0-9]+)[^>]*>', preceding_html, re.IGNORECASE))
                if last_tag_match:
                    tag_markup = last_tag_match[-1].group(0)
                    tag_name = last_tag_match[-1].group(1)
                    
                    # Extract ID and class for better context
                    id_match = re.search(r'id\s*=\s*["\']([^"\']+)["\']', tag_markup, re.IGNORECASE)
                    class_match = re.search(r'class\s*=\s*["\']([^"\']+)["\']', tag_markup, re.IGNORECASE)
                    
                    id_text = f"#{id_match.group(1)}" if id_match else ""
                    class_text = f".{class_match.group(1).replace(' ', '.')}" if class_match else ""
                    
                    if id_text or class_text:
                        tag_context = f"<{tag_name}{id_text}{class_text}>"
                    else:
                        tag_context = f"<{tag_name}>"

                start = max(0, match.start() - 100)
                end = min(len(html), match.end() + 100)
                snippet = html[start:end].replace("\n", " ").strip()
                findings.append(
                    {
                        "page_url": page_url,
                        "domain": domain,
                        "attribute": f"TEXT_CONTENT_NEAR_{tag_context}",
                        "url": domain,
                        "snippet": snippet,
                    }
                )
                # Avoid flooding with same domain in text, just one finding per page is usually enough
                # but let's keep it consistent. We add it to captured offsets.
                captured_offsets.append((match.start(), match.end()))

    return findings


def detect_redirection(html: str) -> dict | None:
    """Detects if a page is a redirection page based on HTML markup."""
    if not html:
        return None

    # 1. JS Redirect: window.location.href = '...' or location.replace('...')
    js_redirect = re.search(
        r'(?:window\.|document\.)?location\.(?:href|replace)\s*=\s*["\']([^"\']+)["\']',
        html,
        re.IGNORECASE,
    )
    if js_redirect:
        return {"type": "JS Redirect", "target": js_redirect.group(1)}

    # 2. Anchor tag redirect: "This page has moved to <a href="...">here</a>"
    # User mentioned "src in anchor tags", checking both href and src just in case
    anchor_redirect = re.search(
        r'moved\s+to\s+<a\s+[^>]*?(?:href|src)=["\']([^"\']+)["\']',
        html,
        re.IGNORECASE,
    )
    if anchor_redirect:
        return {"type": "Anchor Tag Redirect", "target": anchor_redirect.group(1)}

    return None


async def check_page(
    url: str,
    context,
    config: dict,
    blacklist: list[str],
    verbose: bool = False,
    screenshot_folder: str = None,
    fast_mode: bool = False,
    cache_dir: Path = None,
    use_cache: bool = False,
    capture_screenshots: bool = True,
) -> dict:
    page = None
    try:
        page = await context.new_page()

        if fast_mode:
            async def block_resources(route):
                # Blocking stylesheets as well in fast mode for maximum speed
                if route.request.resource_type in {"image", "media", "font", "stylesheet"}:
                    await route.abort()
                else:
                    await route.continue_()
            await page.route("**/*", block_resources)

        html, loaded, status_code, from_cache = await get_rendered_html(url, page, config, verbose, cache_dir, use_cache)

        if not loaded:
            return {
                "url": url,
                "status": "FAILED",
                "findings": [],
                "index": -1,
                "from_cache": False,
                "reason": "Page load failed after retries",
            }
        
        if status_code == 404:
            return {
                "url": url,
                "status": "404_NOT_FOUND",
                "findings": [],
                "index": -1,
                "from_cache": from_cache,
                "reason": "HTTP 404",
            }

        findings = find_unintended_domains(html, blacklist, url)
        redirection = detect_redirection(html)

        # Capture screenshot if findings found and screenshot folder provided and enabled
        screenshot_path = None
        if findings and screenshot_folder and capture_screenshots:
            # If we used the cache, the page is empty, so we MUST navigate now to take the screenshot
            if from_cache:
                if verbose:
                    print(f"{Colors.YELLOW}  -> Re-loading page for screenshot (leaks detected)...{Colors.RESET}", file=sys.stderr)
                try:
                    await page.goto(url, wait_until="load", timeout=30000)
                    # Scroll to bottom again for lazy loading
                    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    await asyncio.sleep(2) # Brief wait for stabilization
                except Exception as e:
                    if verbose:
                        print(f"{Colors.RED}  -> Failed to re-load for screenshot: {e}{Colors.RESET}", file=sys.stderr)
                    # We can still report the finding without the screenshot
            safe_filename = re.sub(r'[^a-zA-Z0-9]', '_', url)[:100]
            screenshot_path = f"{screenshot_folder}/{safe_filename}.png"

            # Inject a visible banner at the top of the page if findings exist
            # This ensures even invisible findings (meta tags) are captured in the picture
            try:
                findings_json = json.dumps([{"attr": f["attribute"], "val": f["url"]} for f in findings])
                await page.evaluate(f"""
                    () => {{
                        const findings = {findings_json};
                        const banner = document.createElement('div');
                        banner.id = 'unintended-domains-banner';
                        banner.style.backgroundColor = '#ff0000';
                        banner.style.color = 'white';
                        banner.style.padding = '15px';
                        banner.style.fontSize = '16px';
                        banner.style.fontFamily = 'monospace';
                        banner.style.borderBottom = '5px solid black';
                        banner.style.zIndex = '2147483647';
                        banner.style.position = 'relative';
                        banner.style.width = '100%';
                        banner.style.boxSizing = 'border-box';
                        
                        let html = '<h2 style="margin:0 0 10px 0; color: white;">⚠️ UNINTENDED DOMAINS FOUND!</h2>';
                        html += '<ul style="margin:0; padding-left:20px;">';
                        findings.forEach(f => {{
                            html += `<li><strong>${{f.attr}}:</strong> ${{f.val}}</li>`;
                        }});
                        html += '</ul>';
                        banner.innerHTML = html;
                        document.body.prepend(banner);
                    }}
                """)
            except Exception as e:
                if verbose:
                    print(f"  -> Warning: Could not inject banner: {e}", file=sys.stderr)

            # Highlight the elements containing blacklisted domains
            for finding in findings:
                attr = finding.get("attribute", "")
                found_domain = finding.get("domain", "")
                
                # Handle our special meta[...] naming for highlighting
                highlight_attr = "content" if attr.startswith("meta") else attr
                
                if highlight_attr not in ("TEXT_CONTENT", "style"):
                    # Try to highlight the element with this attribute
                    try:
                        await page.evaluate(f"""
                            () => {{
                                const elements = document.querySelectorAll('[{highlight_attr}*="{found_domain}"]');
                                elements.forEach(el => {{
                                    el.style.outline = '5px solid red';
                                    el.style.backgroundColor = 'rgba(255, 0, 0, 0.3)';
                                }});
                            }}
                        """)
                    except:
                        pass

            await page.screenshot(path=screenshot_path, full_page=True)

        return {
            "url": url,
            "status": "FOUND" if findings else "OK",
            "findings": findings,
            "redirection": redirection,
            "screenshot": screenshot_path,
            "index": -1,
            "from_cache": from_cache,
            "reason": "",
        }
    except Exception as e:
        print(f"{Colors.RED}Error checking {url}: {e}{Colors.RESET}", file=sys.stderr)
        return {
            "url": url,
            "status": "FAILED",
            "findings": [],
            "redirection": None,
            "index": -1,
            "from_cache": False,
            "reason": str(e),
        }
    finally:
        if page:
            await page.close()


def print_table(results: list[dict], total: int):
    print(f"\n{Colors.BOLD}{'=' * 60}{Colors.RESET}")
    print(f"{Colors.BOLD}{'Page URL':<50} {'Status':<10}{Colors.RESET}")
    print(f"{Colors.BOLD}{'=' * 60}{Colors.RESET}")

    for r in results:
        url_short = r["url"][:47] + "..." if len(r["url"]) > 50 else r["url"]
        if r["status"] == "FOUND":
            status = f"{Colors.RED}{r['status']}{Colors.RESET}"
        elif r["status"] == "FAILED":
            status = f"{Colors.YELLOW}{r['status']}{Colors.RESET}"
        else:
            status = f"{Colors.GREEN}{r['status']}{Colors.RESET}"

        print(f"{url_short:<50} {status}")

    print(f"{Colors.BOLD}{'=' * 60}{Colors.RESET}")

    found_count = sum(1 for r in results if r["status"] == "FOUND")
    failed_count = sum(1 for r in results if r["status"] == "FAILED")

    print(
        f"{Colors.CYAN}Scanned: {total} | Found: {found_count} | Failed: {failed_count}{Colors.RESET}\n"
    )


def generate_report(results: list[dict], all_findings: list[dict], output_dir: Path, config: dict):
    report_path = output_dir / "audit_report.md"
    run_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    total_pages = len(results)
    sorted_results = sorted(results, key=lambda r: r["url"])
    sorted_findings = sorted(
        all_findings,
        key=lambda f: (
            f.get("domain", ""),
            f.get("attribute", ""),
            f.get("page_url", ""),
            f.get("url", ""),
        ),
    )

    status_counts = {
        "OK": sum(1 for r in results if r["status"] == "OK"),
        "FOUND": sum(1 for r in results if r["status"] == "FOUND"),
        "FAILED": sum(1 for r in results if r["status"] == "FAILED"),
        "404_NOT_FOUND": sum(1 for r in results if r["status"] == "404_NOT_FOUND"),
    }

    found_pages = [r for r in sorted_results if r["status"] == "FOUND"]
    not_found_pages = [r for r in sorted_results if r["status"] == "404_NOT_FOUND"]
    failed_pages = [r for r in sorted_results if r["status"] == "FAILED"]
    redirect_pages = [r for r in sorted_results if r.get("redirection")]
    cache_hits = sum(1 for r in results if r.get("from_cache"))

    domain_summary = {}
    page_violation_counts = {}
    page_findings = {}
    unique_assets_total = set()

    for finding in sorted_findings:
        domain = finding["domain"]
        attr = finding["attribute"]
        page_url = finding["page_url"]
        asset_url = finding["url"]

        unique_assets_total.add(asset_url)

        if domain not in domain_summary:
            domain_summary[domain] = {"count": 0, "pages": set(), "assets": set(), "attrs": {}}
        domain_summary[domain]["count"] += 1
        domain_summary[domain]["pages"].add(page_url)
        domain_summary[domain]["assets"].add(asset_url)
        domain_summary[domain]["attrs"][attr] = domain_summary[domain]["attrs"].get(attr, 0) + 1

        page_violation_counts[page_url] = page_violation_counts.get(page_url, 0) + 1
        page_findings.setdefault(page_url, []).append(finding)

    top_impacted_pages = sorted(
        page_violation_counts.items(), key=lambda item: (-item[1], item[0])
    )

    max_pages = config.get("max_pages", -1)
    scan_limit = "Unlimited" if max_pages <= 0 else str(max_pages)

    sitemaps_count = len(config.get("sitemaps", []))
    direct_urls_count = len(config.get("urls", []))
    blacklist_count = len(config.get("blacklisted_domains", []))

    with open(report_path, "w", encoding="utf-8") as f:
        f.write("# Unintended Domain Audit Report\n\n")

        f.write("## Run Overview\n\n")
        f.write("| Key | Value |\n")
        f.write("|-----|-------|\n")
        f.write(f"| Run Timestamp | `{run_ts}` |\n")
        f.write(f"| Pages Scanned | {total_pages} |\n")
        f.write(f"| Sitemap Sources | {sitemaps_count} |\n")
        f.write(f"| Direct URLs | {direct_urls_count} |\n")
        f.write(f"| Blacklisted Domains | {blacklist_count} |\n")
        f.write(f"| Configured Scan Limit | {scan_limit} |\n")
        f.write(f"| Worker Count | {config.get('max_workers', 'N/A')} |\n")
        f.write(f"| Cache Hits | {cache_hits} |\n")
        f.write(f"| **Total Unique Assets Found** | **{len(unique_assets_total)}** |\n")
        f.write(f"| **Total Violations** | **{len(sorted_findings)}** |\n")
        f.write("\n---\n\n")

        f.write("## Scan Health\n\n")
        f.write("| Status | Count | Percent |\n")
        f.write("|--------|------:|--------:|\n")
        for status_key, label in [
            ("OK", "Clean (OK)"),
            ("FOUND", "Pages With Findings"),
            ("FAILED", "Failed Scans"),
            ("404_NOT_FOUND", "404 Not Found"),
        ]:
            count = status_counts[status_key]
            percent = (count / total_pages * 100) if total_pages else 0
            f.write(f"| {label} | {count} | {percent:5.1f}% |\n")
        f.write(f"| **Total Violations** | **{len(sorted_findings)}** | - |\n")
        f.write(f"| **Redirection Pages** | **{len(redirect_pages)}** | {(len(redirect_pages) / total_pages * 100) if total_pages else 0:5.1f}% |\n")
        f.write("\n---\n\n")

        f.write("## Findings Summary\n\n")
        if not sorted_findings:
            f.write("No unintended domain findings were detected.\n\n")
        else:
            f.write("| Blacklisted Domain | Unique Assets | Total Violations | Affected Pages |\n")
            f.write("|--------------------|--------------:|-----------------:|---------------:|\n")
            for domain in sorted(domain_summary.keys()):
                summary = domain_summary[domain]
                f.write(
                    f"| `{escape_md(domain)}` | {len(summary['assets'])} | {summary['count']} | {len(summary['pages'])} |\n"
                )

            for domain in sorted(domain_summary.keys()):
                f.write(f"\n### Domain: `{escape_md(domain)}`\n\n")
                f.write("| Attribute | Violations |\n")
                f.write("|-----------|-----------:|\n")
                for attr, count in sorted(
                    domain_summary[domain]["attrs"].items(),
                    key=lambda item: (-item[1], item[0]),
                ):
                    f.write(f"| `{escape_md(attr)}` | {count} |\n")
                f.write("\n")
        f.write("\n---\n\n")

        f.write("## Top Impacted Pages\n\n")
        if not top_impacted_pages:
            f.write("No impacted pages.\n")
        else:
            f.write("| Page URL | Violations |\n")
            f.write("|----------|-----------:|\n")
            for page_url, count in top_impacted_pages:
                f.write(f"| `{escape_md(page_url)}` | {count} |\n")
        f.write("\n---\n\n")

        f.write("## Detailed Findings\n\n")
        if not sorted_findings:
            f.write("No detailed findings to report.\n")
        else:
            for page_url in sorted(page_findings.keys()):
                findings = sorted(
                    page_findings[page_url],
                    key=lambda item: (
                        item.get("domain", ""),
                        item.get("attribute", ""),
                        item.get("url", ""),
                    ),
                )
                f.write(f"### `{escape_md(page_url)}`\n\n")
                f.write("| Domain | Attribute | Found URL | Snippet |\n")
                f.write("|--------|-----------|-----------|---------|\n")
                for finding in findings:
                    snippet = truncate_text(escape_md(finding.get("snippet", "")), 180)
                    found_url = truncate_text(escape_md(finding.get("url", "")), 120)
                    f.write(
                        f"| `{escape_md(finding.get('domain', ''))}` "
                        f"| `{escape_md(finding.get('attribute', ''))}` "
                        f"| `{found_url}` "
                        f"| `{snippet}` |\n"
                    )
                f.write("\n")
        f.write("\n---\n\n")

        f.write("## 404 Pages\n\n")
        if not not_found_pages:
            f.write("No 404 pages detected.\n")
        else:
            if len(not_found_pages) > 20:
                f.write("<details><summary>Expand 404 page list</summary>\n\n")
            f.write("| Page URL | Status |\n")
            f.write("|----------|--------|\n")
            for item in not_found_pages:
                f.write(f"| `{escape_md(item['url'])}` | 404 Not Found |\n")
            if len(not_found_pages) > 20:
                f.write("\n</details>\n")
        f.write("\n---\n\n")

        f.write("## Failed Scans\n\n")
        if not failed_pages:
            f.write("No failed scans detected.\n")
        else:
            if len(failed_pages) > 20:
                f.write("<details><summary>Expand failed scan list</summary>\n\n")
            f.write("| Page URL | Reason |\n")
            f.write("|----------|--------|\n")
            for item in failed_pages:
                reason = item.get("reason", "") or "Unknown"
                f.write(
                    f"| `{escape_md(item['url'])}` | `{truncate_text(escape_md(reason), 120)}` |\n"
                )
            if len(failed_pages) > 20:
                f.write("\n</details>\n")
        f.write("\n---\n\n")

        f.write("## Redirection Pages\n\n")
        if not redirect_pages:
            f.write("No redirection pages detected in the markup.\n")
        else:
            f.write("| Page URL | Status | Redirection Type | Target Destination |\n")
            f.write("|----------|--------|------------------|--------------------|\n")
            for r in redirect_pages:
                redir = r["redirection"]
                status = r.get("status", "OK")
                f.write(
                    f"| `{escape_md(r['url'])}` | {status} | {redir['type']} | `{escape_md(redir['target'])}` |\n"
                )
        f.write("\n---\n\n")

        f.write("## Visual Evidence\n\n")
        if not found_pages:
            f.write("No screenshots captured because no findings were detected.\n")
        else:
            f.write("> Collapsible full-page screenshots with highlighted findings.\n\n")
            evidence_count = 0
            for page in found_pages:
                if page.get("screenshot"):
                    evidence_count += 1
                    rel_ss = Path(page["screenshot"]).name
                    f.write(f"<details><summary>{escape_md(page['url'])}</summary>\n\n")
                    f.write(f"![Screenshot](screenshots/{rel_ss})\n\n")
                    f.write("</details>\n\n")
            if evidence_count == 0:
                f.write("No screenshots were captured for findings in this run.\n")

    print(f"{Colors.GREEN}Report generated: {report_path}{Colors.RESET}", file=sys.stderr)


async def main_async():
    import argparse

    parser = argparse.ArgumentParser(
        description="Check rendered HTML for unintended (blacklisted) domains"
    )
    parser.add_argument(
        "-c",
        "--config",
        default="config.json",
        help="Path to config JSON file (default: config.json)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose logging and table output",
    )
    parser.add_argument(
        "--fast",
        action="store_true",
        help="Enable fast mode (blocks images, media, and fonts to speed up loading)",
    )
    parser.add_argument(
        "--cache",
        action="store_true",
        help="Enable caching of rendered HTML in 'cache' folder",
    )
    args = parser.parse_args()

    # Detect script directory for relative path resolution
    script_dir = Path(__file__).parent.absolute()
    
    # Resolve config path
    config_path = args.config
    if not Path(config_path).is_absolute():
        config_path = script_dir / config_path

    config = load_config(str(config_path), args.verbose)
    sitemaps = config.get("sitemaps", [])
    blacklist = config.get("blacklisted_domains", [])
    max_pages = config.get("max_pages", -1)
    max_workers = config.get("max_workers", 4)
    direct_urls = config.get("urls", [])

    if not blacklist:
        print(
            f"{Colors.RED}No blacklisted domains in config{Colors.RESET}",
            file=sys.stderr,
        )
        sys.exit(1)

    # Combine direct URLs and sitemaps
    all_page_urls = []
    
    # Add direct URLs first
    if direct_urls:
        all_page_urls.extend(direct_urls)
        print(
            f"{Colors.CYAN}Using {len(direct_urls)} direct URL(s) from config{Colors.RESET}",
            file=sys.stderr,
        )

    # Add sitemap URLs if we haven't reached max_pages yet (treat 0 or -1 as unlimited)
    if sitemaps and (max_pages <= 0 or len(all_page_urls) < max_pages):
        print(f"{Colors.CYAN}Parsing sitemaps...{Colors.RESET}", file=sys.stderr)
        for sitemap_url in sitemaps:
            if max_pages > 0 and len(all_page_urls) >= max_pages:
                break
            urls = parse_sitemap(sitemap_url, config, args.verbose)
            all_page_urls.extend(urls)
            if args.verbose:
                print(
                    f"  -> Found {len(urls)} URLs from {sitemap_url}", file=sys.stderr
                )
    
    # Limit to max_pages only if it's a positive number
    if max_pages > 0:
        all_page_urls = all_page_urls[:max_pages]
        print(
            f"{Colors.YELLOW}Total scan limit: {max_pages} pages{Colors.RESET}",
            file=sys.stderr,
        )
    else:
        print(
            f"{Colors.YELLOW}Total scan limit: Unlimited{Colors.RESET}",
            file=sys.stderr,
        )


    if not all_page_urls:
        print(
            f"{Colors.RED}No page URLs found in sitemaps{Colors.RESET}", file=sys.stderr
        )
        sys.exit(1)

    total = len(all_page_urls)
    print(
        f"{Colors.CYAN}Checking {total} pages with {max_workers} workers...{Colors.RESET}",
        file=sys.stderr,
    )

    # Create session-specific folder in reports/
    session_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = script_dir / "reports" / f"session_{session_timestamp}"
    screenshot_folder = output_dir / "screenshots"
    screenshot_folder.mkdir(parents=True, exist_ok=True)
    print(
        f"{Colors.CYAN}Reports and screenshots: {output_dir}/{Colors.RESET}",
        file=sys.stderr,
    )

    # Initialize cache folder
    cache_dir = script_dir / "cache"
    if args.cache:
        cache_dir.mkdir(parents=True, exist_ok=True)
        print(
            f"{Colors.CYAN}Cache enabled. Using folder: {cache_dir}/{Colors.RESET}",
            file=sys.stderr,
        )

    results = []
    all_findings = []
    start_time = time.monotonic()
    progress_stats = {
        "completed": 0,
        "total": total,
        "ok": 0,
        "found": 0,
        "failed": 0,
        "not_found": 0,
        "cache_hits": 0,
    }

    # Get rate limit delay
    rate_limit_config = config.get("rate_limit", {})
    rate_delay_ms = rate_limit_config.get("delay_ms", 0)
    rate_delay = rate_delay_ms / 1000.0 if rate_delay_ms > 0 else 0

    async with async_playwright() as p:
        browser_config = config.get("browser", {})
        user_agent = browser_config.get(
            "user_agent",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        )
        viewport = browser_config.get("viewport", {"width": 1280, "height": 720})

        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent=user_agent, viewport=viewport)

        # Set custom headers from config if provided
        custom_headers = config.get("headers", {})
        if custom_headers:
            print(
                f"{Colors.CYAN}Applying {len(custom_headers)} custom header(s)...{Colors.RESET}",
                file=sys.stderr,
            )
            await context.set_extra_http_headers(custom_headers)

        # Set cookies from config
        cookies_config = config.get("cookies", [])
        if cookies_config:
            print(
                f"{Colors.CYAN}Setting {len(cookies_config)} cookie(s)...{Colors.RESET}",
                file=sys.stderr,
            )
            for cookie in cookies_config:
                await context.add_cookies([cookie])
                if args.verbose:
                    print(
                        f"  -> {cookie['name']}={cookie['value']} for {cookie['domain']}",
                        file=sys.stderr,
                    )

        semaphore = asyncio.Semaphore(max_workers)

        async def limited_check(url):
            async with semaphore:
                result = await check_page(
                    url, context, config, blacklist, args.verbose, screenshot_folder, args.fast, cache_dir, args.cache, config.get("capture_screenshots", True)
                )
                # Rate limiting delay
                if rate_delay > 0:
                    await asyncio.sleep(rate_delay)
                return result

        tasks = []
        for i, url in enumerate(all_page_urls):
            task = asyncio.create_task(limited_check(url))
            tasks.append(task)

        completed = 0
        last_progress_render = 0.0
        render_progress(progress_stats, start_time)
        for coro in asyncio.as_completed(tasks):
            result = await coro
            results.append(result)
            completed += 1
            progress_stats["completed"] = completed

            all_findings.extend(result["findings"])
            if result.get("redirection"):
                if args.verbose:
                    print(f"{Colors.YELLOW}  -> Detected redirection: {result['redirection']['type']} to {result['redirection']['target']}{Colors.RESET}", file=sys.stderr)
            
            if result["status"] == "OK":
                progress_stats["ok"] += 1
            elif result["status"] == "FOUND":
                progress_stats["found"] += 1
            elif result["status"] == "404_NOT_FOUND":
                progress_stats["not_found"] += 1
            else:
                progress_stats["failed"] += 1
            if result.get("from_cache"):
                progress_stats["cache_hits"] += 1

            if args.verbose:
                status_symbol = (
                    "✓"
                    if result["status"] == "OK"
                    else "✗"
                    if result["status"] == "FOUND"
                    else "!"
                )
                color = (
                    Colors.GREEN
                    if result["status"] == "OK"
                    else Colors.RED
                    if result["status"] == "FOUND"
                    else Colors.YELLOW
                )
                print(
                    f"[{completed}/{total}] {color}{status_symbol}{Colors.RESET} {result['url']}",
                    file=sys.stderr,
                )

            now = time.monotonic()
            if completed == total or (now - last_progress_render) >= 0.2:
                render_progress(progress_stats, start_time)
                last_progress_render = now

        print("", file=sys.stderr)
        print(
            f"{Colors.CYAN}Final scan stats: ok={progress_stats['ok']} "
            f"found={progress_stats['found']} failed={progress_stats['failed']} "
            f"404={progress_stats['not_found']} cache={progress_stats['cache_hits']}{Colors.RESET}",
            file=sys.stderr,
        )

        await browser.close()

    # Generate the Markdown report
    generate_report(results, all_findings, output_dir, config)

    if args.verbose:
        print_table(results, total)

    # Show screenshot paths for any findings
    screenshot_count = 0
    for r in results:
        if r["status"] == "FOUND" and r.get("screenshot"):
            screenshot_count += 1

    if all_findings:
        print(
            f"{Colors.RED}{Colors.BOLD}=== UNINTENDED DOMAINS FOUND ==={Colors.RESET}\n"
        )
        for f in all_findings:
            print(f"{Colors.RED}Page: {f['page_url']}{Colors.RESET}")
            print(f"{Colors.RED}Found: {f['domain']}{Colors.RESET}")
            if "attribute" in f:
                print(
                    f"{Colors.YELLOW}Attribute: {f['attribute']}={f.get('url', 'N/A')}{Colors.RESET}"
                )
            print(f"{Colors.CYAN}Markup: ...{f['snippet']}...{Colors.RESET}")
            # Show screenshot path if available
            for r in results:
                if r["url"] == f["page_url"] and r.get("screenshot"):
                    print(f"{Colors.YELLOW}Screenshot: {r['screenshot']}{Colors.RESET}")
                    break
            print("-" * 40)
        print(
            f"\n{Colors.RED}{Colors.BOLD}Total findings: {len(all_findings)}{Colors.RESET}"
        )
        print(f"{Colors.YELLOW}Exit code: 1 (findings detected){Colors.RESET}")
        print(f"{Colors.CYAN}Screenshots saved to: {screenshot_folder}/{Colors.RESET}")
        sys.exit(1)
    else:
        print(f"{Colors.GREEN}No unintended domains found.{Colors.RESET}")
        print(f"{Colors.YELLOW}Exit code: 0 (no findings){Colors.RESET}")
        sys.exit(0)


def main():
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
