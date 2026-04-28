from datamodel import Order, TradingState

C=[('HYDROGEL_PACK', 9994, 32.588, 1.0, 17, 2.0, 200), ('VELVETFRUIT_EXTRACT', 5247, 17.091, 1.0, 17, 2.0, 200), ('VEV_4000', 1247, 17.114, 1.0, 17, 2.0, 300), ('VEV_4500', 747, 17.105, 1.0, 17, 2.0, 300), ('VEV_5000', 252, 16.381, 1.0, 17, 2.0, 300), ('VEV_5100', 163, 15.327, 1.0, 17, 2.0, 300), ('VEV_5200', 91, 12.796, 1.0, 17, 2.0, 300), ('VEV_5300', 43, 8.976, 1.0, 17, 2.0, 300), ('VEV_5400', 14, 4.608, 1.0, 17, 2.0, 300), ('VEV_5500', 6, 2.477, 1.0, 17, 2.0, 300)]
P=[('VEV_5300', 'VEV_5400', -5.688267546997425, 0.44486879297874654, 0.8202267498882495, 2.0, 1, True), ('VELVETFRUIT_EXTRACT', 'HYDROGEL_PACK', 7510.880029874439, 0.4727495807097714, 36.9711850780551, 2.0, 1, False)]
L={x[0]:x[-1] for x in C}
F={"VELVETFRUIT_EXTRACT":{"Mark 67":1.0,"Mark 49":-1.0,"Mark 22":-0.65}}

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
        out={}; pending={}
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
