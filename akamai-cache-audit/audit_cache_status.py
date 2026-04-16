#!/usr/bin/env python3
"""
Audit Akamai cache behavior for a single URL by repeatedly sampling headers.
"""

import argparse
import hashlib
import json
import math
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

import requests
from requests.structures import CaseInsensitiveDict


class LocalCacheManager:
    """Simple file-based cache manager to simulate browser behavior."""

    def __init__(self, cache_dir: Path):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def get_cache_key(self, url: str) -> str:
        return hashlib.md5(url.encode("utf-8")).hexdigest()

    def get(self, url: str) -> dict | None:
        key = self.get_cache_key(url)
        cache_file = self.cache_dir / f"{key}.json"

        if not cache_file.exists():
            return None

        try:
            with open(cache_file, "r") as f:
                data = json.load(f)

            # Check expiration based on captured_at and max-age
            captured_at = data.get("captured_at", 0)
            max_age = data.get("max_age", 0)
            now = time.time()

            if now - captured_at < max_age:
                return data
            else:
                # Expired
                return None
        except (json.JSONDecodeError, OSError):
            return None

    def set(self, url: str, headers: dict):
        # Extract max-age from Cache-Control
        cache_control = headers.get("Cache-Control", "").lower()
        max_age = 0
        if "max-age=" in cache_control:
            try:
                parts = cache_control.split("max-age=")
                max_age = int(parts[1].split(",")[0].strip())
            except (ValueError, IndexError):
                max_age = 0

        if max_age <= 0:
            return  # Don't cache if no max-age

        key = self.get_cache_key(url)
        cache_file = self.cache_dir / f"{key}.json"

        data = {
            "url": url,
            "captured_at": time.time(),
            "max_age": max_age,
            "headers": dict(headers),
        }

        with open(cache_file, "w") as f:
            json.dump(data, f)

    def clear(self):
        if self.cache_dir.exists():
            shutil.rmtree(self.cache_dir)
            self.cache_dir.mkdir(parents=True, exist_ok=True)


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
    avg_per_sample = (elapsed / completed) if completed else 0.0
    eta = avg_per_sample * remaining if completed else 0.0

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


def load_config(config_path: Path) -> dict:
    try:
        with open(config_path, "r", encoding="utf-8") as f:
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


def resolve_settings(config: dict, args: argparse.Namespace) -> dict:
    url = args.url or config.get("url")
    if not url:
        print(
            f"{Colors.RED}Missing URL. Provide `url` in config or use --url.{Colors.RESET}",
            file=sys.stderr,
        )
        sys.exit(1)

    duration = (
        args.duration if args.duration is not None else config.get("duration_seconds", 300)
    )
    interval = (
        args.interval if args.interval is not None else config.get("interval_seconds", 5)
    )
    timeout = (
        args.timeout if args.timeout is not None else config.get("timeout_seconds", 20)
    )

    use_local_cache = args.local_cache
    clear_local_cache = args.clear_cache

    if duration <= 0 or interval <= 0 or timeout <= 0:
        print(
            f"{Colors.RED}duration, interval, and timeout must be > 0.{Colors.RESET}",
            file=sys.stderr,
        )
        sys.exit(1)

    headers = dict(config.get("headers", {}))
    headers["X-Akamai-Debug"] = "true"

    expected = config.get("expected", {})
    akamai_cache_status_expected = expected.get("akamai_cache_status", "Hit from child")
    cache_control_expected = expected.get("cache_control", "max-age=300,s-maxage=300")
    akamai_grn_required = bool(expected.get("akamai_grn_required", True))

    total_samples = max(1, math.ceil(duration / interval))

    return {
        "url": url,
        "duration_seconds": duration,
        "interval_seconds": interval,
        "timeout_seconds": timeout,
        "headers": headers,
        "expected_cache_status": akamai_cache_status_expected,
        "expected_cache_control": cache_control_expected,
        "akamai_grn_required": akamai_grn_required,
        "total_samples": total_samples,
        "use_local_cache": use_local_cache,
        "clear_local_cache": clear_local_cache,
    }


