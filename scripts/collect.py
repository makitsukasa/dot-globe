"""Build static question bundle; network is required only when running this script."""
import collections, csv, io, json, math, os, re, tarfile, time, unicodedata, urllib.error, urllib.parse, urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
# 目標の問題数。施設・自然などの問題を先に入れ、残りを地名パターンの問題で埋める。
TARGET=1000
# 地名パターンの問題は多くてもこの数まで。
NAME_BUDGET=100
# 点数がこの範囲外の候補は問題にしない。多すぎる候補は間引かずに除外する（陸地の形が浮かぶだけで推理にならないため）。
# 大きなデータは「〇〇な××」の条件で絞って範囲に収める。点は0.1度単位に丸めて重複を除いた数で数える。
MIN_POINTS=30
MAX_POINTS=3000
# 施設・自然の問題で、既に採用した問題とここまで分布が似ていたら除く。
SIMILARITY_THRESHOLD=.95
# 地名パターンの問題の選び方。
NAME_MIN_POINTS=50
NAME_TOP3_SHARE=.6       # 上位3か国に6割以上が集まる語尾・語頭だけ使う（言語圏が読み取れるもの）
NAME_COUNTRY_CAP=15      # 過半数が同じ国にある問題はその国ごとに15問まで
# Wikidataの「種類」（P31の値）から作る問題。1か国に偏った種類は国の輪郭が浮かぶだけなので除く。
CLASS_MAX_COUNTRY_SHARE=.5
# Wikidata全体と同じような分布（欧米に固まるだけ）の種類は除く。
CLASS_MAX_BASE_SIMILARITY=.9
# 派生問題の条件。
CLASS_BUILT_BEFORE=(1000,1500,1800)
CLASS_ELEVATION_AT_LEAST=(1000,2000,3000)
# 地図で当てられる「もの」に限るため、これらのどれかの下位分類（P279*）にあたる種類だけを使う。
# 「施設」「建築構造物」のような広い分類だと、店や部屋のようにWikidataの登録の偏り（欧米）が出るだけの種類が混ざるため、場所と結びつく分類に絞る。
CLASS_ROOTS={
 'Q271669':'地形','Q15324':'水域','Q35145263':'自然地理的な物体','Q8072':'火山','Q473972':'保護区','Q35509':'洞窟','Q34038':'滝','Q23442':'島','Q35666':'氷河',
 'Q24398318':'宗教建築','Q839954':'遺跡','Q57821':'要塞','Q23413':'城','Q12516':'ピラミッド','Q486972':'集落',
 'Q820477':'鉱山','Q159719':'発電所','Q12323':'ダム','Q39715':'灯台','Q1248784':'空港','Q44782':'港','Q62832':'天文台','Q130003':'スキー場','Q194188':'宇宙港',
}
QLEVER='https://qlever.cs.uni-freiburg.de/api/wikidata'
NAME_MAX_JACCARD=.4      # 地点の4割以上が重なる問題は片方だけ
NAME_LOOKALIKE_CAP=3     # 見た目がほぼ同じ分布（指紋の類似度.97以上）の問題は3問まで
# 地図に描いて目視で確認し、問題に向かないと判断した候補。理由を必ず書く。
EXCLUDE={
 '世界の気球発着場':'ほぼ米国のみ。データの網羅範囲の偏りが出ているだけ',
 '世界の水上飛行場':'米国・カナダに偏り、定期便のある水上飛行場・ヘリポートと紛らわしい',
 '標高3000m以上の飛行場':'標高5000m以上の山とほぼ同じ分布（アンデスとチベット）',
 'コジェネレーション発電所':'WRIのデータが米国中心で、ほぼ米国のみ',
 '楯状火山':'同じ意味の問題が既にある（盾状火山）',
 '溶岩円頂丘':'同じ意味の問題が既にある（溶岩ドーム）',
 'スコリア丘':'同じ意味の問題が既にある（噴石丘）',
 '首都':'同じ意味の問題が既にある（世界の首都）',
 '州都':'同じ意味の問題が既にある（州都・県庁所在地など）',
 'プラヤ':'同じ意味の問題が既にある（干上がった湖（プラヤ））',
 '海峡':'同じ意味の問題が既にある（主要な海峡）',
 '諸島':'同じ意味の問題が既にある（主要な諸島）',
 '人造湖':'同じ意味の問題が既にある（主要な人造湖）',
 '大きな湾':'同じ意味の問題が既にある（大湾）',
 'バシリカ・マイナー':'同じ意味の問題が既にある（マイナー・バシリカ）',
 '築城':'同じ意味の問題が既にある（要塞）',
 '階':'場所との結びつきが弱く、Wikidataの登録の偏り（欧米）が出るだけ',
 '庭':'場所との結びつきが弱く、Wikidataの登録の偏り（欧米）が出るだけ',
 '並木':'場所との結びつきが弱く、Wikidataの登録の偏り（欧米）が出るだけ',
 '商店街':'場所との結びつきが弱く、Wikidataの登録の偏り（欧米）が出るだけ',
 'クラインガルテン':'場所との結びつきが弱く、Wikidataの登録の偏り（欧米）が出るだけ',
 '住宅地':'場所との結びつきが弱く、Wikidataの登録の偏り（欧米）が出るだけ',
 '街区':'場所との結びつきが弱く、Wikidataの登録の偏り（欧米）が出るだけ',
 '市街地':'場所との結びつきが弱く、Wikidataの登録の偏り（欧米）が出るだけ',
 '焼却施設':'場所との結びつきが弱く、Wikidataの登録の偏り（欧米）が出るだけ',
 '中心業務地区':'場所との結びつきが弱く、Wikidataの登録の偏り（欧米）が出るだけ',
 '都市的地域':'場所との結びつきが弱く、Wikidataの登録の偏り（欧米）が出るだけ',
 '宗教建築物':'場所との結びつきが弱く、Wikidataの登録の偏り（欧米）が出るだけ',
 '水域':'場所との結びつきが弱く、Wikidataの登録の偏り（欧米）が出るだけ',
 '海':'場所との結びつきが弱く、Wikidataの登録の偏り（欧米）が出るだけ',
 '線形公園':'場所との結びつきが弱く、Wikidataの登録の偏り（欧米）が出るだけ',
 'トレーラーパーク':'場所との結びつきが弱く、Wikidataの登録の偏り（欧米）が出るだけ',
 'ゲーテッドコミュニティ':'場所との結びつきが弱く、Wikidataの登録の偏り（欧米）が出るだけ',
 '王国会館':'場所との結びつきが弱く、Wikidataの登録の偏り（欧米）が出るだけ',
 'リフェクトリー':'場所との結びつきが弱く、Wikidataの登録の偏り（欧米）が出るだけ',
 '防空壕':'場所との結びつきが弱く、Wikidataの登録の偏り（欧米）が出るだけ',
 '貯水槽':'場所との結びつきが弱く、Wikidataの登録の偏り（欧米）が出るだけ',
 'ユダヤ人ゲットーの建設':'出来事であって場所の種類ではない',
 '蓄電所':'WRIのデータが米国中心で、ほぼ米国のみ',
}
OURAIRPORTS='https://raw.githubusercontent.com/davidmegginson/ourairports-data/main/'
POWER_PLANTS='https://raw.githubusercontent.com/wri/global-power-plant-database/master/output_database/global_power_plant_database.csv'
NATURAL_EARTH='https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/'
EARTHQUAKES='https://raw.githubusercontent.com/plotly/datasets/master/earthquakes-23k.csv'
VOLCANOES='https://raw.githubusercontent.com/plotly/datasets/master/volcano_db.csv'
CITIES='https://registry.npmjs.org/cities.json/-/cities.json-1.1.65.tgz'
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
def note(name,count,result,quiet=False):
 report.append((name,count,result))
 if not quiet:print(f'{name}\t{count}\t{result}',flush=True)
