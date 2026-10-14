#!/usr/bin/env python3
"""Refresh official Ehime housing-accommodation addresses; cautiously geocode public entries.

Dependencies: PyMuPDF and requests. This script cannot certify that a PDF's layout was
extracted perfectly; it checks obvious omissions and emits provenance/precision.
"""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.parse import urljoin
import json
from pathlib import Path
import re
import sys
import time
import unicodedata

import fitz
import requests

ROOT=Path(__file__).resolve().parents[1]
DEFAULT_URL='https://www.pref.ehime.jp/uploaded/attachment/190246.pdf'
PAGE='https://www.pref.ehime.jp/page/57100.html'
CITIES=('四国中央市','久万高原町','新居浜市','八幡浜市','宇和島市','今治市','松山市',
       '西条市','大洲市','伊予市','西予市','東温市')
TOWNS=('上島町','松前町','砥部町','内子町','伊方町','松野町','鬼北町','愛南町')
MUNICIPALITIES=tuple(sorted(CITIES+TOWNS,key=len,reverse=True))
# Explicit city/municipality start; do not confuse building names with place names.
PREFIX=re.compile(r'^\s*(?:愛媛県)?(?:(?:[一-龥々]+郡))?('+ '|'.join(map(re.escape,MUNICIPALITIES)) +r')')
GSI_URL='https://msearch.gsi.go.jp/address-search/AddressSearch'


def normalize(s: str) -> str:
    return re.sub(r'\s+', ' ',unicodedata.normalize('NFKC',s).replace('\u3000',' ')).strip()


def municipality(addr: str) -> str | None:
    return next((c for c in MUNICIPALITIES if c in addr),None)


def read_pdf(pdf_bytes: bytes) -> tuple[list[str],list[str]]:
    """Extract one address per line, return addresses and anomaly lines.

    Keeping duplicates is intentional: distinct apartment units may share a postal address.
    """
    document=fitz.open(stream=pdf_bytes,filetype='pdf')
    if not document.page_count: raise ValueError('Empty PDF')
    addresses=[]; anomalies=[]
    for page in document:
        txt=page.get_text('text',sort=True)
        if not txt.strip(): raise ValueError('PDF has an unextractable text page; manual review required')
        for raw in txt.splitlines():
            s=normalize(raw)
            if not s or '届出住宅の所在地' in s or '住所非公表' in s or '非公表'==s: continue
            match=PREFIX.match(s)
            if match:
                # If the text contains an explicit prefecture prefix, remove it once.
                candidate=s.removeprefix('愛媛県').strip()
                if len(candidate) < 6 or len(candidate)>250: anomalies.append(s);continue
                # Prevent column headings or generic town names from being mistaken for addresses.
                if not re.search(r'[0-9０-９一二三四五六七八九十]+',candidate):
                    anomalies.append(s);continue
                addresses.append(candidate)
            elif '市' in s or '郡' in s or '町' in s:
                # Mostly title/continuation lines. Store for manual spot-check; never silently prepend.
                if re.search(r'\d',s) and len(s)<200: anomalies.append(s)
    document.close()
    return addresses,anomalies


def basename(address: str) -> str:
    s=normalize(address).split(' ')[0]
    hit=re.match(r'^(.*?\d+(?:[-‐−ー]\d+){1,4})(?=[^\d]|$)',s)
    return hit.group(1) if hit else s


def kanji_chome(match) -> str:
    kanji={'一':1,'二':2,'三':3,'四':4,'五':5,'六':6,'七':7,'八':8,'九':9,'十':10}
    s=match.group(1)
    if s in kanji: number=kanji[s]
    elif s.startswith('十'): number=10+kanji.get(s[1:],0)
    elif s.endswith('十'): number=kanji.get(s[:-1],1)*10
    else: return s+'丁目'
    return str(number)+'-'


def norm_for_compare(s: str) -> str:
    s=normalize(s).removeprefix('愛媛県')
    s=re.sub(r'([一二三四五六七八九十]+)丁目',kanji_chome,s)
    s=re.sub(r'(\d+)丁目',r'\1-',s)
    for token in ('番地','番'): s=s.replace(token,'-')
    s=s.replace('号','').replace(' ', '')
    return re.sub(r'[-‐−ーｰ]+','-',s)


def recognized_precision(address: str, title: str) -> str:
    query_norm=norm_for_compare(basename(address))
    title_norm=norm_for_compare(title)
    segments=re.findall(r'\d+(?:-\d+)+',query_norm)
    return 'street' if any(segment in title_norm for segment in segments) else 'district'


class SourceLinks(HTMLParser):
    def __init__(self):
        super().__init__();self.links=[];self.href=None;self.parts=[]
    def handle_starttag(self,tag,attrs):
        if tag=='a': self.href=dict(attrs).get('href','');self.parts=[]
    def handle_data(self, data):
        if self.href is not None:self.parts.append(data)
    def handle_endtag(self,tag):
        if tag=='a' and self.href is not None:
            self.links.append((self.href,''.join(self.parts).strip()))
            self.href=None;self.parts=[]


def current_source(session: requests.Session) -> tuple[str,str]:
    response=session.get(PAGE,timeout=30)
    response.raise_for_status()
    parsed=SourceLinks();parsed.feed(response.text)
    candidates=[(href,label) for href,label in parsed.links if
                '届出住宅一覧' in label and '.pdf' in href.lower()]
    if not candidates:
        print('WARNING: Cannot discover current PDF link from landing page; using pinned 2026-08-31 source.',file=sys.stderr)
        return DEFAULT_URL,'2026-08-31'
    href,label=candidates[0]
    match=re.search(r'令和\s*(\d+)年\s*(\d+)月\s*(\d+)日',label)
    if not match:raise ValueError('Cannot parse official PDF snapshot date')
    y,m,d=map(int,match.groups())
    return urljoin(PAGE,href),f'{2018+y:04d}-{m:02d}-{d:02d}'


