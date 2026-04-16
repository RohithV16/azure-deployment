#!/usr/bin/env python3
"""
Cross-browser console log audit tool.

Hybrid strategy:
- Prefer real browser runs (Selenium): Safari, Chrome, Edge, Firefox.
- Fall back to Playwright engines when real browser startup fails (optional).
"""

import argparse
import asyncio
import json
import shutil
import sys
import time
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import requests

try:
    from selenium import webdriver
    from selenium.common.exceptions import WebDriverException
except Exception:  # pragma: no cover - optional dependency path during setup
    webdriver = None
    WebDriverException = Exception

try:
    from playwright.async_api import async_playwright
except Exception:  # pragma: no cover - optional dependency path during setup
    async_playwright = None


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


SUPPORTED_BROWSERS = ["safari", "chrome", "edge", "firefox"]
LEVEL_MAP = {
    "error": "error",
    "warning": "warning",
    "warn": "warning",
    "info": "info",
    "log": "log",
    "debug": "debug",
}

FALLBACK_ENGINE_MAP = {
    "safari": "webkit",
    "chrome": "chromium",
    "edge": "chromium",
    "firefox": "firefox",
}


SELENIUM_CONSOLE_HOOK = r"""
(() => {
  if (window.__consoleAuditInstalled) return true;
  window.__consoleAuditInstalled = true;
  window.__consoleAuditEvents = window.__consoleAuditEvents || [];

  function push(level, args) {
    try {
      const parts = [];
      for (const a of args) {
        try {
          if (typeof a === 'string') parts.push(a);
          else parts.push(JSON.stringify(a));
        } catch {
          parts.push(String(a));
        }
      }
      window.__consoleAuditEvents.push({
        level,
        message: parts.join(' '),
        source_url: '',
        line: 0,
        column: 0,
        stack: '',
        timestamp: new Date().toISOString()
      });
    } catch (_) {}
  }

  const methods = ['error', 'warn', 'info', 'log', 'debug'];
  for (const method of methods) {
    if (typeof console[method] !== 'function') continue;
    const original = console[method].bind(console);
    console[method] = (...args) => {
      push(method, args);
      return original(...args);
    };
  }
  return true;
})();
"""

SELENIUM_ONETRUST_DISMISS = r"""
(() => {
  try {
    const btn = document.querySelector('#onetrust-accept-btn-handler');
    if (btn) {
      btn.click();
    }
    const styleId = '__console_audit_ot_hide__';
    if (!document.getElementById(styleId)) {
      const st = document.createElement('style');
      st.id = styleId;
      st.textContent = '#onetrust-consent-sdk, #onetrust-banner-sdk, .cookie-banner { display: none !important; }';
      document.head.appendChild(st);
    }
    return true;
  } catch (_) {
    return false;
  }
})();
"""


