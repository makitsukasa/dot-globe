# Dot Globe

GitHub Pagesで遊べる、点群から地理的な対象を当てる4択クイズです。サーバー不要です。

## 公開

`main`へのpushで Actions → **Publish Dot Globe** が走り、サイトのファイルを`gh-pages`ブランチに書き出します。公開URLは `https://makitsukasa.github.io/dot-globe/` です。Pagesの公開元は`gh-pages`ブランチ（ルート）です。

`index.html`にはオフライン用の8問を同梱しています。出題順は毎回シャッフルされます。`questions.json`が存在すれば自動で読み込みます。

## 問題データの生成

`python scripts/collect.py` で`questions.json`を生成します。Actions → **Refresh question data** → Run workflow でも実行でき、生成結果が`main`にコミットされ、公開し直されます。4問未満になった場合は既存ファイルを上書きしません。

目標は約1000問です。現状は約450問（うち地名パターン100問）です。

- 条件を決めて作る問題：空港・発電所・Natural Earth・地震・火山のデータを「出力1000MW以上の水力発電所」「氷・雪の滑走路がある飛行場」のように絞ります。
- Wikidataの種類：日本語名があり、地形・水域・火山・保護区・宗教建築・遺跡・要塞・鉱山・発電所・ダム・灯台・空港・港・天文台・スキー場・集落などの下位分類にあたる種類を、[QLever](https://qlever.dev/wikidata)で集計して使います。国（P17）がわかる項目の半数以上が1か国にある種類と、Wikidata全体と似た分布の種類は除きます。標高（P2044）や創建年（P571）で絞った「標高2000m以上の〇〇」のような派生問題も作ります。
- 地名パターン：GeoNamesの地名から「〜dorfで終わる地名」のような問題を最大100問作ります。
- 点数が30〜3000点の候補だけを問題にします（0.1度単位で重複を除いた数）。範囲外の候補は間引かずに除外します。
- 分布が似た候補は機械的に除きます。
- 地図に描いて目視で確認し、問題に向かない候補・同じ意味の候補は`collect.py`の`EXCLUDE`に理由付きで登録します。
- ゲームでは、正解と分布が似ていない問題を選択肢に選びます。
- 各候補の点数と採否・除外理由は、実行ログとActionsのサマリーに表として出ます。

国・地域で絞った問題は作りません（輪郭がそのまま答えになるため）。ただし地名パターンには、言語の分布として1か国に集まるものがあります。ブラウザ側の「再収集」は実験用で、保存しても公開データは更新されません。

## データ源

- 空港: [OurAirports](https://ourairports.com/data/)（パブリックドメイン）
- 発電所: [WRI Global Power Plant Database](https://github.com/wri/global-power-plant-database)（CC BY 4.0）
- 地名: [GeoNames](https://www.geonames.org/)（CC BY 4.0、npmパッケージ cities.json 経由）
- 地震: USGS（plotly/datasetsのM5.5以上・1965〜2016年）
- 火山: Smithsonian Global Volcanism Program（plotly/datasets経由）
- 都市・港・山・海岸線: [Natural Earth](https://www.naturalearthdata.com/)（パブリックドメイン）
- Wikidata（CC0）: QLever経由。Actions上でのみ取得します