def get(url,accept='*/*'):
 req=urllib.request.Request(url,headers={'User-Agent':'DotGlobeQuestionCollector/1.0 (GitHub Pages static dataset)', 'Accept':accept})
 with urllib.request.urlopen(req,timeout=120) as r:return r.read()
def get_csv(url,encoding='utf-8-sig'):return list(csv.DictReader(io.StringIO(get(url).decode(encoding))))
def representative(geom):
 """点はその座標、面は最も頂点の多い外周の頂点平均を(経度, 緯度)で返す。"""
 if geom['type']=='Point':return geom['coordinates']
 if geom['type']=='Polygon':ring=geom['coordinates'][0]
 elif geom['type']=='MultiPolygon':ring=max((p[0] for p in geom['coordinates']),key=len)
 else:
  # 線などは全頂点の平均。
  ring=[];stack=[geom['coordinates']]
  while stack:
   c=stack.pop()
   if isinstance(c[0],(int,float)):ring.append(c)
   else:stack.extend(c)
 return [sum(p[0] for p in ring)/len(ring),sum(p[1] for p in ring)/len(ring)]
def get_geojson(name):
 return [f['properties']|{'_lonlat':representative(f['geometry'])} for f in json.loads(get(NATURAL_EARTH+name))['features'] if f.get('geometry')]
