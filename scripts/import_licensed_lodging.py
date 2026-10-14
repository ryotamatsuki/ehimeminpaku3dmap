#!/usr/bin/env python3
"""Import only clearly CC BY-licensed local government lodging registers.

The licensed accommodation register is a DIFFERENT regulatory population from
housing-accommodation (minpaku) declarations. Never label a hotel/ryokan as a
registered minpaku merely because of an address match.
"""
import argparse
from datetime import datetime, timezone
from html.parser import HTMLParser
from io import BytesIO
from pathlib import Path
from urllib.parse import urljoin, urlparse, unquote
from zipfile import ZipFile
import hashlib
import json
import re
import unicodedata
import xml.etree.ElementTree as ET
import requests

ROOT=Path(__file__).resolve().parents[1]
CITY_URL="https://www.city.matsuyama.ehime.jp/shisei/opendata/metadata/ryokanzensisetu.html"
PREF_URL="https://www.pref.ehime.jp/opendata-catalog/dataset/2312.html"
CC_BY="https://creativecommons.org/licenses/by/4.0/deed.ja"
NS={"m":"http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
MUNI="四国中央市 久万高原町 新居浜市 八幡浜市 宇和島市 今治市 松山市 西条市 大洲市 伊予市 西予市 東温市 上島町 松前町 砥部町 内子町 伊方町 松野町 鬼北町 愛南町".split()

class Links(HTMLParser):
    def __init__(self):
        super().__init__();self.links=[];self.current=None;self.parts=[]
    def handle_starttag(self,tag,attrs):
        if tag=="a": self.current=dict(attrs).get("href","");self.parts=[]
    def handle_data(self,s):
        if self.current is not None:self.parts.append(s)
    def handle_endtag(self,tag):
        if tag=="a" and self.current is not None:
            self.links.append((self.current,"".join(self.parts).strip()))
            self.current=None;self.parts=[]

def normalize(s):
    return unicodedata.normalize("NFKC",str(s or "")).replace("\u3000"," ").strip()

def addrkey(s):
    s=normalize(s).replace("愛媛県","").replace(" ","").replace("　","")
    s=re.sub(r"([一二三四五六七八九十]+)丁目",lambda m:str(japanese_number(m.group(1)))+"-",s)
    s=re.sub(r"(\d+)丁目",r"\1-",s)
    return re.sub(r"[-‐−ーｰ]+","-",s.replace("番地","-").replace("番","-").replace("号",""))

def japanese_number(s):
    n={"一":1,"二":2,"三":3,"四":4,"五":5,"六":6,"七":7,"八":8,"九":9,"十":10}
    if s in n:return n[s]
    if s.startswith("十"):return 10+n.get(s[1:],0)
    if s.endswith("十"):return n.get(s[:-1],1)*10
    return -1

def city_of(s):
    return next((name for name in MUNI if name in s),None)

def cols_of_xlsx(buf):
    """Read spreadsheet cell values using OOXML zip/XML (no workbook rewriting)."""
    with ZipFile(BytesIO(buf)) as z:
        strings=[]
        if "xl/sharedStrings.xml" in z.namelist():
            root=ET.fromstring(z.read("xl/sharedStrings.xml"))
            strings=["".join(t.text or "" for t in si.findall(".//m:t",NS))
                     for si in root.findall("m:si",NS)]
        sheets=sorted((p for p in z.namelist() if re.fullmatch(r"xl/worksheets/sheet\d+\.xml",p)),
                     key=lambda p:int(re.search(r"sheet(\d+)",p).group(1)))
        for sheet in sheets:
            root=ET.fromstring(z.read(sheet))
            for row in root.findall(".//m:sheetData/m:row",NS):
                cells={}
                for cell in row.findall("m:c",NS):
                    ref=cell.attrib.get("r","")
                    idx=0
                    for ch in re.match(r"[A-Z]+",ref).group(0):idx=idx*26+ord(ch)-64
                    val=cell.find("m:v",NS)
                    if cell.attrib.get("t")=="inlineStr":
                        value="".join(t.text or "" for t in cell.findall(".//m:t",NS))
                    elif val is None:value=""
                    elif cell.attrib.get("t")=="s":value=strings[int(val.text or "0")]
                    else:value=val.text or ""
                    cells[idx-1]=normalize(value)
                if cells:
                    yield sheet,[cells.get(i,"") for i in range(max(cells)+1)]

def cols_of_xls(buf):
    """Read legacy BIFF .xls published by Matsuyama (read-only)."""
    import xlrd
    book=xlrd.open_workbook(file_contents=buf)
    for sheet in book.sheets():
        for i in range(sheet.nrows):
            values=[normalize(x) for x in sheet.row_values(i)]
            if any(values):yield sheet.name,values

def cols_of_excel(buf):
    if buf.startswith(b"PK"):return cols_of_xlsx(buf)
    if buf.startswith(bytes.fromhex("D0CF11E0A1B11AE1")):return cols_of_xls(buf)
    raise ValueError("Unsupported spreadsheet format")

def guess_columns(rows):
    """Conservatively find only a clear facility name and facility address pair."""
    for i,row in enumerate(rows[:45]):
        for n,name in enumerate(row):
            name=normalize(name).replace("\n","")
            if not (("名称" in name or "施設名" in name or "屋号" in name) and
                    any(w in name for w in ("施設","営業","宿泊","名称","屋号"))):
                continue
            for a,addr in enumerate(row):
                if a==n:continue
                addr=normalize(addr).replace("\n","")
                if ("所在地" in addr or "施設住所" in addr or
                    "営業所住所" in addr or ("住所" in addr and "営業" in addr)):
                    return i,n,a
    return None

def parse_xlsx(buf,source_id,source_url,download_url):
    allrows={}
    for sheet,row in cols_of_excel(buf):allrows.setdefault(sheet,[]).append(row)
    entries=[];diagnostics=[]
    for sheet,rows in allrows.items():
        spec=guess_columns(rows)
        diagnostics.append({"sheet":sheet,"header":rows[:7],"columns":spec})
        if not spec:continue
        header,name_col,addr_col=spec
        for row in rows[header+1:]:
            name=row[name_col] if name_col<len(row) else ""
            address=row[addr_col] if addr_col<len(row) else ""
            name=normalize(name);address=normalize(address)
            if not name or not address or len(name)>140 or len(address)>240:continue
            if not city_of(address):continue
            # Reject rows with no actual street/town specification or with headers.
            if name in ("営業施設名","施設名","施設名称","営業所の名称"):continue
            if len(address)<7:continue
            ident=hashlib.sha256((source_id+"|"+name+"|"+address).encode()).hexdigest()[:16]
            entries.append({"id":ident,"name":name,"address":address,
              "city":city_of(address),"legal_basis":"旅館業法許可施設（住宅宿泊事業法の届出住宅とは別）",
              "source":source_id,"source_page":source_url,"resource_url":download_url,
              "license":"CC BY 4.0","license_url":CC_BY})
    unique={r["id"]:r for r in entries}
    return list(unique.values()),diagnostics

def find_city_xlsx(session):
    resp=session.get(CITY_URL,timeout=30);resp.raise_for_status()
    resp.encoding=resp.apparent_encoding or "utf-8"
    parser=Links();parser.feed(resp.text)
    # Only download the data explicitly designated as the full city registry.
    matches=[urljoin(CITY_URL,href) for href,title in parser.links
             if "旅館全施設" in title and (".xlsx" in href.lower() or ".xls" in href.lower())]
    matches=[u for u in matches if urlparse(u).hostname=="www.city.matsuyama.ehime.jp" and urlparse(u).path.lower().endswith((".xls",".xlsx"))]
    if not matches:
        print("DEBUG CITY:",{"status":resp.status_code,"url":resp.url,"encoding":resp.encoding,"type":resp.headers.get("Content-Type"),"length":len(resp.content),"links":len(parser.links),"sample":resp.text[:900],"matches":[(u,t) for u,t in parser.links if "旅館" in t or ".xlsx" in u.lower()][:12]},flush=True)
        raise RuntimeError("No clearly labeled Matsuyama complete registry XLSX found")
    return matches[0]

def find_pref_xlsx(session):
    resp=session.get(PREF_URL,timeout=30);resp.raise_for_status()
    parser=Links();parser.feed(resp.text)
    # This catalog may use download actions with no direct XLSX links.
    matches=[urljoin(PREF_URL,href) for href,title in parser.links
             if "令和7年12月末時点" in normalize(unquote(href)) and "旅館業施設一覧" in unquote(href) and ".xlsx" in href.lower()]
    matches=[u for u in matches if urlparse(u).hostname=="www.pref.ehime.jp" and u.lower().endswith(".xlsx")]
    if not matches:
        print("DEBUG PREF:",[(u,t) for u,t in parser.links if ".xlsx" in u.lower() or "ダウンロード" in t][:15],flush=True)
        raise RuntimeError("Prefecture catalog requires dedicated resource URL discovery; not guessing")
    return matches[0]

def run(session, only="all", inspect=False):
    sources=[("matsuyama-city-2026-03-31",CITY_URL,find_city_xlsx)]
    if only in ("all","prefecture"):sources.append(("ehime-pref-2025-12-31",PREF_URL,find_pref_xlsx))
    if only=="city":sources=sources[:1]
    results=[];metadata=[];problems=[]
    for source_id,page,discover in sources:
        try:
            url=discover(session)
            r=session.get(url,timeout=60);r.raise_for_status()
            if not (r.content.startswith(b"PK") or r.content.startswith(bytes.fromhex("D0CF11E0A1B11AE1"))):raise ValueError("Downloaded file is not Excel")
            facilities,details=parse_xlsx(r.content,source_id,page,url)
            if inspect:print(json.dumps({"source":source_id,"url":url,"details":details[:2],
                   "examples":facilities[:8],"count":len(facilities)},ensure_ascii=False)[:16000])
            if not facilities:raise ValueError("No clear name/address columns parsed; human review needed: "+json.dumps(details[:2],ensure_ascii=False)[:3000])
            results.extend(facilities)
            metadata.append({"id":source_id,"page":page,"download":url,"count":len(facilities),
                             "license":"CC BY 4.0","license_url":CC_BY})
        except (requests.RequestException,ValueError,RuntimeError,KeyError) as e:
            problems.append({"source":source_id,"error":str(e)})
            print(f"WARNING {source_id}: {e}",flush=True)
    # Distinct permit sources never silently inferred to be the minpaku register.
    return {"generated_at":datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
      "notice":"旅館業法の許可施設データ。住宅宿泊事業法の届出住宅296件とは異なり、同一施設と断定できません。休業・廃業を含む可能性があります。",
      "coverage":"partial" if problems else "sources_attempted",
      "sources":metadata,"warnings":problems,"facilities":results}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--only",choices=["city","prefecture","all"],default="all")
    p.add_argument("--inspect",action="store_true")
    p.add_argument("--output",type=Path,default=ROOT/"data"/"licensed_lodging.json")
    args=p.parse_args()
    session=requests.Session()
    session.headers["User-Agent"]="EhimeMinpakuAtlas/0.2 (open-data integration; https://github.com/ryotamatsuki/ehimeminpaku3dmap)"
    payload=run(session,args.only,args.inspect)
    if not payload["facilities"]:
        raise SystemExit("No valid CC BY facility records; existing data retained")
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("Imported CC BY permitted lodgings:",len(payload["facilities"]),"warnings:",payload["warnings"],flush=True)

if __name__=="__main__":main()
