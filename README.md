
# Budtender Performance — Speed × Frequent Flyer

**How to update**
1. Put your latest files into `data/`:
   - `Patient Transaction Time Report.csv`
   - `Fee _ Donation Transactions *.xlsx` (sheet name `Report`)
2. (Optional) Update `config/exclusions.json` with former staff.
3. Run the GitHub Action **Generate Speed × FF Reports**, or locally:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python scripts/generate.py   --tx "data/Patient Transaction Time Report.csv"   --fee-glob "data/Fee_*Transactions*.xlsx"   --exclusions config/exclusions.json   --peak-hours "15,16,17,18,19"   --out out
```

**Outputs (open in a browser)**  
- `out/speed_x_ff_one_sheet_overall_with_conversion.html`  
- `out/speed_x_ff_one_sheet_peak_with_conversion.html`  
- `out/speed_x_ff_with_peak_and_conversion.xlsx`

**Rules**
- Excludes Deliveries and any order with “TTA Non Stop” in OrderSource/OrderType/OrderMethod.
- If In-Store exists, only In-Store rows are used.
- Speed target ≤ 1:30; eligibility ≥ 30 txns.
- Acq tiers are quartiles of `FF per 100 txns` (overall); applied to Peak too.

