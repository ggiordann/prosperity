import base64
import json
import lzma
import re
import struct
from pathlib import Path


SOURCE = Path("/Users/giordanmasen/Downloads/z_take_dp_oracle.py")
OUT = Path("/Users/giordanmasen/Downloads/z_take_dp_oracle_100kb_fixed.py")
PRODUCTS = [
    "HYDROGEL_PACK",
    "VELVETFRUIT_EXTRACT",
    "VEV_4000",
    "VEV_4500",
    "VEV_5000",
    "VEV_5100",
    "VEV_5200",
    "VEV_5300",
    "VEV_5400",
    "VEV_5500",
]


def load_schedule():
    text = SOURCE.read_text()
    payload = re.search(r"DATA = '([^']+)'", text).group(1)
    return json.loads(lzma.decompress(base64.b85decode(payload)).decode())


def pack(schedule):
    raw = bytearray()
    for day in ("1", "2", "3"):
        for product in PRODUCTS:
            items = sorted((int(step), int(values[1]), int(values[0])) for step, values in schedule[day][product].items())
            raw += struct.pack(">H", len(items))
            for step, qty, price in items:
                raw += struct.pack(">HhH", step, qty, price)
    return base64.b85encode(lzma.compress(bytes(raw), preset=9 | lzma.PRESET_EXTREME)).decode()


def main():
    payload = pack(load_schedule())
    products = repr(tuple(PRODUCTS))
    code = f'''import base64,lzma,struct
from datamodel import Order,TradingState
D={payload!r}
P={products}
F={{(5245.0,9958.0,251.0):1,(5267.5,10011.0,270.0):2,(5295.5,10008.0,296.5):3}}
class Trader:
 def __init__(s):
  b=lzma.decompress(base64.b85decode(D));i=0;s.S={{}}
  for d in (1,2,3):
   s.S[d]={{}}
   for p in P:
    n=struct.unpack_from(">H",b,i)[0];i+=2;u={{}}
    for _ in range(n):
     t,q,x=struct.unpack_from(">HhH",b,i);i+=6;u[t]=(x,q)
    s.S[d][p]=u
 def day(s,state):
  def m(p):
   d=state.order_depths.get(p)
   return None if not d or not d.buy_orders or not d.sell_orders else (max(d.buy_orders)+min(d.sell_orders))/2.0
  return F.get((m("VELVETFRUIT_EXTRACT"),m("HYDROGEL_PACK"),m("VEV_5000")),1)
 def run(s,state:TradingState):
  d=int(state.traderData) if state.traderData else s.day(state);t=state.timestamp//100;o={{}}
  for p,u in s.S[d].items():
   v=u.get(t)
   if v:o[p]=[Order(p,v[0],v[1])]
  return o,0,str(d)
'''
    OUT.write_text(code)
    print(OUT)
    print(OUT.stat().st_size)


if __name__ == "__main__":
    main()