def run_audit(settings: dict, verbose: bool = False) -> list[dict]:
    url = settings["url"]
    headers = settings["headers"]
    timeout = settings["timeout_seconds"]
    total_samples = settings["total_samples"]
    interval = settings["interval_seconds"]
    expected_cache_status = settings["expected_cache_status"]
    expected_cache_control = settings["expected_cache_control"]
    require_grn = settings["akamai_grn_required"]
    use_local_cache = settings["use_local_cache"]
    clear_local_cache = settings["clear_local_cache"]

    cache_manager = LocalCacheManager(Path(__file__).parent / ".local_cache")
    if clear_local_cache:
        cache_manager.clear()

    results = []
    session = requests.Session()
    start_mono = time.monotonic()
    render_progress(0, total_samples, start_mono)

    for sample_no in range(1, total_samples + 1):
        request_start = time.monotonic()
        wall_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        row = {
            "sample": sample_no,
            "timestamp": wall_time,
            "http_status": None,
            "latency_ms": None,
            "akamai_cache_status": None,
            "cache_control": None,
            "akamai_grn": None,
            "check_cache_status": False,
            "check_cache_control": False,
            "check_akamai_grn": False,
            "passed": False,
            "source": "Network",
            "error": "",
            "failure_reason": "",
        }

        try:
            response_headers = None
            latency_ms = 0
            http_status = 200

            cached_data = cache_manager.get(url) if use_local_cache else None

            if cached_data:
                response_headers = CaseInsensitiveDict(cached_data["headers"])
                latency_ms = 0
                row["source"] = "Local Cache"
            else:
                response = session.get(url, headers=headers, timeout=timeout, allow_redirects=True)
                latency_ms = int((time.monotonic() - request_start) * 1000)
                response_headers = response.headers
                http_status = response.status_code
                if use_local_cache:
                    cache_manager.set(url, response_headers)

            hdr = response_headers
            cache_status = hdr.get("akamai-cache-status", "")
            cache_control = hdr.get("cache-control", "")
            akamai_grn = hdr.get("akamai-grn", "")

            check_cache_status = cache_status == expected_cache_status
            check_cache_control = cache_control == expected_cache_control
            check_akamai_grn = bool(akamai_grn.strip()) if require_grn else True
            passed = check_cache_status and check_cache_control and check_akamai_grn

            reasons = []
            if not check_cache_status:
                reasons.append(
                    f"akamai-cache-status expected '{expected_cache_status}', got '{cache_status or 'MISSING'}'"
                )
            if not check_cache_control:
                reasons.append(
                    f"cache-control expected '{expected_cache_control}', got '{cache_control or 'MISSING'}'"
                )
            if not check_akamai_grn:
                reasons.append("akamai-grn missing/empty")

            row.update(
                {
                    "http_status": http_status,
                    "latency_ms": latency_ms,
                    "akamai_cache_status": cache_status,
                    "cache_control": cache_control,
                    "akamai_grn": akamai_grn,
                    "check_cache_status": check_cache_status,
                    "check_cache_control": check_cache_control,
                    "check_akamai_grn": check_akamai_grn,
                    "passed": passed,
                    "failure_reason": "; ".join(reasons),
                }
            )
        except requests.RequestException as e:
            latency_ms = int((time.monotonic() - request_start) * 1000)
            row["latency_ms"] = latency_ms
            row["error"] = str(e)
            row["failure_reason"] = f"request error: {e}"

        results.append(row)
        render_progress(sample_no, total_samples, start_mono)

        if verbose:
            status_label = (
                f"{Colors.GREEN}PASS{Colors.RESET}"
                if row["passed"]
                else f"{Colors.RED}FAIL{Colors.RESET}"
            )
            print(
                (
                    f"\n[{sample_no}/{total_samples}] {status_label} "
                    f"http={row['http_status']} "
                    f"source={row['source']} "
                    f"cache-status={row['akamai_cache_status'] or 'MISSING'} "
                    f"cache-control={row['cache_control'] or 'MISSING'} "
                    f"akamai-grn={row['akamai_grn'] or 'MISSING'}"
                ),
                file=sys.stderr,
            )
            render_progress(sample_no, total_samples, start_mono)

        next_target = start_mono + (sample_no * interval)
        sleep_for = next_target - time.monotonic()
        if sleep_for > 0 and sample_no < total_samples:
            time.sleep(sleep_for)

    print("", file=sys.stderr)
    return results