def format_duration(seconds: float) -> str:
    seconds = max(0, int(seconds))
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def load_config(config_path: Path) -> dict:
    try:
        return json.loads(config_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(f"{Colors.RED}Config file not found: {config_path}{Colors.RESET}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"{Colors.RED}Invalid JSON in config: {e}{Colors.RESET}", file=sys.stderr)
        sys.exit(1)


def parse_sitemap(url: str, config: dict, verbose: bool = False) -> list[str]:
    timeout = config.get("timeouts", {}).get("sitemap_fetch", 30)
    headers = config.get("headers", {})
    cookies = config.get("cookies", [])

    session = requests.Session()
    session.headers.update(headers)
    sitemap_host = (urlparse(url).hostname or "").lower()
    for cookie in cookies:
        name = cookie.get("name")
        value = cookie.get("value")
        if not name or value is None:
            continue
        cdom = cookie.get("domain")
        if cdom and domain_matches(sitemap_host, cdom):
            session.cookies.set(name, value, domain=cdom)
        else:
            # Host-scoped fallback for sitemap fetch.
            session.cookies.set(name, value)

    try:
        response = session.get(url, timeout=timeout, allow_redirects=True)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"{Colors.RED}Failed to fetch sitemap {url}: {e}{Colors.RESET}", file=sys.stderr)
        return []

    mapping = config.get("sitemap_domain_replace", {})
    replace_from = mapping.get("from")
    replace_to = mapping.get("to")

    try:
        root = ET.fromstring(response.content)
    except ET.ParseError as e:
        print(f"{Colors.RED}Failed to parse sitemap {url}: {e}{Colors.RESET}", file=sys.stderr)
        return []

    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    urls = []

    loc_nodes = root.findall(".//sm:loc", ns) or root.findall(".//loc")
    for loc in loc_nodes:
        if not loc.text:
            continue
        value = loc.text.strip()
        if replace_from and replace_to:
            value = value.replace(replace_from, replace_to)
        urls.append(value)

    if verbose:
        print(f"{Colors.CYAN}Sitemap {url}: {len(urls)} URL(s){Colors.RESET}", file=sys.stderr)
    return urls


def build_url_list(config: dict, verbose: bool = False) -> list[str]:
    urls = list(config.get("urls", []))
    sitemaps = config.get("sitemaps", [])
    max_pages = config.get("max_pages", -1)

    if sitemaps and (max_pages <= 0 or len(urls) < max_pages):
        for sitemap_url in sitemaps:
            if max_pages > 0 and len(urls) >= max_pages:
                break
            urls.extend(parse_sitemap(sitemap_url, config, verbose))

    if max_pages > 0:
        urls = urls[:max_pages]

    seen = set()
    deduped = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            deduped.append(u)
    return deduped


def enabled_levels(config: dict, cli_levels: str | None) -> set[str]:
    if cli_levels:
        levels = {LEVEL_MAP.get(x.strip().lower(), x.strip().lower()) for x in cli_levels.split(",") if x.strip()}
        return {l for l in levels if l in {"error", "warning", "info", "log", "debug"}}

    ca = config.get("console_audit", {})
    result = set()
    if ca.get("log_error", True):
        result.add("error")
    if ca.get("log_warning", True):
        result.add("warning")
    if ca.get("log_info", False):
        result.add("info")
    if ca.get("log_log", False):
        result.add("log")
    if ca.get("log_debug", False):
        result.add("debug")
    return result


def normalize_level(level: str) -> str:
    if not level:
        return "log"
    return LEVEL_MAP.get(level.lower(), level.lower())


def normalize_same_site(value) -> str | None:
    if value is None:
        return None
    norm = str(value).strip().lower()
    if norm == "none":
        return "None"
    if norm == "lax":
        return "Lax"
    if norm == "strict":
        return "Strict"
    return None


def normalize_event(event: dict, browser: str, mode: str, page_url: str) -> dict:
    return {
        "browser": browser,
        "mode": mode,
        "level": normalize_level(str(event.get("level", "log"))),
        "message": str(event.get("message", "")).strip(),
        "source_url": str(event.get("source_url", "") or ""),
        "line": int(event.get("line", 0) or 0),
        "column": int(event.get("column", 0) or 0),
        "stack": str(event.get("stack", "") or ""),
        "timestamp": str(event.get("timestamp", datetime.now().isoformat())),
        "page_url": page_url,
    }


def domain_matches(host: str | None, cookie_domain: str | None) -> bool:
    if not host or not cookie_domain:
        return False
    host = host.lower().lstrip(".")
    cookie_domain = cookie_domain.lower().lstrip(".")
    return host == cookie_domain or host.endswith(f".{cookie_domain}")


def build_selenium_cookie_for_host(cookie: dict, host: str) -> dict | None:
    name = cookie.get("name")
    value = cookie.get("value")
    if not name or value is None:
        return None

    out = {
        "name": str(name),
        "value": str(value),
        "path": cookie.get("path", "/"),
    }
    cdom = cookie.get("domain")
    if cdom and domain_matches(host, cdom):
        out["domain"] = cdom
    if cookie.get("secure") is not None:
        out["secure"] = bool(cookie.get("secure"))
    if cookie.get("httpOnly") is not None:
        out["httpOnly"] = bool(cookie.get("httpOnly"))
    if cookie.get("expiry") is not None:
        out["expiry"] = int(cookie.get("expiry"))
    same_site = normalize_same_site(cookie.get("sameSite"))
    if same_site:
        out["sameSite"] = same_site
        if same_site == "None" and "secure" not in out:
            out["secure"] = True
    return out


def seed_cookies_for_url_selenium(driver, url: str, cookies: list[dict], verbose: bool = False):
    if not cookies:
        return

    parsed = urlparse(url)
    host = parsed.hostname
    if not host:
        return
    origin = f"{parsed.scheme or 'https'}://{host}"

    try:
        driver.get(origin)
    except Exception as e:
        if verbose:
            print(f"{Colors.YELLOW}Cookie seed origin warning ({origin}): {e}{Colors.RESET}", file=sys.stderr)
        return

    for cookie in cookies:
        cooked = build_selenium_cookie_for_host(cookie, host)
        if not cooked:
            continue
        try:
            driver.add_cookie(cooked)
        except Exception as e:
            if verbose:
                print(
                    f"{Colors.YELLOW}Cookie add warning ({host}/{cookie.get('name')}): {e}{Colors.RESET}",
                    file=sys.stderr,
                )


def build_playwright_cookies_for_url(url: str, cookies: list[dict]) -> list[dict]:
    parsed = urlparse(url)
    host = parsed.hostname
    if not host:
        return []
    origin = f"{parsed.scheme or 'https'}://{host}"

    out = []
    for c in cookies:
        name = c.get("name")
        value = c.get("value")
        if not name or value is None:
            continue
        cookie_domain = c.get("domain")
        if cookie_domain and not domain_matches(host, cookie_domain):
            continue

        out_cookie = {
            "name": str(name),
            "value": str(value),
            "path": c.get("path", "/"),
        }
        same_site = normalize_same_site(c.get("sameSite", "Lax"))
        if same_site:
            out_cookie["sameSite"] = same_site
        if cookie_domain:
            out_cookie["domain"] = cookie_domain
        else:
            out_cookie["url"] = origin
        if c.get("secure") is not None:
            out_cookie["secure"] = bool(c.get("secure"))
        elif same_site == "None":
            out_cookie["secure"] = True
        if c.get("httpOnly") is not None:
            out_cookie["httpOnly"] = bool(c.get("httpOnly"))
        if c.get("expires") is not None:
            out_cookie["expires"] = c.get("expires")
        out.append(out_cookie)
    return out


def build_selenium_driver(browser: str, timeout_s: int):
    if webdriver is None:
        raise RuntimeError("Selenium is not installed")

    if browser == "safari":
        driver = webdriver.Safari()
    elif browser == "chrome":
        options = webdriver.ChromeOptions()
        options.set_capability("goog:loggingPrefs", {"browser": "ALL"})
        driver = webdriver.Chrome(options=options)
    elif browser == "edge":
        options = webdriver.EdgeOptions()
        options.set_capability("goog:loggingPrefs", {"browser": "ALL"})
        driver = webdriver.Edge(options=options)
    elif browser == "firefox":
        options = webdriver.FirefoxOptions()
        driver = webdriver.Firefox(options=options)
    else:
        raise ValueError(f"Unsupported browser: {browser}")

    driver.set_page_load_timeout(timeout_s)
    return driver


def install_preload_console_hook_selenium(driver, browser: str, verbose: bool = False):
    if browser not in {"chrome", "edge"}:
        return
    try:
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {"source": SELENIUM_CONSOLE_HOOK})
    except Exception as e:
        if verbose:
            print(
                f"{Colors.YELLOW}Preload console hook warning ({browser}): {e}{Colors.RESET}",
                file=sys.stderr,
            )