def num(v,default=math.nan):
 try:return float(v)
 except (TypeError,ValueError):return default
def valid(lat,lon):return math.isfinite(lat) and math.isfinite(lon) and abs(lat)<=90 and abs(lon)<=180
def grid(coords):
 """(緯度, 経度)の列を0.1度単位の整数に丸め、重複を除く。"""
 return list(dict.fromkeys((round(lat*10),round(lon*10)) for lat,lon in coords if valid(lat,lon)))
def fingerprint(points):
 bins=[0]*144
 for lat,lon in points:bins[min(5,max(0,int((lat/10+90)//30)))*24+min(23,max(0,int((lon/10+180)//15)))]+=1
 n=len(points);return [math.sqrt(x/n) for x in bins]
def similarity(a,b):return sum(x*y for x,y in zip(a,b))
def collect_airports():
 airports=get_csv(OURAIRPORTS+'airports.csv');runways=get_csv(OURAIRPORTS+'runways.csv')
 by_ident={a['ident']:a for a in airports}
 def pos(a):return num(a['latitude_deg']),num(a['longitude_deg'])
 def where(f):return [pos(a) for a in airports if f(a)]
 def runway_airports(f):return [pos(by_ident[r['airport_ident']]) for r in runways if r['closed']!='1' and r['airport_ident'] in by_ident and f(r)]
 def named(pattern):return where(lambda a:a['type']!='closed' and re.search(pattern,a['name'],re.I))
 elev=lambda a:num(a['elevation_ft'])*.3048
 surface=lambda r:r['surface'].upper()
 return [
  ('世界の大型空港',where(lambda a:a['type']=='large_airport')),
  ('世界の水上飛行場',where(lambda a:a['type']=='seaplane_base')),
  ('世界の気球発着場',where(lambda a:a['type']=='balloonport')),
  ('標高3000m以上の飛行場',where(lambda a:a['type']!='closed' and elev(a)>=3000)),
  ('標高1500m以上にある定期便のある空港',where(lambda a:a['scheduled_service']=='yes' and elev(a)>=1500)),
  ('海抜0m未満の飛行場',where(lambda a:a['type']!='closed' and elev(a)<0)),
  ('定期便のある水上飛行場・ヘリポート',where(lambda a:a['scheduled_service']=='yes' and a['type'] in ('seaplane_base','heliport'))),
  ('定期便のある未舗装滑走路の空港',[pos(by_ident[r['airport_ident']]) for r in runways if r['airport_ident'] in by_ident and by_ident[r['airport_ident']]['scheduled_service']=='yes' and re.search(r'GRAVEL|GRVL|GVL|DIRT|EARTH|TURF|GRASS|GRS|SAND|CLAY|LATERITE',surface(r))]),
  ('滑走路が4000m以上ある空港',runway_airports(lambda r:num(r['length_ft'],0)*.3048>=4000)),
  ('滑走路が3500m以上4000m未満の空港',runway_airports(lambda r:3500<=num(r['length_ft'],0)*.3048<4000)),
  ('氷・雪の滑走路がある飛行場',runway_airports(lambda r:re.search(r'ICE|SNOW',surface(r)))),
  # 米国の「GRAVEL / CINDERS / CRUSHED ROCK / CORAL/SHELLS / SLAG」は雑多な分類なので除く。
  ('サンゴの滑走路がある飛行場',runway_airports(lambda r:re.search(r'CORAL|^COR$',surface(r)) and 'SLAG' not in surface(r))),
  ('名前に「Air Base」を含む飛行場',named(r'\bair base\b')),
  ('名前に「Mission」を含む飛行場',named(r'\bmission\b')),
  ('名前に「Glid」「Segelflug」を含む滑空場',named(r'glid|segelflug|vol à voile|zweefvlieg')),
 ]
def collect_power_plants():
 rows=get_csv(POWER_PLANTS)
 def where(f):return [(num(r['latitude']),num(r['longitude'])) for r in rows if f(r)]
 def plant(fuel,min_mw=0,max_mw=math.inf,since=0,until=math.inf):
  return where(lambda r:r['primary_fuel']==fuel and min_mw<=num(r['capacity_mw'],0)<max_mw and (since==0 and until==math.inf or since<=num(r['commissioning_year'],0)<until))
 return [
  ('地熱発電所',plant('Geothermal')),
  ('原子力発電所',plant('Nuclear')),
  ('出力3000MW以上の水力発電所',plant('Hydro',3000)),
  ('出力1000MW以上3000MW未満の水力発電所',plant('Hydro',1000,3000)),
  ('1950年より前に運転を始めた水力発電所',plant('Hydro',until=1950)),
  ('出力3000MW以上の石炭火力発電所',plant('Coal',3000)),
  ('出力1000MW以上の石炭火力発電所',plant('Coal',1000)),
  ('2010年以降に運転を始めた石炭火力発電所',plant('Coal',since=2010)),
  ('出力1000MW以上のガス火力発電所',plant('Gas',1000)),
  ('出力50MW以上の石油火力発電所',plant('Oil',50)),
  ('出力500MW以上の太陽光発電所',plant('Solar',500)),
  ('出力100MW以上の太陽光発電所',plant('Solar',100)),
  ('出力200MW以上の風力発電所',plant('Wind',200)),
  ('出力50MW以上のバイオマス発電所',plant('Biomass',50)),
  ('出力50MW以上の廃棄物発電所',plant('Waste',50)),
  ('蓄電所',plant('Storage')),
  ('コジェネレーション発電所',plant('Cogeneration')),
 ]
def collect_natural_earth():
 places=get_geojson('ne_10m_populated_places_simple.geojson')
 peaks=get_geojson('ne_10m_geography_regions_elevation_points.geojson')
 region_points=get_geojson('ne_10m_geography_regions_points.geojson')
 regions=get_geojson('ne_10m_geography_regions_polys.geojson')
 marine=get_geojson('ne_10m_geography_marine_polys.geojson')
 lakes=get_geojson('ne_10m_lakes.geojson')
 def where(rows,f=lambda p:True):return [(p['_lonlat'][1],p['_lonlat'][0]) for p in rows if f(p)]
 cla=lambda key,*values:lambda p:p.get(key) in values
 return [
  ('人口500万人以上の都市',where(places,lambda p:(p['pop_max'] or 0)>=5e6)),
  ('人口100万人以上の都市',where(places,lambda p:(p['pop_max'] or 0)>=1e6)),
  ('世界の首都',where(places,lambda p:p['adm0cap']==1)),
  ('州都・県庁所在地など（第1級行政区の首府）',where(places,cla('featurecla','Admin-1 capital'))),
  ('観測基地・科学基地',where(places,cla('featurecla','Scientific station'))),
  ('世界の主要な港',where(get_geojson('ne_10m_ports.geojson'))),
  ('標高5000m以上の山',where(peaks,lambda p:p['featurecla']=='mountain' and (p['elevation'] or 0)>=5000)),
  ('標高3000m以上5000m未満の山',where(peaks,lambda p:p['featurecla']=='mountain' and 3000<=(p['elevation'] or 0)<5000)),
  ('主要な岬',where(region_points,cla('featurecla','cape'))),
  ('主要な島',where(regions,cla('FEATURECLA','Island'))),
  ('主要な諸島',where(regions,cla('FEATURECLA','Island group'))),
  ('主要な山脈',where(regions,cla('FEATURECLA','Range/mtn'))),
  ('主要な砂漠',where(regions,cla('FEATURECLA','Desert'))),
  ('主要な高原',where(regions,cla('FEATURECLA','Plateau'))),
  ('主要な平野',where(regions,cla('FEATURECLA','Plain'))),
  ('主要な海',where(marine,cla('featurecla','sea'))),
  ('主要な湾（gulf）',where(marine,cla('featurecla','gulf'))),
  ('主要な湾（bay）',where(marine,cla('featurecla','bay'))),
  ('主要な海峡',where(marine,cla('featurecla','strait'))),
  ('主要な湖',where(lakes,cla('featurecla','Lake'))),
  ('主要な人造湖',where(lakes,cla('featurecla','Reservoir'))),
  ('塩湖・アルカリ湖',where(lakes,cla('featurecla','Alkaline Lake'))),
  ('干上がった湖（プラヤ）',where(get_geojson('ne_10m_playas.geojson'))),
  ('サンゴ礁',where(get_geojson('ne_10m_reefs.geojson'))),
  ('氷河',where(get_geojson('ne_10m_glaciated_areas.geojson'))),
 ]
def collect_earth():
 quakes=get_csv(EARTHQUAKES)
 def quake(lo,hi=99):return [(num(r['Latitude']),num(r['Longitude'])) for r in quakes if lo<=num(r['Magnitude'],0)<hi]
 volcanoes=get_csv(VOLCANOES,'latin-1')
 def volcano(f):return [(num(r['Latitude']),num(r['Longitude'])) for r in volcanoes if f(r)]
 kind=lambda name:volcano(lambda r:r['Type']==name)
 return [
  ('M7.5以上の地震（1965〜2016年）',quake(7.5)),
  ('M7.0以上7.5未満の地震（1965〜2016年）',quake(7,7.5)),
  ('成層火山',kind('Stratovolcano')),
  ('盾状火山',kind('Shield volcano')),
  ('海底火山',kind('Submarine volcano')),
  ('火山地帯（火山群）',kind('Volcanic field')),
  ('カルデラ',kind('Caldera')),
  ('噴石丘',kind('Cinder cone')),
  ('複合火山',kind('Complex volcano')),
  ('溶岩ドーム',kind('Lava dome')),
  ('1964年以降に噴火した火山',volcano(lambda r:r['Last Known']=='D1')),
  ('標高4000m以上の火山',volcano(lambda r:num(r['Elev'],0)>=4000)),
 ]
def collect_wikidata():
 # 公式の窓口(query.wikidata.org)は混雑時に強く制限されるため、QLeverに問い合わせる。
 out=[]
 for name,where in WIKIDATA.items():
  try:
   coords=[]
   for row in qlever(f'SELECT DISTINCT ?item ?coord WHERE {{ {where} }} LIMIT {MAX_POINTS*2}'):
    p=wkt_point(row[1]) if len(row)>1 else None
    if p:coords.append(p)
   out.append((name,coords))
  except Exception as e:note(name,'-',f'取得失敗: {e}')
 return out
def qlever(query):
 """QLeverのWikidata窓口にSPARQLを投げ、TSVの行を返す。"""
 prefixes='PREFIX wd: <http://www.wikidata.org/entity/> PREFIX wdt: <http://www.wikidata.org/prop/direct/> PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#> PREFIX xsd: <http://www.w3.org/2001/XMLSchema#> '
 url=QLEVER
 for _ in range(3):
  req=urllib.request.Request(url,data=urllib.parse.urlencode({'query':prefixes+query}).encode(),headers={'User-Agent':'DotGlobeQuestionCollector/1.0 (GitHub Pages static dataset)','Accept':'text/tab-separated-values','Content-Type':'application/x-www-form-urlencoded'})
  try:
   with urllib.request.urlopen(req,timeout=600) as r:lines=r.read().decode('utf-8').splitlines()
   return [line.split('\t') for line in lines[1:]]
  except urllib.error.HTTPError as e:
   # urllibはPOSTの307/308をたどらないので、移転先に送り直す。
   if e.code not in (307,308) or not e.headers.get('Location'):raise
   url=urllib.parse.urljoin(url,e.headers['Location']);print('QLever redirect',url,flush=True)
 raise RuntimeError('QLever: too many redirects')
def wkt_point(text):
 """WKTの "POINT(経度 緯度)" を(緯度, 経度)にする。月や火星など地球以外の座標は "<天体のIRI> Point(...)" の形になるので除く。"""
 m=re.fullmatch(r'"?point\((-?[\d.eE+-]+) (-?[\d.eE+-]+)\)"?(\^\^\S+)?',text.strip(),re.I)
 return (float(m.group(2)),float(m.group(1))) if m else None
def collect_wikidata_classes():
 """日本語名のあるWikidataの種類のうち、座標付きの項目が範囲内の数あるものを候補にする。"""
 classes={}
 for qid,label,n in qlever('SELECT ?class ?label (COUNT(DISTINCT ?item) AS ?n) WHERE { ?item wdt:P31 ?class . ?item wdt:P625 ?coord . ?class rdfs:label ?label . FILTER(LANG(?label)="ja") } GROUP BY ?class ?label HAVING (COUNT(DISTINCT ?item) >= %d && COUNT(DISTINCT ?item) <= %d)'%(MIN_POINTS,MAX_POINTS*2)):
  label=re.sub(r'^"|"@ja$','',label)
  classes.setdefault(qid,label)
 print('Wikidata classes in range',len(classes),flush=True)
 roots=' '.join('wd:'+q for q in CLASS_ROOTS)
 allowed={row[0] for row in qlever(f'SELECT DISTINCT ?class WHERE {{ VALUES ?root {{ {roots} }} ?class wdt:P279* ?root }}') if row}
 classes={q:l for q,l in classes.items() if q in allowed}
 print('Wikidata classes under roots',len(classes),flush=True)
 coords=collections.defaultdict(dict);country=collections.defaultdict(dict);built=collections.defaultdict(dict);elevation=collections.defaultdict(dict)
 ids=sorted(classes)
 for start in range(0,len(ids),300):
  values=' '.join(ids[start:start+300])
  rows=qlever(f'SELECT ?class ?item ?coord ?country ?built ?elevation WHERE {{ VALUES ?class {{ {values} }} ?item wdt:P31 ?class . ?item wdt:P625 ?coord . OPTIONAL {{ ?item wdt:P17 ?country }} OPTIONAL {{ ?item wdt:P571 ?built }} OPTIONAL {{ ?item wdt:P2044 ?elevation }} }}')
  if start==0:print('QLever sample rows',rows[:3],flush=True)
  for row in rows:
   p=wkt_point(row[2]) if len(row)>2 else None
   if not p:continue
   coords[row[0]][row[1]]=p;country[row[0]].setdefault(row[1],row[3] if len(row)>3 else '')
   m=re.match(r'"(-?\d+)-',row[4]) if len(row)>4 else None
   if m:built[row[0]].setdefault(row[1],int(m.group(1)))
   e=re.match(r'"?(-?[\d.]+)',row[5]) if len(row)>5 and row[5] else None
   if e:elevation[row[0]].setdefault(row[1],float(e.group(1)))
 out=[]
 for qid,label in classes.items():
  items=coords.get(qid,{})
  if not items:continue
  # 国（P17）がわかっている項目の中で、1か国が半数を超える種類は除く。
  known=[c for c in country[qid].values() if c]
  top=collections.Counter(known).most_common(1)
  if top and top[0][1]>len(known)*CLASS_MAX_COUNTRY_SHARE:note(label,len(items),f'除外: 半数以上が1か国（{qid}）',quiet=True);continue
  if label in EXCLUDE:note(label,len(items),'除外: '+EXCLUDE[label]);continue
  out.append((label,list(items.values())))
  # 「〇〇な××」の派生問題。創建年（P571）と標高（P2044）で絞る。派生でも1か国に偏るものは除く。
  variants=[(f'{year}年より前に作られた{label}',[i for i,y in built[qid].items() if y<year]) for year in CLASS_BUILT_BEFORE]
  variants+=[(f'標高{meters}m以上の{label}',[i for i,h in elevation[qid].items() if h>=meters]) for meters in CLASS_ELEVATION_AT_LEAST]
  for name,ids in variants:
   known=[country[qid][i] for i in ids if country[qid].get(i)]
   top=collections.Counter(known).most_common(1)
   if top and top[0][1]>len(known)*CLASS_MAX_COUNTRY_SHARE:continue
   out.append((name,[items[i] for i in ids]))
 return out
def collect_place_names():
 """GeoNamesの地名から「〜dorfで終わる地名」のような問題の候補を作る。(問題名, 地点の添字の集合)の列と、各地点の(緯度, 経度)・国を返す。"""
 with tarfile.open(fileobj=io.BytesIO(get(CITIES))) as tar:cities=json.load(tar.extractfile('package/cities.json'))
 coords=[(num(c['lat']),num(c['lng'])) for c in cities];countries=[c['country'] for c in cities]
 groups=collections.defaultdict(set)
 for i,c in enumerate(cities):
  name=unicodedata.normalize('NFC',c['name']).lower();words=name.split()
  groups['exact',name].add(i)
  if len(words)>1:groups['first',words[0]].add(i);groups['last',words[-1]].add(i)
  # ハイフンやアポストロフィは残す（「Saint-L…」のように表記が崩れないように）。
  first=words[0].strip('.,()');last=words[-1].strip('.,()')
  for k in range(3,7):
   if len(last)>k:groups['suffix',last[-k:]].add(i)
   if len(first)>k:groups['prefix',first[:k]].add(i)
 out=[]
 for (kind,text),idx in groups.items():
  if len(text.strip('.'))<2 or not NAME_MIN_POINTS<=len(idx)<=MAX_POINTS:continue
  if kind in ('suffix','prefix'):
   # 1文字短い語尾・語頭がほぼ同じ地点を指すなら、そちらを使う。
   shorter=text[1:] if kind=='suffix' else text[:-1]
   if len(shorter)>=3 and len(groups.get((kind,shorter),()))<=len(idx)*1.2:continue
   top3=sum(n for _,n in collections.Counter(countries[i] for i in idx).most_common(3))
   if top3<len(idx)*NAME_TOP3_SHARE:continue
  title=text.title() if kind in ('exact','first','last','prefix') else text
  label={'exact':f'「{title}」という名前の地名','first':f'「{title} …」という名前の地名','last':f'「… {title}」という名前の地名','suffix':f'「…{title}」で終わる地名','prefix':f'「{title}…」で始まる地名'}[kind]
  out.append((label,kind,idx))
 # 単語の問題を優先し、同じ種類の中では地点の多い（形がはっきりする）ものから選ぶ。
 out.sort(key=lambda x:(x[1] in ('suffix','prefix'),-len(x[2])))
 return out,coords,countries
def select_place_names(budget,taken):
 picked=[];sets=[];fps=[];per_country=collections.Counter()
 if budget<=0:return picked
 candidates,coords,countries=collect_place_names()
 for label,kind,idx in candidates:
  if len(picked)>=budget:break
  top,n=collections.Counter(countries[i] for i in idx).most_common(1)[0]
  dominant=top if n*2>len(idx) else None
  if dominant and per_country[dominant]>=NAME_COUNTRY_CAP:continue
  if any(len(idx&s)>NAME_MAX_JACCARD*len(idx|s) for s in sets):continue
  points=grid(coords[i] for i in idx)
  if len(points)<MIN_POINTS:continue
  fp=fingerprint(points)
  if any(similarity(fp,other)>=.995 for other in taken):continue
  if sum(similarity(fp,other)>=.97 for other in fps)>=NAME_LOOKALIKE_CAP:continue
  picked.append({'name':label,'points':points});sets.append(idx);fps.append(fp);per_country[dominant]+=1 if dominant else 0
 note('地名パターン',len(candidates),f'候補{len(candidates)}件から{len(picked)}問を採用')
 return picked
def write_summary(kept):
 path=os.environ.get('GITHUB_STEP_SUMMARY')
 if not path:return
 lines=[f'## 問題データ: {len(kept)}問',f'点数の範囲: {MIN_POINTS}〜{MAX_POINTS}（0.1度単位で重複を除いた数）','','| 候補 | 点数 | 結果 |','|---|---:|---|']
 # Actionsのサマリーは1MBまでなので、長すぎる表は切り詰める。
 lines+=[f'| {n} | {c} | {r} |' for n,c,r in report[:3000]]
 with open(path,'a',encoding='utf-8') as f:f.write('\n'.join(lines)+'\n')
def main():
 def gather(sources):
  out=[]
  for fn in sources:
   try:
    for name,coords in fn():
     if name in EXCLUDE:note(name,len(coords),'除外: '+EXCLUDE[name]);continue
     points=grid(coords)
     if len(points)<MIN_POINTS:note(name,len(points),f'除外: {MIN_POINTS}点未満',quiet=True);continue
     if len(points)>MAX_POINTS:note(name,len(points),f'除外: {MAX_POINTS}点超',quiet=True);continue
     out.append({'name':name,'points':points})
   except Exception as e:note(fn.__name__,'-',f'取得失敗: {e}')
  return out
 kept=[];fps=[];names=set()
 def add(items,budget=math.inf):
  for item in items:
   if len(kept)>=budget:break
   if item['name'] in names:continue
   fp=fingerprint(item['points'])
   similar=[kept[i]['name'] for i,other in enumerate(fps) if similarity(fp,other)>=SIMILARITY_THRESHOLD]
   if similar:note(item['name'],len(item['points']),f'除外: {similar[0]}と分布が類似',quiet=True);continue
   kept.append(item);fps.append(fp);names.add(item['name']);note(item['name'],len(item['points']),'採用')
 # 条件を決めて作った問題を先に入れる。点数の少ない（＝特徴が出やすい）候補を優先する。
 add(sorted(gather((collect_airports,collect_power_plants,collect_natural_earth,collect_earth,collect_wikidata)),key=lambda x:len(x['points'])))
 # Wikidataの種類は、全体の分布から離れている（特徴のある）ものから、地名パターンの枠を残して入れる。
 classes=gather((collect_wikidata_classes,))
 if classes:
  base=fingerprint([p for c in classes for p in c['points']])
  scored=[]
  for c in classes:
   sim=similarity(fingerprint(c['points']),base)
   if sim>=CLASS_MAX_BASE_SIMILARITY:note(c['name'],len(c['points']),'除外: Wikidata全体と似た分布',quiet=True)
   else:scored.append((sim,c))
  add([c for _,c in sorted(scored,key=lambda x:x[0])],TARGET-NAME_BUDGET)
 try:kept+=select_place_names(min(NAME_BUDGET,TARGET-len(kept)),fps)
 except Exception as e:note('地名パターン','-',f'取得失敗: {e}')
 write_summary(kept)
 if len(kept)<4:raise SystemExit('Insufficient validated sources: no overwrite of existing questions.json')
 # 座標は0.1度単位の整数を[緯度, 経度, 緯度, 経度, ...]と並べる。
 sets=[{'name':x['name'],'p':[v for p in x['points'] for v in p]} for x in kept]
 (ROOT/'questions.json').write_text(json.dumps({'version':2,'source':'OurAirports / WRI Global Power Plant Database / Natural Earth / USGS / Smithsonian GVP / GeoNames / Wikidata','sets':sets},ensure_ascii=False,separators=(',',':'))+'\n')
 print(f'Generated {len(kept)} questions')
if __name__=='__main__':main()
