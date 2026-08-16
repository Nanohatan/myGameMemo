
privateで作っているゲームのリソース確認用ドキュメント
https://nanohatan.github.io/myGameMemo/

## リソースドキュメントの生成

```powershell
python py_scrips/parse_resorce.py
python py_scrips/generate_resource_docs.py
hugo
```

`_game/Resources` 内の `.tres` / `.res` 1ファイルにつき、`data/generated/resources`
にJSONを1ファイル生成します。元のディレクトリは Hugo の一覧ページになり、各JSONは
個別の詳細ページに対応します。