def build_markdown_report(
    settings: dict, results: list[dict], report_path: Path, started_at: str, finished_at: str
):
    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    failed = total - passed
    overall_pass = failed == 0

    failure_breakdown = {}
    for row in results:
        if row["passed"]:
            continue
        key = row["failure_reason"] or "unknown failure"
        failure_breakdown[key] = failure_breakdown.get(key, 0) + 1

    with open(report_path, "w", encoding="utf-8") as f:
        f.write("# Akamai Cache Status Audit Report\n\n")

        f.write("## Meta\n\n")
        f.write("| Key | Value |\n")
        f.write("|-----|-------|\n")
        f.write(f"| Started At | `{started_at}` |\n")
        f.write(f"| Finished At | `{finished_at}` |\n")
        f.write(f"| URL | `{settings['url']}` |\n")
        f.write(f"| Duration Seconds | `{settings['duration_seconds']}` |\n")
        f.write(f"| Interval Seconds | `{settings['interval_seconds']}` |\n")
        f.write(f"| Timeout Seconds | `{settings['timeout_seconds']}` |\n")
        f.write(f"| Total Samples | `{total}` |\n")
        f.write(f"| Passed Samples | `{passed}` |\n")
        f.write(f"| Failed Samples | `{failed}` |\n")
        f.write(f"| Overall Result | `{'PASS' if overall_pass else 'FAIL'}` |\n")
        f.write("\n---\n\n")

        f.write("## Validation Rules\n\n")
        f.write(
            f"- `akamai-cache-status` must equal `{settings['expected_cache_status']}`\n"
        )
        f.write(
            f"- `cache-control` must equal `{settings['expected_cache_control']}`\n"
        )
        f.write("- `akamai-grn` must be present and non-empty\n")
        f.write("\n---\n\n")

        f.write("## Sample Summary\n\n")
        f.write("| # | Timestamp | Source | HTTP | Latency (ms) | Result |\n")
        f.write("|---|-----------|--------|------|--------------|--------|\n")
        for row in results:
            result = "PASS" if row["passed"] else "FAIL"
            http_status = row["http_status"] if row["http_status"] is not None else "ERR"
            latency = row["latency_ms"] if row["latency_ms"] is not None else "-"
            f.write(
                f"| {row['sample']} | `{row['timestamp']}` | {row['source']} | {http_status} | {latency} | {result} |\n"
            )
        f.write("\n---\n\n")

        f.write("## Failure Breakdown\n\n")
        if failure_breakdown:
            f.write("| Reason | Count |\n")
            f.write("|--------|------:|\n")
            for reason, count in sorted(
                failure_breakdown.items(), key=lambda item: item[1], reverse=True
            ):
                safe_reason = reason.replace("\n", " ").replace("|", "\\|")
                f.write(f"| {safe_reason} | {count} |\n")
        else:
            f.write("No failures.\n")
        f.write("\n---\n\n")

        f.write("## Failed Samples\n\n")
        failed_rows = [r for r in results if not r["passed"]]
        if failed_rows:
            f.write("| # | Timestamp | HTTP | Reason |\n")
            f.write("|---|-----------|------|--------|\n")
            for row in failed_rows:
                http_status = row["http_status"] if row["http_status"] is not None else "ERR"
                reason = (row["failure_reason"] or row["error"] or "unknown").replace(
                    "|", "\\|"
                )
                f.write(
                    f"| {row['sample']} | `{row['timestamp']}` | {http_status} | {reason} |\n"
                )
        else:
            f.write("No failed samples.\n")
        f.write("\n---\n\n")

        f.write("## Raw Header Snapshot\n\n")
        f.write(
            "| # | akamai-cache-status | cache-control | akamai-grn |\n"
        )
        f.write(
            "|---|---------------------|---------------|------------|\n"
        )
        for row in results:
            cache_status = (row["akamai_cache_status"] or "MISSING").replace("|", "\\|")
            cache_control = (row["cache_control"] or "MISSING").replace("|", "\\|")
            akamai_grn = (row["akamai_grn"] or "MISSING").replace("|", "\\|")
            f.write(f"| {row['sample']} | {cache_status} | {cache_control} | {akamai_grn} |\n")


def print_console_summary(settings: dict, results: list[dict], report_path: Path):
    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    failed = total - passed

    print(f"{Colors.BOLD}Akamai Cache Audit Summary{Colors.RESET}")
    print(f"{Colors.CYAN}URL: {settings['url']}{Colors.RESET}")
    print(
        f"{Colors.CYAN}Samples: {total} | Passed: {passed} | Failed: {failed}{Colors.RESET}"
    )
    print(f"{Colors.CYAN}Report: {report_path}{Colors.RESET}")

    if failed == 0:
        print(f"{Colors.GREEN}All samples passed strict cache validation.{Colors.RESET}")
    else:
        print(
            f"{Colors.RED}Validation failed: strict checks did not pass for all samples.{Colors.RESET}"
        )


def main():
    script_dir = Path(__file__).resolve().parent
    default_config = script_dir / "cache_audit_config.json"

    parser = argparse.ArgumentParser(
        description="Audit Akamai cache headers for one URL over repeated samples."
    )
    parser.add_argument(
        "--config",
        default=str(default_config),
        help=f"Path to config JSON file (default: {default_config})",
    )
    parser.add_argument("--url", help="Override config URL")
    parser.add_argument("--duration", type=int, help="Override run duration in seconds")
    parser.add_argument("--interval", type=int, help="Override sample interval in seconds")
    parser.add_argument("--timeout", type=int, help="Override request timeout in seconds")
    parser.add_argument("--local-cache", action="store_true", help="Enable local client-side cache simulation")
    parser.add_argument("--clear-cache", action="store_true", help="Clear local cache before run")
    parser.add_argument("--verbose", action="store_true", help="Print per-sample details")
    args = parser.parse_args()

    config = load_config(Path(args.config))
    settings = resolve_settings(config, args)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = script_dir / "reports" / f"session_{timestamp}"
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "cache_audit_report.md"

    print(
        (
            f"{Colors.CYAN}Running cache audit for {settings['duration_seconds']}s "
            f"with {settings['total_samples']} sample(s) every {settings['interval_seconds']}s...{Colors.RESET}"
        ),
        file=sys.stderr,
    )

    started_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    results = run_audit(settings, verbose=args.verbose)
    finished_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    build_markdown_report(settings, results, report_path, started_at, finished_at)
    print_console_summary(settings, results, report_path)

    all_pass = all(r["passed"] for r in results)
    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    main()
