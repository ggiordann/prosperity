import concurrent.futures
import pathlib
import re
import subprocess
import textwrap


ROOT = pathlib.Path("/Users/giordanmasen/Desktop/projects/prosperity")
BT = pathlib.Path("/Users/giordanmasen/Library/Caches/rust_backtester/target/debug/rust_backtester")
BT_CWD = ROOT / "prosperity_rust_backtester"
OUT = ROOT / "tmp_backtests" / "z_take_product_depth"
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

BASE_I1 = {s: -0.25 for s, *_ in CONFIGS}
BASE_I3 = {s: -1.0 for s, *_ in CONFIGS}


def safe(x):
    return str(x).replace("-", "m").replace(".", "p").replace("_", "")


def source(i1, i3):
    return textwrap.dedent(
        f"""
        from datamodel import Order, TradingState

        C={CONFIGS!r}
        I1={i1!r}
        I3={i3!r}

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

        class Trader:
            def bid(self): return 0
            def run(self, state: TradingState):
                orders={{}}; pos=state.position
                for sym,mean,sd,thr,take,limit in C:
                    d=state.order_depths.get(sym)
                    if not d or not d.buy_orders or not d.sell_orders: continue
                    bb=max(d.buy_orders); ba=min(d.sell_orders); mid=(bb+ba)/2
                    bv1=abs(d.buy_orders[bb]); av1=abs(d.sell_orders[ba]); den1=bv1+av1
                    i1=((bv1-av1)/den1) if den1 else 0
                    bv=0; av=0
                    for px in sorted(d.buy_orders, reverse=True)[:3]: bv+=abs(d.buy_orders[px])
                    for px in sorted(d.sell_orders)[:3]: av+=abs(d.sell_orders[px])
                    den=bv+av; i3=((bv-av)/den) if den else 0
                    fair=mean+I1.get(sym,0)*sd*i1+I3.get(sym,0)*sd*i3
                    z=(mid-fair)/sd if sd>0 else 0
                    if abs(z)<thr: continue
                    p=pos.get(sym,0)
                    if z>0:
                        room=max(0, min(take, limit+p))
                        if room: orders[sym]=walk(d,-1,sym,lambda px, fair=fair: px>=fair,room)
                    else:
                        room=max(0, min(take, limit-p))
                        if room: orders[sym]=walk(d,1,sym,lambda px, fair=fair: px<=fair,room)
                return orders,0,""
        """
    ).strip() + "\n"


def run_variant(args):
    sym, v1, v3 = args
    i1 = dict(BASE_I1)
    i3 = dict(BASE_I3)
    i1[sym] = v1
    i3[sym] = v3
    name = f"{safe(sym)}_i1{safe(v1)}_i3{safe(v3)}"
    path = OUT / f"{name}.py"
    path.write_text(source(i1, i3))
    cmd = [str(BT), "--trader", str(path), "--dataset", "round4", "--products", "summary", "--artifact-mode", "submission", "--run-id", name]
    cp = subprocess.run(cmd, cwd=BT_CWD, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=90)
    txt = cp.stdout
    m = re.search(r"TOTAL\s+-\s+\d+\s+\d+\s+(-?\d+(?:\.\d+)?)", txt)
    total = float(m.group(1)) if m else None
    days = []
    for d in (1, 2, 3):
        m = re.search(rf"D\+{d}\s+{d}\s+\d+\s+\d+\s+(-?\d+(?:\.\d+)?)", txt)
        days.append(float(m.group(1)) if m else None)
    return {"sym": sym, "i1": v1, "i3": v3, "total": total, "d1": days[0], "d2": days[1], "d3": days[2], "rc": cp.returncode, "path": str(path)}


def main():
    params = []
    for sym, *_ in CONFIGS:
        for v1 in [-1.0, -0.75, -0.5, -0.25, 0, 0.25, 0.5]:
            for v3 in [-2.0, -1.5, -1.0, -0.5, 0, 0.5, 1.0]:
                params.append((sym, v1, v3))
    rows = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        for row in pool.map(run_variant, params):
            rows.append(row)
            print(row, flush=True)
    rows.sort(key=lambda r: (r["total"] is not None, r["total"] or -10**18), reverse=True)
    (OUT / "summary.csv").write_text(
        "sym,i1,i3,total,d1,d2,d3,rc,path\n"
        + "\n".join(f"{r['sym']},{r['i1']},{r['i3']},{r['total']},{r['d1']},{r['d2']},{r['d3']},{r['rc']},{r['path']}" for r in rows)
        + "\n"
    )
    print("BEST_OVERALL", flush=True)
    for row in rows[:30]:
        print(row, flush=True)
    print("BEST_BY_PRODUCT", flush=True)
    for sym, *_ in CONFIGS:
        best = max((r for r in rows if r["sym"] == sym and r["total"] is not None), key=lambda r: r["total"])
        print(best, flush=True)


if __name__ == "__main__":
    main()
