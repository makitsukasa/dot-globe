"""Build static question bundle; network is required only when running this script."""
import csv, io, json, math, re, time, urllib.parse, urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
CATEGORIES={"世界の灯台":"Q39715","世界の火山":"Q8072","世界の博物館":"Q33506","世界の大学":"Q3918","世界の動物園":"Q43501","世界の植物園":"Q167346","世界の城":"Q23413","世界のダム":"Q12323","世界の水族館":"Q2281788","世界の国立公園":"Q46169","世界の天文台":"Q62832","世界の大聖堂":"Q2977","世界の美術館":"Q207694","世界の橋":"Q12280","世界のスタジアム":"Q483110","世界の鉄道駅":"Q55488","世界の発電所":"Q159719","世界の滝":"Q34038","世界の洞窟":"Q35509","世界の考古遺跡":"Q839954","世界の空港":"Q1248784"}
def get(url,accept='*/*'):
 req=urllib.request.Request(url,headers={'User-Agent':'DotGlobeQuestionCollector/1.0 (GitHub Pages static dataset)', 'Accept':accept})
 with urllib.request.urlopen(req,timeout=35) as r:return r.read()
def valid(lat,lon):return math.isfinite(lat) and math.isfinite(lon) and abs(lat)<=90 and abs(lon)<=180
def fingerprint(points):
 bins=[0]*144
 for lat,lon in points:bins[min(5,max(0,int((lat+90)//30)))*24+min(23,max(0,int((lon+180)//15)))]+=1
 n=len(points);return [math.sqrt(x/n) for x in bins]
def similarity(a,b):return sum(x*y for x,y in zip(a,b))
def collect_airports():
 rows=list(csv.DictReader(io.StringIO(get('https://raw.githubusercontent.com/datasets/airport-codes/master/data/airport-codes.csv').decode('utf-8-sig'))))
 categories={'大型空港':'large_airport','中型空港':'medium_airport','小型空港':'small_airport','ヘリポート':'heliport','水上飛行場':'seaplane_base','閉鎖された飛行場':'closed'}
 out=[]
 for label,typ in categories.items():
  pts=[]
  for row in rows:
   if row.get('type')!=typ:continue
   try:
    lat,lon=map(float,(row.get('coordinates') or '').split(',')[::-1])
    if valid(lat,lon):pts.append([round(lat,4),round(lon,4)])
   except (ValueError,TypeError):pass
  if len(pts)>=25:out.append({'name':'世界の'+label,'points':pts})
 return out
def collect_wikidata():
 out=[]
 for name,qid in CATEGORIES.items():
  query=f'SELECT DISTINCT ?item ?coord WHERE {{ ?item wdt:P31/wdt:P279* wd:{qid}; wdt:P625 ?coord. }} LIMIT 12000'
  url='https://query.wikidata.org/sparql?'+urllib.parse.urlencode({'query':query,'format':'json'})
  try:
   data=json.loads(get(url,'application/sparql-results+json'));pts=[]
   for item in data['results']['bindings']:
    m=re.fullmatch(r'Point\((-?[\d.]+) (-?[\d.]+)\)',item['coord']['value'])
    if m:
     lon,lat=map(float,m.groups())
     if valid(lat,lon):pts.append([round(lat,4),round(lon,4)])
   if len(pts)>=25:out.append({'name':name,'points':pts})
   print(name,len(pts),flush=True)
  except Exception as e:print('FAILED',name,str(e),flush=True)
  time.sleep(1)
 return out
def main():
 candidates=[]
 for fn in (collect_airports,collect_wikidata):
  try:candidates.extend(fn())
  except Exception as e:print('FAILED source',fn.__name__,e,flush=True)
 ranked=sorted(candidates,key=lambda x:-len(x['points']));kept=[];fps=[]
 for item in ranked:
  fp=fingerprint(item['points'])
  if all(similarity(fp,other)<.88 for other in fps):kept.append(item);fps.append(fp)
 if len(kept)<4:raise SystemExit('Insufficient validated sources: no overwrite of existing questions.json')
 (ROOT/'questions.json').write_text(json.dumps({'version':1,'source':'Wikidata / airport-codes','sets':kept},ensure_ascii=False,separators=(',',':'))+'\n')
 print(f'Generated {len(kept)} questions from {len(candidates)} candidates')
if __name__=='__main__':main()
