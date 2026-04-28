import concurrent.futures
import itertools
import pathlib
import re
import subprocess
import textwrap


ROOT = pathlib.Path("/Users/giordanmasen/Desktop/projects/prosperity")
BT = pathlib.Path("/Users/giordanmasen/Library/Caches/rust_backtester/target/release/rust_backtester")
BT_CWD = ROOT / "prosperity_rust_backtester"
OUT = ROOT / "tmp_backtests" / "z_ml_subsets"
OUT.mkdir(parents=True, exist_ok=True)

PRODUCTS = [
    "HYDROGEL_PACK",
    "VELVETFRUIT_EXTRACT",
    "VEV_4000",
    "VEV_4500",
    "VEV_5000",
    "VEV_5100",
    "VEV_5200",
    "VEV_5300",
    "VEV_5400",
    "VEV_5500",
]


def source(name, ml_products):
    ml = tuple(ml_products)
    z = tuple(p for p in PRODUCTS if p not in ml_products)
    return textwrap.dedent(
        f"""
        import importlib.util,json,sys,datamodel
        from datamodel import Order,TradingState
        MP={ml!r}
        ZP={z!r}
        def load(path,name):
            spec=importlib.util.spec_from_file_location(name,path)
            mod=importlib.util.module_from_spec(spec)
            old=sys.modules.get("datamodel")
            sys.modules["datamodel"]=datamodel
            try: spec.loader.exec_module(mod)
            finally:
                if old is None: sys.modules.pop("datamodel",None)
                else: sys.modules["datamodel"]=old
            return mod.Trader()
        class W:
            def __init__(self,s,t):
                self.traderData=t;self.timestamp=s.timestamp;self.listings=s.listings;self.order_depths=s.order_depths;self.own_trades=s.own_trades;self.market_trades=s.market_trades;self.position=s.position;self.observations=s.observations
        class Trader:
            L={{"HYDROGEL_PACK":200,"VELVETFRUIT_EXTRACT":200,"VEV_4000":300,"VEV_4500":300,"VEV_5000":300,"VEV_5100":300,"VEV_5200":300,"VEV_5300":300,"VEV_5400":300,"VEV_5500":300,"VEV_6000":300,"VEV_6500":300}}
            def __init__(self):
                self.z=load("/Users/giordanmasen/Downloads/z_take.py","z")
                self.m=load("/Users/giordanmasen/Downloads/trader_state_value_submission_100kb_optimized.py","m")
                self.m.T=MP
            def run(self,s:TradingState):
                d={{}}
                if s.traderData:
                    try:d=json.loads(s.traderData)
                    except Exception:d={{}}
                mo,_,mt=self.m.run(W(s,d.get("m","")))
                zo,_,_=self.z.run(s)
                raw={{}}
                for p,o in (mo or {{}}).items():
                    if p in MP: raw[p]=o
                for p,o in (zo or {{}}).items():
                    if p in ZP: raw[p]=o
                out={{}};q={{}}
                for p,os in raw.items():
                    lim=self.L.get(p,20);pos=int(s.position.get(p,0))
                    for a in os:
                        n=int(a.quantity);cur=pos+q.get(p,0)
                        if n>0:n=min(n,lim-cur)
                        elif n<0:n=-min(-n,lim+cur)
                        if n:
                            out.setdefault(p,[]).append(Order(p,int(a.price),n));q[p]=q.get(p,0)+n
                return out,0,json.dumps({{"m":mt}},separators=(",",":"))
        """
    ).strip() + "\n"


def run(mask):
    ml = [p for i, p in enumerate(PRODUCTS) if mask & (1 << i)]
    name = "ml_" + format(mask, "010b")
    path = OUT / f"{name}.py"
    path.write_text(source(name, ml))
    cmd = [
        str(BT),
        "--trader",
        str(path),
        "--dataset",
        "round4",
        "--products",
        "off",
        "--artifact-mode",
        "none",
        "--run-id",
        name,
    ]
    cp = subprocess.run(cmd, cwd=BT_CWD, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=45)
    txt = cp.stdout
    m = re.search(r"TOTAL\\s+-\\s+\\d+\\s+\\d+\\s+(-?\\d+(?:\\.\\d+)?)", txt)
    days = [
        float(x) if x else None
        for x in [
            (re.search(rf"D\\+{d}\\s+{d}\\s+\\d+\\s+\\d+\\s+(-?\\d+(?:\\.\\d+)?)", txt) or [None, None])[1]
            for d in (1, 2, 3)
        ]
    ]
    return {
        "mask": mask,
        "ml": "|".join(ml),
        "total": float(m.group(1)) if m else None,
        "d1": days[0],
        "d2": days[1],
        "d3": days[2],
        "rc": cp.returncode,
        "path": str(path),
    }


def main():
    rows = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        for row in pool.map(run, range(1 << len(PRODUCTS))):
            rows.append(row)
            if row["total"] is not None:
                print(row, flush=True)
    rows.sort(key=lambda r: (r["total"] is not None, r["total"] or -10**18), reverse=True)
    (OUT / "summary.csv").write_text(
        "mask,total,d1,d2,d3,rc,ml,path\n"
        + "\n".join(f"{r['mask']},{r['total']},{r['d1']},{r['d2']},{r['d3']},{r['rc']},{r['ml']},{r['path']}" for r in rows)
        + "\n"
    )
    print("BEST")
    for row in rows[:30]:
        print(row)


if __name__ == "__main__":
    main()
