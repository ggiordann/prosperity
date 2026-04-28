import concurrent.futures
import pathlib
import re
import subprocess
import textwrap


ROOT = pathlib.Path("/Users/giordanmasen/Desktop/projects/prosperity")
BT = pathlib.Path("/Users/giordanmasen/Library/Caches/rust_backtester/target/debug/rust_backtester")
BT_CWD = ROOT / "prosperity_rust_backtester"
OUT = ROOT / "tmp_backtests" / "z_take_flow"
OUT.mkdir(parents=True, exist_ok=True)

CONFIGS = [
    ("HYDROGEL_PACK", 9994, 32.588, 1.0, 17, 200),
    ("VELVETFRUIT_EXTRACT", 5247, 17.091, 1.0, 17, 200),
    ("VEV_4000", 1247, 17.114, 1.0, 17, 300),
    ("VEV_4500", 747, 17.105, 1.0, 17, 300),
    ("VEV_5000", 252, 16.381, 1.0, 17, 300),
    ("VEV_5100", 163, 15.327, 1.0, 17, 300),
    ("VEV_5200", 91, 12.796, 1.0, 17, 300),
    ("VEV_5300", 43, 8.976, 1.0, 17, 300),
    ("VEV_5400", 14, 4.608, 1.0, 17, 300),
    ("VEV_5500", 6, 2.477, 1.0, 17, 300),
]

WEIGHTS = {
    "core": {"Mark 67": 1.0, "Mark 49": -1.0, "Mark 22": -0.7},
    "broad": {"Mark 67": 1.0, "Mark 49": -1.0, "Mark 22": -0.7, "Mark 14": -0.15, "Mark 01": 0.2, "Mark 55": 0.15},
    "strong": {"Mark 67": 1.5, "Mark 49": -1.5, "Mark 22": -1.0},
}


def safe(x):
    return str(x).replace("-", "m").replace(".", "p")


def source(params):
    name, iw, weights_name, flow_mult, flow_cap, trigger, active_edge, active_qty, active_cap, small_only = params
    return textwrap.dedent(
        f"""
        from datamodel import Order, TradingState

        C={CONFIGS!r}
        IW={iw!r}
        W={WEIGHTS[weights_name]!r}
        FM={flow_mult!r}
        FC={flow_cap!r}
        TR={trigger!r}
        AE={active_edge!r}
        AQ={active_qty!r}
        AC={active_cap!r}
        SO={small_only!r}

        def walk(d,side,sym,ok,n):
            ps=sorted(d.sell_orders) if side>0 else sorted(d.buy_orders, reverse=True)
            b=d.sell_orders if side>0 else d.buy_orders
            out=[]; f=0
            for px in ps:
                if f>=n or not ok(px): break
                q=min(abs(b[px]), n-f)
                if q<=0: break
                out.append(Order(sym, px, side*q)); f+=q
            return out

        def flow(state):
            x=0
            for t in state.market_trades.get("VELVETFRUIT_EXTRACT",[]) or []:
                q=int(t.quantity)
                b=t.buyer or ""; s=t.seller or ""
                if SO:
                    if b=="Mark 67" and 1<=q<=5: x+=q
                    if s=="Mark 67" and 1<=q<=5: x-=q
                    if s=="Mark 22" and 3<=q<=5: x+=q
                    if b=="Mark 22" and 3<=q<=5: x-=q
                    if s=="Mark 49" and 1<=q<=8: x+=q
                    if b=="Mark 49" and 1<=q<=8: x-=q
                else:
                    x+=q*(W.get(b,0)-W.get(s,0))
            return x

        class Trader:
            def bid(self): return 0
            def run(self, state: TradingState):
                orders={{}}
                pos=state.position
                vf=flow(state)
                for sym,mean,sd,thr,take,limit in C:
                    d=state.order_depths.get(sym)
                    if not d or not d.buy_orders or not d.sell_orders: continue
                    bb=max(d.buy_orders); ba=min(d.sell_orders); mid=(bb+ba)/2
                    bv=abs(d.buy_orders[bb]); av=abs(d.sell_orders[ba]); den=bv+av
                    imb=((bv-av)/den) if den else 0
                    fair=mean+IW*sd*imb
                    if sym=="VELVETFRUIT_EXTRACT" and FM:
                        sh=max(-FC,min(FC,FM*vf))
                        fair+=sh
                    z=(mid-fair)/sd if sd>0 else 0
                    if abs(z)<thr: continue
                    p=pos.get(sym,0)
                    if z>0:
                        room=max(0, min(take, limit+p))
                        if room: orders[sym]=walk(d,-1,sym,lambda px, fair=fair: px>=fair,room)
                    else:
                        room=max(0, min(take, limit-p))
                        if room: orders[sym]=walk(d,1,sym,lambda px, fair=fair: px<=fair,room)
                d=state.order_depths.get("VELVETFRUIT_EXTRACT")
                if d and d.buy_orders and d.sell_orders and abs(vf)>=TR:
                    p=pos.get("VELVETFRUIT_EXTRACT",0)
                    if vf>0 and p<AC:
                        px=min(d.sell_orders); q=min(abs(d.sell_orders[px]), AQ, 200-p, AC-p)
                        if q>0 and px<=5247+AE:
                            orders.setdefault("VELVETFRUIT_EXTRACT",[]).append(Order("VELVETFRUIT_EXTRACT",px,q))
                    elif vf<0 and p>-AC:
                        px=max(d.buy_orders); q=min(abs(d.buy_orders[px]), AQ, 200+p, AC+p)
                        if q>0 and px>=5247-AE:
                            orders.setdefault("VELVETFRUIT_EXTRACT",[]).append(Order("VELVETFRUIT_EXTRACT",px,-q))
                return orders,0,""
        """
    ).strip() + "\n"


