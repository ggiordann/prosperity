import concurrent.futures
import pathlib
import re
import subprocess
import textwrap


ROOT = pathlib.Path("/Users/giordanmasen/Desktop/projects/prosperity")
BT = pathlib.Path("/Users/giordanmasen/Library/Caches/rust_backtester/target/debug/rust_backtester")
BT_CWD = ROOT / "prosperity_rust_backtester"
OUT = ROOT / "tmp_backtests" / "z_take_depth"
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


def safe(x):
    return str(x).replace("-", "m").replace(".", "p")


def source(name, mw, i1w, i3w):
    return textwrap.dedent(
        f"""
        from datamodel import Order, TradingState

        C={CONFIGS!r}
        MW={mw!r}; I1W={i1w!r}; I3W={i3w!r}

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
                    micro=((ba*bv1+bb*av1)/den1-mid) if den1 else 0
                    i1=((bv1-av1)/den1) if den1 else 0
                    bv=0; av=0
                    for px in sorted(d.buy_orders, reverse=True)[:3]: bv+=abs(d.buy_orders[px])
                    for px in sorted(d.sell_orders)[:3]: av+=abs(d.sell_orders[px])
                    den=bv+av; i3=((bv-av)/den) if den else 0
                    fair=mean+MW*micro+I1W*sd*i1+I3W*sd*i3
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


def run_variant(params):
    name, mw, i1w, i3w = params
    path = OUT / f"{name}.py"
    path.write_text(source(name, mw, i1w, i3w))
    cmd = [str(BT), "--trader", str(path), "--dataset", "round4", "--products", "summary", "--artifact-mode", "submission", "--run-id", name]
    cp = subprocess.run(cmd, cwd=BT_CWD, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=90)
    txt = cp.stdout
    m = re.search(r"TOTAL\s+-\s+\d+\s+\d+\s+(-?\d+(?:\.\d+)?)", txt)
    total = float(m.group(1)) if m else None
    days = []
    for d in (1, 2, 3):
        m = re.search(rf"D\+{d}\s+{d}\s+\d+\s+\d+\s+(-?\d+(?:\.\d+)?)", txt)
        days.append(float(m.group(1)) if m else None)
    return {"name": name, "mw": mw, "i1w": i1w, "i3w": i3w, "total": total, "d1": days[0], "d2": days[1], "d3": days[2], "rc": cp.returncode, "path": str(path)}


def main():
    params = []
    for i3w in [-1.5, -1, -0.75, -0.5, -0.25, -0.1, 0.1, 0.25, 0.5, 0.75, 1, 1.5]:
        params.append((f"i3_{safe(i3w)}", 0, 0, i3w))
        params.append((f"i1m025_i3_{safe(i3w)}", 0, -0.25, i3w))
    for mw in [0.5, 1, 1.5]:
        for i1w in [-0.25, 0, 0.25]:
            for i3w in [-0.5, -0.25, 0.25, 0.5]:
                params.append((f"mw{safe(mw)}_i1{safe(i1w)}_i3{safe(i3w)}", mw, i1w, i3w))
    rows = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        for row in pool.map(run_variant, params):
            rows.append(row)
            print(row, flush=True)
    rows.sort(key=lambda r: (r["total"] is not None, r["total"] or -10**18), reverse=True)
    (OUT / "summary.csv").write_text(
        "name,mw,i1w,i3w,total,d1,d2,d3,rc,path\n"
        + "\n".join(f"{r['name']},{r['mw']},{r['i1w']},{r['i3w']},{r['total']},{r['d1']},{r['d2']},{r['d3']},{r['rc']},{r['path']}" for r in rows)
        + "\n"
    )
    print("BEST", flush=True)
    for row in rows[:20]:
        print(row, flush=True)


if __name__ == "__main__":
    main()