def scan_url_selenium(
    driver, browser: str, url: str, settle_s: float, cookies: list[dict], verbose: bool = False
) -> tuple[list[dict], str | None]:
    try:
        install_preload_console_hook_selenium(driver, browser, verbose)
        seed_cookies_for_url_selenium(driver, url, cookies, verbose)
        driver.get(url)
    except Exception as e:
        return [], f"Navigation failed: {e}"

    events = []

    # Dismiss OneTrust if present (same pattern used in other repo audit scripts).
    try:
        driver.execute_script(SELENIUM_ONETRUST_DISMISS)
    except Exception:
        pass

    # Native browser logs (where supported).
    try:
        logs = driver.get_log("browser")
        for item in logs:
            events.append(
                {
                    "level": normalize_level(item.get("level", "")),
                    "message": item.get("message", ""),
                    "source_url": "",
                    "line": 0,
                    "column": 0,
                    "stack": "",
                    "timestamp": datetime.now().isoformat(),
                }
            )
    except Exception:
        pass

    # JS hook capture for non-native/limited log APIs.
    try:
        driver.execute_script(SELENIUM_CONSOLE_HOOK)
        if settle_s > 0:
            time.sleep(settle_s)
        hooked = driver.execute_script("return window.__consoleAuditEvents || [];")
        if isinstance(hooked, list):
            events.extend(hooked)
    except Exception:
        pass

    dedup = []
    seen = set()
    for e in events:
        key = (
            normalize_level(str(e.get("level", ""))),
            str(e.get("message", "")),
            str(e.get("source_url", "")),
            int(e.get("line", 0) or 0),
            int(e.get("column", 0) or 0),
        )
        if key in seen:
            continue
        seen.add(key)
        dedup.append(e)

    normalized = [normalize_event(e, browser, "real", url) for e in dedup]
    return normalized, None


