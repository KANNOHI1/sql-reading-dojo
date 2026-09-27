# SQL Reading Dojo

BigQuery SQL を「読む」ための学習サイト。予測して、動きで答え合わせして、要件とのズレに気づく。

https://kannohi1.github.io/sql-reading-dojo/

- 単一 HTML（`index.html`）+ 生成データ（`lessons.js`）。CDN 依存なし。ダブルクリックでも開ける
- 題材はすべて架空の化粧品卸「ミツキ化粧品」

## 開発

```
python -m pip install duckdb pyyaml
python tools/build_lessons.py        # content/ を検証して lessons.js を生成
node tests/app.test.cjs              # 構造テスト
python -m http.server 8765           # ローカル確認
```

原稿は `content/levels/L*.yaml`。途中経過の表は人が書かず、DuckDB で実行して生成・検証する。
