#!/usr/bin/env python3
"""
Audit Asset Domains Script
Crawls sitemaps and flags <img> tags using non-production asset domains.
"""

import asyncio
import csv
import json
import os
import re
import shutil
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse, quote

import requests
from playwright.async_api import async_playwright

class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    RESET = "\033[0m"


def format_duration(seconds: float) -> str:
    seconds = max(0, int(seconds))
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def render_progress(completed: int, total: int, start_time: float):
    elapsed = time.monotonic() - start_time
    pct = (completed / total) if total else 0.0
    remaining = total - completed
    avg_per_page = (elapsed / completed) if completed else 0.0
    eta = avg_per_page * remaining if completed else 0.0

    term_width = shutil.get_terminal_size((120, 20)).columns
    static_text = (
        f" {completed}/{total} {pct * 100:5.1f}% "
        f"elapsed {format_duration(elapsed)} ETA {format_duration(eta)}"
    )
    bar_space = max(10, min(40, term_width - len(static_text) - 8))
    filled = int(bar_space * pct)
    bar = f"[{'#' * filled}{'-' * (bar_space - filled)}]"

    line = f"\r{Colors.CYAN}{bar}{Colors.RESET}{static_text}"
    print(line.ljust(term_width), end="", file=sys.stderr, flush=True)


def load_config(config_path: str) -> dict:
    try:
        with open(config_path, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"{Colors.RED}Error loading config: {e}{Colors.RESET}", file=sys.stderr)
        sys.exit(1)

def parse_sitemap(url: str, config: dict, crawled_sitemaps: list = None) -> list[str]:
    if crawled_sitemaps is None:
        crawled_sitemaps = []
    
    timeout = config.get("timeouts", {}).get("sitemap_fetch", 30)
    cookies_config = config.get("cookies", [])
    cookies = {c["name"]: c["value"] for c in cookies_config}
    
    try:
        if url not in crawled_sitemaps:
            crawled_sitemaps.append(url)
            
        print(f"{Colors.YELLOW}Parsing sitemap: {url}{Colors.RESET}")
        response = requests.get(url, timeout=timeout, cookies=cookies)
        response.raise_for_status()
        root = ET.fromstring(response.content)
        tag = root.tag.split('}')[-1]
        
        ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        
        if tag == 'sitemapindex':
            all_urls = []
            for loc in root.findall(".//sm:loc", ns):
                if loc.text:
                    all_urls.extend(parse_sitemap(loc.text, config, crawled_sitemaps))
            return all_urls
        
        urls = [loc.text for loc in root.findall(".//sm:loc", ns) if loc.text]
        if not urls:
             urls = [loc.text for loc in root.findall(".//loc") if loc.text]
        return [str(u) for u in urls if u]
    except Exception as e:
        print(f"{Colors.RED}Failed to parse sitemap {url}: {e}{Colors.RESET}", file=sys.stderr)
        return []

