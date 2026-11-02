"""Holt die aktuelle Belegung der HYROX-Kurse im Pace Club München (bsport) und schreibt pace.json.

Läuft per GitHub Actions alle 30 Minuten. Bei Fehlern bleibt die alte Datei unverändert.
"""
import datetime
import json
import sys
import urllib.request
from zoneinfo import ZoneInfo

API = "https://api.production.bsport.io/book/v1"
COMPANY, ESTABLISHMENT = 3511, 12427


def get(url):
    req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "Mozilla/5.0 (Trainingsplan)"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def short(first, last):
    first = (first or "").strip().split(" ")[0]
    last = (last or "").strip().split(" ")[-1] if (last or "").strip() else ""
    return (first[:1].upper() + first[1:] + (" " + last[:1].upper() + "." if last else "")).strip()


def fmt(name):
    n = name.lower()
    for key, code in (("simulation doubles", "sd"), ("simulation", "sm"), ("doubles", "do"), ("sprint", "sp"), ("signature", "si")):
        if key in n:
            return code
    return name.strip()


today = datetime.datetime.now(ZoneInfo("Europe/Berlin")).date()
frm, to = today.isoformat(), (today + datetime.timedelta(days=14)).isoformat()
try:
    offers = get(f"{API}/offer/?company={COMPANY}&min_date={frm}&max_date={to}&page_size=400")["results"]
except Exception as e:  # noqa: BLE001
    print("Abruf fehlgeschlagen:", e)
    sys.exit(0)

coach = {}
try:
    for r in get(f"{API}/coach/?company={COMPANY}&page_size=200").get("results", []):
        u = r.get("user") or {}
        coach[str(r.get("id"))] = "" if r.get("id") == 106800 else short(u.get("first_name"), u.get("last_name"))
except Exception as e:  # noqa: BLE001
    print("Coaches nicht abrufbar:", e)

names, rows = [], []
for r in offers:
    an = (r.get("activity_name") or "").strip()
    if r.get("establishment") != ESTABLISHMENT or not an.lower().startswith("class"):
        continue
    co = r.get("coach_override")
    cn = co.strip() if isinstance(co, str) and co.strip() else coach.get(str(r.get("coach")), "")
    if cn and cn not in names:
        names.append(cn)
    wp = next((p for p in (r.get("partnership_offers") or []) if p.get("partnership_identifier") == "wellpass"), {})
    flags = (1 if wp.get("status") == "LIVE" and wp.get("allowed_on_partner") and wp.get("spot_limit") != 0 else 0) \
        | (2 if r.get("available") else 0) | (4 if r.get("full") else 0)
    rows.append([r["id"], r["date_start"][:16], r.get("duration_minute") or 60, fmt(an.split("-", 1)[-1]),
                 names.index(cn) if cn else -1, r.get("effectif") or 0, r.get("validated_booking_count") or 0, flags])
rows.sort(key=lambda x: x[1])
if len(rows) < 10:
    print("Zu wenige Kurse, nichts geschrieben:", len(rows))
    sys.exit(0)

now = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
try:
    old = json.load(open("pace.json", encoding="utf-8"))
except Exception:  # noqa: BLE001
    old = {}
same = old.get("c") == rows and old.get("coaches") == names and old.get("to") == to
age = now - datetime.datetime.fromisoformat(str(old.get("updatedAt", "2000-01-01T00:00:00Z")).replace("Z", "+00:00"))
if same and age < datetime.timedelta(hours=2):
    print("Keine Änderung")
    sys.exit(0)
doc = {"v": 2, "updatedAt": now.isoformat().replace("+00:00", "Z"), "from": frm, "to": to, "coaches": names, "c": rows}
with open("pace.json", "w", encoding="utf-8") as f:
    json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))
print("pace.json:", len(rows), "Kurse,", frm, "bis", to)
