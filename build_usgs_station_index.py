#!/usr/bin/env python3
# build_usgs_station_index.py
# Builds stations.json + stations.min.json of all USGS sites with 00065 (gage height)
# including: site_no, name, state, city (parsed), county_name, lat, lon

import re, json, time, sys
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

STATES = [
    "AL","AR","AZ","CA","CO","CT","DE","FL","GA","IA","ID","IL","IN","KS","KY","LA",
    "MA","MD","ME","MI","MN","MO","MS","MT","NC","ND","NE","NH","NJ","NM","NV","NY",
    "OH","OK","OR","PA","RI","SC","SD","TN","TX","UT","VA","VT","WA","WI","WV","WY"
]

STATE_FULL = {
    "AL":"Alabama","AR":"Arkansas","AZ":"Arizona","CA":"California","CO":"Colorado","CT":"Connecticut",
    "DE":"Delaware","FL":"Florida","GA":"Georgia","IA":"Iowa","ID":"Idaho","IL":"Illinois","IN":"Indiana",
    "KS":"Kansas","KY":"Kentucky","LA":"Louisiana","MA":"Massachusetts","MD":"Maryland","ME":"Maine",
    "MI":"Michigan","MN":"Minnesota","MO":"Missouri","MS":"Mississippi","MT":"Montana","NC":"North Carolina",
    "ND":"North Dakota","NE":"Nebraska","NH":"New Hampshire","NJ":"New Jersey","NM":"New Mexico","NV":"Nevada",
    "NY":"New York","OH":"Ohio","OK":"Oklahoma","OR":"Oregon","PA":"Pennsylvania","RI":"Rhode Island",
    "SC":"South Carolina","SD":"South Dakota","TN":"Tennessee","TX":"Texas","UT":"Utah","VA":"Virginia",
    "VT":"Vermont","WA":"Washington","WI":"Wisconsin","WV":"West Virginia","WY":"Wyoming"
}

USGS_SITE_RDB = "https://waterservices.usgs.gov/nwis/site/?format=rdb&stateCd={state}&parameterCd=00065&siteOutput=expanded"
USGS_COUNTY_JSON = "https://help.waterdata.usgs.gov/code/county_query?fmt=json&state_cd={state}"

HEADERS = {"User-Agent": "mccoy.fish-station-index/1.0"}

def http_get(url):
    req = Request(url, headers=HEADERS)
    with urlopen(req, timeout=60) as resp:
        return resp.read()

def parse_rdb(text):
    lines = [ln for ln in text.splitlines() if ln and not ln.startswith("#")]
    if not lines: return [], []
    header = lines[0].split("\t")
    rows = []
    for ln in lines[1:]:
        parts = ln.split("\t")
        if len(parts) != len(header): continue
        row = {header[i]: parts[i] for i in range(len(header))}
        rows.append(row)
    return header, rows

def title_case_city(s):
    s = s.strip()
    if not s: return ""
    parts = re.split(r"([\s\-'/\.])", s.lower())
    out = []
    for p in parts:
        if not p or re.match(r"[\s\-'/\.]", p): out.append(p)
        else: out.append(p[0].upper() + p[1:])
    city = "".join(out)
    city = re.sub(r"\bNw\b","NW",city); city = re.sub(r"\bNe\b","NE",city)
    city = re.sub(r"\bSe\b","SE",city); city = re.sub(r"\bSw\b","SW",city)
    return city.strip()

def parse_city_from_station_name(name, state_code):
    if not name: return ""
    s = re.sub(r"\s+"," ", name.strip())
    m = re.search(r"\b(AT|NEAR|NR|ABOVE|BELOW)\s+([^,]+)", s, flags=re.IGNORECASE)
    if m:
        candidate = m.group(2).strip()
        candidate = re.sub(rf"\b{state_code}\b\.?$","",candidate,flags=re.IGNORECASE).strip()
        full = STATE_FULL.get(state_code,"")
        if full:
            candidate = re.sub(rf"\b{re.escape(full)}\b\.?$","",candidate,flags=re.IGNORECASE).strip()
        candidate = re.sub(r"\b(CO|COUNTY|RES|RESERVOIR|DAM|GATE|DIVERSION|GAGING\s*STATION)\b\.?$",
                           "",candidate,flags=re.IGNORECASE).strip()
        if re.search(r"\b(RIVER|CREEK|CRK|FORK|BRANCH|BAYOU|CANAL|SLOUGH|BROOK|LAKE|WASH)\b",
                     candidate, flags=re.IGNORECASE):
            return ""
        return title_case_city(candidate)
    m2 = re.search(rf",\s*{state_code}\b", s, flags=re.IGNORECASE)
    if m2:
        before = s[:m2.start()]
        toks = before.split(",")
        cand = toks[-1].strip()
        if cand and not re.search(r"\b(RIVER|CREEK|CRK|FORK|BRANCH|BAYOU|CANAL|SLOUGH|BROOK|LAKE|WASH)\b",
                                  cand, flags=re.IGNORECASE):
            return title_case_city(cand)
    return ""

def build_county_map(state):
    url = USGS_COUNTY_JSON.format(state=state)
    try:
        raw = http_get(url)
        j = json.loads(raw.decode("utf-8"))
        return {c.get("value"): c.get("name") for c in j.get("codes",[]) if c.get("value") and c.get("name")}
    except Exception:
        return {}

def fetch_state_rows(state):
    url = USGS_SITE_RDB.format(state=state)
    raw = http_get(url).decode("utf-8","replace")
    header, rows = parse_rdb(raw)
    return rows

def main():
    all_records = {}
    total = 0
    print("Building county maps…")
    county_by_state = {}
    for st in STATES:
        county_by_state[st] = build_county_map(st)
        time.sleep(0.2)
    print("Fetching stations…")
    for st in STATES:
        try:
            rows = fetch_state_rows(st)
        except (HTTPError, URLError) as e:
            print(f"[{st}] fetch error: {e}", file=sys.stderr)
            continue
        added = 0
        for r in rows:
            site_no = (r.get("site_no") or "").strip()
            name = (r.get("station_nm") or "").strip()
            lat = r.get("dec_lat_va") or ""
            lon = r.get("dec_long_va") or ""
            county_cd = r.get("county_cd") or ""
            try:
                latf = float(lat); lonf = float(lon)
            except ValueError:
                continue
            if not site_no or not name: continue
            city = parse_city_from_station_name(name, st)
            county_name = county_by_state.get(st, {}).get(county_cd, "")
            rec = {
                "site_no": site_no,
                "name": name,
                "state": st,
                "city": city,
                "county_name": county_name,
                "lat": latf,
                "lon": lonf
            }
            if site_no not in all_records:
                all_records[site_no] = rec
                added += 1
        total += added
        print(f"[{st}] +{added} (total {total})")
        time.sleep(0.3)
    out = sorted(all_records.values(), key=lambda x: (x["state"], x["name"]))
    with open("stations.json","w",encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    with open("stations.min.json","w",encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",",":"))
    print(f"Done: {len(out)} stations")
if __name__ == "__main__":
    main()
