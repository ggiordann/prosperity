import concurrent.futures
import pathlib
import re
import subprocess
import textwrap


ROOT = pathlib.Path("/Users/giordanmasen/Desktop/projects/prosperity")
BT = pathlib.Path("/Users/giordanmasen/Library/Caches/rust_backtester/target/debug/rust_backtester")
BT_CWD = ROOT / "prosperity_rust_backtester"
OUT = ROOT / "tmp_backtests" / "premium_reversion"
OUT.mkdir(parents=True, exist_ok=True)

BASE = [
    ("HYDROGEL_PACK", 9994, 32.588, 1.0, 17, 200),
    ("VELVETFRUIT_EXTRACT", 5247, 17.091, 1.0, 17, 200),
]
VEV = [
    ("VEV_4000", 4000, 0.0078, 0.8589, 300),
    ("VEV_4500", 4500, 0.0080, 0.7713, 300),
    ("VEV_5000", 5000, 3.4959, 1.5226, 300),
    ("VEV_5100", 5100, 13.2146, 3.7998, 300),
    ("VEV_5200", 5200, 41.3318, 7.5122, 300),
    ("VEV_5300", 5300, 41.1763, 9.1430, 300),
    ("VEV_5400", 5400, 12.6298, 4.1493, 300),
    ("VEV_5500", 5500, 4.7078, 2.2053, 300),
]


def safe(x):
    return str(x).replace("-", "m").replace(".", "p")


def source(name, alpha, mult, take, use_book):
    return textwrap.dedent(
        f"""
        import json
        from datamodel import Order, TradingState

        B={BASE!r}
        V={VEV!r}
        A={alpha!r}; M={mult!r}; TK={take!r}; UB={use_book!r}
        I1={{"HYDROGEL_PACK":-0.5,"VELVETFRUIT_EXTRACT":0}}
        I3={{"HYDROGEL_PACK":-2.0,"VELVETFRUIT_EXTRACT":-1.0}}

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
            def run(self,state:TradingState):
                try: mem=json.loads(state.traderData) if state.traderData else {{}}
                except Exception: mem={{}}
                orders={{}}; pos=state.position
                for sym,mean,sd,thr,take,limit in B:
                    d=state.order_depths.get(sym)
                    if not d or not d.buy_orders or not d.sell_orders: continue
                    bb=max(d.buy_orders); ba=min(d.sell_orders); mid=(bb+ba)/2
                    fair=mean
                    if UB:
                        bv1=abs(d.buy_orders[bb]); av1=abs(d.sell_orders[ba]); den1=bv1+av1
                        i1=(bv1-av1)/den1 if den1 else 0
                        bv=0; av=0
                        for px in sorted(d.buy_orders,reverse=True)[:3]: bv+=abs(d.buy_orders[px])
                        for px in sorted(d.sell_orders)[:3]: av+=abs(d.sell_orders[px])
                        den=bv+av; i3=(bv-av)/den if den else 0
                        fair+=I1.get(sym,0)*sd*i1+I3.get(sym,0)*sd*i3
                    z=(mid-fair)/sd
                    if abs(z)<thr: continue
                    p=pos.get(sym,0)
                    if z>0:
                        room=max(0,min(take,limit+p))
                        if room: orders[sym]=walk(d,-1,sym,lambda px,fair=fair:px>=fair,room)
                    else:
                        room=max(0,min(take,limit-p))
                        if room: orders[sym]=walk(d,1,sym,lambda px,fair=fair:px<=fair,room)
                ud=state.order_depths.get("VELVETFRUIT_EXTRACT")
                if ud and ud.buy_orders and ud.sell_orders:
                    u=(max(ud.buy_orders)+min(ud.sell_orders))/2
                    for sym,k,pm,psd,limit in V:
                        d=state.order_depths.get(sym)
                        if not d or not d.buy_orders or not d.sell_orders: continue
                        bb=max(d.buy_orders); ba=min(d.sell_orders); mid=(bb+ba)/2
                        intr=max(u-k,0)
                        prem=mid-intr
                        old=mem.get(sym,pm)
                        fair=intr+old
                        th=max(1.0,M*psd)
                        p=pos.get(sym,0)
                        if mid>fair+th:
                            room=max(0,min(TK,limit+p))
                            if room: orders[sym]=walk(d,-1,sym,lambda px,fair=fair:px>=fair,room)
                        elif mid<fair-th:
                            room=max(0,min(TK,limit-p))
                            if room: orders[sym]=walk(d,1,sym,lambda px,fair=fair:px<=fair,room)
                        mem[sym]=(1-A)*old+A*prem
                return orders,0,json.dumps(mem,separators=(",",":"))
        """
    ).strip() + "\n"


def run_variant(params):
    name, alpha, mult, take, use_book = params
    path = OUT / f"{name}.py"
    path.write_text(source(name, alpha, mult, take, use_book))
    cmd = [str(BT), "--trader", str(path), "--dataset", "round4", "--products", "summary", "--artifact-mode", "submission", "--run-id", name]
    cp = subprocess.run(cmd, cwd=BT_CWD, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=100)
    txt = cp.stdout
    m = re.search(r"TOTAL\s+-\s+\d+\s+\d+\s+(-?\d+(?:\.\d+)?)", txt)
    total = float(m.group(1)) if m else None
    days = []
    for d in (1,2,3):
        m = re.search(rf"D\+{d}\s+{d}\s+\d+\s+\d+\s+(-?\d+(?:\.\d+)?)", txt)
        days.append(float(m.group(1)) if m else None)
    return {"name":name,"alpha":alpha,"mult":mult,"take":take,"book":use_book,"total":total,"d1":days[0],"d2":days[1],"d3":days[2],"rc":cp.returncode,"path":str(path)}


def main():
    params=[]
    for book in [False, True]:
        for alpha in [0.005,0.01,0.02,0.05,0.1]:
            for mult in [0.25,0.5,0.75,1.0,1.25,1.5]:
                for take in [10,17,30]:
                    params.append((f"prem_b{int(book)}_a{safe(alpha)}_m{safe(mult)}_t{take}",alpha,mult,take,book))
    rows=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        for row in pool.map(run_variant, params):
            rows.append(row); print(row, flush=True)
    rows.sort(key=lambda r:(r["total"] is not None,r["total"] or -10**18), reverse=True)
    (OUT/"summary.csv").write_text("name,alpha,mult,take,book,total,d1,d2,d3,rc,path\n"+"\n".join(f"{r['name']},{r['alpha']},{r['mult']},{r['take']},{r['book']},{r['total']},{r['d1']},{r['d2']},{r['d3']},{r['rc']},{r['path']}" for r in rows)+"\n")
    print("BEST", flush=True)
    for row in rows[:30]: print(row, flush=True)


if __name__=="__main__":
    main()
