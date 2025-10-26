# Budtender Performance — Speed × Frequent Flyer

This repo builds a combined view of **transaction speed** and **Frequent Flyer acquisitions**. Delivery orders and any order marked as **TTA Non Stop** (in OrderSource/OrderType/OrderMethod) are excluded; In-Store is preferred when present.

## How to use
1. Drop your files in `data/`:
   - `Patient Transaction Time Report.csv` (export from POS)
   - `Fee _ Donation Transactions *.xlsx` (all periods)
2. Optional: edit `config/exclusions.json` to remove ex-staff.
3. Run via **GitHub Actions → Generate Speed × FF Reports** or locally:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python scripts/generate.py --tx "data/Patient Transaction Time Report.csv" \
  --fee-glob "data/Fee_*Transactions*.xlsx" \
  --exclusions config/exclusions.json \
  --out out
```

## Output
- `out/speed_x_ff_with_peak_and_conversion.xlsx` — Overall sheet with Speed tier, FF count and tier, simple coaching notes.
- (Optional) HTML one-sheets can be added later; the `index.html` checks for them if you commit them to `out/`.

## Notes
- **Speed target:** ≤ 1:30; **Eligibility:** ≥ 30 txns.
- **Acquisition tiers:** based on team quartiles of `FF per 100 txns` among eligible budtenders.
- **Coaching:** auto-generated from Speed × FF tier.
