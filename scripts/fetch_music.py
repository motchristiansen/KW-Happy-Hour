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


# 3) Extra sources: Hank's (Elfsight widget), Schooner Wharf (HTML calendar), OurKeyWest weekly posts
FIXED={"hanks":("Hank's Hair of the Dog Saloon","409 Caroline St",24.5573,-81.8058),
       "schooner":("Schooner Wharf","202 William St",24.5610,-81.8018)}
KNOWN={"general horseplay":("423 Caroline St",24.5574,-81.8052),"the gardens hotel":("526 Angela St",24.5543,-81.7991),
       "hugh's view atop studios of key west":("533 Eaton St",24.5582,-81.8003),"the roost":("508 Fleming St",24.5553,-81.8015),
       "key west empourium":("618 Duval St",24.5546,-81.8006),"rams head southernmost":("804 Whitehead St",24.5530,-81.8053),
       "green parrot bar":("601 Whitehead St",24.5541,-81.8030),"sloppy joe's":("201 Duval St",24.5591,-81.8050)}
def tparse(s):
    """'7-11pm' / 'noon - 5pm' / '8pm - Late' / '11AM–2 PM' / '9 PM' / '6:30-Midnight' -> (start,end)"""
    s=s.lower().replace("–","-").replace("—","-").replace(" ","")
    parts=s.split("-",1)
    def one(x,suf=None):
        if not x: return None,None
        if x.startswith("noon"): return 12.0,"pm"
        if x.startswith("midnight"): return 24.0,"am"
        if x.startswith("late"): return None,None
        m=re.match(r"(\d{1,2})(?::(\d\d))?(am|pm)?",x)
        if not m: return None,None
        h=int(m[1])+(int(m[2])/60 if m[2] else 0);sf=m[3]
        return h,sf
    a,asf=one(parts[0]);b,bsf=one(parts[1]) if len(parts)>1 else (None,None)
    if a is None: return None,None
    if bsf=="pm" and b is not None and b<12: b+=12
    if bsf=="am" and b is not None and b<12 and b!=24: b+=24
    if asf=="pm" and a<12: a+=12
    if asf is None:
        if (bsf in("pm",) or (len(parts)>1 and re.search(r"midnight|late",parts[1]))) and a<12: a+=12
        elif bsf is None and len(parts)==1 and a<12 and a>=1: a+=12 if a<9 else 0
    if b is not None and b<=a: b+=12 if b+12>a else 24
    return a,b
def tc(n):
    def cw(w):
        if w.upper() in ("DJ","II","III","&"): return w.upper()
        w=w.lower();w=w[:1].upper()+w[1:]
        return re.sub(r"(['’])(\w)",lambda m:m[1]+m[2].upper(),w) if re.match(r"^(o|d|mc)['’]",w.lower()) else w
    s=" ".join(cw(w) for w in n.split())
    return re.sub(r"\b(Of|The|And|In|At)\b",lambda m:m[0].lower(),s[:1].upper()+s[1:]) if s else s
extra=[]
try:  # Hank's
    d=json.loads(curl("https://core.service.elfsight.com/p/boot/?page=https%3A%2F%2Fwww.hankskeywest.com%2Fcalendar-of-events%2F&w=03f84b62-e88e-4c7d-a854-258767db7791"))
    for e in d["data"]["widgets"]["03f84b62-e88e-4c7d-a854-258767db7791"]["data"]["settings"]["events"]:
        sd=(e.get("start") or {}).get("date");st=(e.get("start") or {}).get("time")
        if not sd or not st or not (str(start)<=sd<=str(end)): continue
        et=(e.get("end") or {}).get("time");h,m=map(int,st.split(":"));s=h+m/60
        en=None
        if et: eh,em=map(int,et.split(":"));en=eh+em/60;en=en+24 if en<=s else en
        vn,a,la,lo=FIXED["hanks"];n=clean(e.get("name"))
        extra.append({"dt":sd,"s":s,"e":en,"n":n,"v":vn,"a":a,"lat":la,"lng":lo,"t":tag(n),"src":"HANKS"})
