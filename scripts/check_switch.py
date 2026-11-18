"""Verify the customer tariff-change flow end to end (then switch back)."""

from __future__ import annotations

import http.cookiejar
import re
import urllib.error
import urllib.parse
import urllib.request

BASE = "http://127.0.0.1:5000"
results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):  # noqa: ANN002, ANN003
        return None


class Client:
    def __init__(self) -> None:
        jar = http.cookiejar.CookieJar()
        self.op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
        self.raw = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(jar), _NoRedirect
        )

    def get(self, path: str) -> tuple[int, str]:
        try:
            with self.op.open(BASE + path, timeout=15) as r:
                return r.status, r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode("utf-8", "replace")

    def post(self, path: str, data: dict) -> tuple[int, str]:
        """POST without following redirects (so flash survives for assertions)."""
        req = urllib.request.Request(BASE + path, data=urllib.parse.urlencode(data).encode(),
                                     method="POST")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        try:
            with self.raw.open(req, timeout=15) as r:
                return r.status, r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode("utf-8", "replace")

    def csrf(self, path: str) -> str:
        _, body = self.get(path)
        return re.search(r'name="_csrf" value="([^"]+)"', body).group(1)


c = Client()

# login as demo customer 1 (originally on BKC-0001)
s, _ = c.get("/customer/login")
tok = re.search(r'name="_csrf" value="([^"]+)"', _).group(1)
s, _ = c.post("/customer/login",
              {"email": "customer@demo.local", "password": "Demo-Customer-2026", "_csrf": tok})
check("customer login", s in (200, 302), f"got {s}")

# recommendations page shows the change-tariff catalog
s, body = c.get("/customer/recommendations")
check("recommendations 200", s == 200, f"got {s}")
check("'Tarifinizi dəyişin' section", "Tarifinizi dəyişin" in body)
check("switch buttons present", body.count('action="/customer/change-tariff"') >= 3,
      "{} forms".format(body.count('action="/customer/change-tariff"')))

# find a non-current plan to switch to
m = re.findall(r'name="tariff" value="([^"]+)"', body)
current = None
cur = re.search(r'<input type="hidden" name="tariff" value="([^"]+)"', body)
others = [v for v in dict.fromkeys(m)]
check("catalog lists plans", len(others) >= 2, f"{len(others)} plans in forms")

# discover the current tariff from the dashboard
s, dash = c.get("/customer/")
cur_m = re.search(r'sim-title">([^<]+)</h1>', dash)
current = cur_m.group(1).strip() if cur_m else None
check("dashboard shows current tariff", current is not None, current or "")
target = next(v for v in others if v != current)
check("found a different plan to switch to", target != current, f"{current} → {target}")

# switch (POST with CSRF)
s, body = c.post("/customer/change-tariff",
                 {"tariff": target, "_csrf": c.csrf("/customer/recommendations")})
check("switch POST redirects (302)", s == 302, f"got {s}")

# dashboard reflects the new plan + flash message
s, dash = c.get("/customer/")
check("dashboard 200 after switch", s == 200, f"got {s}")
new_cur = re.search(r'sim-title">([^<]+)</h1>', dash)
check("dashboard shows new tariff", new_cur and new_cur.group(1).strip() == target,
      new_cur.group(1).strip() if new_cur else "none")
check("flash success message shown", "Tarif dəyişdi" in dash)
check("tenure wording ('switched recently')", "yaxınlarda dəyişdirildi" in dash)
check("end date back to source-missing wording", "Mənbə məlumatlarında yoxdur" in dash)
check("renewal demo-mock note cleared", "demo təxmini" not in dash)

# recommendation snapshot regenerated for the new current plan
s, body = c.get("/customer/recommendations")
check("recommendations regenerated", s == 200 and target in body)
check("current-plan marker on new tariff",
      f">{target}" in body and "Sizin cari planınız" in body)

# switching to the same plan is a no-op
s, body = c.post("/customer/change-tariff",
                 {"tariff": target, "_csrf": c.csrf("/customer/recommendations")})
s, dash = c.get("/customer/")
check("already-current handled", "artıq" in dash)

# unknown tariff rejected
s, body = c.post("/customer/change-tariff",
                 {"tariff": "No Such Plan", "_csrf": c.csrf("/customer/recommendations")})
s, dash = c.get("/customer/recommendations")
check("unknown tariff rejected", "kataloqda yoxdur" in dash)

# switch back to the original plan
s, body = c.post("/customer/change-tariff",
                 {"tariff": current, "_csrf": c.csrf("/customer/recommendations")})
s, dash = c.get("/customer/")
back = re.search(r'sim-title">([^<]+)</h1>', dash)
check("switched back to original plan", back and back.group(1).strip() == current,
      back.group(1).strip() if back else "none")

# CSRF still enforced
s, body = c.post("/customer/change-tariff", {"tariff": target})
# will follow redirect; check via no-token on a fresh anonymous session instead
anon = Client()
anon.get("/customer/login")
s, _ = anon.post("/customer/change-tariff", {"tariff": target, "_csrf": "bogus"})
check("invalid CSRF rejected", s == 400, f"got {s}")

failed = [r for r in results if not r[1]]
print(f"\nSwitch-flow check: {len(results) - len(failed)}/{len(results)} passed")
raise SystemExit(1 if failed else 0)
