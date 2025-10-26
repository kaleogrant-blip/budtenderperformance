import argparse, json, os, re, glob
from pathlib import Path
import numpy as np
import pandas as pd
from datetime import datetime

TARGET_SEC = 90.0
MIN_TXNS   = 30

def normalize_name(s: str) -> str:
    if pd.isna(s): return ""
    s = str(s).strip().lower()
    s = re.sub(r"[^\w\s]", "", s)
    s = re.sub(r"\s+", " ", s)
    return s

def read_tx_csv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df.columns = [c.strip() for c in df.columns]
    df['TransactionTime'] = pd.to_numeric(df.get('TransactionTime'), errors='coerce')
    for col in ['TransactionBy','OrderType','OrderSource','OrderMethod']:
        if col in df.columns: df[col] = df[col].astype(str)
    if 'TransactionCompleted' in df.columns:
        df['TransactionCompleted'] = pd.to_datetime(df['TransactionCompleted'], errors='coerce')
    else:
        for alt in ['Transaction Completed','Transaction_Completed','CompletedAt']:
            if alt in df.columns:
                df['TransactionCompleted'] = pd.to_datetime(df[alt], errors='coerce'); break
    return df

def contains_nonstop(series: pd.Series) -> pd.Series:
    return series.astype(str).str.contains(r"non\s*stop", case=False, na=False)

def filter_tx(df: pd.DataFrame) -> pd.DataFrame:
    is_delivery = df['OrderType'].str.contains('Delivery', case=False, na=False) if 'OrderType' in df.columns else False
    is_nonstop  = contains_nonstop(df.get('OrderSource', pd.Series("", index=df.index))) |                   contains_nonstop(df.get('OrderType', pd.Series("", index=df.index)))   |                   contains_nonstop(df.get('OrderMethod', pd.Series("", index=df.index)))
    out = df.loc[~is_delivery & ~is_nonstop].copy()
    if 'OrderType' in out.columns and out['OrderType'].str.contains('In-Store', case=False, na=False).any():
        out = out[out['OrderType'].str.contains('In-Store', case=False, na=False)].copy()
    return out

def build_speed(df: pd.DataFrame) -> pd.DataFrame:
    g = (df.groupby('TransactionBy', as_index=False)
           .agg(Txns=('txn_seconds','size'),
                avg_s=('txn_seconds','mean'),
                pct_meet=('txn_seconds', lambda x: (x <= TARGET_SEC).mean()*100.0)))
    g['Avg (mm:ss)'] = g['avg_s'].apply(lambda s: f"{int(s//60)}:{int(s%60):02d}" if pd.notna(s) else "")
    g['% ≤ 1:30']    = g['pct_meet'].round(1)
    def speed_tier(row):
        if row['Txns'] < MIN_TXNS: return 'Gray'
        if (row['avg_s'] <= 90) or (row['pct_meet'] >= 70): return 'Green'
        if ((row['avg_s'] > 90 and row['avg_s'] <= 120) or (50 <= row['pct_meet'] < 70)): return 'Yellow'
        return 'Red'
    g['Speed_Tier'] = g.apply(speed_tier, axis=1)
    return g

def read_fee_glob(glob_pattern: str) -> pd.DataFrame:
    parts = []
    for p in glob.glob(glob_pattern):
        try:
            df = pd.read_excel(p, sheet_name="Report", header=0)
            df['TransactionDate'] = pd.to_datetime(df['TransactionDate'], errors='coerce')
            df['CashValue'] = pd.to_numeric(df['CashValue'], errors='coerce')
            df['Budtender'] = df['Budtender'].astype(str)
            parts.append(df)
        except Exception as e:
            print(f"WARNING: failed to read {p}: {e}")
    if not parts:
        return pd.DataFrame(columns=['ReceiptID','FeeDonationName','TransactionDate','CashValue','Budtender'])
    return pd.concat(parts, ignore_index=True)

def build_acq(df: pd.DataFrame) -> pd.DataFrame:
    ff = df[df['FeeDonationName'].fillna('').str.contains('frequent flyer', case=False, na=False)].copy()
    by = (ff.groupby('Budtender', as_index=False)
            .agg(FF_Acquisitions=('ReceiptID','nunique'),
                 FF_Fee_Total=('CashValue','sum'),
                 FF_First=('TransactionDate','min'),
                 FF_Last=('TransactionDate','max')))
    return by

