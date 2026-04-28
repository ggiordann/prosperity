from datamodel import Order,TradingState
C=[('HYDROGEL_PACK', 9994, 32.588, 200, 0, 10, -0.5, -2, 2), ('VELVETFRUIT_EXTRACT', 5247, 17.091, 200, 0, 10, -0.5, -2, 2), ('VEV_4000', 1247, 17.114, 300, 0, 10, -0.5, -2, 2), ('VEV_4500', 747, 17.105, 300, 0, 10, -0.5, -2, 2), ('VEV_5000', 252, 16.381, 300, 0, 10, -0.5, -2, 2), ('VEV_5100', 163, 15.327, 300, 0, 10, -0.5, -2, 2), ('VEV_5200', 91, 12.796, 300, 0, 10, -0.5, -2, 2), ('VEV_5300', 43, 8.976, 300, 0, 10, -0.5, -2, 2), ('VEV_5400', 14, 4.608, 300, 0, 10, -0.5, -2, 2), ('VEV_5500', 6, 2.477, 300, 0, 10, -0.5, -2, 2)]
def walk(d,side,sym,ok,n):
 ps=sorted(d.sell_orders) if side>0 else sorted(d.buy_orders,reverse=True);b=d.sell_orders if side>0 else d.buy_orders;o=[];f=0
 for px in ps:
  if f>=n or not ok(px):break
  q=min(abs(b[px]),n-f)
  if q<=0:break
  o.append(Order(sym,px,side*q));f+=q
 return o
class Trader:
 def run(s,state:TradingState):
  o={};pos=state.position
  for sym,mean,sd,lim,thr,take,i1w,i3w,edge in C:
   d=state.order_depths.get(sym)
   if not d or not d.buy_orders or not d.sell_orders:continue
   bb=max(d.buy_orders);ba=min(d.sell_orders);mid=(bb+ba)/2
   bv1=abs(d.buy_orders[bb]);av1=abs(d.sell_orders[ba]);den1=bv1+av1;i1=(bv1-av1)/den1 if den1 else 0
   bv=sum(abs(d.buy_orders[p]) for p in sorted(d.buy_orders,reverse=True)[:3]);av=sum(abs(d.sell_orders[p]) for p in sorted(d.sell_orders)[:3]);den=bv+av;i3=(bv-av)/den if den else 0
   fair=mean+sd*(i1w*i1+i3w*i3);z=(mid-fair)/sd if sd else 0;p=pos.get(sym,0)
   if z>thr:
    n=max(0,min(take,lim+p))
    if n:
     r=walk(d,-1,sym,lambda px,F=fair,E=edge:px>=F+E,n)
     if r:o[sym]=r
   elif z<-thr:
    n=max(0,min(take,lim-p))
    if n:
     r=walk(d,1,sym,lambda px,F=fair,E=edge:px<=F-E,n)
     if r:o[sym]=r
  return o,0,''