def run_variant(params):
    name = params[0]
    path = OUT / f"{name}.py"
    path.write_text(source(params))
    cmd = [
        str(BT), "--trader", str(path), "--dataset", "round4", "--products", "summary",
        "--artifact-mode", "submission", "--run-id", name,
    ]
    cp = subprocess.run(cmd, cwd=BT_CWD, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=90)
    txt = cp.stdout
    m = re.search(r"TOTAL\s+-\s+\d+\s+\d+\s+(-?\d+(?:\.\d+)?)", txt)
    total = float(m.group(1)) if m else None
    days = []
    for d in (1, 2, 3):
        m = re.search(rf"D\+{d}\s+{d}\s+\d+\s+\d+\s+(-?\d+(?:\.\d+)?)", txt)
        days.append(float(m.group(1)) if m else None)
    return {
        "name": name,
        "total": total,
        "d1": days[0],
        "d2": days[1],
        "d3": days[2],
        "rc": cp.returncode,
        "path": str(path),
        "params": params[1:],
    }


def main():
    params = []
    for iw in [0, -0.25]:
        for wn in ["core", "broad", "strong"]:
            for fm, fc in [(0, 0), (0.1, 2), (0.25, 4), (0.5, 6), (1.0, 8)]:
                params.append((f"fair_iw{safe(iw)}_{wn}_fm{safe(fm)}_fc{safe(fc)}", iw, wn, fm, fc, 999, 0, 0, 0, False))
    for iw in [0, -0.25]:
        for small in [True, False]:
            for tr in [2, 3, 5, 8]:
                for edge in [2, 4, 6, 8]:
                    params.append((f"act_iw{safe(iw)}_{'small' if small else 'all'}_tr{tr}_e{edge}", iw, "core", 0, 0, tr, edge, 20, 80, small))
    rows = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        for row in pool.map(run_variant, params):
            rows.append(row)
            print(row, flush=True)
    rows.sort(key=lambda r: (r["total"] is not None, r["total"] or -10**18), reverse=True)
    (OUT / "summary.csv").write_text(
        "name,total,d1,d2,d3,rc,path,params\n"
        + "\n".join(f"{r['name']},{r['total']},{r['d1']},{r['d2']},{r['d3']},{r['rc']},{r['path']},{r['params']}" for r in rows)
        + "\n"
    )
    print("BEST", flush=True)
    for row in rows[:20]:
        print(row, flush=True)


if __name__ == "__main__":
    main()
