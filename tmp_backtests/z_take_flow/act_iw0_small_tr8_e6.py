from datamodel import Order, TradingState

C=[('HYDROGEL_PACK', 9994, 32.588, 1.0, 17, 200), ('VELVETFRUIT_EXTRACT', 5247, 17.091, 1.0, 17, 200), ('VEV_4000', 1247, 17.114, 1.0, 17, 300), ('VEV_4500', 747, 17.105, 1.0, 17, 300), ('VEV_5000', 252, 16.381, 1.0, 17, 300), ('VEV_5100', 163, 15.327, 1.0, 17, 300), ('VEV_5200', 91, 12.796, 1.0, 17, 300), ('VEV_5300', 43, 8.976, 1.0, 17, 300), ('VEV_5400', 14, 4.608, 1.0, 17, 300), ('VEV_5500', 6, 2.477, 1.0, 17, 300)]
IW=0
W={'Mark 67': 1.0, 'Mark 49': -1.0, 'Mark 22': -0.7}
FM=0
FC=0
TR=8
AE=6
AQ=20
AC=80
SO=True

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

def flow(state):
    x=0
    for t in state.market_trades.get("VELVETFRUIT_EXTRACT",[]) or []:
        q=int(t.quantity)
        b=t.buyer or ""; s=t.seller or ""
        if SO:
            if b=="Mark 67" and 1<=q<=5: x+=q
            if s=="Mark 67" and 1<=q<=5: x-=q
            if s=="Mark 22" and 3<=q<=5: x+=q
            if b=="Mark 22" and 3<=q<=5: x-=q
            if s=="Mark 49" and 1<=q<=8: x+=q
            if b=="Mark 49" and 1<=q<=8: x-=q
        else:
            x+=q*(W.get(b,0)-W.get(s,0))
    return x

class Trader:
    def bid(self): return 0
    def run(self, state: TradingState):
        orders={}
        pos=state.position
        vf=flow(state)
        for sym,mean,sd,thr,take,limit in C:
            d=state.order_depths.get(sym)
            if not d or not d.buy_orders or not d.sell_orders: continue
            bb=max(d.buy_orders); ba=min(d.sell_orders); mid=(bb+ba)/2
            bv=abs(d.buy_orders[bb]); av=abs(d.sell_orders[ba]); den=bv+av
            imb=((bv-av)/den) if den else 0
            fair=mean+IW*sd*imb
            if sym=="VELVETFRUIT_EXTRACT" and FM:
                sh=max(-FC,min(FC,FM*vf))
                fair+=sh
            z=(mid-fair)/sd if sd>0 else 0
            if abs(z)<thr: continue
            p=pos.get(sym,0)
            if z>0:
                room=max(0, min(take, limit+p))
                if room: orders[sym]=walk(d,-1,sym,lambda px, fair=fair: px>=fair,room)
            else:
                room=max(0, min(take, limit-p))
                if room: orders[sym]=walk(d,1,sym,lambda px, fair=fair: px<=fair,room)
        d=state.order_depths.get("VELVETFRUIT_EXTRACT")
        if d and d.buy_orders and d.sell_orders and abs(vf)>=TR:
            p=pos.get("VELVETFRUIT_EXTRACT",0)
            if vf>0 and p<AC:
                px=min(d.sell_orders); q=min(abs(d.sell_orders[px]), AQ, 200-p, AC-p)
                if q>0 and px<=5247+AE:
                    orders.setdefault("VELVETFRUIT_EXTRACT",[]).append(Order("VELVETFRUIT_EXTRACT",px,q))
            elif vf<0 and p>-AC:
                px=max(d.buy_orders); q=min(abs(d.buy_orders[px]), AQ, 200+p, AC+p)
                if q>0 and px>=5247-AE:
                    orders.setdefault("VELVETFRUIT_EXTRACT",[]).append(Order("VELVETFRUIT_EXTRACT",px,-q))
        return orders,0,""