def tier_acq(perf: pd.DataFrame):
    eligible = perf[perf['Txns'] >= MIN_TXNS]
    if eligible.empty or eligible['FF per 100 txns'].isna().all():
        p25 = p75 = 0.0
    else:
        p25 = float(eligible['FF per 100 txns'].quantile(0.25))
        p75 = float(eligible['FF per 100 txns'].quantile(0.75))
    def acq_tier(v):
        if pd.isna(v): return 'Low'
        if v >= p75: return 'High'
        if v < p25:  return 'Low'
        return 'Mid'
    perf['Acq_Tier'] = perf['FF per 100 txns'].apply(acq_tier)
    return perf, p25, p75

def coaching(speed_t, acq_t):
    if speed_t == 'Green' and acq_t == 'High':
        return "Exceeds: keep speed + enrollment; share script; mentor one peer weekly."
    if speed_t == 'Green' and acq_t in ['Mid','Low']:
        return "Fast but low FF: add one-liner at tender; ask every customer; micro-goal = +1 FF/shift."
    if speed_t == 'Yellow' and acq_t == 'High':
        return "Quality-first: protect pitch; shave 10–20s via ID ready, barcode flow, preset bag, tender script."
    if speed_t == 'Yellow' and acq_t in ['Mid','Low']:
        return "Middle: two speed fixes + FF pitch; shadow Green-High once; recheck in 7 days."
    if speed_t == 'Red' and acq_t == 'High':
        return "Converting but slow: keep pitch; targeted speed drills; register workflow retrain."
    if speed_t == 'Red' and acq_t in ['Mid','Low']:
        return "Under target: coaching card + 2-week plan; shadow + daily check-ins; escalate if no change."
    if speed_t == 'Gray':
        return "Insufficient data (<30 txns); monitor next cycle."
    return "Review individually."