except Exception as x: print("Hank's failed:",x,file=sys.stderr)
try:  # Schooner Wharf
    t=curl("https://www.schoonerwharf.com/entertainment.htm")
    hm=re.search(r"Entertainment Schedule\s+(\w+)\s+(\d{4})",clean(re.sub("<[^>]+>"," ",t)))
    MON2={m:i for i,m in enumerate(["january","february","march","april","may","june","july","august","september","october","november","december"],1)}
    if hm:
        mon=MON2[hm[1].lower()];yr=int(hm[2])
        rows=re.findall(r"<tr[^>]*>(.*?)</tr>",t,re.S|re.I)
        cur_m=None;prev=None;dates=None
        for r in rows:
            cells=re.findall(r"<td[^>]*>(.*?)</td>",r,re.S|re.I)
            if len(cells)!=7: continue
            txt=[clean(re.sub("<[^>]+>"," ",c)) for c in cells]
            if all(re.fullmatch(r"(?:[A-Za-z]+\s+)?\d{1,2}|",x) for x in txt) and any(txt):
                dates=[]
                for x in txt:
                    if not x: dates.append(None);continue
                    dn=int(re.search(r"\d+",x)[0])
                    if cur_m is None: cur_m=mon-1 if dn>20 else mon
                    elif prev is not None and dn<prev: cur_m+=1
                    prev=dn;yy=yr+(1 if cur_m>12 else 0)-(1 if cur_m<1 else 0);mm=(cur_m-1)%12+1
                    dates.append(dt.date(yy,mm,dn))
                continue
            if not dates: continue
            for di,c in enumerate(cells):
                d0=dates[di] if di<len(dates) else None
                if not d0 or not (start<=d0<=end): continue
                lines=[clean(re.sub("<[^>]+>"," ",x)) for x in re.split(r"<br\s*/?>",re.sub(r"</?p[^>]*>","<br>",c),flags=re.I)]
                lines=[x for x in lines if x]
                name=[]
                for ln in lines:
                    if re.match(r"(?i)^(noon|\d{1,2}(:\d\d)?\s*(am|pm)?\s*-)",ln):
                        s,en=tparse(ln)
                        if name and s is not None:
                            n=tc(" ".join(name));vn,a,la,lo=FIXED["schooner"]
                            extra.append({"dt":str(d0),"s":s,"e":en,"n":n,"v":vn,"a":a,"lat":la,"lng":lo,"t":tag(n),"src":"SCHOONER"})
                        name=[]
                    else: name.append(ln)
except Exception as x: print("Schooner failed:",x,file=sys.stderr)
try:  # OurKeyWest weekly
    posts=json.loads(curl("https://ourkeywest.com/wp-json/wp/v2/posts?search=this%20week%20in%20key%20west&per_page=3&_fields=date,content"))
    for po in posts:
        c=po["content"]["rendered"];yr=int(po["date"][:4])
        if "Live Music" not in c: continue
        c=c[c.find("Live Music"):]
        cur=None
        for blk in re.findall(r"<h[23][^>]*>(.*?)</h[23]>|<p[^>]*>(.*?)</p>",c,re.S):
            h,pp=blk
            if h:
                m=re.match(r"\w+day,\s+(\w+)\s+(\d+)",clean(re.sub("<[^>]+>","",h)))
                if m and m[1][:3].lower() in [k.lower() for k in MON]:
                    cur=dt.date(yr,MON[m[1][:3].title()],int(m[2]))
                elif h and not m and cur: cur=None if re.search(r"(?i)event|festival|food|tour",h) else cur
                continue
            if not cur or not (start<=cur<=end): continue
            for li in re.split(r"<br\s*/?>",pp):
                li=clean(re.sub("<[^>]+>","",li)).lstrip("•").strip()
                m=re.match(r"(.+?)\s*@\s*(.+?)\s*[—–-]\s*([\d:]+\s*(?:AM|PM)?\s*(?:[–-]\s*[\d:]+\s*(?:AM|PM)?)?|Noon.*)$",li,re.I)
                if not m: continue
                n,vn,tm=m[1].strip(),m[2].strip(),m[3]
                if re.search(r"(?i)happy hour",n): continue
                s,en=tparse(tm)
                if s is None: continue
                k=vn.lower().replace("’","'")
                kk=KNOWN.get(k) or next((v for kn,v in KNOWN.items() if re.sub(r"[^a-z]","",kn)[:8]==re.sub(r"[^a-z]","",k)[:8]),None)
                if kk: a,la,lo=kk
                else:
                    kv=vkey(vn)
                    if kv: vn,a,la,lo=kv
                    else: a="";la,lo=geocode(vn)
                extra.append({"dt":str(cur),"s":s,"e":en,"n":n,"v":vn,"a":a,"lat":la,"lng":lo,"t":tag(n),"src":"OKW"})
except Exception as x: print("OurKeyWest failed:",x,file=sys.stderr)
out+=extra
# dedupe: same date, venue (first 8 letters), start within 30 min, similar name -> keep LME
def nk(s): return re.sub(r"[^a-z]","",s.lower())
seen=[];final=[]
RANK={"LME":0,"OKW":1,"HANKS":2,"SCHOONER":3,"KWC":4}
for e in sorted(out,key=lambda e:RANK.get(e["src"],9)):
    k=(e["dt"],nk(e["v"])[:8])
    if any(k==(f["dt"],nk(f["v"])[:8]) and abs(e["s"]-f["s"])<=0.5 and (nk(e["n"])[:6]==nk(f["n"])[:6]) for f in final): continue
    final.append(e)
final.sort(key=lambda e:(e["dt"],e["s"],e["v"]))
if len(final)<20:
    print("Too few results (",len(final),") - keeping previous music.json",file=sys.stderr); sys.exit(0)
json.dump(GEO,open("geocache.json","w"),indent=0)
json.dump({"updated":dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),"items":final},open("music.json","w"),ensure_ascii=False,separators=(",",":"))
print("wrote",len(final),"items")
