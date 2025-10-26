<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>TTA — Speed × Frequent Flyer Reports</title>
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <style>
    body{font-family:system-ui,-apple-system,Segoe UI,Roboto,Ubuntu,Arial;margin:24px;color:#111}
    h1{margin:0 0 8px 0;font-size:24px}
    .muted{color:#666}
    code{background:#f2f2f2;border:1px solid #e6e6e6;border-radius:6px;padding:2px 6px}
    ul{margin:8px 0 8px 18px}
  </style>
</head>
<body>
  <h1>Speed × FF — In-Store</h1>
  <p class="muted">Drop your latest <code>Patient Transaction Time Report.csv</code> and <code>Fee _ Donation Transactions *.xlsx</code> files into <code>/data</code>, then run the workflow.</p>
  <h2>Outputs</h2>
  <ul>
    <li>Overall: <code>out/speed_x_ff_one_sheet_overall_with_conversion.html</code></li>
    <li>Peak 3–7pm: <code>out/speed_x_ff_one_sheet_peak_with_conversion.html</code></li>
    <li>Workbook: <code>out/speed_x_ff_with_peak_and_conversion.xlsx</code></li>
  </ul>
</body>
</html>
