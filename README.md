# EHIME MINPAKU ATLAS — 愛媛県民泊3D集中度マップ

愛媛県公表の「住宅宿泊事業法に基づく届出住宅一覧」を対象に、届出住宅の所在地をジオコーディングし、地図上で250m / 500m / 1km / 2kmの3D集計メッシュとして表現するオープンソースの試作です。北海道新聞の民泊可視化企画に着想を得ていますが、本実装・ソースコードは独自制作です。

**公式資料**：愛媛県観光振興課 [住宅宿泊事業について](https://www.pref.ehime.jp/page/57100.html)（[2026年8月31日時点のPDF](https://www.pref.ehime.jp/uploaded/attachment/190246.pdf)）。県は松山市を含む県全域の住宅宿泊事業届出事務を扱っています。

## 表示対象（2026-10-15改修）

**公開サイトでは住宅宿泊事業法に基づく届出住宅296行のみを表示します。**
地図の立体メッシュ、市町別件数、タップしたメッシュ内の住所一覧は、すべて愛媛県公表の届出住宅に限定しています。

- 届出住宅の営業名称は県公式一覧にないため「名称未掲載」と表示。ホテル、旅館、簡易宿所の名称を割り当てません。
- 旅館業法による許可施設は、地図上の点、サイドバーの名称検索、メッシュ詳細のいずれにも**表示しません**。
- 旅館業法許可施設979件の過去調査データと座標は、再利用時の監査用にGitHubリポジトリ内に保管しています。ただし**Webサイトの配信アーティファクトには含めず、画面から取得もしません**。
- 県PDFは2026年8月31日時点。公表住所296行の座標検索のうち65行が地番水準の照合、231行が町域等の代表点です。PDF原本との全件照合は未実施です。
- 公表一覧には所在地非公表の住宅が含まれません。見えている件数を実際の届出・営業施設数と同一視できません。

## データ公開範囲

GitHub Pagesでは `index.html`、`src/style.css`、`src/main.mjs`、`src/geo.mjs`、`src/mesh-details.mjs`、`data/listings.json` のみをパッケージ化して配信します。

`data/licensed_lodging.json`、`data/permit_coordinates.json`、これらの補助コードや取り込みスクリプトは**GitHub Pagesから配信しません**。ただし、公開設定のGitHubリポジトリからは閲覧でき、リポジトリから削除したわけではありません。

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

## タップ操作

3Dメッシュや地図の任意地点をタップすると、選択したメッシュ内に集計された**届出住宅の所在地だけ**を表示します。施設名称は未確認として扱い、住所検索で町域代表点しか特定できなかったケースも区別して表示します。

## 機能

- 愛媛県全域・市町別の絞り込みと、松山・今治・宇和島への移動
- 250m / 500m / 1km / 2kmの3D集計柱と相対色分け
- 届出住宅の行数 / 同一の地番表記をまとめた「推定所在地数」の切替
- 住所検索の位置精度を区別。**町域代表点などの低精度座標は250m・500mで原則除外**（明示的なオプションで解除可能）
- 市町別の届出住宅掲載数と座標取得済み件数の表示
- ブラウザ上の座標再検索とローカルキャッシュ（ローカル実行中のみ）
- 旅館業法の許可施設の表示・検索・地図上での紐付けは行わない

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
scripts/refine_permit_geocodes.py 過去調査の位置照合コード（サイトでは使用しない）
data/licensed_lodging.json 旅館業法の過去調査データ（サイト配信から除外）
data/permit_coordinates.json 同データの座標（サイト配信から除外）
.github/workflows/      テスト / Pagesデプロイ / 県データ更新
tests/                  最低限の自動テスト
```

このリポジトリは愛媛県の公式サイトではなく、県の公表資料を用いた第三者の可視化プロジェクトです。
