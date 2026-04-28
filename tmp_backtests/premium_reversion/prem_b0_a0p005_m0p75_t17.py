import json
from datamodel import Order, TradingState

B=[('HYDROGEL_PACK', 9994, 32.588, 1.0, 17, 200), ('VELVETFRUIT_EXTRACT', 5247, 17.091, 1.0, 17, 200)]
V=[('VEV_4000', 4000, 0.0078, 0.8589, 300), ('VEV_4500', 4500, 0.008, 0.7713, 300), ('VEV_5000', 5000, 3.4959, 1.5226, 300), ('VEV_5100', 5100, 13.2146, 3.7998, 300), ('VEV_5200', 5200, 41.3318, 7.5122, 300), ('VEV_5300', 5300, 41.1763, 9.143, 300), ('VEV_5400', 5400, 12.6298, 4.1493, 300), ('VEV_5500', 5500, 4.7078, 2.2053, 300)]
A=0.005; M=0.75; TK=17; UB=False
I1={"HYDROGEL_PACK":-0.5,"VELVETFRUIT_EXTRACT":0}
I3={"HYDROGEL_PACK":-2.0,"VELVETFRUIT_EXTRACT":-1.0}

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
    def run(self,state:TradingState):
        try: mem=json.loads(state.traderData) if state.traderData else {}
        except Exception: mem={}
        orders={}; pos=state.position
        for sym,mean,sd,thr,take,limit in B:
            d=state.order_depths.get(sym)
            if not d or not d.buy_orders or not d.sell_orders: continue
            bb=max(d.buy_orders); ba=min(d.sell_orders); mid=(bb+ba)/2
            fair=mean
            if UB:
                bv1=abs(d.buy_orders[bb]); av1=abs(d.sell_orders[ba]); den1=bv1+av1
                i1=(bv1-av1)/den1 if den1 else 0
                bv=0; av=0
                for px in sorted(d.buy_orders,reverse=True)[:3]: bv+=abs(d.buy_orders[px])
                for px in sorted(d.sell_orders)[:3]: av+=abs(d.sell_orders[px])
                den=bv+av; i3=(bv-av)/den if den else 0
                fair+=I1.get(sym,0)*sd*i1+I3.get(sym,0)*sd*i3
            z=(mid-fair)/sd
            if abs(z)<thr: continue
            p=pos.get(sym,0)
            if z>0:
                room=max(0,min(take,limit+p))
                if room: orders[sym]=walk(d,-1,sym,lambda px,fair=fair:px>=fair,room)
            else:
                room=max(0,min(take,limit-p))
                if room: orders[sym]=walk(d,1,sym,lambda px,fair=fair:px<=fair,room)
        ud=state.order_depths.get("VELVETFRUIT_EXTRACT")
        if ud and ud.buy_orders and ud.sell_orders:
            u=(max(ud.buy_orders)+min(ud.sell_orders))/2
            for sym,k,pm,psd,limit in V:
                d=state.order_depths.get(sym)
                if not d or not d.buy_orders or not d.sell_orders: continue
                bb=max(d.buy_orders); ba=min(d.sell_orders); mid=(bb+ba)/2
                intr=max(u-k,0)
                prem=mid-intr
                old=mem.get(sym,pm)
                fair=intr+old
                th=max(1.0,M*psd)
                p=pos.get(sym,0)
                if mid>fair+th:
                    room=max(0,min(TK,limit+p))
                    if room: orders[sym]=walk(d,-1,sym,lambda px,fair=fair:px>=fair,room)
                elif mid<fair-th:
                    room=max(0,min(TK,limit-p))
                    if room: orders[sym]=walk(d,1,sym,lambda px,fair=fair:px<=fair,room)
                mem[sym]=(1-A)*old+A*prem
        return orders,0,json.dumps(mem,separators=(",",":"))