def plausible_gsi(data, address: str):
    town=municipality(address)
    if not town or not isinstance(data,list): return None
    for feature in data:
        try:
            lon,lat=feature['geometry']['coordinates'];title=feature['properties']['title']
            if not (132<=lon<=134.2 and 32.8<=lat<=34.5 and town in title):continue
            return dict(coord=[lon,lat],precision=recognized_precision(address,title),geocode_title=title)
        except (ValueError,TypeError,KeyError): continue
    return None


def geocode(address: str, session:requests.Session):
    # No city-center fallback. Incorrect municipal matches are excluded from the published dataset.
    candidate=basename(address)
    queries=[candidate]
    shorter=re.sub(r'\d.*$','',candidate).strip()
    if shorter and shorter!=candidate:queries.append(shorter)
    for q in queries:
        try:
            response=session.get(GSI_URL,params={'q':q},timeout=15)
            response.raise_for_status()
            match=plausible_gsi(response.json(),address)
            if match:return match
        except (ValueError,requests.RequestException):pass
    return None


def refresh(pdf_bytes:bytes, no_geocode:bool, cache_path:Path, threshold:int=147, pdf_url:str=DEFAULT_URL, source_date:str='2026-08-31') -> tuple[dict,list[str]]:
    addresses,anomalies=read_pdf(pdf_bytes)
    counts=Counter(municipality(a) for a in addresses)
    if len(addresses)<threshold:
        raise ValueError(f'Parsed only {len(addresses)} rows; expected at least {threshold}; keeping previous dataset')
    if len([city for city,n in counts.items() if city and n])<3:
        raise ValueError(f'Only {len(counts)} municipalities parsed. PDF layout extraction may be incomplete')
    if counts['松山市']<125:
        raise ValueError(f'Unexpected Matsuyama count {counts["松山市"]}; investigate source PDF layout')
    cache=json.loads(cache_path.read_text(encoding='utf-8')) if cache_path.exists() else {}
    session=requests.Session();session.headers['User-Agent']='EhimeMinpakuAtlas/0.1 (public-interest visualization)'
    records=[];success=0
    for i,address in enumerate(addresses):
        b=basename(address)
        if b not in cache and not no_geocode:
            cache[b]=geocode(address,session)
            if (i+1)%10==0:
                print(f'geocoding: {i+1}/{len(addresses)}',flush=True)
            time.sleep(.4)
        loc=cache.get(b)
        if loc and loc.get('geocode_title'):
            loc['precision']=recognized_precision(address,loc['geocode_title'])
        if loc:success+=1
        records.append(dict(id=i+1,address=address,city=municipality(address),
                           coord=loc['coord'] if loc else None,
                           precision=loc['precision'] if loc else 'unresolved',
                           geocode_title=loc.get('geocode_title','') if loc else ''))
    cache_path.parent.mkdir(parents=True,exist_ok=True)
    cache_path.write_text(json.dumps(cache,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    date=datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    return dict(source='愛媛県「住宅宿泊事業法に基づく届出住宅一覧」',source_url=PAGE,
                pdf_url=pdf_url,source_date=source_date,generated_at=date,
                scope='prefecture',method='PDF text extraction (not individually audited) / GSI geocoder',
                notice='自動抽出した住所。原PDFと全件の照合・座標精度の保証はしていません。',
                quality=dict(extracted=len(addresses),geocoded=success,street_precision=sum(r['precision']=='street' for r in records),district_precision=sum(r['precision']=='district' for r in records),unique_municipalities=len([k for k,v in counts.items() if k and v]),
                             anomalies_for_review=len(anomalies)),records=records),anomalies


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pdf',type=Path,help='Process a previously downloaded official PDF')
    parser.add_argument('--url',help='Override the latest source PDF URL (defaults to official landing page)')
    parser.add_argument('--source-date',help='Source snapshot date YYYY-MM-DD when overriding the URL/PDF')
    parser.add_argument('--output',type=Path,default=ROOT/'data/listings.json')
    parser.add_argument('--cache',type=Path,default=ROOT/'data/geocode-cache.json')
    parser.add_argument('--no-geocode',action='store_true')
    args=parser.parse_args()
    if args.pdf:
        url=args.url or DEFAULT_URL;source_date=args.source_date or '2026-08-31'
        buf=args.pdf.read_bytes()
    else:
        session=requests.Session()
        session.headers['User-Agent']='Mozilla/5.0 (compatible; EhimeMinpakuAtlas/0.1)'
        url,source_date=(args.url,args.source_date or '2026-08-31') if args.url else current_source(session)
        r=session.get(url,timeout=50);r.raise_for_status();buf=r.content
    if not buf.startswith(b'%PDF'):raise ValueError('Unexpected/non-PDF response')
    result,anomalies=refresh(buf,args.no_geocode,args.cache,pdf_url=url,source_date=source_date)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (ROOT/'data/extraction-anomalies.txt').write_text('\n'.join(anomalies)+'\n',encoding='utf-8')
    print(json.dumps(result['quality'],ensure_ascii=False,indent=2))
    print('Review anomalies: data/extraction-anomalies.txt')

if __name__=='__main__':main()
