from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "research" / "round5" / "pebbles" / "generated_traders"

P = ("PEBBLES_XS", "PEBBLES_S", "PEBBLES_M", "PEBBLES_L", "PEBBLES_XL")
M = {
    "PEBBLES_XS": 7404.64,
    "PEBBLES_S": 8932.357,
    "PEBBLES_M": 10263.243,
    "PEBBLES_L": 10174.111,
    "PEBBLES_XL": 13225.589,
}
SHIFT = {"PEBBLES_XS": -1014.683, "PEBBLES_S": 1.0, "PEBBLES_M": -17.195, "PEBBLES_L": -31.117}
MODE = {"PEBBLES_XS": "static", "PEBBLES_S": "mid", "PEBBLES_M": "static", "PEBBLES_L": "static", "PEBBLES_XL": "static"}
Z = {"PEBBLES_XS": 0.35, "PEBBLES_S": 0.0, "PEBBLES_M": 0.15, "PEBBLES_L": 0.35, "PEBBLES_XL": 0.35}
S = {"PEBBLES_XS": 1449.547, "PEBBLES_S": 833.282, "PEBBLES_M": 687.817, "PEBBLES_L": 622.332, "PEBBLES_XL": 1776.546}
EDGE = {"PEBBLES_XS": 2.0, "PEBBLES_S": 3.0, "PEBBLES_M": 20.0, "PEBBLES_L": 0.0, "PEBBLES_XL": 0.0}
IMP = {"PEBBLES_XS": 0, "PEBBLES_S": 1, "PEBBLES_M": 4, "PEBBLES_L": 1, "PEBBLES_XL": 0}
BASE_SIG = {
    "PEBBLES_XS": (("PEBBLES_XL", 200, 0.1), ("PEBBLES_XL", 500, 0.25)),
    "PEBBLES_S": (("PEBBLES_XS", 500, 0.1), ("PEBBLES_L", 10, -0.1)),
    "PEBBLES_M": (("PEBBLES_XS", 200, -0.05), ("PEBBLES_XL", 200, 0.5)),
    "PEBBLES_L": (("PEBBLES_S", 500, 0.5), ("PEBBLES_XL", 5, 0.5)),
    "PEBBLES_XL": (("PEBBLES_M", 20, -1.0), ("PEBBLES_M", 500, -0.1)),
}


