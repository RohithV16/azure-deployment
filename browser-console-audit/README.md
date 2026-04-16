# Browser Console Audit

Cross-browser console log scanner for:
- Safari
- Chrome
- Edge
- Firefox

Hybrid mode behavior:
- Tries real browser automation first (Selenium drivers).
- Falls back to Playwright engines when a real browser/driver is unavailable (if enabled in config).

## Setup

Run from `browser-console-audit/`.

1. Create venv:
```bash
python3 -m venv venv
source venv/bin/activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
playwright install
```

3. Enable Safari automation once (macOS only):
```bash
safaridriver --enable
```
Also enable Safari's `Develop > Allow Remote Automation`.

## Usage

Basic:
```bash
python3 check_console_logs.py
```

With custom config:
```bash
python3 check_console_logs.py -c console_audit_config.json
```

Browser override:
```bash
python3 check_console_logs.py --browsers safari,chrome,edge,firefox
```

Level override:
```bash
python3 check_console_logs.py --levels error,warning
```

Real-only run (disable fallback):
```bash
python3 check_console_logs.py --no-fallback
```

## Output

Session output is written under:
- `reports/session_YYYYMMDD_HHMMSS/console_audit_report.md`
- `reports/session_YYYYMMDD_HHMMSS/console_events.json`

Exit code behavior:
- `1` when enabled-level console events are detected.
- `0` when no enabled-level events are detected.
