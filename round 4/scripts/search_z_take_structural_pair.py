from __future__ import annotations

import concurrent.futures
import pathlib
import re
import subprocess
import textwrap


ROOT = pathlib.Path("/Users/giordanmasen/Desktop/projects/prosperity")
BT = pathlib.Path("/Users/giordanmasen/Library/Caches/rust_backtester/target/debug/rust_backtester")
BT_CWD = ROOT / "prosperity_rust_backtester"
OUT = ROOT / "tmp_backtests" / "z_take_structural_pair"
OUT.mkdir(parents=True, exist_ok=True)

CONFIGS = [
    ("HYDROGEL_PACK", 9994, 32.588, 1.0, 17, 2.0, 200),
    ("VELVETFRUIT_EXTRACT", 5247, 17.091, 1.0, 17, 2.0, 200),
    ("VEV_4000", 1247, 17.114, 1.0, 17, 2.0, 300),
    ("VEV_4500", 747, 17.105, 1.0, 17, 2.0, 300),
    ("VEV_5000", 252, 16.381, 1.0, 17, 2.0, 300),
    ("VEV_5100", 163, 15.327, 1.0, 17, 2.0, 300),
    ("VEV_5200", 91, 12.796, 1.0, 17, 2.0, 300),
    ("VEV_5300", 43, 8.976, 1.0, 17, 2.0, 300),
    ("VEV_5400", 14, 4.608, 1.0, 17, 2.0, 300),
    ("VEV_5500", 6, 2.477, 1.0, 17, 2.0, 300),
]

BASE_PAIR = ("VEV_5300", "VEV_5400", -5.688267546997425, 0.44486879297874654, 0.8202267498882495, 2.0, 1, True)
CANDIDATES = [
    ("VELVETFRUIT_EXTRACT", "HYDROGEL_PACK", 7510.880029874439, 0.4727495807097714, 36.9711850780551),
    ("HYDROGEL_PACK", "VELVETFRUIT_EXTRACT", 4535.260620751395, 0.07136983054152737, 14.36498339590434),
    ("VEV_5300", "HYDROGEL_PACK", 9955.510322488064, 0.7790535228043952, 37.36897347488459),
    ("VEV_5100", "HYDROGEL_PACK", 9931.103686667082, 0.3694401207693747, 37.35172184788699),
    ("VEV_5000", "HYDROGEL_PACK", 9877.84322047984, 0.45096156769903445, 37.10907327904687),
    ("VEV_5200", "HYDROGEL_PACK", 9965.9122988353, 0.2748158007904125, 37.53570114146763),
    ("HYDROGEL_PACK", "VEV_5000", -334.325807068465, 0.0588056011689192, 13.40045948907325),
]


def safe(value) -> str:
    return str(value).replace("-", "m").replace(".", "p")


