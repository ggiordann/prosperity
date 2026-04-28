from datamodel import Order,TradingState
C=[('HYDROGEL_PACK', 9994, 32.588, 200, 0.5, 150, -0.5, -2.0), ('VELVETFRUIT_EXTRACT', 5247, 17.091, 200, 0.5, 150, 0, -1.0), ('VEV_4000', 1247, 17.114, 300, 0.5, 150, -0.5, -1.5), ('VEV_4500', 747, 17.105, 300, 0.5, 150, 0, -1.5), ('VEV_5000', 252, 16.381, 300, 0.5, 150, -0.25, -1.5), ('VEV_5100', 163, 15.327, 300, 0.5, 150, 0.25, 1.0), ('VEV_5200', 91, 12.796, 300, 0.5, 150, -0.25, -1.0), ('VEV_5300', 43, 8.976, 300, 0.5, 150, 0, 1.0), ('VEV_5400', 14, 4.608, 300, 0.5, 150, 0, 0), ('VEV_5500', 6, 2.477, 300, 0.5, 150, -0.25, -1.0)]
def w(d,s,y,ok,n):
 p=sorted(d.sell_orders) if s>0 else sorted(d.buy_orders,reverse=True);b=d.sell_orders if s>0 else d.buy_orders;o=[];f=0
 for x in p:
  if f>=n or not ok(x):break
  q=min(abs(b[x]),n-f)
  if q<=0:break
  o.append(Order(y,x,s*q));f+=q
 return o
class Trader:
 def run(self,state:TradingState):
  o={};pos=state.position
  for y,m,sd,lim,thr,take,i1w,i3w in C:
   d=state.order_depths.get(y)
   if not d or not d.buy_orders or not d.sell_orders:continue
   bb=max(d.buy_orders);ba=min(d.sell_orders);mid=(bb+ba)/2
   bv1=abs(d.buy_orders[bb]);av1=abs(d.sell_orders[ba]);den1=bv1+av1;i1=(bv1-av1)/den1 if den1 else 0
   bv=sum(abs(d.buy_orders[p]) for p in sorted(d.buy_orders,reverse=True)[:3]);av=sum(abs(d.sell_orders[p]) for p in sorted(d.sell_orders)[:3]);den=bv+av;i3=(bv-av)/den if den else 0
   fair=m+sd*(i1w*i1+i3w*i3);z=(mid-fair)/sd if sd else 0;p=pos.get(y,0)
   if z>thr:
    n=max(0,min(take,lim+p));r=w(d,-1,y,lambda x,F=fair:x>=F,n) if n else []
    if r:o[y]=r
   elif z<-thr:
    n=max(0,min(take,lim-p));r=w(d,1,y,lambda x,F=fair:x<=F,n) if n else []
    if r:o[y]=r
  return o,0,''