async def check_page(url, context, config, screenshot_folder):
    asset_base = config.get("asset_base_url", "https://assets.mandg.com/is/image/")
    prod_path = config.get("production_asset_path", "mandgdigital")
    
    page = await context.new_page()
    findings = []
    
    try:
        # Load page
        # Navigate to page with 'load' instead of 'networkidle' to avoid analytics-related timeouts
        await page.goto(url, wait_until="load", timeout=config["timeouts"]["page_load"] * 1000)
        
        await asyncio.sleep(config["timeouts"]["network_idle"])
        
        # Dismiss cookie banner if present
        try:
            # Specific selector for M&G OneTrust banner
            accept_btn = page.locator('#onetrust-accept-btn-handler')
            if await accept_btn.is_visible(timeout=3000):
                await accept_btn.click()
                # Wait a bit for the banner to actually disappear from the DOM
                await asyncio.sleep(1)
            else:
                # Fallback: Hide it via CSS to ensure it doesn't block screenshots
                await page.add_style_tag(content="#onetrust-consent-sdk, #onetrust-banner-sdk, .cookie-banner { display: none !important; }")
        except:
            pass
        
        # Find all images
        imgs = await page.query_selector_all("img")
        
        # 1. First, find all violations and gather data
        raw_violations = []
        for i, img in enumerate(imgs):
            src = await img.get_attribute("src")
            if not src: continue
            
            # Custom Skip: Ignore Header Logo (Wait, user wants footer logged once, not skipped)
            should_skip_header_logo = await img.evaluate("""el => !!el.closest('.cmp-header__logo')""")
            if should_skip_header_logo: continue

            # SmartCrop & Container Info Check
            # Extract info from container
            container_info = await img.evaluate("""el => {
                const container = el.closest('[data-cmp-is="image"]');
                if (!container) return { found: false, attr: null, fileref: null, id: null, datalayer: null };
                return { 
                    found: true, 
                    attr: container.getAttribute('data-cmp-smartcroprendition'),
                    fileref: container.getAttribute('data-cmp-filereference'),
                    id: container.getAttribute('id'),
                    datalayer: container.getAttribute('data-cmp-data-layer')
                };
            }""")
            
            fileref = container_info.get('fileref') or ""
            is_valid_smartcrop = container_info['found'] and container_info['attr'] == "SmartCrop:Auto"

            # Domain & Path Check
            prod_prefix = f"{asset_base}{prod_path}/"
            content_prefix = prod_prefix.replace("/is/image/", "/is/content/")
            is_valid_domain = src.startswith(prod_prefix) or src.startswith(content_prefix)
            
            # Exclusion Check (checks both external URL and internal DAM path)
            should_exclude = any(
                re.search(p, src) or (fileref and re.search(p, fileref)) 
                for p in config.get("exclude_patterns", [])
            )
            
            # If the domain is marked for exclusion (e.g. OneTrust) or it matches an ignore pattern, skip it
            if should_exclude:
                continue
            
            # SmartCrop & Icon Check - Additional metadata extraction
            # Parse orientation from data-layer JSON
            orientation = "unknown"
            try:
                if container_info.get('datalayer'):
                    dl = json.loads(container_info['datalayer'])
                    for node in dl.values():
                        tags = node.get('image', {}).get('xdm:tags', [])
                        for tag in tags:
                            if tag.startswith('properties:orientation/'):
                                orientation = tag.split('/')[-1]
                                break
            except Exception:
                pass
            
            # Extract DM asset ID from src URL (last path segment, before query string)
            asset_id = "unknown"
            try:
                src_path = src.split('?')[0]
                asset_id = src_path.rstrip('/').split('/')[-1]
            except Exception:
                pass
            
            # Derive component type from ID prefix
            comp_id = container_info.get('id') or ""
            component_type = "teaser" if comp_id.startswith("teaser-") else "image"
            
            domain_violation = not is_valid_domain
            smartcrop_violation = not is_valid_smartcrop
            
            if domain_violation or smartcrop_violation:
                v_labels = []
                if domain_violation:
                    src_l = src.lower()
                    if "stage" in src_l: v_labels.append("Stage Domain Used")
                    elif "dev" in src_l or "test" in src_l: v_labels.append("Dev Domain Used")
                    else: v_labels.append("Invalid Domain Used")
                if smartcrop_violation:
                    v_labels.append(f"{container_info['attr']} Used" if container_info['attr'] else "SmartCrop Missing")
                
                # Capture markup (closest container or self)
                markup = await img.evaluate("el => el.closest('[data-cmp-is=\"image\"]') ? el.closest('[data-cmp-is=\"image\"]').outerHTML : el.outerHTML")
                
                # Identify if this is a shared/global component (Header, Footer, or Meganav)
                is_shared = await img.evaluate("""el => {
                    return !!el.closest('header, footer, .cmp-header, .cmp-footer, .cmp-experiencefragment--header, .cmp-experiencefragment--footer, .meganav, .cmp-meganav, .header, .footer');
                }""")
                if is_shared:
                    continue
                
                raw_violations.append({
                    "element": img,
                    "src": src,
                    "labels": v_labels,
                    "smartcrop_attr": container_info['attr'] or "None",
                    "markup": markup,
                    "is_shared": is_shared,
                    "asset_id": asset_id,
                    "dam_path": container_info.get('fileref') or "",
                    "component_id": comp_id,
                    "component_type": component_type,
                    "orientation": orientation,
                })

        # 2. If there are violations, highlight all of them and take one screenshot
        if raw_violations:
            clean_url = re.sub(r'https?://', '', url)
            clean_url = re.sub(r'[^a-zA-Z0-9]', '_', clean_url).strip('_')
            screenshot_path = Path(screenshot_folder) / f"{clean_url[:100]}.png"
            
            try:
                # Highlight all at once
                for v in raw_violations:
                    img_el = v["element"]
                    labels_str = ", ".join(v["labels"])
                    is_visible = await img_el.is_visible()
                    v["is_visible"] = is_visible
                    
                    if is_visible:
                        await img_el.evaluate(f"""el => {{
                            el.style.outline = '8px solid red';
                            el.style.outlineOffset = '5px';
                            const label = document.createElement('div');
                            label.className = 'audit-visual-label';
                            label.innerText = "{labels_str}";
                            label.style.position = 'absolute';
                            label.style.background = 'red';
                            label.style.color = 'white';
                            label.style.padding = '5px 10px';
                            label.style.fontSize = '14px';
                            label.style.fontWeight = 'bold';
                            label.style.zIndex = '999999';
                            label.style.borderRadius = '3px';
                            const rect = el.getBoundingClientRect();
                            label.style.top = (window.scrollY + rect.top - 30) + 'px';
                            label.style.left = (window.scrollX + rect.left) + 'px';
                            document.body.appendChild(label);
                        }}""")
                
                await page.screenshot(path=str(screenshot_path), full_page=True)
                
                # Format findings for report
                for v in raw_violations:
                    findings.append({
                        "tag": "img",
                        "src": v["src"],
                        "url": url,
                        "screenshot": str(screenshot_path),
                        "violations": v["labels"],
                        "smartcrop_attr": v["smartcrop_attr"],
                        "markup": v["markup"],
                        "is_shared": v["is_shared"],
                        "notes": "" if v["is_visible"] else "(Element hidden)",
                        "asset_id": v.get("asset_id", "unknown"),
                        "dam_path": v.get("dam_path", ""),
                        "component_id": v.get("component_id", ""),
                        "component_type": v.get("component_type", "image"),
                        "orientation": v.get("orientation", "unknown"),
                    })
            except Exception as e:
                print(f"Error highlighting/screenshoting {url}: {e}")

        return {"url": url, "findings": findings}
        
    except Exception as e:
        print(f"{Colors.YELLOW}Error checking {url}: {e}{Colors.RESET}", file=sys.stderr)
        return {"url": url, "findings": [], "error": str(e)}
    finally:
        await page.close()