TEMPLATE = '''from datamodel import Order, OrderDepth, TradingState
from typing import Dict, List
import json
P={P!r}
M={M!r}
SHIFT={SHIFT!r}
MODE={MODE!r}
Z={Z!r}
S={S!r}
EDGE={EDGE!r}
IMP={IMP!r}
WALK={WALK!r}
SIG={SIG!r}
CURVE_K={CURVE_K!r}
LINE_K={LINE_K!r}
BFLY_K={BFLY_K!r}
class Trader:
 L=10;Q=20
 def run(self,state:TradingState):
  out:Dict[str,List[Order]]={{}}
  try:h=json.loads(state.traderData) if state.traderData else {{}}
  except Exception:h={{}}
  mids={{}}
  for p in P:
   d=state.order_depths.get(p)
   if d and d.buy_orders and d.sell_orders:
    mids[p]=(max(d.buy_orders)+min(d.sell_orders))/2
    a=h.get(p,[]);a.append(mids[p]);h[p]=a[-501:]
  curve=0
  fits={{}}
  if len(mids)==5:
   curve=50000-sum(mids[p] for p in P)
   if LINE_K:
    ys=[mids[p] for p in P];avg=sum(ys)/5;sl=sum((i-2)*(ys[i]-avg) for i in range(5))/10
    for i,p in enumerate(P):fits[p]=avg+sl*(i-2)
  for p in P:
   d=state.order_depths.get(p)
   if not d or not d.buy_orders or not d.sell_orders:
    out[p]=[];continue
   if MODE[p]=='mid':
    fair=mids.get(p,0)+SHIFT.get(p,0);take=10**9
   else:
    fair=M[p]+SHIFT.get(p,0);take=Z[p]*S[p]
   if CURVE_K and len(mids)==5:fair+=CURVE_K*curve
   if LINE_K and p in fits:fair-=LINE_K*(mids[p]-fits[p])
   if BFLY_K and len(mids)==5 and p=='PEBBLES_M':fair+=BFLY_K*((mids['PEBBLES_S']+mids['PEBBLES_L'])/2-mids['PEBBLES_M'])
   for lp,lag,k in SIG.get(p,()):
    a=h.get(lp,[])
    if len(a)>lag:fair+=k*(a[-1]-a[-1-lag])
   out[p]=self.tr(p,d,int(state.position.get(p,0)),fair,take,EDGE[p],IMP[p])
  return out,0,json.dumps(h,separators=(',',':'))
 def tr(self,p,d,pos,fair,take,edge,imp):
  bb=max(d.buy_orders);ba=min(d.sell_orders);bc=max(0,self.L-pos);sc=max(0,self.L+pos);out=[]
  if p in WALK and bc>0:
   for px in sorted(d.sell_orders):
    if px>fair-take or bc<=0:break
    q=min(bc,self.Q,-int(d.sell_orders[px]))
    if q>0:out.append(Order(p,px,q));bc-=q
  elif bc>0 and ba<=fair-take:
   q=min(bc,self.Q,-int(d.sell_orders[ba]))
   if q>0:out.append(Order(p,ba,q));bc-=q
  if p in WALK and sc>0:
   for px in sorted(d.buy_orders,reverse=True):
    if px<fair+take or sc<=0:break
    q=min(sc,self.Q,int(d.buy_orders[px]))
    if q>0:out.append(Order(p,px,-q));sc-=q
  elif sc>0 and bb>=fair+take:
   q=min(sc,self.Q,int(d.buy_orders[bb]))
   if q>0:out.append(Order(p,bb,-q));sc-=q
  if ba-bb>2*imp:bid,ask=bb+imp,ba-imp
  elif ba-bb>1:bid,ask=bb+1,ba-1
  else:bid,ask=bb,ba
  if bc>0 and bid<=fair-edge:out.append(Order(p,bid,min(self.Q,bc)))
  if sc>0 and ask>=fair+edge:out.append(Order(p,ask,-min(self.Q,sc)))
  return out
'''


def scaled_sig(scale: float, extra: dict[str, tuple[tuple[str, int, float], ...]] | None = None) -> dict[str, tuple[tuple[str, int, float], ...]]:
    sig = {p: tuple((leader, lag, round(coeff * scale, 6)) for leader, lag, coeff in edges) for p, edges in BASE_SIG.items()}
    if extra:
        for product, edges in extra.items():
            sig[product] = sig.get(product, ()) + edges
    return sig


def product_scaled_sig(product: str, scale: float) -> dict[str, tuple[tuple[str, int, float], ...]]:
    sig = dict(BASE_SIG)
    sig[product] = tuple((leader, lag, round(coeff * scale, 6)) for leader, lag, coeff in BASE_SIG[product])
    return sig


def dropped_sig(product: str, index: int) -> dict[str, tuple[tuple[str, int, float], ...]]:
    sig = dict(BASE_SIG)
    sig[product] = tuple(edge for i, edge in enumerate(BASE_SIG[product]) if i != index)
    return sig


