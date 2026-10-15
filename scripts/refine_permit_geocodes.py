#!/usr/bin/env python3
"""Raise permit-address geocoding precision using *exact* Geolonia ABR v2 matches.

Do not conflate lots with buildings; all coordinates are representative points.
A partial lot number, a town-only match, or an inconsistent municipality is never
promoted to street precision. No Google/booking-site geocoder or TOS-restricted data.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
from io import StringIO
import json
from pathlib import Path
import re
import sys
import time
import unicodedata
from urllib.parse import quote

import requests
from refresh_data import MUNICIPALITIES, municipality

ROOT=Path(__file__).resolve().parents[1]
API="https://japanese-addresses-v2.geoloniamaps.com/api/ja"
LICENSE="https://creativecommons.org/licenses/by/4.0/deed.ja"
TIMEOUT=30

def standard(text):
    s=unicodedata.normalize("NFKC",str(text or ""))
    n={"一":1,"二":2,"三":3,"四":4,"五":5,"六":6,"七":7,"八":8,"九":9,"十":10}
    def arabic(m):
        v=m.group(1)
        if v in n: k=n[v]
        elif v.startswith("十"):k=10+n.get(v[1:],0)
        elif v.endswith("十"):k=n.get(v[:-1],1)*10
        else:return m.group(0)
        return f"{k}丁目"
    s=re.sub(r"([一二三四五六七八九十]+)丁目",arabic,s)
    return s.translate(str.maketrans({"−":"-","‐":"-","－":"-","ー":"-","ｰ":"-"})).replace(" ","").replace("\u3000","")

def city_town_suffix(address,city,area):
    addr=standard(address)
    town=standard(area)
    # Remove pref and optionally county from user address; matching starts at city.
    start=addr.find(city)
    if start<0:return None
    remainder=addr[start+len(city):]
    if not remainder.startswith(town):return None
    return remainder[len(town):]

def parse_numbers(s):
    """Exact numeric suffix only. Any residual room/lot letter rejects the match."""
    s=standard(s).replace("番地","-").replace("番","-").replace("号","")
    s=re.sub(r"[-]+","-",s).strip("-")
    if not re.fullmatch(r"\d+(?:-\d+){0,2}",s):return None
    return tuple(str(int(n)) for n in s.split("-"))

def is_ehime(coord):
    return isinstance(coord,(list,tuple)) and len(coord)==2 and all(isinstance(x,(int,float)) for x in coord) and 132<=coord[0]<=134.2 and 32.8<=coord[1]<=34.5

def gsi_exact(address,title):
    """Full street-number agreement; partial 877 vs 877-2 is not street-level."""
    city=municipality(address)
    if not city or city not in title:return False
    a=standard(address)
    t=standard(title)
    a=a[a.index(city)+len(city):]
    t=t[t.index(city)+len(city):]
    # Match identical town name (before first numeral) and full street numeric tuple.
    first=re.search(r"\d",a)
    if not first:return False
    town=a[:first.start()]
    if not town:return False
    if not t.startswith(town):return False
    tail=a[len(town):]
    cand=t[len(town):]
    # Handle kanji-address dashes and block/lot syntax equivalently; reject any gaps.
    def numbers(raw):
        raw=raw.replace("丁目","-").replace("番地","-").replace("番","-").replace("号","")
        raw=re.sub(r"-+","-",raw).strip("-")
        return tuple(str(int(x)) for x in raw.split("-")) if re.fullmatch(r"\d+(?:-\d+)*",raw) else None
    return numbers(tail) is not None and numbers(tail)==numbers(cand)

def name_for_aza(entry):
    return (entry.get("oaza_cho") or "")+(entry.get("chome") or "")+(entry.get("koaza") or "")

class ABR:
    def __init__(self,session=None):
        self.s=session or requests.Session()
        self.s.headers.setdefault("User-Agent","EhimeMinpakuAtlas/0.4 (CC BY dataset; https://github.com/ryotamatsuki/ehimeminpaku3dmap)")
        self.towns={}
        self.ranges={}
        self.failures=[]
        self.calls=0
        self.updated={}
    def fetch_towns(self,city):
        if city in self.towns:return self.towns[city]
        # Paths use municipality only; if town belongs to county, try county-prefixed fallback.
        paths=[city]
        all_counties={"久万高原町":"上浮穴郡","上島町":"越智郡","松前町":"伊予郡","砥部町":"伊予郡","内子町":"喜多郡","伊方町":"西宇和郡","松野町":"北宇和郡","鬼北町":"北宇和郡","愛南町":"南宇和郡"}
        if city in all_counties:paths.insert(0,all_counties[city]+city)
        for location in paths:
            url=f"{API}/{quote('愛媛県')}/{quote(location)}.json"
            try:
                r=self.s.get(url,timeout=TIMEOUT)
                if r.status_code==404:continue
                r.raise_for_status()
                payload=r.json()
                items=payload.get("data")
                if isinstance(items,list):
                    self.updated[city]=payload.get("meta",{}).get("updated")
                    self.towns[city]=[(x,name_for_aza(x)) for x in items if isinstance(x,dict) and x.get("csv_ranges")]
                    self.towns[city].sort(key=lambda x:len(standard(x[1])),reverse=True)
                    return self.towns[city]
            except (requests.RequestException,ValueError) as e:
                self.failures.append(f"{city}: town API {type(e).__name__}: {str(e)[:140]}")
        self.towns[city]=[]
        return []
    def get_range(self,city,kind,spec):
        start,length=spec["start"],spec["length"]
        key=(city,kind,start,length)
        if key in self.ranges:return self.ranges[key]
        if not isinstance(start,int) or not isinstance(length,int) or length<=0 or length>4_000_000:
            self.failures.append(f"{city}: unsafe range {start}+{length}")
            return []
        # Correct API endpoints, including optional county prefix used in town JSON.
        variants=[city]
        county={"久万高原町":"上浮穴郡","上島町":"越智郡","松前町":"伊予郡","砥部町":"伊予郡","内子町":"喜多郡","伊方町":"西宇和郡","松野町":"北宇和郡","鬼北町":"北宇和郡","愛南町":"南宇和郡"}
        if city in county:variants.insert(0,county[city]+city)
        for c in variants:
            url=f"{API}/{quote('愛媛県')}/{quote(c+'-'+kind)}.txt"
            try:
                r=self.s.get(url,headers={"Range":f"bytes={start}-{start+length-1}"},timeout=TIMEOUT,stream=True)
                if r.status_code==404:r.close();continue
                if r.status_code!=206:
                    # Reject 200 (entire potentially huge file). Do not accidentally treat byte-0
                    # content as data from an arbitrary town.
                    self.failures.append(f"{city}: HTTP {r.status_code} (Range unsupported)")
                    r.close();return []
                raw=r.content
                if len(raw)!=length:
                    self.failures.append(f"{city}: short range {len(raw)}/{length}");return []
                text=raw.decode("utf-8-sig")
                rows=list(csv.reader(StringIO(text)))
                self.calls+=1
                self.ranges[key]=rows
                return rows
            except (requests.RequestException,UnicodeDecodeError) as e:
                self.failures.append(f"{city}: {kind} API {type(e).__name__}: {str(e)[:100]}")
        self.ranges[key]=[]
        return []
    def match(self,address):
        city=municipality(address)
        if not city:return None
        for aza,name in self.fetch_towns(city):
            if not name:continue
            suffix=city_town_suffix(address,city,name)
            if suffix is None:continue
            requested=parse_numbers(suffix)
            if requested is None:continue
            ranges=aza.get("csv_ranges",{})
            candidates=[]
            for kind in ("住居表示","地番"):
                span=ranges.get(kind)
                if not isinstance(span,dict):continue
                rows=self.get_range(city,kind,span)
                if len(rows)<3:continue
                header=rows[1]
                if not ("lng" in header and "lat" in header):continue
                for row in rows[2:]:
                    if len(row)!=len(header):continue
                    obj=dict(zip(header,row))
                    keys=(["blk_num","rsdt_num","rsdt_num2"] if kind=="住居表示" else ["prc_num1","prc_num2","prc_num3"])
                    vals=[obj.get(k,"").strip() for k in keys]
                    if kind=="住居表示":
                        if not vals[1]:continue
                    else:
                        if not vals[0]:continue
                    try:
                        nums=tuple(str(int(x)) for x in vals if x)
                        point=[float(obj["lng"]),float(obj["lat"])]
                    except (ValueError,KeyError):continue
                    if nums==requested and is_ehime(point):
                        candidates.append((tuple(point),kind))
            locations=set(p for p,k in candidates)
            # Different locations for one canonical address need human QA.
            if len(locations)!=1:continue
            point=list(locations.pop())
            return dict(coord=point,precision="street",address_level=candidates[0][1],
                source="Geolonia Japanese Addresses v2 / Digital Agency ABR",
                source_url="https://github.com/geolonia/japanese-addresses-v2",
                license="CC BY 4.0",license_url=LICENSE,
                matched_address=f"愛媛県{city}{name}{'-'.join(requested)}",
                evidence="exact-city-town-and-all-address-numbers")
        return None

def refine(facilities,existing,matcher,limit=0):
    cache={key:dict(val) for key,val in existing.items()}
    processed=0
    changed=0
    upgraded_by_gsi=0
    for record in facilities:
        key=record["id"]
        old=cache.get(key,{})
        if old.get("address")!=record["address"]:continue
        if old.get("precision")=="street":continue
        # Baseline contains candidate GSI title and coordinate, but may be a town centroid.
        # Only upgrade with *complete* numeric address match.
        if is_ehime(old.get("coord")) and gsi_exact(record["address"],old.get("geocode_title","")):
            cache[key]={**old,"precision":"street","source":"GSI address search",
               "evidence":"verified-full-address-number-match",
               "reviewed_at":datetime.now(timezone.utc).isoformat()}
            upgraded_by_gsi+=1;changed+=1;continue
        if limit and processed>=limit:continue
        processed+=1
        match=matcher.match(record["address"])
        if match:
            cache[key]={**old,**match,"address":record["address"],
                        "checked_at":datetime.now(timezone.utc).isoformat()}
            changed+=1
        if processed%100==0:
            print(f"ABR processed {processed}; upgraded {changed}, GSI upgraded {upgraded_by_gsi}",flush=True)
    return cache,dict(abr_attempted=processed,upgraded=changed,gsi_upgrades=upgraded_by_gsi,abr_upgrades=changed-upgraded_by_gsi)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--limit",type=int,default=0,help="Number of ABR queries for initial test; 0=all")
    p.add_argument("--input",type=Path,default=ROOT/"data/licensed_lodging.json")
    p.add_argument("--coordinates",type=Path,default=ROOT/"data/permit_coordinates.json")
    args=p.parse_args()
    facilities=json.loads(args.input.read_text(encoding="utf-8"))["facilities"]
    data=json.loads(args.coordinates.read_text(encoding="utf-8"))
    before=Counter(x.get("precision") for x in data["coordinates"].values())
    matcher=ABR()
    new,stats=refine(facilities,data["coordinates"],matcher,args.limit)
    after=Counter(x.get("precision") for x in new.values())
    data["coordinates"]=new
    data["summary"].update({"street":after["street"],"district":after["district"],
                            "unresolved":after["unresolved"],"total":len(facilities),
                            "attempted":len(new)})
    data["refinement"]={"method":"full-address GSI verification, then ABR exact lot/residence match",
        "before":dict(before),"after":dict(after),**stats,"abr_town_api_cities":len(matcher.towns),
        "abr_range_requests":matcher.calls,"warnings":matcher.failures[:60],
        "source":"Geolonia Japanese Addresses v2; derived from Digital Agency ABR",
        "source_url":"https://github.com/geolonia/japanese-addresses-v2",
        "license":"CC BY 4.0","license_url":LICENSE,
        "updated_at":datetime.now(timezone.utc).isoformat()}
    # Fail closed if the new matcher downgraded previous precision or altered record count.
    if after["street"]<before["street"] or len(new)!=len(data["coordinates"]):
        raise RuntimeError("Precision downgrade or record loss detected")
    if args.limit==0 or stats["upgraded"]:
        args.coordinates.write_text(json.dumps(data,ensure_ascii=False,separators=(",",":"))+"\n",encoding="utf-8")
    print("RESULT:",json.dumps({"before":dict(before),"after":dict(after),"statistics":stats,
         "cities":len(matcher.towns),"ranges":matcher.calls,"warnings":matcher.failures[:12]},ensure_ascii=False),flush=True)

if __name__=="__main__":main()
