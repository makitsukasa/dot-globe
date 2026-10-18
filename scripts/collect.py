"""Build static question bundle; network is required only when running this script."""
import csv, io, json, math, os, re, time, urllib.parse, urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
# 点数がこの範囲外の候補は問題にしない。多すぎる候補は間引かずに除外する（陸地の形が浮かぶだけで推理にならないため）。
# 大きなデータは「〇〇な××」の条件で絞って範囲に収める。
MIN_POINTS=30
MAX_POINTS=3000
SIMILARITY_THRESHOLD=.88
# 地図に描いて目視で確認し、問題に向かないと判断した候補。理由を必ず書く。
EXCLUDE={
 '世界の気球発着場':'ほぼ米国のみ。データの網羅範囲の偏りが出ているだけ',
 '世界の水上飛行場':'米国・カナダに偏り、定期便のある水上飛行場・ヘリポートと紛らわしい',
 '標高3000m以上の飛行場':'標高5000m以上の山とほぼ同じ分布（アンデスとチベット）',
}
OURAIRPORTS='https://raw.githubusercontent.com/davidmegginson/ourairports-data/main/'
POWER_PLANTS='https://raw.githubusercontent.com/wri/global-power-plant-database/master/output_database/global_power_plant_database.csv'
NATURAL_EARTH='https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/'
# Wikidataは条件付きで絞った問い合わせだけを使う。WHERE句の中身（?item と ?coord を束縛すること）。
WIKIDATA={
 '1500年以前に創立された大学':'?item wdt:P31 wd:Q3918; wdt:P625 ?coord; wdt:P571 ?d. FILTER(YEAR(?d)<1500)',
 '1800年以前に創立された大学':'?item wdt:P31 wd:Q3918; wdt:P625 ?coord; wdt:P571 ?d. FILTER(YEAR(?d)<1800)',
 '世界遺産':'?item wdt:P1435 wd:Q9259; wdt:P625 ?coord.',
 '標高2000m以上の天文台':'?item wdt:P31/wdt:P279* wd:Q62832; wdt:P625 ?coord; wdt:P2044 ?e. FILTER(?e>=2000)',
 '宇宙港':'?item wdt:P31/wdt:P279* wd:Q194188; wdt:P625 ?coord.',
 '1900年以前に建てられた灯台':'?item wdt:P31 wd:Q39715; wdt:P625 ?coord; wdt:P571 ?d. FILTER(YEAR(?d)<1900)',
 '標高2000m以上の湖':'?item wdt:P31 wd:Q23397; wdt:P625 ?coord; wdt:P2044 ?e. FILTER(?e>=2000)',
 '1000年以前に建てられた寺院・教会・モスク':'VALUES ?type { wd:Q44539 wd:Q16970 wd:Q32815 wd:Q44613 } ?item wdt:P31 ?type; wdt:P625 ?coord; wdt:P571 ?d. FILTER(YEAR(?d)<1000)',
}
report=[]
def note(name,count,result):
 report.append((name,count,result));print(f'{name}\t{count}\t{result}',flush=True)
def get(url,accept='*/*'):
 req=urllib.request.Request(url,headers={'User-Agent':'DotGlobeQuestionCollector/1.0 (GitHub Pages static dataset)', 'Accept':accept})
 with urllib.request.urlopen(req,timeout=120) as r:return r.read()
def get_csv(url):return list(csv.DictReader(io.StringIO(get(url).decode('utf-8-sig'))))
def get_geojson(name):return [f['properties']|{'_coords':f['geometry']['coordinates']} for f in json.loads(get(NATURAL_EARTH+name))['features']]
def num(v,default=math.nan):
 try:return float(v)
 except (TypeError,ValueError):return default
