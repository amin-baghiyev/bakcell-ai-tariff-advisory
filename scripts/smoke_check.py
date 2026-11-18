"""End-to-end smoke check against a running server (default http://127.0.0.1:5000).

Usage: python scripts/smoke_check.py [base_url]
Exit code 0 = all checks passed. Used to verify core flows for the demo.
"""

from __future__ import annotations

import http.cookiejar
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:5000"
PHONE_RE = re.compile(r"\+994|\d{2}\s?\d{3}\s?\d{2}\s?\d{2}")
RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, ok, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):  # noqa: ANN002, ANN003
        return None


class Client:
    def __init__(self):
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.jar)
        )
        self.raw_opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.jar), _NoRedirect
        )
        self.last_html = ""

    def get(self, path: str, follow: bool = True) -> tuple[int, str]:
        opener = self.opener if follow else self.raw_opener
        try:
            with opener.open(BASE + path, timeout=15) as r:
                body = r.read().decode("utf-8", "replace")
                self.last_html = body
                return r.status, body
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")
            self.last_html = body
            return e.code, body

    def post(self, path: str, data: dict, follow: bool = True) -> tuple[int, str]:
        payload = urllib.parse.urlencode(data).encode()
        req = urllib.request.Request(BASE + path, data=payload, method="POST")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        opener = self.opener if follow else self.raw_opener
        try:
            with opener.open(req, timeout=15) as r:
                body = r.read().decode("utf-8", "replace")
                self.last_html = body
                return r.status, body
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")
            self.last_html = body
            return e.code, body

    def csrf(self) -> str:
        m = re.search(r'name="_csrf" value="([^"]+)"', self.last_html)
        return m.group(1) if m else ""


def login(client: Client, path: str, email: str, password: str) -> int:
    client.get(path)
    return client.post(path, {"email": email, "password": password,
                              "_csrf": client.csrf()}, follow=False)[0]


def main() -> int:
    print(f"Smoke check against {BASE}")

    # 1. health
    c = Client()
    status, body = c.get("/health")
    try:
        data = json.loads(body)
        ok = status == 200 and data.get("status") == "ok" and data["checks"]["customers"] == 100
    except Exception:
        ok, data = False, {}
    check("/health ok with 100 customers", ok, str(data.get("checks")))

    # 2. separate login pages (default locale = AZ)
    c = Client()
    s, body = c.get("/customer/login")
    check("customer login page", s == 200 and "Müştəri girişi" in body)
    check("no admin link on customer login", "/admin" not in body)
    c2 = Client()
    s2, body2 = c2.get("/admin/login")
    check("admin login page (separate)", s2 == 200 and "Admin girişi" in body2)

    # 3. wrong creds rejected
    c = Client()
    c.get("/customer/login")
    s, _ = c.post("/customer/login", {"email": "customer@demo.local", "password": "nope",
                                     "_csrf": c.csrf()})
    check("wrong password rejected (401)", s == 401)

    # 4. CSRF required
    c = Client()
    c.get("/customer/login")
    s, _ = c.post("/customer/login", {"email": "customer@demo.local",
                                     "password": "Demo-Customer-2026", "_csrf": "bad"})
    check("POST without valid CSRF rejected (400)", s == 400)

    # 5. customer login + dashboard with Suggested tariffs row (default AZ)
    c = Client()
    s = login(c, "/customer/login", "customer@demo.local", "Demo-Customer-2026")
    s2, body = c.get("/customer")
    check("customer login → dashboard", s in (302, 200) and s2 == 200)
    check("AZ: html lang=az", 'lang="az"' in body)
    check("dashboard has 'Təklif olunan tariflər' row", "Təklif olunan tariflər" in body)
    check("dashboard shows current tariff card", "Cari tarif" in body and "Klass 10" in body)
    check("no phone number in dashboard", not PHONE_RE.search(body))
    check("top suggestion badge present",
          "Ən yaxşı təklif" in body or "Ən uyğun" in body)

    # 6. customer pages (AZ)
    for path, marker in [
        ("/customer/recommendations", "Cari planınızla müqayisə"),
        ("/customer/history", "İstifadə və xərc tarixçəsi"),
        ("/customer/notifications", "Bildiriş üstünlükləri"),
    ]:
        s, body = c.get(path)
        check(f"GET {path}", s == 200 and marker in body)
        check(f"no phone on {path}", not PHONE_RE.search(body))

    # reminder visible for demo customer (seeded end date within 5 days)
    s, body = c.get("/customer/notifications")
    check("five-day reminder visible in-app",
          "Tarif bitmə xəbərdarlığı" in body or "Demo xəbərdarlıq" in body)
    check("demo notification disclaimer shown", "tətbiqdaxili" in body)

    # 7. customer cannot access admin
    s, _ = c.get("/admin")
    check("customer blocked from /admin (403)", s == 403)
    s, _ = c.get("/admin/customers")
    check("customer blocked from /admin/customers (403)", s == 403)

    # 8. admin login + dashboard + tables
    a = Client()
    s = login(a, "/admin/login", "admin@demo.local", "Demo-Admin-2026")
    s2, body = a.get("/admin")
    check("admin login → dashboard", s in (302, 200) and s2 == 200)
    check("dashboard has business stats", "Ümumi müştərilər" in body and "Tarif paylanması" in body)
    check("unavailable metrics shown as unavailable", "Əlçatmaz" in body)
    check("no phone in admin dashboard", not PHONE_RE.search(body))

    s, body = a.get("/admin/customers")
    check("customer/recommendation table", s == 200 and "Təklif olunan tarif" in body)
    check("table has reason column + pagination",
          "Səbəb" in body and ("səhifə" in body.lower()))
    # reasons must be plain language, never snake_case keywords
    cells = re.findall(r'class="reason-cell">(.*?)</td>', body, re.S)
    kw = re.compile(r"\b[a-z]+(?:_[a-z]+)+\b")
    leaks = [x for x in cells if kw.search(x)]
    check("admin reasons are plain text (no keywords)",
          bool(cells) and not leaks, f"{len(cells)} cells, {len(leaks)} with keywords")
    s, body = a.get("/admin/customers/BKC-0001")
    check("admin customer detail", s == 200 and "BKC-0001" in body)
    check("detail has no phone number", not PHONE_RE.search(body))
    cells = re.findall(r'class="reason-cell">(.*?)</td>', body, re.S)
    leaks = [x for x in cells if kw.search(x)]
    check("detail reasons are plain text (no keywords)", not leaks,
          f"{len(cells)} cells, {len(leaks)} with keywords")
    s, _ = a.get("/admin/customers/NOPE-9999")
    check("unknown customer → 404", s == 404)

    # 9. anonymous redirected (no-follow to observe the first hop: 308 slash → 302 login)
    anon = Client()
    s, body = anon.get("/customer", follow=False)
    check("anonymous /customer → login redirect", s in (302, 308), f"got {s}")
    s, _ = anon.get("/admin", follow=False)
    check("anonymous /admin → admin login redirect", s in (302, 308), f"got {s}")

    passed = sum(1 for _, ok, _ in RESULTS if ok)
    print(f"\n{passed}/{len(RESULTS)} checks passed")
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