def build_views(tx_csv: str, fee_glob: str, exclusions_path: str, out_dir: str, peak_hours: list[int]):
    tx = read_tx_csv(Path(tx_csv))
    tx = filter_tx(tx)

    excl = []
    if exclusions_path and os.path.exists(exclusions_path):
        with open(exclusions_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            excl = [normalize_name(x) for x in data.get("former_staff", [])]
    tx['_bt_norm'] = tx['TransactionBy'].apply(normalize_name)
    if excl:
        tx = tx[~tx['_bt_norm'].isin(excl)].copy()

    tx['txn_seconds'] = tx['TransactionTime'] * 60.0
    tx['hour_24'] = tx['TransactionCompleted'].dt.hour if 'TransactionCompleted' in tx.columns else np.nan

    speed_all = build_speed(tx)
    speed_peak = build_speed(tx[tx['hour_24'].isin(peak_hours)]) if 'hour_24' in tx.columns else speed_all.iloc[0:0,:].copy()

    fees = read_fee_glob(fee_glob)
    if not fees.empty and 'Budtender' in fees.columns:
        fees['_bt_norm'] = fees['Budtender'].apply(normalize_name)
    if excl and not fees.empty and '_bt_norm' in fees.columns:
        fees = fees[~fees['_bt_norm'].isin(excl)].copy()
    ff_by = build_acq(fees) if not fees.empty else pd.DataFrame(columns=['Budtender','FF_Acquisitions','FF_Fee_Total','FF_First','FF_Last'])

    perf_all = speed_all.merge(ff_by, left_on='TransactionBy', right_on='Budtender', how='left')
    perf_all['Budtender'] = perf_all['TransactionBy']
    perf_all['FF_Acquisitions'] = perf_all['FF_Acquisitions'].fillna(0).astype(int)
    perf_all['FF per 100 txns'] = (perf_all['FF_Acquisitions'] / perf_all['Txns'] * 100.0).replace([np.inf,-np.inf], np.nan).round(3)
    perf_all['FF Conversion Rate'] = (perf_all['FF_Acquisitions'] / perf_all['Txns']).replace([np.inf,-np.inf], np.nan).fillna(0).round(4)
    perf_all, p25, p75 = tier_acq(perf_all)
    perf_all['Recommendation'] = perf_all.apply(lambda r: coaching(r['Speed_Tier'], r['Acq_Tier']), axis=1)

    if not speed_peak.empty:
        perf_peak = speed_peak.merge(ff_by[['Budtender','FF_Acquisitions']], left_on='TransactionBy', right_on='Budtender', how='left')
        if not fees.empty and 'TransactionDate' in fees.columns:
            ff_pk = fees.copy()
            ff_pk['hour_24'] = ff_pk['TransactionDate'].dt.hour
            ff_pk = ff_pk[ff_pk['hour_24'].isin(peak_hours)]
            ff_pk_by = (ff_pk.groupby('Budtender', as_index=False)
                        .agg(FF_Acq_Peak=('ReceiptID','nunique')))
            perf_peak = perf_peak.merge(ff_pk_by, on='Budtender', how='left')
        else:
            perf_peak['FF_Acq_Peak'] = np.nan
        perf_peak['Budtender'] = perf_peak['TransactionBy']
        perf_peak['FF_Acq_Peak'] = perf_peak['FF_Acq_Peak'].fillna(0).astype(int)
        perf_peak['FF per 100 (Peak)'] = (perf_peak['FF_Acq_Peak'] / perf_peak['Txns'] * 100.0).replace([np.inf,-np.inf], np.nan).round(3)
        perf_peak['FF Conversion (Peak)'] = (perf_peak['FF_Acq_Peak'] / perf_peak['Txns']).replace([np.inf,-np.inf], np.nan).fillna(0).round(4)
        def acq_tier_peak(v):
            if pd.isna(v): return 'Low'
            if v >= p75: return 'High'
            if v < p25:  return 'Low'
            return 'Mid'
        perf_peak['Acq_Tier_Peak'] = perf_peak['FF per 100 (Peak)'].apply(acq_tier_peak)
        perf_peak['Recommendation'] = perf_peak.apply(lambda r: coaching(r['Speed_Tier'], r['Acq_Tier_Peak']), axis=1)
    else:
        perf_peak = pd.DataFrame(columns=['Budtender'])

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    excel_out = out_dir / "speed_x_ff_with_peak_and_conversion.xlsx"
    with pd.ExcelWriter(excel_out, engine="xlsxwriter") as writer:
        perf_all[['Budtender','Txns','Avg (mm:ss)','% ≤ 1:30','Speed_Tier','FF_Acquisitions','FF per 100 txns','FF Conversion Rate','Acq_Tier','Recommendation']].to_excel(writer, index=False, sheet_name="Overall")
        if not perf_peak.empty:
            perf_peak[['Budtender','Txns','Avg (mm:ss)','% ≤ 1:30','Speed_Tier','FF_Acq_Peak','FF per 100 (Peak)','FF Conversion (Peak)','Acq_Tier_Peak','Recommendation']].to_excel(writer, index=False, sheet_name="Peak_3to7pm")
        pd.DataFrame({'FF_per_100_p25_overall':[p25], 'FF_per_100_p75_overall':[p75], 'generated_at':[datetime.now()]}).to_excel(writer, index=False, sheet_name="Thresholds")


def row_color(speed_t, acq_t):
    if speed_t == 'Green' and acq_t == 'High': return "#d5f5e3"
    if speed_t == 'Green': return "#e8f8f5"
    if speed_t == 'Yellow' and acq_t == 'High': return "#fcf3cf"
    if speed_t == 'Yellow': return "#fef5e7"
    if speed_t == 'Red': return "#f5b7b1"
    return "#eceff1"

def html_header(title, sub):
    return f'''<!DOCTYPE html><html><head><meta charset="utf-8"><title>{title}</title>
<style>
body {{ font-family: Arial, Helvetica, sans-serif; margin: 24px; color:#111; }}
h1 {{ margin: 0 0 8px 0; font-size: 22px; }}
.sub {{ color:#444; margin-bottom: 14px; }}
table {{ width:100%; border-collapse: collapse; }}
th, td {{ padding:8px 10px; border-bottom:1px solid #e6e6e6; text-align:right; font-size: 13px; }}
th.left, td.left {{ text-align:left; }}
thead th {{ background:#fafafa; position: sticky; top: 0; }}
</style></head><body>
<h1>{title}</h1>
<div class="sub">{sub}</div>
<table><thead>'''

def write_htmls(perf_all, perf_peak, out_dir):
    # Overall
    rows = []
    for _, r in perf_all.sort_values(['Speed_Tier','FF per 100 txns'], ascending=[True, False]).iterrows():
        bg = row_color(r['Speed_Tier'], r['Acq_Tier'])
        rows.append(f'''
<tr style="background:{bg}">
  <td class="left">{r['Budtender']}</td>
  <td>{int(r['Txns'])}</td>
  <td>{r['Avg (mm:ss)']}</td>
  <td>{r['% ≤ 1:30']:.1f}%</td>
  <td>{r['Speed_Tier']}</td>
  <td>{int(r['FF_Acquisitions'])}</td>
  <td>{r['FF per 100 txns']:.3f}</td>
  <td>{r['FF Conversion Rate']:.2%}</td>
  <td>{r['Acq_Tier']}</td>
  <td class="left">{r['Recommendation']}</td>
</tr>''')
    overall_html = html_header(
        "Speed × FF — Overall (Ex-Staff Removed)",
        "Filters: No Delivery, no “TTA Non Stop”, In-Store only when present. Includes **FF Conversion Rate** and **FF per 100 txns**. Eligible = ≥ 30 txns."
    ) + '''
<tr>
<th class="left">Budtender</th><th>Txns</th><th>Avg Time</th><th>% ≤ 1:30</th><th>Speed</th>
<th>FF</th><th>FF / 100</th><th>FF Conversion</th><th>Acq Tier</th><th class="left">Coaching Note</th>
</tr></thead><tbody>''' + "".join(rows) + "\n</tbody></table>\n</body></html>"
    (out_dir / "speed_x_ff_one_sheet_overall_with_conversion.html").write_text(overall_html, encoding="utf-8")

    # Peak
    if not perf_peak.empty:
        rows_pk = []
        for _, r in perf_peak.sort_values(['Speed_Tier','FF per 100 (Peak)'], ascending=[True, False]).iterrows():
            bg = row_color(r['Speed_Tier'], r['Acq_Tier_Peak'])
            rows_pk.append(f'''
<tr style="background:{bg}">
  <td class="left">{r['Budtender']}</td>
  <td>{int(r['Txns'])}</td>
  <td>{r['Avg (mm:ss)']}</td>
  <td>{r['% ≤ 1:30']:.1f}%</td>
  <td>{r['Speed_Tier']}</td>
  <td>{int(r['FF_Acq_Peak'])}</td>
  <td>{r['FF per 100 (Peak)']:.3f}</td>
  <td>{r['FF Conversion (Peak)']:.2%}</td>
  <td>{r['Acq_Tier_Peak']}</td>
  <td class="left">{r['Recommendation']}</td>
</tr>''')
        peak_html = html_header(
            "Speed × FF — Peak 3–7pm",
            "Same filters; hours 15–19 only. Includes **FF Conversion (Peak)**."
        ) + '''
<tr>
<th class="left">Budtender</th><th>Txns</th><th>Avg Time</th><th>% ≤ 1:30</th><th>Speed</th>
<th>FF (Peak)</th><th>FF / 100 (Peak)</th><th>FF Conversion (Peak)</th><th>Acq Tier (Peak)</th><th class="left">Coaching Note</th>
</tr></thead><tbody>''' + "".join(rows_pk) + "\n</tbody></table>\n</body></html>"
        (out_dir / "speed_x_ff_one_sheet_peak_with_conversion.html").write_text(peak_html, encoding="utf-8")

def main():
    parser = argparse.ArgumentParser(description="Generate Speed × Frequent Flyer one-sheets + Excel.")
    parser.add_argument("--tx", default="data/Patient Transaction Time Report.csv", help="Path to transaction time CSV")
    parser.add_argument("--fee-glob", default="data/Fee_*Transactions*.xlsx", help="Glob for fee/donation Excel files")
    parser.add_argument("--exclusions", default="config/exclusions.json", help="JSON file with former_staff list")
    parser.add_argument("--out", default="out", help="Output directory")
    parser.add_argument("--peak-hours", default="15,16,17,18,19", help="Comma separated 24h hours for peak")
    args = parser.parse_args()

    peak_hours = [int(h.strip()) for h in args.peak_hours.split(",") if h.strip().isdigit()]

    # Build datasets and Excel
    tx_csv = args.tx
    fee_glob = args.fee_glob
    exclusions = args.exclusions
    out_dir = Path(args.out)
    # Use helper to build base outputs
    build_views(tx_csv, fee_glob, exclusions, out_dir, peak_hours)

    # Recompute to render HTMLs (keeps functions modular/simple)
    tx = read_tx_csv(Path(tx_csv))
    tx = filter_tx(tx)
    tx['_bt_norm'] = tx['TransactionBy'].apply(normalize_name)
    tx['txn_seconds'] = tx['TransactionTime'] * 60.0
    tx['hour_24'] = tx['TransactionCompleted'].dt.hour if 'TransactionCompleted' in tx.columns else np.nan
    speed_all = build_speed(tx)
    speed_peak = build_speed(tx[tx['hour_24'].isin(peak_hours)]) if 'hour_24' in tx.columns else speed_all.iloc[0:0,:].copy()

    fees = read_fee_glob(fee_glob)
    if not fees.empty and 'Budtender' in fees.columns:
        fees['_bt_norm'] = fees['Budtender'].apply(normalize_name)
    ff_by = build_acq(fees) if not fees.empty else pd.DataFrame(columns=['Budtender','FF_Acquisitions','FF_Fee_Total','FF_First','FF_Last'])

    perf_all = speed_all.merge(ff_by, left_on='TransactionBy', right_on='Budtender', how='left')
    perf_all['Budtender'] = perf_all['TransactionBy']
    perf_all['FF_Acquisitions'] = perf_all['FF_Acquisitions'].fillna(0).astype(int)
    perf_all['FF per 100 txns'] = (perf_all['FF_Acquisitions'] / perf_all['Txns'] * 100.0).replace([np.inf,-np.inf], np.nan).round(3)
    perf_all['FF Conversion Rate'] = (perf_all['FF_Acquisitions'] / perf_all['Txns']).replace([np.inf,-np.inf], np.nan).fillna(0).round(4)
    perf_all, p25, p75 = tier_acq(perf_all)
    perf_all['Recommendation'] = perf_all.apply(lambda r: coaching(r['Speed_Tier'], r['Acq_Tier']), axis=1)

    if not speed_peak.empty:
        perf_peak = speed_peak.merge(ff_by[['Budtender','FF_Acquisitions']], left_on='TransactionBy', right_on='Budtender', how='left')
        if not fees.empty and 'TransactionDate' in fees.columns:
            ff_pk = fees.copy()
            ff_pk['hour_24'] = ff_pk['TransactionDate'].dt.hour
            ff_pk = ff_pk[ff_pk['hour_24'].isin(peak_hours)]
            ff_pk_by = (ff_pk.groupby('Budtender', as_index=False)
                        .agg(FF_Acq_Peak=('ReceiptID','nunique')))
            perf_peak = perf_peak.merge(ff_pk_by, on='Budtender', how='left')
        else:
            perf_peak['FF_Acq_Peak'] = np.nan
        perf_peak['Budtender'] = perf_peak['TransactionBy']
        perf_peak['FF_Acq_Peak'] = perf_peak['FF_Acq_Peak'].fillna(0).astype(int)
        perf_peak['FF per 100 (Peak)'] = (perf_peak['FF_Acq_Peak'] / perf_peak['Txns'] * 100.0).replace([np.inf,-np.inf], np.nan).round(3)
        perf_peak['FF Conversion (Peak)'] = (perf_peak['FF_Acq_Peak'] / perf_peak['Txns']).replace([np.inf,-np.inf], np.nan).fillna(0).round(4)
        def acq_tier_peak(v):
            if pd.isna(v): return 'Low'
            if v >= p75: return 'High'
            if v < p25:  return 'Low'
            return 'Mid'
        perf_peak['Acq_Tier_Peak'] = perf_peak['FF per 100 (Peak)'].apply(acq_tier_peak)
        perf_peak['Recommendation'] = perf_peak.apply(lambda r: coaching(r['Speed_Tier'], r['Acq_Tier_Peak']), axis=1)
    else:
        perf_peak = pd.DataFrame(columns=['Budtender'])

    write_htmls(perf_all, perf_peak, out_dir)
    print("Generated HTML and Excel in", out_dir)

if __name__ == "__main__":
    main()
