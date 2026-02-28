"""Automative OSINT tool.

A lightweight, API-optional command-line utility that automates passive
open-source intelligence collection for common indicators.

Supported indicators:
- domains
- email addresses
- IPv4 / IPv6 addresses
- usernames

This script intentionally focuses on passive collection to reduce operational
risk, and only relies on publicly available endpoints.
"""

from __future__ import annotations

import argparse
import ipaddress
import json
import re
import socket
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
DOMAIN_REGEX = re.compile(r"^(?=.{1,253}$)([a-zA-Z0-9-]{1,63}\.)+[a-zA-Z]{2,63}$")
USERNAME_REGEX = re.compile(r"^[A-Za-z0-9_.-]{3,32}$")


@dataclass
class IndicatorResult:
    """Container for a single indicator's findings."""

    indicator: str
    indicator_type: str
    findings: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


class AutomativeOSINT:
    """Collect passive OSINT data for common indicators."""

    def __init__(self, timeout: float = 8.0, request_delay: float = 0.35) -> None:
        self.timeout = timeout
        self.request_delay = request_delay

    def _http_get_json(self, url: str) -> Any:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "automative-osint-tool/1.0 (+https://example.local)"
            },
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as response:
            body = response.read().decode("utf-8", errors="replace")
            return json.loads(body)

    def _http_get_text(self, url: str) -> str:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "automative-osint-tool/1.0 (+https://example.local)"
            },
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as response:
            return response.read().decode("utf-8", errors="replace")

    def detect_type(self, indicator: str) -> str:
        """Infer indicator type from string form."""
        indicator = indicator.strip()

        if EMAIL_REGEX.match(indicator):
            return "email"

        try:
            ipaddress.ip_address(indicator)
            return "ip"
        except ValueError:
            pass

        if DOMAIN_REGEX.match(indicator.lower()):
            return "domain"

        if USERNAME_REGEX.match(indicator):
            return "username"

        return "unknown"

    def collect(self, indicator: str) -> IndicatorResult:
        """Dispatch collection based on indicator type."""
        indicator_type = self.detect_type(indicator)
        result = IndicatorResult(indicator=indicator, indicator_type=indicator_type)

        try:
            if indicator_type == "domain":
                result.findings = self._collect_domain(indicator)
            elif indicator_type == "email":
                result.findings = self._collect_email(indicator)
            elif indicator_type == "ip":
                result.findings = self._collect_ip(indicator)
            elif indicator_type == "username":
                result.findings = self._collect_username(indicator)
            else:
                result.errors.append("Unable to infer indicator type.")
        except Exception as exc:  # Defensive catch for per-indicator resilience.
            result.errors.append(str(exc))

        return result

    def _collect_domain(self, domain: str) -> dict[str, Any]:
        findings: dict[str, Any] = {
            "dns": {},
            "certificate_transparency": {},
            "tls": {},
        }

        # DNS resolution (A/AAAA via getaddrinfo)
        try:
            info = socket.getaddrinfo(domain, None)
            unique_ips = sorted({entry[4][0] for entry in info})
            findings["dns"]["resolved_ips"] = unique_ips
        except socket.gaierror as err:
            findings["dns"]["error"] = str(err)

        # MX records (uses DNS-over-HTTPS via Google for portability)
        try:
            mx_url = (
                "https://dns.google/resolve?name="
                f"{urllib.parse.quote(domain)}&type=MX"
            )
            mx_data = self._http_get_json(mx_url)
            answers = mx_data.get("Answer", [])
            findings["dns"]["mx_records"] = [a.get("data", "") for a in answers]
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as err:
            findings["dns"]["mx_error"] = str(err)

        time.sleep(self.request_delay)

        # Certificate transparency lookups via crt.sh
        try:
            crt_url = (
                "https://crt.sh/?q="
                f"{urllib.parse.quote(domain)}&output=json"
            )
            certs = self._http_get_json(crt_url)
            findings["certificate_transparency"] = {
                "result_count": len(certs),
                "sample": certs[:5],
            }
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as err:
            findings["certificate_transparency"]["error"] = str(err)

        # TLS certificate metadata from live endpoint
        try:
            context = ssl.create_default_context()
            with socket.create_connection((domain, 443), timeout=self.timeout) as sock:
                with context.wrap_socket(sock, server_hostname=domain) as secure_sock:
                    cert = secure_sock.getpeercert()
            findings["tls"] = {
                "subject": cert.get("subject", []),
                "issuer": cert.get("issuer", []),
                "not_before": cert.get("notBefore"),
                "not_after": cert.get("notAfter"),
                "subject_alt_names": cert.get("subjectAltName", []),
            }
        except (ssl.SSLError, OSError) as err:
            findings["tls"]["error"] = str(err)

        return findings

    def _collect_email(self, email: str) -> dict[str, Any]:
        findings: dict[str, Any] = {}
        local, domain = email.split("@", 1)

        findings["structure"] = {
            "local_part": local,
            "domain": domain,
            "length": len(email),
        }

        findings["domain_intel"] = self._collect_domain(domain)

        # Basic breach lookup endpoint pattern placeholder (optional service).
        # No API key included; result may be unavailable unless user adds one.
        hibp_url = f"https://haveibeenpwned.com/unifiedsearch/{urllib.parse.quote(email)}"
        findings["breach_lookup_hint"] = {
            "endpoint": hibp_url,
            "note": "This endpoint generally requires an API key."
        }

        return findings

    def _collect_ip(self, ip: str) -> dict[str, Any]:
        findings: dict[str, Any] = {"reverse_dns": {}, "geo": {}}

        try:
            hostname, aliases, _ = socket.gethostbyaddr(ip)
            findings["reverse_dns"] = {
                "hostname": hostname,
                "aliases": aliases,
            }
        except (socket.herror, socket.gaierror) as err:
            findings["reverse_dns"]["error"] = str(err)

        # Free geolocation ASN-ish context (no key)
        try:
            geo_url = f"http://ip-api.com/json/{urllib.parse.quote(ip)}"
            geo_data = self._http_get_json(geo_url)
            findings["geo"] = {
                "status": geo_data.get("status"),
                "country": geo_data.get("country"),
                "regionName": geo_data.get("regionName"),
                "city": geo_data.get("city"),
                "isp": geo_data.get("isp"),
                "org": geo_data.get("org"),
                "as": geo_data.get("as"),
            }
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as err:
            findings["geo"]["error"] = str(err)

        return findings

    def _collect_username(self, username: str) -> dict[str, Any]:
        findings: dict[str, Any] = {"platform_presence": {}}

        # Lightweight username enumeration checks.
        platforms = {
            "github": f"https://github.com/{urllib.parse.quote(username)}",
            "reddit": f"https://www.reddit.com/user/{urllib.parse.quote(username)}",
            "x": f"https://x.com/{urllib.parse.quote(username)}",
            "instagram": f"https://www.instagram.com/{urllib.parse.quote(username)}/",
        }

        for platform, profile_url in platforms.items():
            try:
                req = urllib.request.Request(
                    profile_url,
                    headers={
                        "User-Agent": "Mozilla/5.0 (compatible; automative-osint/1.0)"
                    },
                )
                with urllib.request.urlopen(req, timeout=self.timeout) as response:
                    findings["platform_presence"][platform] = {
                        "url": profile_url,
                        "http_status": response.status,
                        "likely_exists": response.status < 400,
                    }
            except urllib.error.HTTPError as err:
                findings["platform_presence"][platform] = {
                    "url": profile_url,
                    "http_status": err.code,
                    "likely_exists": err.code not in (404, 410),
                }
            except urllib.error.URLError as err:
                findings["platform_presence"][platform] = {
                    "url": profile_url,
                    "error": str(err),
                }

            time.sleep(self.request_delay)

        return findings


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Automative OSINT: passive indicator enrichment CLI"
    )
    parser.add_argument(
        "indicators",
        nargs="+",
        help="Indicators to investigate (domain/email/ip/username)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=8.0,
        help="Per-request timeout in seconds (default: 8)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.35,
        help="Delay between outbound requests in seconds (default: 0.35)",
    )
    parser.add_argument(
        "--output",
        default="osint_report.json",
        help="Output report path (default: osint_report.json)",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    collector = AutomativeOSINT(timeout=args.timeout, request_delay=args.delay)

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "tool": "automative-osint",
        "results": [],
    }

    for indicator in args.indicators:
        result = collector.collect(indicator)
        report["results"].append(asdict(result))

    with open(args.output, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)

    print(f"Report written to {args.output}")


if __name__ == "__main__":
    main()
