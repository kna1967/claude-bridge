# Phase 3 v5.2 軸定義（screening.pyから抽出）

## 軸①～⑱
コード内で明示的に番号付けされた軸が無いため、フィルタ条件から推定して列挙:

- **EqAR >= 0.40** （自己資本比率）
- **OP_margin >= 8** （営業利益率、% 表記）
- **ROE >= 10** （自己資本利益率、% 表記）

データソース: J-Quants `get_fin_summary` の最新 DiscDate レコード（`Code` ごと last）

## 軸③ ポートフォリオ相関
既存保有セクターとの被りチェック。

- 入力: `portfolio_codes`（4桁コード5文字スライスで突合）
- 判定: `listed["S17Nm"]` でセクター名取得 → 通過銘柄のセクターと一致するものを `sector_overlap=True`
- 出力: `overlap`（被り）/ `no_overlap`（分散候補）に分割

## 軸④ 割安度（PBR）
PBR < 1.5 のフィルタ。

- 価格データ: J-Quants `get_eq_bars_daily` の `AdjC` を `Close` として利用
- BPS: `fin` データフレームから銘柄インデックスで `BPS` 列を引く
- 計算: `PBR = Close / BPS`
- ソート: 通過銘柄を ROE 降順

## 軸⑤ 答え合わせ
過去の通過銘柄との継続性チェック。

- 入力: `screening_results` テーブル（SQLite）から `screening_date < date('now')` の DISTINCT Code
- 判定: 今回通過銘柄が過去 DISTINCT Code に含まれるか → `継続通過` 列
- 出力: `continuous` データフレーム

---

※ 軸①～⑱の詳細定義は screening.py 本体には記載なし。別途定義書要。