async def scan_url_playwright(playwright, browser: str, url: str, config: dict) -> tuple[list[dict], str | None]:
    if async_playwright is None:
        return [], "Playwright is not installed"

    engine = FALLBACK_ENGINE_MAP[browser]
    browser_type = getattr(playwright, engine)
    timeout_ms = int(config.get("timeouts", {}).get("page_load", 60) * 1000)
    settle_s = float(config.get("console_audit", {}).get("settle_seconds", 1.5))

    launch_kwargs = {"headless": True}
    if browser in {"chrome", "edge"}:
        launch_kwargs["channel"] = "chrome" if browser == "chrome" else "msedge"

    try:
        pw_browser = await browser_type.launch(**launch_kwargs)
    except Exception:
        # fallback to engine default if channel-specific launch fails
        launch_kwargs.pop("channel", None)
        try:
            pw_browser = await browser_type.launch(**launch_kwargs)
        except Exception as e:
            return [], f"Fallback browser launch failed: {e}"

    events = []
    try:
        context = await pw_browser.new_context(
            user_agent=config.get("browser", {}).get(
                "user_agent",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            ),
            viewport=config.get("browser", {}).get("viewport", {"width": 1280, "height": 720}),
            extra_http_headers=config.get("headers", {}),
        )

        cookies = build_playwright_cookies_for_url(url, config.get("cookies", []))
        if cookies:
            try:
                await context.add_cookies(cookies)
            except Exception:
                pass

        page = await context.new_page()

        def on_console(msg):
            loc = msg.location or {}
            events.append(
                normalize_event(
                    {
                        "level": msg.type,
                        "message": msg.text,
                        "source_url": loc.get("url", ""),
                        "line": loc.get("lineNumber", 0),
                        "column": loc.get("columnNumber", 0),
                        "stack": "",
                        "timestamp": datetime.now().isoformat(),
                    },
                    browser,
                    "fallback",
                    url,
                )
            )

        page.on("console", on_console)

        await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
        # Dismiss OneTrust banner if present; fallback to CSS hide.
        try:
            accept_btn = page.locator("#onetrust-accept-btn-handler")
            if await accept_btn.is_visible(timeout=3000):
                await accept_btn.click()
                await asyncio.sleep(0.5)
            else:
                await page.add_style_tag(
                    content="#onetrust-consent-sdk, #onetrust-banner-sdk, .cookie-banner { display: none !important; }"
                )
        except Exception:
            pass

        if settle_s > 0:
            await asyncio.sleep(settle_s)

        await context.close()
    except Exception as e:
        return [], f"Fallback page scan failed: {e}"
    finally:
        await pw_browser.close()

    return events, None