def source(extra_pairs: list[tuple]) -> str:
    pairs = [BASE_PAIR, *extra_pairs]
    return textwrap.dedent(
        f"""
        from datamodel import Order, TradingState

        C={CONFIGS!r}
        P={pairs!r}
        L={{x[0]:x[-1] for x in C}}
        F={{"VELVETFRUIT_EXTRACT":{{"Mark 67":1.0,"Mark 49":-1.0,"Mark 22":-0.65}}}}

        def walk(d,side,sym,ok,n):
            ps=sorted(d.sell_orders) if side>0 else sorted(d.buy_orders, reverse=True)
            book=d.sell_orders if side>0 else d.buy_orders
            out=[]; got=0
            for px in ps:
                if got>=n or not ok(px): break
                q=min(abs(book[px]), n-got)
                if q<=0: break
                out.append(Order(sym, px, side*q)); got+=q
            return out,got

        def avail(d,side,ok):
            ps=sorted(d.sell_orders) if side>0 else sorted(d.buy_orders, reverse=True)
            book=d.sell_orders if side>0 else d.buy_orders
            total=0
            for px in ps:
                if not ok(px): break
                total+=abs(book[px])
            return total

        def pos_room(state,pending,sym,side):
            p=state.position.get(sym,0)+pending.get(sym,0)
            lim=L[sym]
            return max(0,lim-p) if side>0 else max(0,lim+p)

        def add(out,pending,sym,orders):
            if orders:
                out.setdefault(sym,[]).extend(orders)
                pending[sym]=pending.get(sym,0)+sum(o.quantity for o in orders)

        def imb(d):
            b=sum(abs(v) for v in d.buy_orders.values())
            a=sum(abs(v) for v in d.sell_orders.values())
            return (b-a)/(b+a) if b+a else 0.0

        def flow(state,sym):
            m=F.get(sym)
            if not m: return 0.0
            v=0.0
            for t in state.market_trades.get(sym,[]):
                if t.buyer in m: v+=m[t.buyer]*max(1,abs(t.quantity))
                if t.seller in m: v-=m[t.seller]*max(1,abs(t.quantity))
            return max(-1.0,min(1.0,v))

        class Trader:
            def bid(self): return 0
            def run(self,state:TradingState):
                out={{}}; pending={{}}
                for sym,mean,sd,thr,take,ik,lim in C:
                    d=state.order_depths.get(sym)
                    if not d or not d.buy_orders or not d.sell_orders: continue
                    bb=max(d.buy_orders); ba=min(d.sell_orders); mid=(bb+ba)/2
                    fair=mean+(0.15*flow(state,sym) if sym=="VELVETFRUIT_EXTRACT" else 0.0)
                    z=(mid-fair)/sd+ik*imb(d)
                    if abs(z)<thr: continue
                    side=-1 if z>0 else 1
                    room=min(take,pos_room(state,pending,sym,side))
                    if room<=0: continue
                    ok=(lambda px,f=fair: px>=f) if side<0 else (lambda px,f=fair: px<=f)
                    os,_=walk(d,side,sym,ok,room)
                    add(out,pending,sym,os)

                for x,y,a,b,sd,thr,size,strict in P:
                    dx=state.order_depths.get(x); dy=state.order_depths.get(y)
                    if not dx or not dy or not dx.buy_orders or not dx.sell_orders or not dy.buy_orders or not dy.sell_orders: continue
                    xm=(max(dx.buy_orders)+min(dx.sell_orders))/2
                    ym=(max(dy.buy_orders)+min(dy.sell_orders))/2
                    fy=a+b*xm
                    if sd<=0 or b<=0: continue
                    z=(ym-fy)/sd
                    if abs(z)<thr: continue
                    ix=(ym-a)/b
                    if z>0:
                        sy=-1; sx=1
                        oy=(lambda px,f=fy: True if not strict else px>=f)
                        ox=(lambda px,f=ix: True if not strict else px<=f)
                    else:
                        sy=1; sx=-1
                        oy=(lambda px,f=fy: True if not strict else px<=f)
                        ox=(lambda px,f=ix: True if not strict else px>=f)
                    ycap=min(size,pos_room(state,pending,y,sy),avail(dy,sy,oy))
                    xneed=max(1,int(round(b*ycap))) if ycap>0 else 0
                    xcap=min(pos_room(state,pending,x,sx),avail(dx,sx,ox))
                    if ycap<=0 or xneed<=0 or xcap<=0: continue
                    if xneed>xcap:
                        ycap=max(0,int(xcap/b))
                        xneed=max(1,int(round(b*ycap))) if ycap>0 else 0
                    if ycap<=0 or xneed<=0: continue
                    yo,_=walk(dy,sy,y,oy,int(ycap))
                    xo,_=walk(dx,sx,x,ox,int(xneed))
                    add(out,pending,y,yo); add(out,pending,x,xo)
                return out,0,""
        """
    ).strip() + "\n"


def run_variant(params):
    name, pair = params
    path = OUT / f"{name}.py"
    path.write_text(source([pair] if pair else []))
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
    cp = subprocess.run(cmd, cwd=BT_CWD, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=120)
    txt = cp.stdout
    total_match = re.search(r"TOTAL\s+-\s+\d+\s+\d+\s+(-?\d+(?:\.\d+)?)", txt)
    total = float(total_match.group(1)) if total_match else None
    days = []
    for day in (1, 2, 3):
        match = re.search(rf"D\+{day}\s+{day}\s+\d+\s+\d+\s+(-?\d+(?:\.\d+)?)", txt)
        days.append(float(match.group(1)) if match else None)
    return name, total, days[0], days[1], days[2], cp.returncode, str(path), pair


def main() -> None:
    variants = [("base", None)]
    for index, (x, y, alpha, beta, sd) in enumerate(CANDIDATES):
        thresholds = (1.0,) if index == 0 else (1.0, 1.5, 2.0)
        sizes = (1, 2, 3, 5, 8) if index == 0 else (1, 2, 3, 5, 8, 13)
        for threshold in thresholds:
            for size in sizes:
                for strict in (True, False):
                    pair = (x, y, alpha, beta, sd, threshold, size, strict)
                    variants.append((f"{x}_{y}_z{safe(threshold)}_n{size}_s{int(strict)}", pair))
    rows = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        for row in pool.map(run_variant, variants):
            rows.append(row)
            print(row, flush=True)
    rows.sort(key=lambda row: (row[1] is not None, row[1] or -10**18), reverse=True)
    (OUT / "summary.csv").write_text(
        "name,total,d1,d2,d3,rc,path,pair\n"
        + "\n".join(f"{name},{total},{d1},{d2},{d3},{rc},{path},{pair!r}" for name,total,d1,d2,d3,rc,path,pair in rows)
        + "\n"
    )
    print("BEST")
    for row in rows[:40]:
        print(row)


if __name__ == "__main__":
    main()
