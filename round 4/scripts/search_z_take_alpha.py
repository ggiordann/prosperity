import concurrent.futures
import pathlib
import re
import subprocess
import textwrap


ROOT = pathlib.Path("/Users/giordanmasen/Desktop/projects/prosperity")
BT = pathlib.Path("/Users/giordanmasen/Library/Caches/rust_backtester/target/debug/rust_backtester")
BT_CWD = ROOT / "prosperity_rust_backtester"
OUT = ROOT / "tmp_backtests" / "z_take_alpha"
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


def source(name, micro_weight, imb_weight, filter_threshold, take_size):
    cfg = [(s, m, sd, th, take_size if take_size is not None else ts, lim) for s, m, sd, th, ts, lim in CONFIGS]
    return textwrap.dedent(
        f"""
        from datamodel import Order, TradingState

        C={cfg!r}
        MW={micro_weight!r}
        IW={imb_weight!r}
        FT={filter_threshold!r}

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
                orders={{}}
                pos=state.position
                for sym,mean,sd,thr,take,limit in C:
                    d=state.order_depths.get(sym)
                    if not d or not d.buy_orders or not d.sell_orders: continue
                    bb=max(d.buy_orders); ba=min(d.sell_orders); mid=(bb+ba)/2
                    bv=abs(d.buy_orders[bb]); av=abs(d.sell_orders[ba]); den=bv+av
                    micro=((ba*bv+bb*av)/den-mid) if den else 0
                    imb=((bv-av)/den) if den else 0
                    fair=mean+MW*micro+IW*sd*imb
                    z=(mid-fair)/sd if sd>0 else 0
                    if abs(z)<thr: continue
                    p=pos.get(sym,0)
                    if z>0:
                        if FT is not None and micro>FT: continue
                        room=max(0, min(take, limit+p))
                        if room: orders[sym]=walk(d,-1,sym,lambda px, fair=fair: px>=fair,room)
                    else:
                        if FT is not None and micro<-FT: continue
                        room=max(0, min(take, limit-p))
                        if room: orders[sym]=walk(d,1,sym,lambda px, fair=fair: px<=fair,room)
                return orders,0,""
        """
    ).strip() + "\n"


def run_variant(params):
    name, mw, iw, ft, take = params
    path = OUT / f"{name}.py"
    path.write_text(source(name, mw, iw, ft, take))
    cmd = [
        str(BT),
        "--trader",
        str(path),
        "--dataset",
        "round4",
        "--products",
        "summary",
        "--artifact-mode",
        "submission",
        "--run-id",
        name,
    ]
    cp = subprocess.run(cmd, cwd=BT_CWD, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=90)
    txt = cp.stdout
    total = None
    days = []
    m = re.search(r"TOTAL\s+-\s+\d+\s+\d+\s+(-?\d+(?:\.\d+)?)", txt)
    if m:
        total = float(m.group(1))
    for d in (1, 2, 3):
        m = re.search(rf"D\+{d}\s+{d}\s+\d+\s+\d+\s+(-?\d+(?:\.\d+)?)", txt)
        days.append(float(m.group(1)) if m else None)
    return {
        "name": name,
        "mw": mw,
        "iw": iw,
        "ft": ft,
        "take": take,
        "total": total,
        "d1": days[0],
        "d2": days[1],
        "d3": days[2],
        "rc": cp.returncode,
        "path": str(path),
    }


def main():
    params = []
    for mw in [0, 0.5, 1, 1.5, 2, 3, 4, 6]:
        params.append((f"mw_{safe(mw)}", mw, 0, None, None))
    for iw in [-0.5, -0.25, -0.1, 0.1, 0.25, 0.5, 0.75, 1.0]:
        params.append((f"iw_{safe(iw)}", 0, iw, None, None))
    for mw in [0.5, 1, 1.5, 2]:
        for iw in [-0.25, -0.1, 0.1, 0.25]:
            params.append((f"mix_mw{safe(mw)}_iw{safe(iw)}", mw, iw, None, None))
    for ft in [0, 0.25, 0.5, 1.0, 2.0]:
        params.append((f"filter_{safe(ft)}", 0, 0, ft, None))
    for take in [8, 12, 17, 24, 32]:
        params.append((f"take_{take}", 0, 0, None, take))

    rows = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        for row in pool.map(run_variant, params):
            rows.append(row)
            print(row, flush=True)
    rows.sort(key=lambda r: (r["total"] is not None, r["total"] or -10**18), reverse=True)
    out_csv = OUT / "summary.csv"
    out_csv.write_text(
        "name,mw,iw,ft,take,total,d1,d2,d3,rc,path\n"
        + "\n".join(
            f"{r['name']},{r['mw']},{r['iw']},{r['ft']},{r['take']},{r['total']},{r['d1']},{r['d2']},{r['d3']},{r['rc']},{r['path']}"
            for r in rows
        )
        + "\n"
    )
    print("BEST", flush=True)
    for row in rows[:20]:
        print(row, flush=True)


if __name__ == "__main__":
    main()
