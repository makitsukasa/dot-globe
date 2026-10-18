# Dot Globe

GitHub Pagesで遊べる、点群から地理的な対象を当てる4択クイズです。サーバー不要です。

## 公開

1. Settings → Pages → Source を **GitHub Actions** にします。
2. Actions → Publish Dot Globe の実行結果から公開URLを確認します。

`index.html`にはオフライン用の8問を同梱しています。`questions.json`が存在すれば公開時に自動で読み込みます。

## 問題データの生成

Actions → **Refresh question data** → Run workflow を実行します。Wikidataと空港の公開データをGitHub Actions上で取得し、`questions.json`を生成・コミットします。コミット後はPagesの再デプロイが走ります。外部APIが失敗して4問未満になった場合、既存ファイルは上書きしません。初回の収集が成功するまでは8問版です。

**注意:** 自動収集で得られる問題数は未保証です。分布類似度による間引きのみ実装済みで、人間が判別可能かの審査は未実装です。国・地域で絞った空港問題は生成しません。現状のブラウザ側の「再収集」は実験用で、保存しても公開データは更新されません。

データ源: Wikidata (CC0)、airport-codes (各データの利用条件は提供元を確認)。
