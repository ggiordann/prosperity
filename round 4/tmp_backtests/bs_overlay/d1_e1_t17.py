import math
from datamodel import Order,TradingState
C=[('HYDROGEL_PACK', 9994, 32.588, 1.0, 17, 2.0, 200), ('VELVETFRUIT_EXTRACT', 5247, 17.091, 1.0, 17, 2.0, 200), ('VEV_4000', 1247, 17.114, 1.0, 17, 2.0, 300), ('VEV_4500', 747, 17.105, 1.0, 17, 2.0, 300), ('VEV_5000', 252, 16.381, 1.0, 17, 2.0, 300), ('VEV_5100', 163, 15.327, 1.0, 17, 2.0, 300), ('VEV_5200', 91, 12.796, 1.0, 17, 2.0, 300), ('VEV_5300', 43, 8.976, 1.0, 17, 2.0, 300), ('VEV_5400', 14, 4.608, 1.0, 17, 2.0, 300), ('VEV_5500', 6, 2.477, 1.0, 17, 2.0, 300)];P=[('VEV_5300', 'VEV_5400', -5.688267546997425, 0.44486879297874654, 0.8202267498882495, 2.0, 1, True)];L={x[0]:x[-1] for x in C};F={"VELVETFRUIT_EXTRACT":{"Mark 67":1.0,"Mark 49":-1.0,"Mark 22":-0.65}}
K={"VEV_4000":4000,"VEV_4500":4500,"VEV_5000":5000,"VEV_5100":5100,"VEV_5200":5200,"VEV_5300":5300,"VEV_5400":5400,"VEV_5500":5500}
CO=(0.19013789587662855, 0.01590441489764855, -0.02149770322764756, 0.2744074207724653);T=5/365;SQ=math.sqrt(T);E=1;TK=17
def n(x):return .5*(1+math.erf(x/math.sqrt(2)))
def bs(s,k,v):
 if v<=0:return max(s-k,0)
 q=v*SQ
 if q<=0:return max(s-k,0)
 d1=(math.log(s/k)+.5*v*v*T)/q;d2=d1-q
 return s*n(d1)-k*n(d2)
def walk(d,side,sym,ok,m):
 ps=sorted(d.sell_orders) if side>0 else sorted(d.buy_orders,reverse=True);book=d.sell_orders if side>0 else d.buy_orders;out=[];g=0
 for px in ps:
  if g>=m or not ok(px):break
  q=min(abs(book[px]),m-g)
  if q<=0:break
  out.append(Order(sym,px,side*q));g+=q
 return out,g
def add(o,q,s,os):
 if os:o.setdefault(s,[]).extend(os);q[s]=q.get(s,0)+sum(x.quantity for x in os)
def room(st,q,s,side):
 p=st.position.get(s,0)+q.get(s,0);lim=L[s]
 return max(0,lim-p) if side>0 else max(0,lim+p)
def imb(d):
 b=sum(abs(v) for v in d.buy_orders.values());a=sum(abs(v) for v in d.sell_orders.values());return (b-a)/(b+a) if b+a else 0
def flow(st,s):
 m=F.get(s);v=0
 if not m:return 0
 for t in st.market_trades.get(s,[]):
  if t.buyer in m:v+=m[t.buyer]*max(1,abs(t.quantity))
  if t.seller in m:v-=m[t.seller]*max(1,abs(t.quantity))
 return max(-1,min(1,v))
class Trader:
 def run(self,st:TradingState):
  o={};q={}
  for s,mean,sd,thr,take,ik,lim in C:
   d=st.order_depths.get(s)
   if not d or not d.buy_orders or not d.sell_orders:continue
   bb=max(d.buy_orders);ba=min(d.sell_orders);mid=(bb+ba)/2;fair=mean+(.15*flow(st,s) if s=='VELVETFRUIT_EXTRACT' else 0);z=(mid-fair)/sd+ik*imb(d)
   if abs(z)>=thr:
    side=-1 if z>0 else 1;cap=min(take,room(st,q,s,side));ok=(lambda px,f=fair:px>=f) if side<0 else (lambda px,f=fair:px<=f);os,_=walk(d,side,s,ok,cap);add(o,q,s,os)
  ud=st.order_depths.get('VELVETFRUIT_EXTRACT')
  if ud and ud.buy_orders and ud.sell_orders:
   u=(max(ud.buy_orders)+min(ud.sell_orders))/2
   for s,k in K.items():
    d=st.order_depths.get(s)
    if not d or not d.buy_orders or not d.sell_orders:continue
    bb=max(d.buy_orders);ba=min(d.sell_orders);mid=(bb+ba)/2;m=math.log(k/u)/SQ;vol=max(.05,CO[0]*m*m*m+CO[1]*m*m+CO[2]*m+CO[3]);fair=bs(u,k,vol)
    if mid>fair+E:
     cap=min(TK,room(st,q,s,-1));os,_=walk(d,-1,s,lambda px,f=fair:px>=f,cap);add(o,q,s,os)
    elif mid<fair-E:
     cap=min(TK,room(st,q,s,1));os,_=walk(d,1,s,lambda px,f=fair:px<=f,cap);add(o,q,s,os)
  return o,0,''
