#!/usr/bin/env python3
"""Geocode public, CC BY-licensed permit addresses to a separate incremental cache.

The output is NOT used to relabel a housing-accommodation declaration.
District matches are not treated as true positions of premises.
"""
from __future__ import annotations
import argparse
import json
import os
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import requests
from refresh_data import basename, geocode, municipality, recognized_precision

ROOT=Path(__file__).resolve().parents[1]
INPUT=ROOT/"data"/"licensed_lodging.json"
OUTPUT=ROOT/"data"/"permit_coordinates.json"

def run(input_file:Path,output_file:Path,limit:int=0,interval:float=0.6,session=None):
    facilities=json.loads(input_file.read_text(encoding="utf-8"))["facilities"]
    old=json.loads(output_file.read_text(encoding="utf-8")) if output_file.exists() else {}
    cache=old.get("coordinates",{})
    session=session or requests.Session()
    session.headers["User-Agent"]="EhimeMinpakuAtlas/0.3 (non-commercial public data research; https://github.com/ryotamatsuki/ehimeminpaku3dmap)"
    attempted=0;now=datetime.now(timezone.utc).isoformat()
    for item in facilities:
        key=item["id"];address=item["address"]
        if (cache.get(key,{}).get("address")==address and
            cache[key].get("precision") in ("street","district","unresolved")):
            continue
        if limit and attempted>=limit:break
        found=geocode(address,session)
        if found:
            cache[key]={"address":address,"coord":found["coord"],
                        "precision":found["precision"],
                        "geocode_title":found.get("geocode_title",""),
                        "checked_at":now}
        else:
            cache[key]={"address":address,"coord":None,
                        "precision":"unresolved","geocode_title":"","checked_at":now}
        attempted+=1
        if attempted%25==0:
            save(output_file,cache,facilities)
            print(f"Processed {attempted}; total cached {len(cache)} / {len(facilities)}",flush=True)
        if interval:time.sleep(interval)
    return save(output_file,cache,facilities)

def save(output_file:Path,cache:dict,facilities:list):
    active={p["id"]:cache[p["id"]] for p in facilities if p["id"] in cache}
    counts=Counter(item.get("precision") for item in active.values())
    payload={"generated_at":datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
             "source":"Geocoded addresses from official CC BY hotel/ryokan permit lists using GSI address search",
             "notice":"Coordinates are estimates; only street-address-level matches qualify as within-mesh candidates. Administrative centroid geocodes are excluded from geographic inclusion.",
             "summary":{"total":len(facilities),"attempted":len(active),
                        "street":counts["street"],"district":counts["district"],
                        "unresolved":counts["unresolved"]},
             "coordinates":active}
    output_file.parent.mkdir(parents=True,exist_ok=True)
    output_file.write_text(json.dumps(payload,ensure_ascii=False,separators=(",",":"))+"\n",encoding="utf-8")
    print("Coordinate cache:",payload["summary"],flush=True)
    return payload

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--input",type=Path,default=INPUT)
    parser.add_argument("--output",type=Path,default=OUTPUT)
    parser.add_argument("--limit",type=int,default=0)
    parser.add_argument("--interval",type=float,default=0.6)
    args=parser.parse_args()
    if args.limit<0 or args.interval<0:parser.error("limits and intervals must be nonnegative")
    run(args.input,args.output,args.limit,args.interval)

if __name__=="__main__":main()
