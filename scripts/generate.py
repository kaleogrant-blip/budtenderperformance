import argparse, pandas as pd, numpy as np, json, glob, os

TARGET=90; MIN_TX=30

def build(tx_csv, fee_glob, exclusions, out_dir):
    tx=pd.read_csv(tx_csv)
    tx['TransactionTime']=pd.to_numeric(tx.get('TransactionTime'), errors='coerce')
    tx['sec']=tx['TransactionTime']*60
    for c in ['OrderType','OrderSource','OrderMethod','TransactionBy']:
        if c in tx: tx[c]=tx[c].astype(str)
    is_deliv=tx['OrderType'].str.contains('Delivery', case=False, na=False) if 'OrderType' in tx else False
    is_ns = False
    for c in ['OrderType','OrderSource','OrderMethod']:
        if c in tx: is_ns = is_ns | (tx[c].str.contains('non',case=False,na=False)&tx[c].str.contains('stop',case=False,na=False))
    tx=tx.loc[~is_deliv & ~is_ns].copy()
    if 'OrderType' in tx and tx['OrderType'].str.contains('In-Store',case=False,na=False).any():
        tx=tx[tx['OrderType'].str.contains('In-Store',case=False,na=False)]
    ex=[]
    if exclusions and os.path.exists(exclusions): ex=[s.strip().lower() for s in json.load(open(exclusions))['former_staff']]
    tx['_bt']=tx['TransactionBy'].str.strip().str.lower()
    if ex: tx=tx[~tx['_bt'].isin(ex)]
    sp=tx.groupby('TransactionBy',as_index=False).agg(Txns=('sec','size'),avg=('sec','mean'),hit=('sec',lambda x:(x<=TARGET).mean()*100))
    def tier(r):
        if r.Txns<MIN_TX: return 'Gray'
        if r.avg<=90 or r.hit>=70: return 'Green'
        if r.avg<=120 or r.hit>=50: return 'Yellow'
        return 'Red'
    sp['Speed_Tier']=sp.apply(tier,axis=1)
    # fees
    parts=[pd.read_excel(p, sheet_name='Report') for p in glob.glob(fee_glob)] or [pd.DataFrame(columns=['ReceiptID','FeeDonationName','Budtender'])]
    fees=pd.concat(parts, ignore_index=True)
    ff=fees[fees['FeeDonationName'].astype(str).str.contains('frequent flyer',case=False,na=False)] if not fees.empty else fees
    acq=ff.groupby('Budtender',as_index=False).agg(FF_Acquisitions=('ReceiptID','nunique')) if not ff.empty else pd.DataFrame(columns=['Budtender','FF_Acquisitions'])
    perf=sp.merge(acq, left_on='TransactionBy', right_on='Budtender', how='left')
    perf['Budtender']=perf['TransactionBy']; perf['FF_Acquisitions']=perf['FF_Acquisitions'].fillna(0).astype(int)
    perf['FF per 100 txns']=(perf['FF_Acquisitions']/perf['Txns']*100).replace([np.inf,-np.inf],np.nan).round(3)
    elig=perf[perf['Txns']>=MIN_TX]
    p25=0 if elig.empty else float(elig['FF per 100 txns'].quantile(0.25)); p75=0 if elig.empty else float(elig['FF per 100 txns'].quantile(0.75))
    def at(v):
        if np.isnan(v): return 'Low'
        if v>=p75: return 'High'
        if v<p25: return 'Low'
        return 'Mid'
    perf['Acq_Tier']=perf['FF per 100 txns'].apply(at)
    def coach(a,b):
        if a=='Green' and b=='High': return 'Exceeds; keep speed + enroll.'
        if a=='Green' and b!='High': return 'Fast; raise FF asks.'
        if a=='Yellow' and b=='High': return 'Quality; trim 10–20s.'
        if a=='Yellow' and b!='High': return 'Middle; 2 speed fixes.'
        if a=='Red' and b=='High': return 'Converting but slow.'
        if a=='Red' and b!='High': return 'Under target; 2-week plan.'
        return 'Monitor.'
    perf['Recommendation']=[coach(a,b) for a,b in zip(perf['Speed_Tier'],perf['Acq_Tier'])]
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    x=Path(out_dir)/'speed_x_ff_with_peak_and_conversion.xlsx'
    with pd.ExcelWriter(x, engine='xlsxwriter') as w:
        perf[['Budtender','Txns','avg','hit','Speed_Tier','FF_Acquisitions','FF per 100 txns','Acq_Tier','Recommendation']].to_excel(w,index=False,sheet_name='Overall')
    return str(x)

if __name__=='__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('--tx',default='data/Patient Transaction Time Report.csv'); ap.add_argument('--fee-glob',default='data/Fee_*Transactions*.xlsx'); ap.add_argument('--exclusions',default='config/exclusions.json'); ap.add_argument('--out',default='out'); a=ap.parse_args(); print(build(a.tx,a.fee_glob,a.exclusions,a.out))
