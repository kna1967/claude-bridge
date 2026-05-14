# ===========================================
# Phase 3 Screening - Claude.ai参照用コピー
# 取得日: 2026-05-14
# 出典: ~/phase3/screening.py on さくらVPS（手動転記）
# 注意: 機密情報除去済み。
#   - ポートフォリオコード（L77相当）はREDACTED
#   - VPSのパス（/home/ubuntu/...）は相対パスにREDACTED
#   動作には別途.env設定と元パス復元が必要
# 既知バグ:
#   - L21, L97: date_yyyymmdd="20250509" ハードコード（PR#1で修正済、未デプロイ）
#   - 営業日判定なし（PR#1で追加済）
#   - SQLite if_exists="append" による無条件追記
# ===========================================
import os
import requests
import pandas as pd
from dotenv import load_dotenv
import jquantsapi
import sqlite3
from datetime import date
import subprocess

load_dotenv("./.env")  # REDACTED: 元のパスは /home/ubuntu/phase3/.env
api_key = os.getenv("JQUANTS_API_KEY")
cli = jquantsapi.ClientV2(api_key=api_key)

print("=== Phase3 v5.2 1次スクリーニング ===")

# 1. 銘柄一覧取得
print("銘柄一覧取得中...")
listed = cli.get_list()
listed = listed[listed["MktNmEn"].isin(["Prime", "Standard"])]
print(f"対象銘柄数: {len(listed)}")

# 2. 財務データ取得
print("財務データ取得中...")
fin = cli.get_fin_summary(date_yyyymmdd="20250509")
print(f"財務データ件数: {len(fin)}")
fin = fin.sort_values("DiscDate").groupby("Code").last().reset_index()

# 3. 数値変換
df = fin.copy()
for col in ["OP", "Sales", "NP", "Eq", "EqAR"]:
    df[col] = pd.to_numeric(df[col], errors="coerce")

# 4. 指標計算
df["OP_margin"] = (df["OP"] / df["Sales"] * 100).round(2)
df["ROE"] = (df["NP"] / df["Eq"] * 100).round(2)

# 5. フィルタ
result = df[
    (df["EqAR"] >= 0.40) &
    (df["OP_margin"] >= 8) &
    (df["ROE"] >= 10)
].copy()

# 6. 銘柄名結合
result = result.merge(listed[["Code", "CoName"]], on="Code", how="left")

print(f"\n=== 1次スクリーニング結果 ===")
print(f"通過銘柄数: {len(result)}")
print(result[["Code", "CoName", "EqAR", "OP_margin", "ROE"]].to_string())

# 7. SQLiteに保存
db_path = "./screening.db"  # REDACTED
conn = sqlite3.connect(db_path)
result["screening_date"] = date.today().isoformat()
result[["screening_date", "Code", "CoName", "EqAR", "OP_margin", "ROE"]].to_sql(
    "screening_results", conn, if_exists="append", index=False
)
conn.close()
print(f"\nSQLiteに保存完了: {db_path}")

# 9. 軸③ポートフォリオ相関チェック
portfolio_codes = []  # REDACTED: 実際のコードは.env等で管理
portfolio_sectors = listed[listed["Code"].str[:5].isin(portfolio_codes)]["S17Nm"].tolist()
result2 = result.merge(listed[["Code", "S17Nm", "S33Nm"]], on="Code", how="left")
result2["sector_overlap"] = result2["S17Nm"].isin(portfolio_sectors)
overlap = result2[result2["sector_overlap"] == True]
no_overlap = result2[result2["sector_overlap"] == False]
print(f"\n=== 軸③ポートフォリオ相関 ===")
print(f"既存保有セクター: {portfolio_sectors}")
print(f"セクター被り銘柄数: {len(overlap)}")
print(f"分散候補銘柄数: {len(no_overlap)}")
print("\n--- 分散候補トップ10（ROE順）---")
print(no_overlap.nlargest(10, "ROE")[["Code", "CoName", "S17Nm", "ROE", "OP_margin"]].to_string())