def render_progress(stats: dict, start: float):
    completed = stats.get("completed", 0)
    total = stats.get("total", 0)
    findings = stats.get("findings", 0)
    failures = stats.get("failures", 0)

    elapsed_seconds = time.monotonic() - start
    pct = (completed / total) if total else 0.0
    remaining = total - completed

    # Smooth ETA with a sliding window.
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
    elif completed > 0 and elapsed_seconds > 0:
        rate_per_sec = completed / elapsed_seconds

    eta_text = "--:--"
    if rate_per_sec > 0:
        eta_text = format_duration(remaining / rate_per_sec)
    rate_per_min = rate_per_sec * 60
    if completed < 2 or elapsed_seconds < 1.0:
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
        f"ELAPSED {format_duration(elapsed_seconds)}  ETA {eta_text}  "
        f"RATE {rate_display}/MIN  "
        f"FINDINGS {findings}  FAILURES {failures}"
    )
    if len(stats_line_plain) > term_width:
        stats_line_plain = stats_line_plain[: max(0, term_width - 3)] + "..."

    if stats.get("_rendered_once"):
        prefix = "\x1b[1A\r"
    else:
        prefix = "\r"
        stats["_rendered_once"] = True

    bar_line = f"{Colors.DIM}{bar}{Colors.RESET}"
    stats_line = (
        f"LIVE {completed}/{total} ({pct * 100:5.1f}%)  "
        f"ELAPSED {format_duration(elapsed_seconds)}  ETA {eta_text}  "
        f"RATE {rate_display}/MIN  "
        f"{Colors.SOFT_RED}FINDINGS {findings}{Colors.RESET}  "
        f"{Colors.SOFT_RED}FAILURES {failures}{Colors.RESET}"
    )
    if len(stats_line_plain) > term_width:
        stats_line = stats_line_plain

    output = f"{prefix}\x1b[2K{bar_line}\n\x1b[2K{stats_line}"
    print(output, end="", file=sys.stderr, flush=True)


def write_report(
    output_dir: Path,
    config: dict,
    urls: list[str],
    browsers: list[str],
    levels: set[str],
    events: list[dict],
    page_failures: list[dict],
    browser_status: dict,
):
    report_path = output_dir / "console_audit_report.md"
    json_path = output_dir / "console_events.json"

    events_sorted = sorted(
        events,
        key=lambda e: (e["browser"], e["page_url"], e["level"], e["message"], e["timestamp"]),
    )
    json_path.write_text(json.dumps(events_sorted, indent=2), encoding="utf-8")

    by_browser_level = defaultdict(lambda: defaultdict(int))
    by_page = defaultdict(int)
    for e in events_sorted:
        by_browser_level[e["browser"]][e["level"]] += 1
        by_page[e["page_url"]] += 1

    with report_path.open("w", encoding="utf-8") as f:
        f.write("# Browser Console Audit Report\n\n")
        f.write("## Run Overview\n\n")
        f.write("| Key | Value |\n")
        f.write("|-----|-------|\n")
        f.write(f"| Run Timestamp | `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}` |\n")
        f.write(f"| URLs Scanned | {len(urls)} |\n")
        f.write(f"| Browser Targets | {', '.join(browsers)} |\n")
        f.write(f"| Enabled Levels | {', '.join(sorted(levels)) if levels else '(none)'} |\n")
        f.write(f"| Total Events | {len(events_sorted)} |\n")
        f.write(f"| Page Failures | {len(page_failures)} |\n")
        f.write("\n---\n\n")

        f.write("## Browser Execution Summary\n\n")
        f.write("| Browser | Mode | Status | Note |\n")
        f.write("|---------|------|--------|------|\n")
        for b in browsers:
            status = browser_status.get(b, {"mode": "n/a", "status": "failed", "note": "not attempted"})
            f.write(
                f"| {b} | {status.get('mode', 'n/a')} | {status.get('status', 'unknown')} | "
                f"{status.get('note', '').replace('|', '\\|')} |\n"
            )
        f.write("\n---\n\n")

        f.write("## Counts by Browser and Level\n\n")
        f.write("| Browser | error | warning | info | log | debug | total |\n")
        f.write("|---------|------:|--------:|-----:|----:|------:|------:|\n")
        for b in browsers:
            counts = by_browser_level[b]
            total = sum(counts.values())
            f.write(
                f"| {b} | {counts['error']} | {counts['warning']} | {counts['info']} | "
                f"{counts['log']} | {counts['debug']} | {total} |\n"
            )
        f.write("\n---\n\n")

        f.write("## Top Impacted Pages\n\n")
        if not by_page:
            f.write("No console events captured for enabled levels.\n")
        else:
            f.write("| Page URL | Event Count |\n")
            f.write("|----------|------------:|\n")
            for page, count in sorted(by_page.items(), key=lambda x: (-x[1], x[0])):
                f.write(f"| `{page}` | {count} |\n")
        f.write("\n---\n\n")

        f.write("## Detailed Findings\n\n")
        if not events_sorted:
            f.write("No events found.\n")
        else:
            grouped = defaultdict(lambda: defaultdict(list))
            for e in events_sorted:
                grouped[e["browser"]][e["page_url"]].append(e)

            for b in sorted(grouped.keys()):
                f.write(f"### Browser: `{b}`\n\n")
                for page in sorted(grouped[b].keys()):
                    f.write(f"#### Page: `{page}`\n\n")
                    f.write("| Level | Message | Source | Line | Column | Mode |\n")
                    f.write("|-------|---------|--------|-----:|-------:|------|\n")
                    for e in grouped[b][page]:
                        msg = e["message"].replace("|", "\\|").replace("\n", " ")
                        src = e["source_url"].replace("|", "\\|")
                        f.write(
                            f"| {e['level']} | {msg[:220]} | {src[:120]} | {e['line']} | {e['column']} | {e['mode']} |\n"
                        )
                    f.write("\n")
        f.write("\n---\n\n")

        f.write("## Failed Pages\n\n")
        if not page_failures:
            f.write("No failed page scans.\n")
        else:
            f.write("| Browser | Mode | Page URL | Reason |\n")
            f.write("|---------|------|----------|--------|\n")
            for pf in page_failures:
                reason = str(pf.get("reason", "")).replace("|", "\\|")
                f.write(
                    f"| {pf.get('browser')} | {pf.get('mode')} | `{pf.get('page_url')}` | {reason[:220]} |\n"
                )


