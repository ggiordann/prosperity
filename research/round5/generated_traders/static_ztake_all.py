from datamodel import Order, OrderDepth, TradingState
from typing import Dict, List
import json

M={'GALAXY_SOUNDS_BLACK_HOLES': 11466.872, 'GALAXY_SOUNDS_DARK_MATTER': 10226.662, 'GALAXY_SOUNDS_PLANETARY_RINGS': 10766.673, 'GALAXY_SOUNDS_SOLAR_FLAMES': 11092.572, 'GALAXY_SOUNDS_SOLAR_WINDS': 10437.544, 'MICROCHIP_CIRCLE': 9214.885, 'MICROCHIP_OVAL': 8179.599, 'MICROCHIP_RECTANGLE': 8732.439, 'MICROCHIP_SQUARE': 13594.748, 'MICROCHIP_TRIANGLE': 9686.391, 'OXYGEN_SHAKE_CHOCOLATE': 9556.879, 'OXYGEN_SHAKE_EVENING_BREATH': 9271.895, 'OXYGEN_SHAKE_GARLIC': 11925.64, 'OXYGEN_SHAKE_MINT': 9838.394, 'OXYGEN_SHAKE_MORNING_BREATH': 10000.453, 'PANEL_1X2': 8922.729, 'PANEL_1X4': 9397.581, 'PANEL_2X2': 9576.598, 'PANEL_2X4': 11265.373, 'PANEL_4X4': 9878.719, 'PEBBLES_L': 10174.111, 'PEBBLES_M': 10263.243, 'PEBBLES_S': 8932.357, 'PEBBLES_XL': 13225.589, 'PEBBLES_XS': 7404.64, 'ROBOT_DISHES': 10018.315, 'ROBOT_IRONING': 8701.57, 'ROBOT_LAUNDRY': 9822.762, 'ROBOT_MOPPING': 11100.213, 'ROBOT_VACUUMING': 9166.776, 'SLEEP_POD_COTTON': 11527.614, 'SLEEP_POD_LAMB_WOOL': 10701.442, 'SLEEP_POD_NYLON': 9636.473, 'SLEEP_POD_POLYESTER': 11840.561, 'SLEEP_POD_SUEDE': 11397.42, 'SNACKPACK_CHOCOLATE': 9843.372, 'SNACKPACK_PISTACHIO': 9495.844, 'SNACKPACK_RASPBERRY': 10077.812, 'SNACKPACK_STRAWBERRY': 10706.609, 'SNACKPACK_VANILLA': 10097.302, 'TRANSLATOR_ASTRO_BLACK': 9385.219, 'TRANSLATOR_ECLIPSE_CHARCOAL': 9813.742, 'TRANSLATOR_GRAPHITE_MIST': 10084.64, 'TRANSLATOR_SPACE_GRAY': 9431.902, 'TRANSLATOR_VOID_BLUE': 10858.579, 'UV_VISOR_AMBER': 7911.696, 'UV_VISOR_MAGENTA': 11111.793, 'UV_VISOR_ORANGE': 10426.506, 'UV_VISOR_RED': 11063.294, 'UV_VISOR_YELLOW': 10957.461}
S={'GALAXY_SOUNDS_BLACK_HOLES': 958.445, 'GALAXY_SOUNDS_DARK_MATTER': 330.701, 'GALAXY_SOUNDS_PLANETARY_RINGS': 765.837, 'GALAXY_SOUNDS_SOLAR_FLAMES': 450.15, 'GALAXY_SOUNDS_SOLAR_WINDS': 541.111, 'MICROCHIP_CIRCLE': 532.512, 'MICROCHIP_OVAL': 1551.912, 'MICROCHIP_RECTANGLE': 752.019, 'MICROCHIP_SQUARE': 1830.252, 'MICROCHIP_TRIANGLE': 833.37, 'OXYGEN_SHAKE_CHOCOLATE': 560.602, 'OXYGEN_SHAKE_EVENING_BREATH': 399.821, 'OXYGEN_SHAKE_GARLIC': 953.349, 'OXYGEN_SHAKE_MINT': 508.131, 'OXYGEN_SHAKE_MORNING_BREATH': 652.805, 'PANEL_1X2': 589.917, 'PANEL_1X4': 834.033, 'PANEL_2X2': 674.795, 'PANEL_2X4': 627.191, 'PANEL_4X4': 457.038, 'PEBBLES_L': 622.332, 'PEBBLES_M': 687.817, 'PEBBLES_S': 833.282, 'PEBBLES_XL': 1776.546, 'PEBBLES_XS': 1449.547, 'ROBOT_DISHES': 556.639, 'ROBOT_IRONING': 771.03, 'ROBOT_LAUNDRY': 614.322, 'ROBOT_MOPPING': 767.161, 'ROBOT_VACUUMING': 535.259, 'SLEEP_POD_COTTON': 887.693, 'SLEEP_POD_LAMB_WOOL': 413.169, 'SLEEP_POD_NYLON': 508.729, 'SLEEP_POD_POLYESTER': 977.54, 'SLEEP_POD_SUEDE': 899.946, 'SNACKPACK_CHOCOLATE': 200.733, 'SNACKPACK_PISTACHIO': 187.495, 'SNACKPACK_RASPBERRY': 169.814, 'SNACKPACK_STRAWBERRY': 363.573, 'SNACKPACK_VANILLA': 178.515, 'TRANSLATOR_ASTRO_BLACK': 489.746, 'TRANSLATOR_ECLIPSE_CHARCOAL': 355.637, 'TRANSLATOR_GRAPHITE_MIST': 499.541, 'TRANSLATOR_SPACE_GRAY': 502.706, 'TRANSLATOR_VOID_BLUE': 579.254, 'UV_VISOR_AMBER': 996.918, 'UV_VISOR_MAGENTA': 613.554, 'UV_VISOR_ORANGE': 550.603, 'UV_VISOR_RED': 587.715, 'UV_VISOR_YELLOW': 681.808}
class Trader:
    L=10;Q=20;Z=1.0;E=0.0;IMP=1;PR=1000000000
    def run(self,state:TradingState):
        res:Dict[str,List[Order]]={}
        try:data=json.loads(state.traderData) if state.traderData else {}
        except Exception:data={}
        st=data.get('s',{})
        for p,d in state.order_depths.items():
            if p not in M or not d.buy_orders or not d.sell_orders:
                res[p]=[];continue
            bb=max(d.buy_orders);ba=min(d.sell_orders);mid=(bb+ba)/2
            n,tot=st.get(p,[0,0.0]);n+=1;tot+=mid;st[p]=[n,tot]
            fair=(self.PR*M[p]+tot)/(self.PR+n)
            res[p]=self.tr(p,d,int(state.position.get(p,0)),fair,S[p])
        return res,0,json.dumps({'s':st},separators=(',',':'))
    def tr(self,p,d,pos,fair,sd):
        bb=max(d.buy_orders);ba=min(d.sell_orders);bc=max(0,self.L-pos);sc=max(0,self.L+pos);out=[]
        take=self.Z*sd
        if bc>0 and ba<=fair-take:
            q=min(bc,self.Q,-int(d.sell_orders[ba]));
            if q>0: out.append(Order(p,ba,q));bc-=q
        if sc>0 and bb>=fair+take:
            q=min(sc,self.Q,int(d.buy_orders[bb]));
            if q>0: out.append(Order(p,bb,-q));sc-=q
        if ba-bb>2*self.IMP: bid,ask=bb+self.IMP,ba-self.IMP
        elif ba-bb>1: bid,ask=bb+1,ba-1
        else: bid,ask=bb,ba
        if bc>0 and bid<=fair-self.E: out.append(Order(p,bid,min(self.Q,bc)))
        if sc>0 and ask>=fair+self.E: out.append(Order(p,ask,-min(self.Q,sc)))
        return out