def valid(lat,lon):return math.isfinite(lat) and math.isfinite(lon) and abs(lat)<=90 and abs(lon)<=180
def fingerprint(points):
 bins=[0]*144
 for lat,lon in points:bins[min(5,max(0,int((lat+90)//30)))*24+min(23,max(0,int((lon+180)//15)))]+=1
 n=len(points);return [math.sqrt(x/n) for x in bins]
def similarity(a,b):return sum(x*y for x,y in zip(a,b))
def candidate(name,coords):
 """coordsは(緯度, 経度)の列。範囲内なら候補を返し、範囲外ならNone。"""
 pts=list(dict.fromkeys((round(lat,3),round(lon,3)) for lat,lon in coords if valid(lat,lon)))
 if len(pts)<MIN_POINTS:note(name,len(pts),f'除外: {MIN_POINTS}点未満');return None
 if len(pts)>MAX_POINTS:note(name,len(pts),f'除外: {MAX_POINTS}点超');return None
 return {'name':name,'points':[list(p) for p in pts]}
def collect_airports():
 airports=get_csv(OURAIRPORTS+'airports.csv');runways=get_csv(OURAIRPORTS+'runways.csv')
 by_ident={a['ident']:a for a in airports}
 def pos(a):return num(a['latitude_deg']),num(a['longitude_deg'])
 def where(f):return [pos(a) for a in airports if f(a)]
 def runway_airports(f):return [pos(by_ident[r['airport_ident']]) for r in runways if r['closed']!='1' and r['airport_ident'] in by_ident and f(r)]
 elev=lambda a:num(a['elevation_ft'])*.3048
 surface=lambda r:r['surface'].upper()
 return [
  ('世界の大型空港',where(lambda a:a['type']=='large_airport')),
  ('世界の水上飛行場',where(lambda a:a['type']=='seaplane_base')),
  ('世界の気球発着場',where(lambda a:a['type']=='balloonport')),
  ('標高3000m以上の飛行場',where(lambda a:a['type']!='closed' and elev(a)>=3000)),
  ('海抜0m未満の飛行場',where(lambda a:a['type']!='closed' and elev(a)<0)),
  ('定期便のある水上飛行場・ヘリポート',where(lambda a:a['scheduled_service']=='yes' and a['type'] in ('seaplane_base','heliport'))),
  ('定期便のある未舗装滑走路の空港',[pos(by_ident[r['airport_ident']]) for r in runways if r['airport_ident'] in by_ident and by_ident[r['airport_ident']]['scheduled_service']=='yes' and re.search(r'GRAVEL|GRVL|GVL|DIRT|EARTH|TURF|GRASS|GRS|SAND|CLAY|LATERITE',surface(r))]),
  ('滑走路が4000m以上ある空港',runway_airports(lambda r:num(r['length_ft'],0)*.3048>=4000)),
  ('氷・雪の滑走路がある飛行場',runway_airports(lambda r:re.search(r'ICE|SNOW',surface(r)))),
  # 米国の「GRAVEL / CINDERS / CRUSHED ROCK / CORAL/SHELLS / SLAG」は雑多な分類なので除く。
  ('サンゴの滑走路がある飛行場',runway_airports(lambda r:re.search(r'CORAL|^COR$',surface(r)) and 'SLAG' not in surface(r))),
 ]
def collect_power_plants():
 rows=get_csv(POWER_PLANTS)
 def where(f):return [(num(r['latitude']),num(r['longitude'])) for r in rows if f(r)]
 fuel=lambda *names:lambda r:r['primary_fuel'] in names
 cap=lambda r:num(r['capacity_mw'],0)
 year=lambda r:num(r['commissioning_year'],0)
 return [
  ('地熱発電所',where(fuel('Geothermal'))),
  ('原子力発電所',where(fuel('Nuclear'))),
  ('出力1000MW以上の水力発電所',where(lambda r:r['primary_fuel']=='Hydro' and cap(r)>=1000)),
  ('出力1000MW以上の石炭火力発電所',where(lambda r:r['primary_fuel']=='Coal' and cap(r)>=1000)),
  ('出力1000MW以上のガス火力発電所',where(lambda r:r['primary_fuel']=='Gas' and cap(r)>=1000)),
  ('出力100MW以上の太陽光発電所',where(lambda r:r['primary_fuel']=='Solar' and cap(r)>=100)),
  ('出力200MW以上の風力発電所',where(lambda r:r['primary_fuel']=='Wind' and cap(r)>=200)),
  ('2010年以降に運転を始めた石炭火力発電所',where(lambda r:r['primary_fuel']=='Coal' and year(r)>=2010)),
  ('出力50MW以上の石油火力発電所',where(lambda r:r['primary_fuel']=='Oil' and cap(r)>=50)),
 ]
def collect_natural_earth():
 places=get_geojson('ne_10m_populated_places_simple.geojson')
 peaks=get_geojson('ne_10m_geography_regions_elevation_points.geojson')
 ports=get_geojson('ne_10m_ports.geojson')
 def where(rows,f):return [(p['_coords'][1],p['_coords'][0]) for p in rows if f(p)]
 return [
  ('人口100万人以上の都市',where(places,lambda p:(p['pop_max'] or 0)>=1e6)),
  ('世界の首都',where(places,lambda p:p['adm0cap']==1)),
  ('世界の主要な港',where(ports,lambda p:True)),
  ('標高5000m以上の山',where(peaks,lambda p:p['featurecla']=='mountain' and (p['elevation'] or 0)>=5000)),
 ]
def sparql(query):
 url='https://query.wikidata.org/sparql?'+urllib.parse.urlencode({'query':query,'format':'json'})
 return json.loads(get(url,'application/sparql-results+json'))['results']['bindings']
def collect_wikidata():
 out=[]
 for name,where in WIKIDATA.items():
  try:
   coords=[]
   for item in sparql(f'SELECT DISTINCT ?item ?coord WHERE {{ {where} }} LIMIT {MAX_POINTS*2}'):
    m=re.fullmatch(r'Point\((-?[\d.]+) (-?[\d.]+)\)',item['coord']['value'])
    if m:coords.append((float(m.group(2)),float(m.group(1))))
   out.append((name,coords))
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
 for fn in (collect_airports,collect_power_plants,collect_natural_earth,collect_wikidata):
  try:
   for name,coords in fn():
    if name in EXCLUDE:note(name,len(coords),'除外: '+EXCLUDE[name]);continue
    c=candidate(name,coords)
    if c:candidates.append(c)
  except Exception as e:note(fn.__name__,'-',f'取得失敗: {e}')
 # 点数の少ない（＝特徴が出やすい）候補を優先して残す。
 ranked=sorted(candidates,key=lambda x:len(x['points']));kept=[];fps=[]
 for item in ranked:
  fp=fingerprint(item['points'])
  similar=[kept[i]['name'] for i,other in enumerate(fps) if similarity(fp,other)>=SIMILARITY_THRESHOLD]
  if similar:note(item['name'],len(item['points']),f'除外: {similar[0]}と分布が類似');continue
  kept.append(item);fps.append(fp);note(item['name'],len(item['points']),'採用')
 write_summary(kept,candidates)
 if len(kept)<4:raise SystemExit('Insufficient validated sources: no overwrite of existing questions.json')
 (ROOT/'questions.json').write_text(json.dumps({'version':1,'source':'OurAirports / WRI Global Power Plant Database / Natural Earth / Wikidata','sets':kept},ensure_ascii=False,separators=(',',':'))+'\n')
 print(f'Generated {len(kept)} questions from {len(candidates)} candidates')
if __name__=='__main__':main()