def main():
    parser = argparse.ArgumentParser(description="Cross-browser console log audit")
    parser.add_argument("-c", "--config", default="console_audit_config.json", help="Path to config JSON")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose logs")
    parser.add_argument("--browsers", default="", help="Comma-separated: safari,chrome,edge,firefox")
    parser.add_argument("--levels", default="", help="Comma-separated: error,warning,info,log,debug")
    parser.add_argument("--no-fallback", action="store_true", help="Disable Playwright fallback")
    args = parser.parse_args()

    script_dir = Path(__file__).parent.absolute()
    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = script_dir / config_path

    config = load_config(config_path)
    urls = build_url_list(config, args.verbose)
    if not urls:
        print(f"{Colors.RED}No URLs to scan. Check urls/sitemaps in config.{Colors.RESET}", file=sys.stderr)
        sys.exit(1)

    configured_browsers = config.get("console_audit", {}).get("browsers", SUPPORTED_BROWSERS)
    browsers = configured_browsers
    if args.browsers:
        browsers = [b.strip().lower() for b in args.browsers.split(",") if b.strip()]
    browsers = [b for b in browsers if b in SUPPORTED_BROWSERS]
    if not browsers:
        print(f"{Colors.RED}No valid browsers selected.{Colors.RESET}", file=sys.stderr)
        sys.exit(1)

    levels = enabled_levels(config, args.levels or None)
    fallback_enabled = config.get("console_audit", {}).get("fallback_enabled", True) and not args.no_fallback
    page_load_s = int(config.get("timeouts", {}).get("page_load", 60))
    settle_s = float(config.get("console_audit", {}).get("settle_seconds", 1.5))

    session_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = script_dir / "reports" / f"session_{session_ts}"
    output_dir.mkdir(parents=True, exist_ok=True)

    print(
        f"{Colors.CYAN}Scanning {len(urls)} URL(s) across {len(browsers)} browser(s)...{Colors.RESET}",
        file=sys.stderr,
    )
    print(f"{Colors.CYAN}Report folder: {output_dir}{Colors.RESET}", file=sys.stderr)

    browser_status = {}
    selenium_drivers = {}

    for browser in browsers:
        try:
            driver = build_selenium_driver(browser, page_load_s)
            selenium_drivers[browser] = driver
            browser_status[browser] = {"mode": "real", "status": "ok", "note": "Selenium driver active"}
        except Exception as e:
            if fallback_enabled:
                browser_status[browser] = {
                    "mode": "fallback",
                    "status": "ok",
                    "note": f"Real startup failed; using fallback: {e}",
                }
            else:
                browser_status[browser] = {"mode": "real", "status": "failed", "note": str(e)}

    all_events: list[dict] = []
    page_failures: list[dict] = []

    total_checks = len(urls) * len(browsers)
    completed = 0
    progress_stats = {
        "completed": 0,
        "total": total_checks,
        "findings": 0,
        "failures": 0,
    }
    start = time.monotonic()

    async def run_fallback(browser: str, url: str) -> tuple[list[dict], str | None]:
        if async_playwright is None:
            return [], "Playwright is not installed"
        async with async_playwright() as pw:
            return await scan_url_playwright(pw, browser, url, config)

    for browser in browsers:
        mode = browser_status.get(browser, {}).get("mode")
        if browser_status.get(browser, {}).get("status") != "ok":
            for url in urls:
                completed += 1
                progress_stats["completed"] = completed
                progress_stats["findings"] = len(all_events)
                progress_stats["failures"] = len(page_failures)
                init_reason = browser_status.get(browser, {}).get("note", "Browser init failed")
                page_failures.append(
                    {
                        "browser": browser,
                        "mode": "real",
                        "page_url": url,
                        "reason": init_reason,
                    }
                )
                progress_stats["failures"] = len(page_failures)
                render_progress(progress_stats, start)
            continue

        if mode == "real" and browser in selenium_drivers:
            for url in urls:
                events, err = scan_url_selenium(
                    selenium_drivers[browser],
                    browser,
                    url,
                    settle_s,
                    config.get("cookies", []),
                    args.verbose,
                )
                if err:
                    page_failures.append({"browser": browser, "mode": "real", "page_url": url, "reason": err})
                else:
                    filtered = [e for e in events if e["level"] in levels]
                    all_events.extend(filtered)

                completed += 1
                progress_stats["completed"] = completed
                progress_stats["findings"] = len(all_events)
                progress_stats["failures"] = len(page_failures)
                render_progress(progress_stats, start)

                delay_ms = int(config.get("rate_limit", {}).get("delay_ms", 0))
                if delay_ms > 0:
                    time.sleep(delay_ms / 1000.0)
        else:
            with asyncio.Runner() as runner:
                for url in urls:
                    events, err = runner.run(run_fallback(browser, url))
                    if err:
                        page_failures.append(
                            {"browser": browser, "mode": "fallback", "page_url": url, "reason": err}
                        )
                    else:
                        filtered = [e for e in events if e["level"] in levels]
                        all_events.extend(filtered)

                    completed += 1
                    progress_stats["completed"] = completed
                    progress_stats["findings"] = len(all_events)
                    progress_stats["failures"] = len(page_failures)
                    render_progress(progress_stats, start)

                    delay_ms = int(config.get("rate_limit", {}).get("delay_ms", 0))
                    if delay_ms > 0:
                        time.sleep(delay_ms / 1000.0)

    print("", file=sys.stderr)

    for driver in selenium_drivers.values():
        try:
            driver.quit()
        except Exception:
            pass

    write_report(output_dir, config, urls, browsers, levels, all_events, page_failures, browser_status)

    print(
        f"{Colors.GREEN}Report generated: {output_dir / 'console_audit_report.md'}{Colors.RESET}",
        file=sys.stderr,
    )
    print(
        f"{Colors.CYAN}Events JSON: {output_dir / 'console_events.json'}{Colors.RESET}",
        file=sys.stderr,
    )

    if len(all_events) > 0:
        print(
            f"{Colors.RED}{Colors.BOLD}Detected {len(all_events)} enabled-level console event(s). Exit code 1.{Colors.RESET}",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"{Colors.GREEN}No enabled-level console events detected. Exit code 0.{Colors.RESET}", file=sys.stderr)
    sys.exit(0)


if __name__ == "__main__":
    main()
