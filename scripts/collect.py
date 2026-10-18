"""Build static question bundle; network is required only when running this script."""
import csv, io, json, math, os, re, time, urllib.parse, urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
# 点数がこの範囲外の候補は問題にしない。多すぎる候補は間引かずに除外する（陸地の形が浮かぶだけで推理にならないため）。
MIN_POINTS=30
MAX_POINTS=3000
SIMILARITY_THRESHOLD=.88
CATEGORIES={"世界の灯台":"Q39715","世界の火山":"Q8072","世界の博物館":"Q33506","世界の大学":"Q3918","世界の動物園":"Q43501","世界の植物園":"Q167346","世界の城":"Q23413","世界のダム":"Q12323","世界の水族館":"Q2281788","世界の国立公園":"Q46169","世界の天文台":"Q62832","世界の大聖堂":"Q2977","世界の美術館":"Q207694","世界の橋":"Q12280","世界のスタジアム":"Q483110","世界の鉄道駅":"Q55488","世界の発電所":"Q159719","世界の滝":"Q34038","世界の洞窟":"Q35509","世界の考古遺跡":"Q839954","世界の空港":"Q1248784"}
report=[]
def note(name,count,result):
 report.append((name,count,result));print(f'{name}\t{count}\t{result}',flush=True)
def get(url,accept='*/*'):
 req=urllib.request.Request(url,headers={'User-Agent':'DotGlobeQuestionCollector/1.0 (GitHub Pages static dataset)', 'Accept':accept})
 with urllib.request.urlopen(req,timeout=60) as r:return r.read()
def valid(lat,lon):return math.isfinite(lat) and math.isfinite(lon) and abs(lat)<=90 and abs(lon)<=180
def unique(points):return [list(p) for p in dict.fromkeys(map(tuple,points))]
def fingerprint(points):
 bins=[0]*144
 for lat,lon in points:bins[min(5,max(0,int((lat+90)//30)))*24+min(23,max(0,int((lon+180)//15)))]+=1
 n=len(points);return [math.sqrt(x/n) for x in bins]
def similarity(a,b):return sum(x*y for x,y in zip(a,b))
def in_range(name,pts):
 if len(pts)<MIN_POINTS:note(name,len(pts),f'除外: {MIN_POINTS}点未満');return False
 if len(pts)>MAX_POINTS:note(name,len(pts),f'除外: {MAX_POINTS}点超');return False
 return True
def collect_airports():
 rows=list(csv.DictReader(io.StringIO(get('https://raw.githubusercontent.com/datasets/airport-codes/master/data/airport-codes.csv').decode('utf-8-sig'))))
 categories={'大型空港':'large_airport','中型空港':'medium_airport','小型空港':'small_airport','ヘリポート':'heliport','水上飛行場':'seaplane_base','閉鎖された飛行場':'closed','気球発着場':'balloonport'}
 out=[]
 for label,typ in categories.items():
  pts=[]
  for row in rows:
   if row.get('type')!=typ:continue
   try:
    # coordinatesは "緯度, 経度" の順。
    lat,lon=map(float,(row.get('coordinates') or '').split(','))
    if valid(lat,lon):pts.append([round(lat,4),round(lon,4)])
   except (ValueError,TypeError):pass
  pts=unique(pts)
  if in_range('世界の'+label,pts):out.append({'name':'世界の'+label,'points':pts})
 return out
def sparql(query):
 url='https://query.wikidata.org/sparql?'+urllib.parse.urlencode({'query':query,'format':'json'})
 return json.loads(get(url,'application/sparql-results+json'))['results']['bindings']
def collect_wikidata():
 out=[]
 for name,qid in CATEGORIES.items():
  where=f'?item wdt:P31/wdt:P279* wd:{qid}; wdt:P625 ?coord.'
  try:
   # 先に件数だけ数え、上限を超えるカテゴリは座標を取得しない。
   count=int(sparql(f'SELECT (COUNT(DISTINCT ?item) AS ?n) WHERE {{ {where} }}')[0]['n']['value'])
   if count>MAX_POINTS:note(name,count,f'除外: {MAX_POINTS}点超');continue
   pts=[]
   for item in sparql(f'SELECT DISTINCT ?item ?coord WHERE {{ {where} }} LIMIT {MAX_POINTS*2}'):
    m=re.fullmatch(r'Point\((-?[\d.]+) (-?[\d.]+)\)',item['coord']['value'])
    if m:
     lon,lat=map(float,m.groups())
     if valid(lat,lon):pts.append([round(lat,4),round(lon,4)])
   pts=unique(pts)
   if in_range(name,pts):out.append({'name':name,'points':pts})
  except Exception as e:note(name,'-',f'取得失敗: {e}')
  time.sleep(1)
 return out
def write_summary(kept,candidates):
 path=os.environ.get('GITHUB_STEP_SUMMARY')
 if not path:return
 lines=[f'## 問題データ: {len(kept)}問 / 範囲内候補{len(candidates)}件',f'点数の範囲: {MIN_POINTS}〜{MAX_POINTS}','','| 候補 | 点数 | 結果 |','|---|---:|---|']
 lines+=[f'| {n} | {c} | {r} |' for n,c,r in report]
 with open(path,'a',encoding='utf-8') as f:f.write('\n'.join(lines)+'\n')
def main():
 candidates=[]
 for fn in (collect_airports,collect_wikidata):
  try:candidates.extend(fn())
  except Exception as e:print('FAILED source',fn.__name__,e,flush=True)
 ranked=sorted(candidates,key=lambda x:-len(x['points']));kept=[];fps=[]
 for item in ranked:
  fp=fingerprint(item['points'])
  similar=[kept[i]['name'] for i,other in enumerate(fps) if similarity(fp,other)>=SIMILARITY_THRESHOLD]
  if similar:note(item['name'],len(item['points']),f'除外: {similar[0]}と分布が類似');continue
  kept.append(item);fps.append(fp);note(item['name'],len(item['points']),'採用')
 write_summary(kept,candidates)
 if len(kept)<4:raise SystemExit('Insufficient validated sources: no overwrite of existing questions.json')
 (ROOT/'questions.json').write_text(json.dumps({'version':1,'source':'Wikidata / airport-codes','sets':kept},ensure_ascii=False,separators=(',',':'))+'\n')
 print(f'Generated {len(kept)} questions from {len(candidates)} candidates')
if __name__=='__main__':main()
