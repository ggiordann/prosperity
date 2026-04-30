from datamodel import Order, OrderDepth, TradingState
from typing import Dict, List
import json
P=('GALAXY_SOUNDS_DARK_MATTER', 'GALAXY_SOUNDS_BLACK_HOLES', 'GALAXY_SOUNDS_PLANETARY_RINGS', 'GALAXY_SOUNDS_SOLAR_WINDS', 'GALAXY_SOUNDS_SOLAR_FLAMES')
M={'GALAXY_SOUNDS_BLACK_HOLES': 11466.872, 'GALAXY_SOUNDS_DARK_MATTER': 10226.662, 'GALAXY_SOUNDS_PLANETARY_RINGS': 10766.673, 'GALAXY_SOUNDS_SOLAR_FLAMES': 11092.572, 'GALAXY_SOUNDS_SOLAR_WINDS': 10437.544}
S={'GALAXY_SOUNDS_BLACK_HOLES': 958.445, 'GALAXY_SOUNDS_DARK_MATTER': 330.701, 'GALAXY_SOUNDS_PLANETARY_RINGS': 765.837, 'GALAXY_SOUNDS_SOLAR_FLAMES': 450.15, 'GALAXY_SOUNDS_SOLAR_WINDS': 541.111}
MODE={'GALAXY_SOUNDS_DARK_MATTER': 'mid', 'GALAXY_SOUNDS_BLACK_HOLES': 'mid', 'GALAXY_SOUNDS_PLANETARY_RINGS': 'mid', 'GALAXY_SOUNDS_SOLAR_WINDS': 'mid', 'GALAXY_SOUNDS_SOLAR_FLAMES': 'mid'}
SHIFT={}
Z={'GALAXY_SOUNDS_BLACK_HOLES': 0.0, 'GALAXY_SOUNDS_DARK_MATTER': 0.35, 'GALAXY_SOUNDS_PLANETARY_RINGS': 0.8, 'GALAXY_SOUNDS_SOLAR_FLAMES': 0.8, 'GALAXY_SOUNDS_SOLAR_WINDS': 1.0}
EDGE={'GALAXY_SOUNDS_DARK_MATTER': 2.0, 'GALAXY_SOUNDS_BLACK_HOLES': 2.0, 'GALAXY_SOUNDS_PLANETARY_RINGS': 2.0, 'GALAXY_SOUNDS_SOLAR_WINDS': 2.0, 'GALAXY_SOUNDS_SOLAR_FLAMES': 2.0}
IMP={'GALAXY_SOUNDS_DARK_MATTER': 1, 'GALAXY_SOUNDS_BLACK_HOLES': 1, 'GALAXY_SOUNDS_PLANETARY_RINGS': 1, 'GALAXY_SOUNDS_SOLAR_WINDS': 1, 'GALAXY_SOUNDS_SOLAR_FLAMES': 1}
SIG={}
SELF={'GALAXY_SOUNDS_DARK_MATTER': ((50, 0.2),), 'GALAXY_SOUNDS_BLACK_HOLES': ((50, 0.2),), 'GALAXY_SOUNDS_PLANETARY_RINGS': ((50, 0.2),), 'GALAXY_SOUNDS_SOLAR_WINDS': ((50, 0.2),), 'GALAXY_SOUNDS_SOLAR_FLAMES': ((50, 0.2),)}
BASK={'GALAXY_SOUNDS_DARK_MATTER': (8596.58404479841, {'GALAXY_SOUNDS_BLACK_HOLES': 0.12987741666704228, 'GALAXY_SOUNDS_PLANETARY_RINGS': 0.1114581967199089, 'GALAXY_SOUNDS_SOLAR_WINDS': 0.02919454738094379, 'GALAXY_SOUNDS_SOLAR_FLAMES': -0.11414607344096171}), 'GALAXY_SOUNDS_BLACK_HOLES': (5300.1379672014245, {'GALAXY_SOUNDS_DARK_MATTER': 0.34966183772338355, 'GALAXY_SOUNDS_PLANETARY_RINGS': 0.006042065006631746, 'GALAXY_SOUNDS_SOLAR_WINDS': 0.2272180818094772, 'GALAXY_SOUNDS_SOLAR_FLAMES': 0.030644349820299076}), 'GALAXY_SOUNDS_PLANETARY_RINGS': (5924.598231614611, {'GALAXY_SOUNDS_DARK_MATTER': 0.295472732953266, 'GALAXY_SOUNDS_BLACK_HOLES': 0.22248199010723255, 'GALAXY_SOUNDS_SOLAR_WINDS': 0.16022069049362336, 'GALAXY_SOUNDS_SOLAR_FLAMES': -0.19402744921410364}), 'GALAXY_SOUNDS_SOLAR_WINDS': (13054.907534041844, {'GALAXY_SOUNDS_DARK_MATTER': 0.09345389096597173, 'GALAXY_SOUNDS_BLACK_HOLES': -0.05916388270917731, 'GALAXY_SOUNDS_PLANETARY_RINGS': -0.003878418728118551, 'GALAXY_SOUNDS_SOLAR_FLAMES': -0.2710237478152597}), 'GALAXY_SOUNDS_SOLAR_FLAMES': (15516.57600931881, {'GALAXY_SOUNDS_DARK_MATTER': -0.1322736834812349, 'GALAXY_SOUNDS_BLACK_HOLES': 0.05221677640263342, 'GALAXY_SOUNDS_PLANETARY_RINGS': -0.121136197741997, 'GALAXY_SOUNDS_SOLAR_WINDS': -0.22417723345949092})}
BASK_W=0.0
PAIR=('GALAXY_SOUNDS_DARK_MATTER', 'GALAXY_SOUNDS_PLANETARY_RINGS', 8207.916773, 0.187499, 297.893695)
PAIR_W=0.0
OB_K=0.0
TAKE_OFF=False
class Trader:
 L=10;Q=20
 def run(self,state:TradingState):
  res:Dict[str,List[Order]]={}
  try:data=json.loads(state.traderData) if state.traderData else {}
  except Exception:data={}
  h=data.get('gh',{})
  mids={};imb={}
  for p in P:
   d=state.order_depths.get(p)
   if d and d.buy_orders and d.sell_orders:
    mids[p]=(max(d.buy_orders)+min(d.sell_orders))/2.0
    bv=sum(int(v) for v in d.buy_orders.values()); av=-sum(int(v) for v in d.sell_orders.values())
    imb[p]=(bv-av)/(bv+av) if bv+av else 0.0
  for p in P:
   if p in mids:
    a=h.get(p,[]);a.append(mids[p]);h[p]=a[-501:]
  for p in P:
   d=state.order_depths.get(p)
   if not d or not d.buy_orders or not d.sell_orders:
    res[p]=[];continue
   if MODE.get(p,'mid')=='static':
    fair=M[p]+SHIFT.get(p,0.0);take=Z.get(p,0.0)*S[p]
   else:
    fair=mids[p]+SHIFT.get(p,0.0);take=10**9
   if p in BASK and BASK_W:
    c,b=BASK[p]; bf=c
    ok=True
    for fp,bt in b.items():
     if fp not in mids: ok=False; break
     bf+=bt*mids[fp]
    if ok: fair=(1-BASK_W)*fair+BASK_W*bf
   if PAIR_W and p in (PAIR[0],PAIR[1]) and PAIR[0] in mids and PAIR[1] in mids:
    a,b,c,beta,sd=PAIR
    if p==a:
     pf=c+beta*mids[b]; fair=(1-PAIR_W)*fair+PAIR_W*pf
    else:
     pf=(mids[a]-c)/beta if abs(beta)>1e-9 else fair; fair=(1-PAIR_W)*fair+PAIR_W*pf
   for lag,k in SELF.get(p,()):
    a=h.get(p,[])
    if len(a)>lag: fair+=k*(a[-1]-a[-1-lag])
   for lp,lag,k in SIG.get(p,()):
    a=h.get(lp,[])
    if len(a)>lag: fair+=k*(a[-1]-a[-1-lag])
   fair+=OB_K*imb.get(p,0.0)
   if TAKE_OFF: take=10**9
   res[p]=self.tr(p,d,int(state.position.get(p,0)),fair,take,EDGE.get(p,2.0),IMP.get(p,1))
  return res,0,json.dumps({'gh':h},separators=(',',':'))
 def tr(self,p,d,pos,fair,take,edge,imp):
  bb=max(d.buy_orders);ba=min(d.sell_orders);bc=max(0,self.L-pos);sc=max(0,self.L+pos);out=[]
  if bc>0 and ba<=fair-take:
   q=min(bc,self.Q,-int(d.sell_orders[ba]))
   if q>0:out.append(Order(p,ba,q));bc-=q
  if sc>0 and bb>=fair+take:
   q=min(sc,self.Q,int(d.buy_orders[bb]))
   if q>0:out.append(Order(p,bb,-q));sc-=q
  if ba-bb>2*imp:bid,ask=bb+imp,ba-imp
  elif ba-bb>1:bid,ask=bb+1,ba-1
  else:bid,ask=bb,ba
  if bc>0 and bid<=fair-edge:out.append(Order(p,bid,min(self.Q,bc)))
  if sc>0 and ask>=fair+edge:out.append(Order(p,ask,-min(self.Q,sc)))
  return out
