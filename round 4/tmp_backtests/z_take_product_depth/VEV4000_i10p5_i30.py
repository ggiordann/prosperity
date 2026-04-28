from datamodel import Order, TradingState

C=[('HYDROGEL_PACK', 9994, 32.588, 1.0, 17, 200), ('VELVETFRUIT_EXTRACT', 5247, 17.091, 1.0, 17, 200), ('VEV_4000', 1247, 17.114, 1.0, 17, 300), ('VEV_4500', 747, 17.105, 1.0, 17, 300), ('VEV_5000', 252, 16.381, 1.0, 17, 300), ('VEV_5100', 163, 15.327, 1.0, 17, 300), ('VEV_5200', 91, 12.796, 1.0, 17, 300), ('VEV_5300', 43, 8.976, 1.0, 17, 300), ('VEV_5400', 14, 4.608, 1.0, 17, 300), ('VEV_5500', 6, 2.477, 1.0, 17, 300)]
I1={'HYDROGEL_PACK': -0.25, 'VELVETFRUIT_EXTRACT': -0.25, 'VEV_4000': 0.5, 'VEV_4500': -0.25, 'VEV_5000': -0.25, 'VEV_5100': -0.25, 'VEV_5200': -0.25, 'VEV_5300': -0.25, 'VEV_5400': -0.25, 'VEV_5500': -0.25}
I3={'HYDROGEL_PACK': -1.0, 'VELVETFRUIT_EXTRACT': -1.0, 'VEV_4000': 0, 'VEV_4500': -1.0, 'VEV_5000': -1.0, 'VEV_5100': -1.0, 'VEV_5200': -1.0, 'VEV_5300': -1.0, 'VEV_5400': -1.0, 'VEV_5500': -1.0}

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
        orders={}; pos=state.position
        for sym,mean,sd,thr,take,limit in C:
            d=state.order_depths.get(sym)
            if not d or not d.buy_orders or not d.sell_orders: continue
            bb=max(d.buy_orders); ba=min(d.sell_orders); mid=(bb+ba)/2
            bv1=abs(d.buy_orders[bb]); av1=abs(d.sell_orders[ba]); den1=bv1+av1
            i1=((bv1-av1)/den1) if den1 else 0
            bv=0; av=0
            for px in sorted(d.buy_orders, reverse=True)[:3]: bv+=abs(d.buy_orders[px])
            for px in sorted(d.sell_orders)[:3]: av+=abs(d.sell_orders[px])
            den=bv+av; i3=((bv-av)/den) if den else 0
            fair=mean+I1.get(sym,0)*sd*i1+I3.get(sym,0)*sd*i3
            z=(mid-fair)/sd if sd>0 else 0
            if abs(z)<thr: continue
            p=pos.get(sym,0)
            if z>0:
                room=max(0, min(take, limit+p))
                if room: orders[sym]=walk(d,-1,sym,lambda px, fair=fair: px>=fair,room)
            else:
                room=max(0, min(take, limit-p))
                if room: orders[sym]=walk(d,1,sym,lambda px, fair=fair: px<=fair,room)
        return orders,0,""
