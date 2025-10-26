# Budtender Performance — Speed × Frequent Flyer

Generate color-coded performance reports for budtenders combining **transaction speed** and **Frequent Flyer acquisitions**.

**Filters**: excludes **Delivery** and any order with **"TTA Non Stop"** in OrderSource/OrderType/OrderMethod. If `OrderType` includes *In-Store*, only In-Store rows are used.

## Files to drop in your repo
- `index.html` — clean landing page with quick checks and links.
- `.github/workflows/generate.yml` — GitHub Actions workflow to run on demand or when data files change.
- `scripts/generate.py` — generator (speed tiers, FF acquisitions, conversion, peak slice, coaching notes).
- `config/exclusions.json` — ex-staff list (edit as needed).
- `requirements.txt` — dependencies for the Action and local runs.
- `data/.keep`, `out/.keep` — placeholders to keep folders in git.
- `.gitignore` — ignore raw data/outputs by default.

## How to run (GitHub UI — no local setup)
1. Upload your data into `data/`:
   - `Patient Transaction Time Report.csv` (transaction-time export; `TransactionTime` is minutes)
   - All `Fee _ Donation Transactions *.xlsx` (sheet name `Report`)
2. (Optional) Update `config/exclusions.json` with former staff.
3. Go to **Actions → "Generate Speed × FF Reports" → Run workflow** (or just commit files to `data/` to auto-run).
4. Download the artifact `speed-ff-reports` with:
   - `speed_x_ff_with_peak_and_conversion.xlsx`
   - `one_sheet_overall.html`
   - `one_sheet_peak.html`

## Local run
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python scripts/generate.py   --tx "data/Patient Transaction Time Report.csv"   --fee-glob "data/Fee_*Transactions*.xlsx"   --exclusions config/exclusions.json   --peak-hours "15,16,17,18,19"   --out out
```

## Rules & thresholds
- **Speed target**: ≤ **1:30** (90s). **Eligible** if **≥ 30** transactions.
- **FF detection**: `FeeDonationName` contains "frequent flyer" (case-insensitive).
- **Acquisition tiers**: High/Mid/Low from team quartiles of `FF per 100 txns` among eligible budtenders.
- **Coaching notes**: adapt to the Speed (Green/Yellow/Red/Gray) × Acquisition (High/Mid/Low) combo.
- **Peak view**: defaults to 3–7pm; override via workflow input `peak_hours` or CLI `--peak-hours`.

> Notes: The script excludes Deliveries and any row that includes "TTA Non Stop" in `OrderSource`, `OrderType`, or `OrderMethod`. If `TransactionCompleted` exists, peak hours use that timestamp; if the fee files have `TransactionDate`, peak acquisition is sliced by that as well.
