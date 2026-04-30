from datamodel import Order, OrderDepth, TradingState
from typing import Dict, List
import json
P=('PEBBLES_XS', 'PEBBLES_S', 'PEBBLES_M', 'PEBBLES_L', 'PEBBLES_XL')
M={'PEBBLES_XS': 7404.64, 'PEBBLES_S': 8932.357, 'PEBBLES_M': 10263.243, 'PEBBLES_L': 10174.111, 'PEBBLES_XL': 13225.589}
SHIFT={'PEBBLES_XS': -1014.683, 'PEBBLES_S': 1.0, 'PEBBLES_M': -17.195, 'PEBBLES_L': -31.117}
MODE={'PEBBLES_XS': 'static', 'PEBBLES_S': 'mid', 'PEBBLES_M': 'static', 'PEBBLES_L': 'static', 'PEBBLES_XL': 'static'}
Z={'PEBBLES_XS': 0.35, 'PEBBLES_S': 0.0, 'PEBBLES_M': 0.15, 'PEBBLES_L': 0.35, 'PEBBLES_XL': 0.35}
S={'PEBBLES_XS': 1449.547, 'PEBBLES_S': 833.282, 'PEBBLES_M': 687.817, 'PEBBLES_L': 622.332, 'PEBBLES_XL': 1776.546}
EDGE={'PEBBLES_XS': 1.5, 'PEBBLES_S': 2.25, 'PEBBLES_M': 15.0, 'PEBBLES_L': 0.0, 'PEBBLES_XL': 0.0}
IMP={'PEBBLES_XS': 0, 'PEBBLES_S': 1, 'PEBBLES_M': 4, 'PEBBLES_L': 1, 'PEBBLES_XL': 0}
WALK={'PEBBLES_M'}
SIG={'PEBBLES_XS': (('PEBBLES_XL', 200, 0.1), ('PEBBLES_XL', 500, 0.25)), 'PEBBLES_S': (('PEBBLES_XS', 500, 0.1), ('PEBBLES_L', 10, -0.1)), 'PEBBLES_M': (('PEBBLES_XS', 200, -0.05), ('PEBBLES_XL', 200, 0.5)), 'PEBBLES_L': (('PEBBLES_S', 500, 0.5), ('PEBBLES_XL', 5, 0.5)), 'PEBBLES_XL': (('PEBBLES_M', 20, -1.0), ('PEBBLES_M', 500, -0.1))}
CURVE_K=0.0
LINE_K=0.0
BFLY_K=0.0
class Trader:
 L=10;Q=20
 def run(self,state:TradingState):
  out:Dict[str,List[Order]]={}
  try:h=json.loads(state.traderData) if state.traderData else {}
  except Exception:h={}
  mids={}
  for p in P:
   d=state.order_depths.get(p)
   if d and d.buy_orders and d.sell_orders:
    mids[p]=(max(d.buy_orders)+min(d.sell_orders))/2
    a=h.get(p,[]);a.append(mids[p]);h[p]=a[-501:]
  curve=0
  fits={}
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