def write_variant(name: str, *, mode=None, shift=None, z=None, edge=None, imp=None, walk=None, sig=None, curve=0.0, line=0.0, bfly=0.0) -> dict:
    path = OUT / f"{name}.py"
    text = TEMPLATE.format(
        P=P,
        M=M,
        SHIFT=shift if shift is not None else SHIFT,
        MODE=mode if mode is not None else MODE,
        Z=z if z is not None else Z,
        S=S,
        EDGE=edge if edge is not None else EDGE,
        IMP=imp if imp is not None else IMP,
        WALK=walk if walk is not None else {"PEBBLES_M"},
        SIG=sig if sig is not None else BASE_SIG,
        CURVE_K=curve,
        LINE_K=line,
        BFLY_K=bfly,
    )
    path.write_text(text)
    return {"name": name, "path": str(path.relative_to(ROOT))}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    specs = []
    specs.append(write_variant("mm_mid_e2", mode={p: "mid" for p in P}, shift={p: 0 for p in P}, z={p: 0 for p in P}, edge={p: 2 for p in P}, imp={p: 1 for p in P}, walk=set(), sig={}))
    specs.append(write_variant("static_no_lead", sig={}))
    for scale in [0.5, 0.75, 1.0, 1.15, 1.25, 1.5]:
        specs.append(write_variant(f"lead_s{str(scale).replace('.', 'p')}", sig=scaled_sig(scale)))
    specs.append(write_variant("lead_s1p0_edge075", edge={p: round(v * 0.75, 3) for p, v in EDGE.items()}, sig=scaled_sig(1.0)))
    specs.append(write_variant("lead_s1p0_edge125", edge={p: round(v * 1.25, 3) for p, v in EDGE.items()}, sig=scaled_sig(1.0)))
    specs.append(write_variant("lead_s1p0_take08", z={p: round(v * 0.8, 3) for p, v in Z.items()}, sig=scaled_sig(1.0)))
    specs.append(write_variant("lead_s1p0_take12", z={p: round(v * 1.2, 3) for p, v in Z.items()}, sig=scaled_sig(1.0)))
    specs.append(write_variant("curve_sum", sig={}, curve=1.0))
    specs.append(write_variant("curve_line025", sig={}, line=0.25))
    specs.append(write_variant("curve_line050", sig={}, line=0.5))
    specs.append(write_variant("butterfly_m025", sig={}, bfly=0.25))
    specs.append(write_variant("lead_plus_line025", sig=scaled_sig(1.0), line=0.25))
    specs.append(write_variant("lead_plus_mlag", sig=scaled_sig(1.0, {"PEBBLES_M": (("PEBBLES_XL", 150, 0.35), ("PEBBLES_L", 100, -0.2)), "PEBBLES_L": (("PEBBLES_M", 15, 0.1),)})))
    for product, edges in BASE_SIG.items():
        for idx in range(len(edges)):
            specs.append(write_variant(f"drop_{product.lower()}_{idx}", sig=dropped_sig(product, idx)))
    for product in BASE_SIG:
        for scale in (0.75, 1.25):
            specs.append(write_variant(f"pscale_{product.lower()}_{str(scale).replace('.', 'p')}", sig=product_scaled_sig(product, scale)))
    for product in ("PEBBLES_XS", "PEBBLES_M", "PEBBLES_L", "PEBBLES_XL"):
        for delta in (-75, -25, 25, 75):
            shift = dict(SHIFT)
            shift[product] = round(shift.get(product, 0.0) + delta, 3)
            specs.append(write_variant(f"shift_{product.lower()}_{delta:+d}".replace("+", "p").replace("-", "m"), shift=shift, sig=scaled_sig(1.0)))
    edge_tests = {
        "edge_xs0": {"PEBBLES_XS": 0.0},
        "edge_xs4": {"PEBBLES_XS": 4.0},
        "edge_s1": {"PEBBLES_S": 1.0},
        "edge_s5": {"PEBBLES_S": 5.0},
        "edge_m10": {"PEBBLES_M": 10.0},
        "edge_m30": {"PEBBLES_M": 30.0},
        "edge_l2": {"PEBBLES_L": 2.0},
        "edge_xl2": {"PEBBLES_XL": 2.0},
    }
    for name, override in edge_tests.items():
        edge = dict(EDGE)
        edge.update(override)
        specs.append(write_variant(name, edge=edge, sig=scaled_sig(1.0)))
    (OUT / "manifest.json").write_text(json.dumps(specs, indent=2))
    print(f"wrote {len(specs)} variants to {OUT}")


if __name__ == "__main__":
    main()
