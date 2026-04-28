import importlib.util,json,sys,datamodel
from datamodel import Order,TradingState
MP=('VELVETFRUIT_EXTRACT', 'VEV_5100')
ZP=('HYDROGEL_PACK', 'VEV_4000', 'VEV_4500', 'VEV_5000', 'VEV_5200', 'VEV_5300', 'VEV_5400', 'VEV_5500')
def load(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    mod=importlib.util.module_from_spec(spec)
    old=sys.modules.get("datamodel")
    sys.modules["datamodel"]=datamodel
    try: spec.loader.exec_module(mod)
    finally:
        if old is None: sys.modules.pop("datamodel",None)
        else: sys.modules["datamodel"]=old
    return mod.Trader()
class W:
    def __init__(self,s,t):
        self.traderData=t;self.timestamp=s.timestamp;self.listings=s.listings;self.order_depths=s.order_depths;self.own_trades=s.own_trades;self.market_trades=s.market_trades;self.position=s.position;self.observations=s.observations
class Trader:
    L={"HYDROGEL_PACK":200,"VELVETFRUIT_EXTRACT":200,"VEV_4000":300,"VEV_4500":300,"VEV_5000":300,"VEV_5100":300,"VEV_5200":300,"VEV_5300":300,"VEV_5400":300,"VEV_5500":300,"VEV_6000":300,"VEV_6500":300}
    def __init__(self):
        self.z=load("/Users/giordanmasen/Downloads/z_take.py","z")
        self.m=load("/Users/giordanmasen/Downloads/trader_state_value_submission_100kb_optimized.py","m")
        self.m.T=MP
    def run(self,s:TradingState):
        d={}
        if s.traderData:
            try:d=json.loads(s.traderData)
            except Exception:d={}
        mo,_,mt=self.m.run(W(s,d.get("m","")))
        zo,_,_=self.z.run(s)
        raw={}
        for p,o in (mo or {}).items():
            if p in MP: raw[p]=o
        for p,o in (zo or {}).items():
            if p in ZP: raw[p]=o
        out={};q={}
        for p,os in raw.items():
            lim=self.L.get(p,20);pos=int(s.position.get(p,0))
            for a in os:
                n=int(a.quantity);cur=pos+q.get(p,0)
                if n>0:n=min(n,lim-cur)
                elif n<0:n=-min(-n,lim+cur)
                if n:
                    out.setdefault(p,[]).append(Order(p,int(a.price),n));q[p]=q.get(p,0)+n
        return out,0,json.dumps({"m":mt},separators=(",",":"))
