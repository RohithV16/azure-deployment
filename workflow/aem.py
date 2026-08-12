#!/usr/bin/env python3
"""Run a local Groovy file on AEM Groovy Console with hardcoded local/cloud settings."""

from __future__ import annotations

import json
import time
from pathlib import Path

import requests

# ============================================================================
# HARDCODED CONFIG
# ============================================================================
TARGET_ENV = "CLOUD"  # LOCAL or CLOUD

# Local author
LOCAL_BASE_URL = "http://localhost:4502"
LOCAL_USERNAME = "admin"
LOCAL_PASSWORD = "admin"

# Cloud Author URL (RDE/Stage/Prod)
# NOTE: Update this URL to target the environment you want to query (e.g. Stage or Prod author URL)
CLOUD_BASE_URL = "https://author-p167805-e1797205.adobeaemcloud.com"
# Use an access token from Cloud Manager AEM Developer Console for your Target user.
CLOUD_BEARER_TOKEN = ""

# Script configuration: Point SCRIPT_FILE to the groovy script to run, and specify the output file name
SCRIPT_FILE = Path("") # example /Users/rvenat01/Documents/AEM/mandg/azure-deployment/workflow/workflow.groovy
OUTPUT_FILE = Path("") # example /Users/rvenat01/Documents/AEM/mandg/azure-deployment/workflow/output.txt

# Runtime behavior
VERIFY_SSL = True
TIMEOUT_SECONDS = 120
ASYNC_RUN = True
POLL_SECONDS = 1.0

POST_ENDPOINT = "/bin/groovyconsole/post.json"
STREAM_ENDPOINT = "/bin/groovyconsole/stream.json"
CSRF_TOKEN_ENDPOINT = "/libs/granite/csrf/token.json"
CLOUD_PRECHECK_ENDPOINT = "/content/dam.json"


def save_output(text: str) -> None:
	OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
	OUTPUT_FILE.write_text(text, encoding="utf-8")


def get_runtime_config() -> tuple[str, bool]:
	env = TARGET_ENV.strip().upper()
	if env == "LOCAL":
		return LOCAL_BASE_URL.rstrip("/"), False
	if env == "CLOUD":
		return CLOUD_BASE_URL.rstrip("/"), True
	raise ValueError("TARGET_ENV must be LOCAL or CLOUD")


def configure_auth(session: requests.Session, cloud_mode: bool) -> None:
	if cloud_mode:
		if (
			not CLOUD_BEARER_TOKEN
			or CLOUD_BEARER_TOKEN == "replace-with-your-bearer-token"
		):
			raise ValueError("Set CLOUD_BEARER_TOKEN for CLOUD mode")
		session.headers["Authorization"] = f"Bearer {CLOUD_BEARER_TOKEN}"
		return

	session.auth = (LOCAL_USERNAME, LOCAL_PASSWORD)


def get_csrf_token(session: requests.Session, base_url: str) -> str | None:
	url = f"{base_url}{CSRF_TOKEN_ENDPOINT}"
	try:
		resp = session.get(url, timeout=TIMEOUT_SECONDS)
		if resp.ok:
			return resp.json().get("token")
	except Exception:
		return None
	return None


def stream_async(session: requests.Session, base_url: str, execution_id: str) -> tuple[dict, str]:
	offset = 0
	stream_url = f"{base_url}{STREAM_ENDPOINT}"
	chunks: list[str] = []

	while True:
		resp = session.get(
			stream_url,
			params={"executionId": execution_id, "offset": offset},
			timeout=TIMEOUT_SECONDS,
		)
		resp.raise_for_status()

		data = resp.json()
		chunk = data.get("chunk")
		if chunk:
			chunks.append(chunk)

		offset = data.get("offset", offset)
		if data.get("done"):
			return data, "".join(chunks)

		time.sleep(POLL_SECONDS)


def main() -> int:
	if not SCRIPT_FILE.exists():
		print(f"Script file not found: {SCRIPT_FILE}")
		return 1

	try:
		base_url, cloud_mode = get_runtime_config()
	except ValueError as exc:
		print(str(exc))
		return 1

	script_text = SCRIPT_FILE.read_text(encoding="utf-8")

	session = requests.Session()
	session.verify = VERIFY_SSL

	try:
		configure_auth(session, cloud_mode)
	except ValueError as exc:
		print(str(exc))
		return 1

	# Cloud precheck equivalent to:
	# curl -H "Authorization: Bearer <token>" https://<author>/content/dam.json
	if cloud_mode:
		precheck_resp = session.get(
			f"{base_url}{CLOUD_PRECHECK_ENDPOINT}", timeout=TIMEOUT_SECONDS
		)
		if precheck_resp.status_code == 401:
			print("Cloud token rejected: HTTP 401 on /content/dam.json")
			return 2
		if not precheck_resp.ok:
			print(
				f"Cloud precheck failed: HTTP {precheck_resp.status_code} at {CLOUD_PRECHECK_ENDPOINT}"
			)
			print(precheck_resp.text)
			return 3

	# Basic check that AEM + Groovy Console are reachable with credentials.
	console_resp = session.get(f"{base_url}/groovyconsole", timeout=TIMEOUT_SECONDS)
	if console_resp.status_code == 401:
		print("Authentication failed for /groovyconsole")
		return 4
	if not console_resp.ok:
		print(f"Connectivity failed: HTTP {console_resp.status_code} at /groovyconsole")
		return 5

	csrf_token = get_csrf_token(session, base_url)
	if csrf_token:
		session.headers["CSRF-Token"] = csrf_token

	payload = {"script": script_text}
	if ASYNC_RUN:
		payload["async"] = "true"

	post_url = f"{base_url}{POST_ENDPOINT}"
	post_resp = session.post(post_url, data=payload, timeout=TIMEOUT_SECONDS)

	if not post_resp.ok:
		print(f"POST failed: HTTP {post_resp.status_code}")
		print(post_resp.text)
		save_output(post_resp.text)
		print(f"Saved output to {OUTPUT_FILE}")
		return 6

	data = post_resp.json()
	if ASYNC_RUN:
		execution_id = data.get("executionId")
		if not execution_id:
			# Some environments may still return a direct/synchronous response.
			fallback_output = str(data.get("output") or "")
			if fallback_output:
				save_output(fallback_output)
				print(f"Saved output to {OUTPUT_FILE}")
				return 0

			response_dump = json.dumps(data, indent=2, ensure_ascii=True)
			save_output(response_dump)
			print("Async run did not return executionId")
			print(response_dump)
			print(f"Saved output to {OUTPUT_FILE}")
			return 7
		final, streamed_output = stream_async(session, base_url, execution_id)
		final_response = final.get("response") if isinstance(final, dict) else None
		output_text = ""
		if isinstance(final_response, dict):
			output_text = str(final_response.get("output") or "")
		if not output_text:
			output_text = streamed_output
		save_output(output_text)
		print(f"Saved output to {OUTPUT_FILE}")
		return 0

	output_text = str(data.get("output") or "")
	save_output(output_text)
	print(f"Saved output to {OUTPUT_FILE}")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
