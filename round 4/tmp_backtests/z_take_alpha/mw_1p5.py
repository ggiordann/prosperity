from datamodel import Order, TradingState

C=[('HYDROGEL_PACK', 9994, 32.588, 1.0, 17, 200), ('VELVETFRUIT_EXTRACT', 5247, 17.091, 1.0, 17, 200), ('VEV_4000', 1247, 17.114, 1.0, 17, 300), ('VEV_4500', 747, 17.105, 1.0, 17, 300), ('VEV_5000', 252, 16.381, 1.0, 17, 300), ('VEV_5100', 163, 15.327, 1.0, 17, 300), ('VEV_5200', 91, 12.796, 1.0, 17, 300), ('VEV_5300', 43, 8.976, 1.0, 17, 300), ('VEV_5400', 14, 4.608, 1.0, 17, 300), ('VEV_5500', 6, 2.477, 1.0, 17, 300)]
MW=1.5
IW=0
FT=None

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
    def run(self, state: TradingState):
        orders={}
        pos=state.position
        for sym,mean,sd,thr,take,limit in C:
            d=state.order_depths.get(sym)
            if not d or not d.buy_orders or not d.sell_orders: continue
            bb=max(d.buy_orders); ba=min(d.sell_orders); mid=(bb+ba)/2
            bv=abs(d.buy_orders[bb]); av=abs(d.sell_orders[ba]); den=bv+av
            micro=((ba*bv+bb*av)/den-mid) if den else 0
            imb=((bv-av)/den) if den else 0
            fair=mean+MW*micro+IW*sd*imb
            z=(mid-fair)/sd if sd>0 else 0
            if abs(z)<thr: continue
            p=pos.get(sym,0)
            if z>0:
                if FT is not None and micro>FT: continue
                room=max(0, min(take, limit+p))
                if room: orders[sym]=walk(d,-1,sym,lambda px, fair=fair: px>=fair,room)
            else:
                if FT is not None and micro<-FT: continue
                room=max(0, min(take, limit-p))
                if room: orders[sym]=walk(d,1,sym,lambda px, fair=fair: px<=fair,room)
        return orders,0,""
