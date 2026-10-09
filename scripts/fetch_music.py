#!/usr/bin/env python3
"""Pull Key West live music/entertainment into music.json.
Sources: livemusiceveryday.com (primary JSON feed), keywestconcierge.com (secondary HTML)."""
import json, re, html, subprocess, datetime as dt, sys

def curl(u,tries=3):
    import time
    for i in range(tries):
        r = subprocess.run(["curl","-s","-m","40","-A","Mozilla/5.0 (KW-HH personal trip page)",u],capture_output=True,text=True)
        if r.stdout.strip(): return r.stdout
        time.sleep(3)
    return ""

def clean(s): return re.sub(r"\s+"," ",html.unescape(s or "")).strip()
def hrs(t):  # "2026-10-19 13:30:00" -> 13.5
    h,m=t[11:16].split(":"); return int(h)+int(m)/60
def tag(n):
    l=n.lower()
    if re.search(r"\bdj\b",l): return "DJ"
    if "karaoke" in l: return "KARAOKE"
    if re.search(r"comedy|comedian|game show|magic|magician",l): return "COMEDY"
    if "bingo" in l: return "BINGO"
    if re.search(r"line danc|dance class|salsa",l): return "DANCE"
    if re.search(r"trivia",l): return "TRIVIA"
    return "LIVE"
def in_kw(lat,lng): return lat and lng and 24.53<=lat<=24.60 and -81.82<=lng<=-81.70
import os, urllib.parse, time
GEO=json.load(open("geocache.json")) if os.path.exists("geocache.json") else {}
def geocode(addr):
    if not addr: return (None,None)
    k=addr.lower()
    if k in GEO: return tuple(GEO[k])
    q=re.sub(r"\s*&\s*\d+","",addr)+", Key West, FL"
    try:
        time.sleep(1.1)
        r=json.loads(curl("https://nominatim.openstreetmap.org/search?format=json&limit=1&q="+urllib.parse.quote(q)) or "[]")
        ll=(float(r[0]["lat"]),float(r[0]["lon"])) if r else (None,None)
    except Exception: ll=(None,None)
    if ll[0] is not None and not in_kw(*ll): ll=(None,None)
    GEO[k]=list(ll); return ll

today=dt.date.today()
start=min(today, dt.date(2026,10,19)); end=max(today+dt.timedelta(days=14), dt.date(2026,10,26))
out=[]; venues={}

# 1) livemusiceveryday.com
try:
    page=1
    while True:
        try: d=json.loads(curl(f"https://livemusiceveryday.com/wp-json/tribe/events/v1/events?start_date={start}&end_date={end}%2023:59&per_page=50&page={page}"))
        except Exception as x:
            print("LME page",page,"failed:",x,file=sys.stderr); page+=1
            if page>40: break
            continue
        for e in d.get("events",[]):
            v=e.get("venue") if isinstance(e.get("venue"),dict) else {}
            vn=clean(v.get("venue")); lat=v.get("geo_lat"); lng=v.get("geo_lng")
            try: lat=float(lat); lng=float(lng)
            except: lat=lng=None
            if clean(v.get("city")).lower()!="key west" or re.search(r"\bMM\s?\d",vn): continue
            if not in_kw(lat,lng): lat,lng=geocode(clean(v.get("address")))
            n=clean(e.get("title")); n=re.sub(r"\s*@\s*"+re.escape(vn.split()[0])+r".*$","",n,flags=re.I) if vn else n
            n=re.sub(r"\s*@.*$","",n)
            s=hrs(e["start_date"]); en=hrs(e["end_date"]) if e.get("end_date") else None
            if en is not None and e["end_date"][:10]>e["start_date"][:10]: en+=24
            a=clean(v.get("address"))
            venues[vn.lower()]=(vn,a,lat,lng)
            out.append({"dt":e["start_date"][:10],"s":s,"e":en,"n":n,"v":vn,"a":a,"lat":lat,"lng":lng,"t":tag(n),"src":"LME"})
        if page>=d.get("total_pages",1) or page>=40: break
        page+=1
except Exception as x: print("LME failed:",x,file=sys.stderr)

# 2) keywestconcierge.com
MON={m:i for i,m in enumerate(["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"],1)}
def vkey(name):
    k=name.lower().replace("’","'")
    for lk,val in venues.items():
        a=re.sub(r"[^a-z]","",lk.replace("’","'"))[:8]; b=re.sub(r"[^a-z]","",k)[:8]
        if a and a==b: return val
    return None
try:
    first=curl("https://www.keywestconcierge.com/live-music-calendar/")
    pages=int((re.search(r"Page \d+ of (\d+)",first) or [0,1])[1])
    for p in range(1,min(pages,20)+1):
        t=first if p==1 else curl(f"https://www.keywestconcierge.com/live-music-calendar/?page={p}")
        for vn,ds,ul in re.findall(r'<h3 class="card-title"><a[^>]*>(.*?)</a></h3>\s*<div class="card-subtitle[^"]*">(.*?)</div>\s*<ul class="card-text">(.*?)</ul>',t,re.S):
            vn=clean(vn); m=re.match(r"\w+, (\w{3}) (\d+), (\d{4})",clean(ds))
            if not m: continue
            d=dt.date(int(m[3]),MON[m[1]],int(m[2]))
            if not (start<=d<=end): continue
            known=vkey(vn)
            for li in re.findall(r"<li>(.*?)</li>",ul,re.S):
                mm=re.match(r"(\d+):(\d+) (AM|PM) - (.*)",clean(li))
                if not mm: continue
                h=int(mm[1])%12+(12 if mm[3]=="PM" else 0)+int(mm[2])/60
                n=mm[4]
                out.append({"dt":str(d),"s":h,"e":None,"n":n,"v":known[0] if known else vn,"a":known[1] if known else "",
                            "lat":known[2] if known else None,"lng":known[3] if known else None,"t":tag(n),"src":"KWC"})
except Exception as x: print("KWC failed:",x,file=sys.stderr)

# dedupe: same date, venue (first 8 letters), start within 30 min, similar name -> keep LME
def nk(s): return re.sub(r"[^a-z]","",s.lower())
seen=[];final=[]
for e in sorted(out,key=lambda e:(e["src"]!="LME")):
    k=(e["dt"],nk(e["v"])[:8])
    if any(k==(f["dt"],nk(f["v"])[:8]) and abs(e["s"]-f["s"])<=0.5 and (nk(e["n"])[:6]==nk(f["n"])[:6]) for f in final): continue
    final.append(e)
final.sort(key=lambda e:(e["dt"],e["s"],e["v"]))
if len(final)<20:
    print("Too few results (",len(final),") - keeping previous music.json",file=sys.stderr); sys.exit(0)
json.dump(GEO,open("geocache.json","w"),indent=0)
json.dump({"updated":dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),"items":final},open("music.json","w"),ensure_ascii=False,separators=(",",":"))
print("wrote",len(final),"items")