# 軸④ 割安度チェック（PBR）
print("\n株価データ取得中（一括）...")
try:
    prices_all = cli.get_eq_bars_daily(date_yyyymmdd="20250509")
    prices_all = prices_all[["Code", "AdjC"]].rename(columns={"AdjC": "Close"})
    result2 = result2.merge(prices_all, on="Code", how="left")
    result2["BPS"] = pd.to_numeric(
        fin.set_index("Code").reindex(result2["Code"].values)["BPS"].values,
        errors="coerce"
    )
    result2["PBR"] = (result2["Close"] / result2["BPS"]).round(2)
    print("割安候補（PBR<1.5）:")
    cheap = result2[result2["PBR"] < 1.5].sort_values("ROE", ascending=False)
    print(cheap[["Code", "CoName", "PBR", "ROE", "S17Nm"]].head(10).to_string())
except Exception as e:
    print(f"株価取得エラー: {e}")

# 軸⑤ 答え合わせ
print("\n=== 軸⑤ 答え合わせ ===")
try:
    conn2 = sqlite3.connect(db_path)
    past = pd.read_sql("SELECT DISTINCT Code FROM screening_results WHERE screening_date < date('now')", conn2)
    conn2.close()
    if len(past) > 0:
        result2["継続通過"] = result2["Code"].isin(past["Code"])
        continuous = result2[result2["継続通過"] == True]
        print(f"継続通過銘柄数: {len(continuous)}")
        print(continuous[["Code", "CoName", "ROE", "OP_margin", "S17Nm"]].to_string())
    else:
        print("過去データなし（初回実行）")
except Exception as e:
    print(f"答え合わせエラー: {e}")

# Obsidian vault連携
today_str2 = date.today().isoformat()
vault_path = "./obsidian-vault/銘柄分析/スクリーニング"  # REDACTED
os.makedirs(vault_path, exist_ok=True)
md = f"# v5.2スクリーニング結果 {today_str2}\n\n"
md += f"## 1次スクリーニング通過: {len(result)}件\n\n"
md += "## 分散候補トップ10（ROE順）\n\n"
md += "| Code | 銘柄名 | セクター | ROE | 営業利益率 | PBR |\n"
md += "|---|---|---|---|---|---|\n"
top10 = result2.nlargest(10, "ROE")
for _, row in top10.iterrows():
    pbr = f"{row.get('PBR', 'N/A')}"
    md += f"| {row['Code']} | {row['CoName']} | {row.get('S17Nm','N/A')} | {row['ROE']}% | {row['OP_margin']}% | {pbr} |\n"
md_path = f"{vault_path}/{today_str2}.md"
with open(md_path, "w", encoding="utf-8") as f:
    f.write(md)
subprocess.run(["git", "-C", "./obsidian-vault", "add", "."])  # REDACTED
subprocess.run(["git", "-C", "./obsidian-vault", "commit", "-m", f"screening {today_str2}"])  # REDACTED
subprocess.run(["git", "-C", "./obsidian-vault", "push"])  # REDACTED
print(f"Obsidian vault保存完了: {md_path}")

# 8. Slack通知
webhook_url = os.getenv("SLACK_WEBHOOK_URL")
top5 = no_overlap.nlargest(5, "ROE")[["Code", "CoName", "OP_margin", "ROE", "S17Nm"]]
msg = f"📊 *v5.2 1次スクリーニング結果 {date.today()}*\n"
msg += f"通過銘柄数: {len(result)}件 / 分散候補: {len(no_overlap)}件\n\n"
msg += "*分散候補トップ5（ROE順）:*\n"
for _, row in top5.iterrows():
    msg += f"• {row['Code']} {row['CoName']} [{row.get('S17Nm','N/A')}] ROE:{row['ROE']}% 営業利益率:{row['OP_margin']}%\n"
requests.post(webhook_url, json={"text": msg})
print("Slack通知送信完了")