async def main():
    # Detect script directory to find config and store outputs
    script_dir = Path(__file__).parent.absolute()
    config_path = script_dir / "audit_config.json"
    config = load_config(str(config_path))
    
    all_urls = []
    crawled_sitemaps = []
    # Direct URLs first
    all_urls.extend(config.get("urls", []))
    
    # Sitemaps if needed
    if not all_urls or config.get("max_pages", -1) > len(all_urls):
        for sitemap in config.get("sitemaps", []):
            urls = parse_sitemap(sitemap, config, crawled_sitemaps)
            all_urls.extend(urls)
    
    if config.get("max_pages", -1) > 0:
        all_urls = all_urls[:config["max_pages"]]
        
    if not all_urls:
        print(f"{Colors.RED}No URLs found to check.{Colors.RESET}")
        return

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    # Store outputs in a session-specific folder within the script's directory
    output_dir = script_dir / "reports" / f"session_{timestamp}"
    screenshot_folder = output_dir / "screenshots"
    screenshot_folder.mkdir(parents=True, exist_ok=True)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=config["browser"]["user_agent"],
            viewport=config["browser"]["viewport"]
        )
        
        # Add cookies
        await context.add_cookies(config.get("cookies", []))
        
        results = []
        semaphore = asyncio.Semaphore(config.get("max_workers", 2))
        
        # Get rate limit delay
        rate_delay = config.get("rate_limit", {}).get("delay_ms", 0) / 1000.0

        async def sem_check(url):
            async with semaphore:
                result = await check_page(url, context, config, screenshot_folder)
                if rate_delay > 0:
                    await asyncio.sleep(rate_delay)
                return result
        
        tasks = [asyncio.create_task(sem_check(url)) for url in all_urls]
        total = len(tasks)
        completed = 0
        start_time = time.monotonic()
        render_progress(completed, total, start_time)
        for coro in asyncio.as_completed(tasks):
            result = await coro
            results.append(result)
            completed += 1
            render_progress(completed, total, start_time)
        print("", file=sys.stderr)

        await browser.close()
        
    # ──────────────────────────────────────────────
    # Generate Report
    # ──────────────────────────────────────────────
    report_path = output_dir / "audit_report.md"

    total_pages = len(results)
    valid_results = [r for r in results if isinstance(r, dict)]
    pages_with_findings = [r for r in valid_results if r.get("findings")]

    # Flatten all violations into a single list with page_path added
    all_violations = []
    for r in pages_with_findings:
        page_path = "/" + urlparse(r["url"]).path.lstrip("/")
        for v in r["findings"]:
            all_violations.append({**v, "page_path": page_path})

    total_violations = len(all_violations)
    violation_types = sorted(set(label for v in all_violations for label in v.get("violations", [])))

    # Build per-asset map: asset_id -> {dam_path, pages, orientation, count}
    asset_map = {}
    for v in all_violations:
        aid = v.get("asset_id", "unknown")
        if aid not in asset_map:
            asset_map[aid] = {
                "dam_path": v.get("dam_path", ""),
                "pages": [],
                "orientation": v.get("orientation", "unknown"),
                "count": 0,
            }
        if v["page_path"] not in asset_map[aid]["pages"]:
            asset_map[aid]["pages"].append(v["page_path"])
        asset_map[aid]["count"] += 1

    # Deduplicated = assets used on more than one page
    deduped = {aid: data for aid, data in asset_map.items() if len(data["pages"]) > 1}

    # Sitemap short names for meta table
    sitemap_names = [s.split("mandg.com/")[-1].split("?")[0] for s in crawled_sitemaps]

    with open(report_path, "w", encoding="utf-8") as f:
        run_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        f.write("# Asset Domain Audit Report\n\n")

        # ── Section 1: Meta
        f.write("## Meta\n\n")
        f.write("| Key | Value |\n")
        f.write("|-----|-------|\n")
        sitemap_str = ", ".join(f"`{s}`" for s in sitemap_names) if sitemap_names else "N/A (direct URLs)"
        f.write(f"| Run Timestamp | `{run_ts}` |\n")
        f.write(f"| Sitemaps | {sitemap_str} |\n")
        f.write(f"| Pages Scanned | {total_pages} |\n")
        f.write(f"| Pages with Violations | {len(pages_with_findings)} |\n")
        f.write(f"| Total Violations | {total_violations} |\n")
        vtype_str = ", ".join(violation_types) if violation_types else "None"
        f.write(f"| Violation Types | {vtype_str} |\n")
        f.write("\n---\n\n")

        if not pages_with_findings:
            f.write("✅ No violations found in scan results.\n")
        else:
            # ── Section 2: Summary — Pages with Violations
            f.write("## Summary — Pages with Violations\n\n")
            f.write("| Page Path | Violations |\n")
            f.write("|-----------|:----------:|\n")
            for r in pages_with_findings:
                page_path = "/" + urlparse(r["url"]).path.lstrip("/")
                f.write(f"| `{page_path}` | {len(r['findings'])} |\n")
            f.write("\n---\n\n")

            # ── Section 3: Flat Violations Index
            f.write("## Violations — Flat Index\n\n")
            f.write("> One row per violation. Sort/filter by any column.  \n")
            f.write("> `component_type`: `image` = standalone Image component, `teaser` = Teaser component image slot.  \n")
            f.write("> `orientation`: sourced from `xdm:tags` on the DAM asset.\n\n")
            f.write("| # | Page Path | Asset ID | DAM Path | Component ID | Component Type | Orientation | Violation |\n")
            f.write("|---|-----------|----------|----------|--------------|----------------|-------------|----------|\n")
            for idx, v in enumerate(all_violations, 1):
                violations_str = ", ".join(v.get("violations", []))
                f.write(
                    f"| {idx} "
                    f"| `{v['page_path']}` "
                    f"| `{v.get('asset_id', '')}` "
                    f"| `{v.get('dam_path', '')}` "
                    f"| `{v.get('component_id', '')}` "
                    f"| {v.get('component_type', 'image')} "
                    f"| {v.get('orientation', 'unknown')} "
                    f"| {violations_str} |\n"
                )
            f.write("\n---\n\n")

            # ── Section 4: Deduplicated Assets
            f.write("## Deduplicated Assets\n\n")
            f.write("> Assets referenced on more than one page — fix once in DAM, resolves all pages.\n\n")
            if deduped:
                f.write("| Asset ID | DAM Path | Used On Pages | Violation Count |\n")
                f.write("|----------|----------|:-------------:|:---------------:|\n")
                for aid, data in sorted(deduped.items(), key=lambda x: -len(x[1]["pages"])):
                    pages_str = ", ".join(f"`{p}`" for p in data["pages"])
                    f.write(f"| `{aid}` | `{data['dam_path']}` | {pages_str} | {data['count']} |\n")
            else:
                f.write("_No assets were found on more than one page._\n")
            f.write("\n---\n\n")

            # ── Section 5: Asset Thumbnail Index
            prod_base = "https://assets.mandg.com/is/image/mandgdigital"
            f.write("## Asset Thumbnail Index\n\n")
            f.write(f"> Quick visual reference per unique asset ID. Format: `{prod_base}/{{asset-id}}?wid=120&qlt=80`\n\n")
            f.write("| Asset ID | Thumb | Orientation | Pages Affected |\n")
            f.write("|----------|-------|-------------|:--------------:|\n")
            for aid, data in asset_map.items():
                thumb_url = f"{prod_base}/{aid}?wid=120&qlt=80"
                f.write(f"| `{aid}` | ![]({thumb_url}) | {data['orientation']} | {len(data['pages'])} |\n")
            f.write("\n---\n\n")

            # ── Section 6: Visual Evidence (screenshots, collapsible)
            f.write("## Visual Evidence\n\n")
            f.write("> Full-page screenshots with violations highlighted in red. Collapsed by default.\n\n")
            for r in pages_with_findings:
                page_path = "/" + urlparse(r["url"]).path.lstrip("/")
                screenshot_val = r["findings"][0].get("screenshot") if r["findings"] else None
                if screenshot_val:
                    rel_ss = Path(screenshot_val).name
                    f.write(f"<details><summary>🔍 {page_path}</summary>\n\n")
                    f.write(f"![Full Page Screenshot](screenshots/{rel_ss})\n\n")
                    f.write(f"[Open in New Tab](screenshots/{rel_ss})\n\n")
                    f.write("</details>\n\n")
            f.write("\n---\n\n")

            # ── Section 7: Schema Reference
            f.write("## Schema Reference\n\n")
            f.write("```\naudit_report.md\n")
            f.write("├── Meta                  — run metadata, scan scope\n")
            f.write("├── Summary               — page-level violation counts\n")
            f.write("├── Violations Flat Index — ONE ROW per violation, all actionable fields\n")
            f.write("├── Deduplicated Assets   — cross-page reuse, highest ROI fixes first\n")
            f.write("├── Thumbnail Index       — visual confirm per unique asset, no HTML markup\n")
            f.write("└── Visual Evidence       — collapsible full-page screenshots\n")
            f.write("```\n\n")
            f.write("### Column Glossary\n\n")
            f.write("| Column | Source in original HTML |\n")
            f.write("|--------|------------------------|\n")
            f.write("| `Asset ID` | DM image name from `data-cmp-src` URL path |\n")
            f.write("| `DAM Path` | `data-cmp-filereference` attribute |\n")
            f.write("| `Component ID` | `id` attribute on the wrapping `<div>` |\n")
            f.write("| `Component Type` | Derived from ID prefix (`teaser-` vs `image-`) |\n")
            f.write("| `Orientation` | First value of `xdm:tags` → `properties:orientation/*` |\n")
            f.write("| `Violation` | Audit rule that fired |\n")

    # ── CSV Export (per-violation, no images)
    csv_path = report_path.parent / "summary.csv"
    try:
        with open(csv_path, "w", newline="", encoding="utf-8") as cf:
            writer = csv.writer(cf)
            writer.writerow(["#", "Page Path", "Page URL", "Asset ID", "DAM Path",
                             "Component ID", "Component Type", "Orientation", "Violation"])
            for idx, v in enumerate(all_violations, 1):
                violations_str = ", ".join(v.get("violations", []))
                writer.writerow([
                    idx,
                    v.get("page_path", ""),
                    v.get("url", ""),
                    v.get("asset_id", ""),
                    v.get("dam_path", ""),
                    v.get("component_id", ""),
                    v.get("component_type", ""),
                    v.get("orientation", ""),
                    violations_str,
                ])
        print(f"Summary CSV generated: {csv_path}")
    except Exception as e:
        print(f"Error generating CSV: {e}")

    print(f"\n{Colors.GREEN}Audit complete!{Colors.RESET}")
    print(f"{Colors.CYAN}Report generated: {report_path}{Colors.RESET}")
    if pages_with_findings:
        print(f"{Colors.RED}Found {len(pages_with_findings)} pages with violations.{Colors.RESET}")
        sys.exit(1)
    else:
        print(f"{Colors.GREEN}No violations found.{Colors.RESET}")
        sys.exit(0)

if __name__ == "__main__":
    asyncio.run(main())
