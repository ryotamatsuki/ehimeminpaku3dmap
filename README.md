# EHIME MINPAKU ATLAS — 愛媛県民泊3D集中度マップ

愛媛県公表の「住宅宿泊事業法に基づく届出住宅一覧」を対象に、届出住宅の所在地をジオコーディングし、地図上で250m / 500m / 1km / 2kmの3D集計メッシュとして表現するオープンソースの試作です。北海道新聞の民泊可視化企画に着想を得ていますが、本実装・ソースコードは独自制作です。

**公式資料**：愛媛県観光振興課 [住宅宿泊事業について](https://www.pref.ehime.jp/page/57100.html)（[2026年8月31日時点のPDF](https://www.pref.ehime.jp/uploaded/attachment/190246.pdf)）。県は松山市を含む県全域の住宅宿泊事業届出事務を扱っています。

## 公表データの収録状況（2026-10-15確認）

- **住宅宿泊事業法の届出所在地**：愛媛県公表PDF（2026年8月31日時点）から**296行**を抽出。19市町に掲載あり。座標検索で296行を補完したが**地番水準の一致は65行**で、他231行は町域等の推定位置。PDFからの自動抽出・原本全件の目視照合は未了。
- **旅館業法に基づく許可施設の公開名称**：**979件**を別の `data/licensed_lodging.json` に収録。内訳は**松山市255件**（市の2026年3月31日時点の一覧）と**松山市以外724件**（県の2025年12月末時点の一覧）。
- これらの**979件は住宅宿泊事業法の民泊296行に加算しない**。法制度が異なり、住所が一致したとしても同一営業施設とは確認できない。3D集中度の高さも296行のみを使う。
- 旅館業の一覧には休止中・廃業施設が含まれる場合がある。また松山市以外の県一覧は2025年12月末基準なので、2026年の新規許可は未統合。いずれも**現に営業中の施設数ではない**。
- 愛媛県の住宅宿泊事業所在地は、届出者の申し出に応じて非公表とされた住宅を含まない。非公表施設を推測・復元する機能は実装しない。

## 名称の取得元、利用許諾、照合上の限界

| データ | URL | 許諾・帰属 | 基準日 |
|---|---|---|---|
| 松山市「旅館全施設一覧」 | https://www.city.matsuyama.ehime.jp/shisei/opendata/metadata/ryokanzensisetu.html | © 松山市、CC BY 4.0 | 2026-03-31 |
| 愛媛県「旅館業一覧」 | https://www.pref.ehime.jp/opendata-catalog/dataset/2312.html | © 愛媛県、CC BY 4.0 | 2025-12-31 |
| 愛媛県「住宅宿泊事業に基づく届出住宅一覧」 | https://www.pref.ehime.jp/page/57100.html | 県の利用条件に従い出典を表示 | 2026-08-31 |

公式ファイルの名称・所在地のみを抜き出し、著作物である写真、紹介文、口コミ、予約料金は取得・転載しない。出典リンクとライセンスURLを各レコードへ保持する。元の一覧は都度更新されるため、利用時点のライセンス条件も確認する。

**楽天トラベル・Airbnb・Booking.com等の通常ページをスクレイピングしない。** 楽天トラベルには公式APIが存在するが、表示、保存、リンク等に個別条件があるため、ユーザー登録・ライセンス条件の充足を確認するまではマップの公開JSONへ取り込まない。

実装済みの住所一致は**「同一住所に別制度の許可施設が掲載されている候補」**の検索だけであり、名前が一致した民泊という確定表示はしない。実際の住宅宿泊事業施設名称を付与するには、届出番号・営業名称・公開住所の同一性を独立に確認し、出典と確認日を記録する必要がある。

**更新**：GitHub Actions の `Import CC BY licensed lodging names` が毎月17日に自治体の公開ファイルを再取得。県PDF取込とは別のワークフローで動く。最新の公開状況はActionsとJSONの `generated_at`, `sources`, `warnings` で確認する。

## 公開手順（GitHub Pages）

1. リポジトリの **Settings → Pages → Build and deployment → Source: GitHub Actions** を選択。
2. **Actions → Import Ehime minpaku PDF → Run workflow** を実行（初回は自動Pushトリガーでも起動可能）。実行ログの抽出件数、`data/extraction-anomalies.txt`、県内自治体ごとの件数を必ず確認。
3. **Actions → Verify and deploy 3D atlas → Run workflow** を実行。公開URLは通常 `https://ryotamatsuki.github.io/ehimeminpaku3dmap/` です。**公開に成功したことはActionsのDeploy結果で判断**してください。
4. GitHub Actions に push 権限がない場合は Settings → Actions → General → Workflow permissions で Read and write permissions を有効化するか、データJSONを手動コミットしてください。

### ローカルで起動

```bash
python -m http.server 8000
# http://localhost:8000/
```

GitHub Pagesでは `/` 配下への配置ではなく、相対パス `./src/...` `./data/...` を使用しているためプロジェクトサイトのサブパスでも動きます。インターネット接続が必要です（MapLibre、地理院タイル、住所検索）。

## 機能

- 愛媛県全域・市町別の絞り込みと、松山・今治・宇和島への移動
- 250m / 500m / 1km / 2kmの3D集計柱と相対色分け
- 届出住宅の行数 / 同一の地番表記をまとめた「推定所在地数」の切替
- 住所検索の位置精度を区別。**町域代表点などの低精度座標は250m・500mで原則除外**（明示的なオプションで解除可能）
- 市町別の届出住宅掲載数と座標取得済み件数の表示
- ブラウザ上の座標再検索とローカルキャッシュ（ローカル実行中のみ）
- 松山市・愛媛県のCC BY許可施設名称を市町・名称・所在地で検索（民泊届出とは別制度）

## 取り込み方法

```bash
pip install -r requirements.txt
python scripts/refresh_data.py                         # 県PDFを取得、全文を取り込み、住所検索
python scripts/refresh_data.py --pdf /path/to/ehime.pdf # 手元のPDFから取り込み
python scripts/refresh_data.py --pdf /path/to/ehime.pdf --no-geocode # 位置変換を後から実施
node --test tests/test_geo.mjs
python -m unittest discover -s tests -p 'test_*.py'
```

`data/geocode-cache.json` は住所変換の再実行を減らすためのキャッシュです。元PDFのフォーマット変更や未認識行は `data/extraction-anomalies.txt` を確認し、必要ならパーサーを改修してください。民泊の掲載数は**各住所行の件数**であり「事業者数」「稼働件数」「実宿泊者数」ではありません。

## 位置と分析上の注意

1. 住宅宿泊事業の届出住宅のみ対象です。旅館業法の許可施設（簡易宿所・旅館・ホテル）は含みません。
2. 地番まで検索できない場合、町丁目・町域等の代表点が返るため、**見かけ上の集中**が発生し得ます。地図が表示するのは推定座標の集計です。統計を公開・報道する前には位置精度と住所の原本照合を行ってください。
3. 「所在地数」は住所正規化の推定値です。棟数・ホスト数・事業者数を意味しません。
4. 3Dの高さは件数を非線形スケールで表示。柱の高さは実際の建物の高さではありません。方眼は緯度経度を近似変換した任意の正方形格子で、行政界メッシュやJIS標準地域メッシュと完全一致しません。
5. 正規化住所・Geocoding出力・同一地番の扱いは実務用途では個別検証が必要です。
6. 地理院タイル：© 国土地理院。利用条件は [地理院タイル](https://maps.gsi.go.jp/development/ichiran.html) に従います。

## 構成

```text
index.html              UI
src/style.css           スタイル
src/main.mjs            MapLibre 3D表示・操作
src/geo.mjs             座標集計・市町認識（純関数）
data/listings.json      公表住所 / 座標 / 精度 / 出典
scripts/refresh_data.py PDF取込・住所変換
scripts/import_licensed_lodging.py 自治体旅館業許可データの名称抽出（XLS/XLSX）
data/licensed_lodging.json 旅館業法の公開施設名（CC BY）
.github/workflows/      テスト / Pagesデプロイ / 県データ更新
tests/                  最低限の自動テスト
```

このリポジトリは愛媛県の公式サイトではなく、県の公表資料を用いた第三者の可視化プロジェクトです。
