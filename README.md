# Speed × Frequent Flyer (In-Store)

Generate color-coded performance reports for budtenders combining **transaction speed** and **Frequent Flyer acquisitions**.
Filters applied: **exclude Delivery** and any order with **"TTA Non Stop"** in OrderSource/OrderType/OrderMethod.

## Quick start (GitHub UI — no local dev)
1. Create a new GitHub repo (Public or Private). Suggested name: `tta-speed-ff-matrix`.
2. Upload all files from this package to the repo root (keep folders intact).
3. Upload data to the `data/` folder:
   - `Patient Transaction Time Report.csv` (transaction-time export)
   - All fee/donation Excel files (e.g., `Fee _ Donation Transactions 1_1_2025-3_31_2025.xlsx`, etc.)
4. (Optional) Update `config/exclusions.json` with ex-staff.
5. Go to **Actions → "Generate Speed × FF Reports" → Run workflow** (or commit files to `data/` to auto-run).
6. Download the **artifact** named `speed-ff-reports` — it contains `speed_x_ff_with_peak_and_conversion.xlsx`, `one_sheet_overall.html`, `one_sheet_peak.html`.

## Local run
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python scripts/generate.py --tx "data/Patient Transaction Time Report.csv" --fee-glob "data/Fee_*Transactions*.xlsx" --exclusions config/exclusions.json --peak-hours "15,16,17,18,19" --out out
```

## Inputs & rules
- Speed target: ≤ **1:30** (90s). Eligible if **≥ 30** txns.
- In-Store only when present; excludes Delivery and "TTA Non Stop".
- Frequent Flyer acquisition rows are detected when `FeeDonationName` contains "frequent flyer" (case-insensitive).
- Tiers: Speed (Green/Yellow/Red/Gray), Acquisition (High/Mid/Low by team quartiles).
- Coaching note adapts to the combination of Speed and Acquisition tiers.

## Customize
- Add/remove names in `config/exclusions.json` (former staff).
- Change peak hours via workflow inputs or CLI `--peak-hours` (default `15,16,17,18,19`).

## Outputs
- Excel: Overall & Peak sheets with metrics and recommendations.
- HTML one-sheets: Color-coded tables you can print or share.
