# Dot Globe

GitHub Pagesで遊べる、点群から地理的な対象を当てる4択クイズです。サーバー不要です。

## 公開

`main`へのpushで Actions → **Publish Dot Globe** が走り、サイトのファイルを`gh-pages`ブランチに書き出します。公開URLは `https://makitsukasa.github.io/dot-globe/` です。Pagesの公開元は`gh-pages`ブランチ（ルート）です。

`index.html`にはオフライン用の8問を同梱しています。`questions.json`が存在すれば自動で読み込みます。

## 問題データの生成

`python scripts/collect.py` で`questions.json`を生成します。Actions → **Refresh question data** → Run workflow でも実行でき、生成結果が`main`にコミットされ、公開し直されます。4問未満になった場合は既存ファイルを上書きしません。

- 大きなデータはそのまま使わず、「出力1000MW以上の水力発電所」「氷・雪の滑走路がある飛行場」のように条件で絞ります。
- 点数が30〜3000点の候補だけを問題にします。範囲外の候補は間引かずに除外します。
- 分布が似た候補は機械的に除きます（点数の少ない方を残します）。
- 地図に描いて目視で確認し、問題に向かない候補は`collect.py`の`EXCLUDE`に理由付きで登録します。
- 各候補の点数と採否・除外理由は、実行ログとActionsのサマリーに表として出ます。

国・地域で絞った問題は作りません（輪郭がそのまま答えになるため）。ブラウザ側の「再収集」は実験用で、保存しても公開データは更新されません。

## データ源

- 空港: [OurAirports](https://ourairports.com/data/)（パブリックドメイン）
- 発電所: [WRI Global Power Plant Database](https://github.com/wri/global-power-plant-database)（CC BY 4.0）
- 都市・港・山・海岸線: [Natural Earth](https://www.naturalearthdata.com/)（パブリックドメイン）
- Wikidata（CC0）: Actions上でのみ取得します
