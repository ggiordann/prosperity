from datamodel import OrderDepth, UserId, TradingState, Order
from typing import List
from numpy import mean, std, log, diff
from math import floor, ceil, sqrt, e
from statistics import fmean, NormalDist
from jsonpickle import encode, decode
import string

class New_Data:
    def __init__(self, product_names, macaron_info):
        self.MAX_HISTORY_LENGTH = 150

        self.sell_order_history = self.make_empty_container(products=product_names)
        self.buy_order_history = self.make_empty_container(products=product_names)
        self.mid_order_history = self.make_empty_container(products=product_names)
        self.current_positions = self.make_empty_container(products=product_names, make_position_dictionary=True)
        self.previous_macaron_information = self.make_empty_container(products=macaron_info)
        self.previous_EMAs = self.make_empty_container(products=product_names, make_position_dictionary=True)

        # Product-specific information
        self.intarian_pepper_root_intercept = None

    def make_empty_container(self, products, make_position_dictionary: bool=False):
        container = {}
        for product in products:
            if make_position_dictionary:
                container[product] = 0

            else:
                container[product] = []
        
        return container
    
    def update_order_history(self, history, product, new_addition):
        if len(history[product]) > self.MAX_HISTORY_LENGTH:
            history[product].pop(0)
        history[product].append(new_addition)
    
    def update_previous_EMA(self, product, new_EMA):
        self.previous_EMAs[product] = new_EMA

class Product:
    def __init__(self, product_name, sell_order_history, buy_order_history, mid_order_history, current_position, position_limit):
        self.product_name = product_name
        self.sell_order_history = sell_order_history
        self.buy_order_history = buy_order_history
        self.mid_order_history = mid_order_history
        self.current_position = current_position
        self.position_limit = position_limit

        self.sell_order_average = 0
        if len(self.sell_order_history) > 0:
            self.sell_order_average = mean(self.sell_order_history)

        self.buy_order_average = 0
        if len(buy_order_history) > 0:
            self.buy_order_average = mean(buy_order_history)

        self.mid_order_average = 0
        if len(mid_order_history) > 0:
            self.mid_order_average = mean(mid_order_history)

        self.historical_average_mid_price = (self.buy_order_average + self.sell_order_average) / 2

        # This will be implemented in children classes
        self.acceptable_buy_price = None
        self.acceptable_sell_price = None

""" NO LONGER IN USE """
class Intarian_Pepper_Root(Product):
    def __init__(self, product_name, sell_order_history, buy_order_history, mid_order_history, current_position, position_limit, intercept):
        super().__init__(product_name, sell_order_history, buy_order_history, mid_order_history, current_position, position_limit)
        
        self.intercept = None
        if intercept is not None:
            self.intercept = intercept

        # The general price increases by 0.001 every timestamp (100 ticks)
        self.drift = 0.001

class Ash_Coated_Osmium(Product):
    def __init__(self, product_name, sell_order_history, buy_order_history, mid_order_history, current_position, position_limit, previous_EMA):
        super().__init__(product_name, sell_order_history, buy_order_history, mid_order_history, current_position, position_limit)
""" ---------------- """

class Hydrogel_Pack(Product):
    def __init__(self, product_name, sell_order_history, buy_order_history, mid_order_history, current_position, position_limit, previous_EMA):
        super().__init__(product_name, sell_order_history, buy_order_history, mid_order_history, current_position, position_limit)

        self.alpha = 0.3

        self.previous_EMA = previous_EMA
        self.EMA = self.previous_EMA

    def calculate_EMA(self, best_bid, best_ask):
        current_mid_price = (best_bid + best_ask) / 2

        if self.previous_EMA == 0 or self.previous_EMA == 0.0:
            self.previous_EMA = current_mid_price

        self.EMA = (self.alpha * current_mid_price) + ((1 - self.alpha) * self.previous_EMA)
        # self.previous_EMA = self.EMA

        # Currently not really used, but it's good in case maybe
        # self.acceptable_buy_price = ceil(self.EMA)
        # self.acceptable_sell_price = floor(self.EMA)

        return self.EMA

class Velvetfruit_Extract_Voucher(Product):
    def __init__(self, product_name, sell_order_history, buy_order_history, mid_order_history, current_position, position_limit, previous_EMA):
        super().__init__(product_name, sell_order_history, buy_order_history, mid_order_history, current_position, position_limit)

        self.all_voucher_strike_prices = {
            "VEV_4000": 4000,
            "VEV_4500": 4500,
            "VEV_5000": 5000,
            "VEV_5100": 5100,
            "VEV_5200": 5200,
            "VEV_5300": 5300,
            "VEV_5400": 5400,
            "VEV_5500": 5500,
            "VEV_6000": 6000,
            "VEV_6500": 6500
        }

        self.strike_price = self.all_voucher_strike_prices[product_name]

        # TODO: Change this when this options product is released
        self.ITERATIONS_PER_DAY = 0
    
    def calculate_predicted_option_price(self, best_bid, best_ask, strike_price, expiry_timestamp, current_timestamp):
        # Use the Black Scholes Model
        PLACEHOLDER = 0

        underlying_mid_price = (best_bid + best_ask) / 2
        expiry_time = max((expiry_timestamp - current_timestamp) / self.ITERATIONS_PER_DAY, 1e-6)
        volatility = self.calculate_volatility()
        interest_rate = 0

        d_1 = (log(underlying_mid_price / strike_price) + (((volatility ** 2) / 2) * expiry_time)) / (volatility * sqrt(expiry_time))
        d_2 = d_1 - (volatility * sqrt(expiry_time))

        # N = Cumulative distribution function of the standard normal distribution
        N = NormalDist(mu=0, sigma=1)
        N_1 = N.cdf(d_1)
        N_2 = N.cdf(d_2)

        predicted_option_price = (underlying_mid_price * N_1) - (strike_price * (e ** (-1 * interest_rate * expiry_time)) * N_2)
        return predicted_option_price

    def calculate_volatility(self):
        log_returns = diff(log(self.mid_order_history))
        return std(log_returns) * sqrt(self.ITERATIONS_PER_DAY)

class Strategy:
    def velvetfruit_extract_voucher_helper(self, voucher_name, sell_order_history, buy_order_history, mid_order_history, current_positions, position_limits, previous_EMAs):
        self.product_info[voucher_name] = Velvetfruit_Extract_Voucher(voucher_name,
                                                                        sell_order_history[voucher_name],
                                                                        buy_order_history[voucher_name],
                                                                        mid_order_history[voucher_name],
                                                                        current_positions[voucher_name],
                                                                        position_limits[voucher_name],
                                                                        previous_EMAs[voucher_name])

    def __init__(self, sell_order_history, buy_order_history, mid_order_history, current_positions, position_limits, previous_EMAs, intarian_pepper_root_intercept):
        self.product_info = {}
        self.available_velvetfruit_extract_vouchers = ["VEV_4000", "VEV_4500", "VEV_5000", "VEV_5100", "VEV_5200", "VEV_5300", "VEV_5400", "VEV_5500", "VEV_6000", "VEV_6500"]
        
        self.product_info["HYDROGEL_PACK"] = Hydrogel_Pack("HYDROGEL_PACK",
                                                           sell_order_history["HYDROGEL_PACK"],
                                                           buy_order_history["HYDROGEL_PACK"],
                                                           mid_order_history["HYDROGEL_PACK"],
                                                           current_positions["HYDROGEL_PACK"],
                                                           position_limits["HYDROGEL_PACK"],
                                                           previous_EMAs["HYDROGEL_PACK"])
        
        for voucher_name in self.available_velvetfruit_extract_vouchers:
            self.velvetfruit_extract_voucher_helper(voucher_name, sell_order_history, buy_order_history, mid_order_history, current_positions, position_limits, previous_EMAs)

    def trade_hydrogel_pack(self, buy_orders, highest_buy_order, sell_orders, lowest_sell_order, order_book_imbalance):
        hydrogel_pack = self.product_info["HYDROGEL_PACK"]
        product_name = hydrogel_pack.product_name
        
        recent_mid_prices = hydrogel_pack.mid_order_history[-20:]
        current_mid_price = (highest_buy_order + lowest_sell_order) / 2

        fair_value = mean(recent_mid_prices)
        # mispriced_threshold = fair_value + 2.0 * order_book_imbalance
        mispriced_threshold = fair_value + 0.5 * order_book_imbalance

        current_position_duplicate = hydrogel_pack.current_position

        # Orders to return back
        orders: List[Order] = []
        remaining_buy_capacity = hydrogel_pack.position_limit - current_position_duplicate
        remaining_sell_capacity = hydrogel_pack.position_limit + current_position_duplicate
        
        # Market making strategy in addition to the mispriced strategy
        ema = hydrogel_pack.calculate_EMA(highest_buy_order, lowest_sell_order)
        spread = abs(lowest_sell_order - highest_buy_order)
        position_skew = 0.15

        position_shift = -current_position_duplicate * position_skew

        acceptable_buy_price = int(ema + position_shift - (spread / 2))
        acceptable_sell_price = int(ema + position_shift + (spread / 2)) + 1

        if acceptable_buy_price >= lowest_sell_order:
            acceptable_buy_price = lowest_sell_order - 1
        
        if acceptable_sell_price <= highest_buy_order:
            acceptable_sell_price = highest_buy_order + 1

        buy_factor = max(0.0, remaining_buy_capacity / hydrogel_pack.position_limit)
        sell_factor = max(0.0, remaining_sell_capacity / hydrogel_pack.position_limit)

        buy_size = int(15 * buy_factor)
        sell_size = int(15 * sell_factor)

        """
        From the practice submissions in Round 4:
            Only selling = spike UP at the end
            Only buying = spike DOWN at the end
        """

        # If we're not in a downward trend
        more_recent_average = mean(hydrogel_pack.mid_order_history[-3:])
        less_recent_average = mean(hydrogel_pack.mid_order_history[-8:])

        test_buy = fair_value - (spread / 8)
        test_sell = fair_value + (spread / 8)

        # if test_buy > highest_buy_order and hydrogel_pack.mid_order_history[-2] <= hydrogel_pack.mid_order_history[-1]:
        #     orders.append(Order(product_name, int(test_buy), min(buy_size, remaining_buy_capacity, 30)))
        #     pass
        # else:
        #     orders.append(Order(product_name, int(test_sell) - 1, -5))
        #     pass

        # # if (test_sell < lowest_sell_order and test_sell > current_mid_price) or True:
        # if test_sell > lowest_sell_order and test_sell > current_mid_price:
        #     orders.append(Order(product_name, int(test_sell), min(sell_size, remaining_sell_capacity, -30)))
        #     pass

        orders.append(Order(product_name, int(test_buy), min(buy_size, remaining_buy_capacity, 30)))
        # orders.append(Order(product_name, int(test_sell - (spread / 8)), min(sell_size, remaining_sell_capacity, -30)))


        # # if hydrogel_pack.mid_order_history[-2] <= hydrogel_pack.mid_order_history[-1] and hydrogel_pack.mid_order_history[-3] <= hydrogel_pack.mid_order_history[-1]:
        # if more_recent_average >= less_recent_average * 1.05 and False:
        #     orders.append(Order(product_name, highest_buy_order + 1, min(buy_size, remaining_buy_capacity)))
        #     orders.append(Order(product_name, lowest_sell_order - 1, -min(buy_size, remaining_buy_capacity)))
        # else:
        #     # Sell some to be safe so we're not holding things too much
        #     orders.append(Order(product_name, lowest_sell_order - 1, 50))
        #     pass
        #     # if current_position_duplicate > 5:
        #     #     for i in range(1, 6):
        #     #         # orders.append(Order(product_name, lowest_sell_order - 1, -5))
        #     #         orders.append(Order(product_name, lowest_sell_order - i, -(int(current_position_duplicate / 5))))

        return orders

    def trade_velvetfruit_extract_vouchers(self, product_name, state, buy_orders, highest_buy_order, sell_orders, lowest_sell_order):
        voucher = self.product_info[product_name]
        
        spread = abs(lowest_sell_order - highest_buy_order)

        # TODO: Fix this function call to match the parameters
        # self, best_bid, best_ask, strike_price, expiry_timestamp, current_timestamp
        predicted_option_price = voucher.calculate_predicted_option_price(best_bid, best_ask)

        max_spread_allowed = 5
        offset = min(spread / 2, max_spread_allowed)

        acceptable_buy_price = predicted_option_price - offset
        acceptable_sell_price = predicted_option_price + offset

        current_position_duplicate = voucher.current_position
        remaining_buy_capacity = voucher.position_limit - voucher.current_position
        remaining_sell_capacity = voucher.position_limit + voucher.current_position

        # Orders to return back
        orders: List[Order] = []

        for ask, ask_amount in list(order_depth.sell_orders.items()):
            if remaining_buy_capacity <= 0:
                break

            if ask < acceptable_buy_price:
                amount_to_buy = min(abs(ask_amount), remaining_buy_capacity, 30)

                print(f"BUY voucher: {str(amount_to_buy)} x {ask}")

                orders.append(Order(product_name, ask, amount_to_buy))
                remaining_buy_capacity -= amount_to_buy
                current_position_duplicate += amount_to_buy

        for bid, bid_amount in list(order_depth.buy_orders.items()):
            if remaining_sell_capacity <= 0:
                break

            if bid > acceptable_sell_price:
                amount_to_sell = min(bid_amount, remaining_sell_capacity, 30)

                print(f"SELL voucher: {str(amount_to_sell)} x {bid}")

                orders.append(Order(product_name, bid, -amount_to_sell))
                remaining_buy_capacity -= amount_to_sell
                current_position_duplicate -= amount_to_sell
        
        return orders

class Trader:
    def __init__(self):
        self.PRODUCT_NAMES = ["HYDROGEL_PACK",
                              "VELVETFRUIT_EXTRACT",
                              "VEV_4000",
                              "VEV_4500",
                              "VEV_5000",
                              "VEV_5100",
                              "VEV_5200",
                              "VEV_5300",
                              "VEV_5400",
                              "VEV_5500",
                              "VEV_6000",
                              "VEV_6500"]

        self.POSITION_LIMITS = {
            "HYDROGEL_PACK": 200,
            "VELVETFRUIT_EXTRACT": 200,
            "VEV_4000": 300,
            "VEV_4500": 300,
            "VEV_5000": 300,
            "VEV_5100": 300,
            "VEV_5200": 300,
            "VEV_5300": 300,
            "VEV_5400": 300,
            "VEV_5500": 300,
            "VEV_6000": 300,
            "VEV_6500": 300
        }

        self.MACARON_INFO = ["askPrice",
                             "bidPrice",
                             "exportTariff",
                             "importTariff",
                             "sugarPrice",
                             "sunlightIndex",
                             "transportFees"]

        """ Make a New_Data object to update (by default) """
        self.new_data = New_Data(self.PRODUCT_NAMES, self.MACARON_INFO)

    def bid(self):
        return 2000

    def run(self, state: TradingState):
        """ Print state properties """
        print("traderData: " + state.traderData)
        print("Observations: " + str(state.observations))
        print(f"Own trades: {state.own_trades}")



        """ Update new_data with previous trading data if it exists """
        if state.traderData != "":
            decoded_data = decode(state.traderData)
            if isinstance(decoded_data, New_Data):
                self.new_data = decoded_data

        # Update the positions of each product
        for product in state.order_depths:
            current_position = 0
            if state.position:
                current_position = state.position.get(product, 0)

            self.new_data.current_positions[product] = current_position

        strategy = Strategy(self.new_data.sell_order_history,
                            self.new_data.buy_order_history,
                            self.new_data.mid_order_history,
                            self.new_data.current_positions,
                            self.POSITION_LIMITS,
                            self.new_data.previous_EMAs,
                            self.new_data.intarian_pepper_root_intercept)



        """ Orders to be placed on exchange matching engine """
        result = {}



        """ state.order_depths: """
        # keys = products, values = OrderDepth instances



        """ Go through each product, for each product """
        for product in state.order_depths:
            print(f"Current product: {product}")



            """
            OrderDepth contains the collection of all outstanding buy and sell orders
            (or “quotes”) that were sent by the trading bots for a certain symbol

            buy_orders and sell_orders dictionaries:
            Key = price associated with the order
            Value = total volume on that price level
            """
            order_depth: OrderDepth = state.order_depths[product]



            """ If either the buy or sell orders are empty, don't trade anything! """
            if len(order_depth.sell_orders) == 0 or len(order_depth.buy_orders) == 0:
                return []



            """ Update order histories """
            sorted_buy_orders = self.sort_buy_orders_ascended(order_depth.buy_orders)
            sorted_sell_orders = self.sort_sell_orders_absolute_value_and_ascended(order_depth.sell_orders)

            best_bid, best_bid_amount = sorted_buy_orders[0]
            best_ask, best_ask_amount = sorted_sell_orders[0]
            current_mid_price = (best_ask + best_bid) / 2.0

            self.new_data.update_order_history(self.new_data.sell_order_history, product, best_ask)
            self.new_data.update_order_history(self.new_data.buy_order_history, product, best_bid)
            self.new_data.update_order_history(self.new_data.mid_order_history, product, current_mid_price)
            


            """ Calculate the order book imbalance (currently for the HYDROGEL_PACK) """
            order_book_imbalance = (best_bid_amount - best_ask_amount) / (best_bid_amount + best_ask_amount + 1e-9)



            if product == "VELVETFRUIT_EXTRACT_VOUCHER":
                print(order_depth.sell_orders)

            """ Skip any products we don't want to trade for now """
            # products_we_want_to_trade: list[str] = ["HYDROGEL_PACK", "VELVETFRUIT_EXTRACT", "VELVETFRUIT_EXTRACT_VOUCHER"]
            products_we_want_to_trade: list[str] = ["HYDROGEL_PACK"]

            if product not in products_we_want_to_trade:
                continue
            
            
            
            """
            This is still in the for product in state.order_depths for loop
            Make our orders, and put those orders in result for that respective product
            """
            if product == "HYDROGEL_PACK":
                result[product] = strategy.trade_hydrogel_pack(sorted_buy_orders, best_bid, sorted_sell_orders, best_ask, order_book_imbalance)

                # Update EMA
                self.new_data.update_previous_EMA(product, strategy.product_info[product].EMA)

            else:
                return []
            
            self.new_data.current_positions[product] = strategy.product_info[product].current_position



        """ Make the new data to append for the next iteration """
        traderData = encode(self.new_data)

        # Sample conversion request. Check more details below. 
        conversions = 0
        return result, conversions, traderData

    def sort_buy_orders_ascended(self, buy_orders):
        return sorted(buy_orders.items(), reverse=True)
    
    def sort_sell_orders_absolute_value_and_ascended(self, sell_orders):
        sell_orders_absolute_value = []
        for price, volume in sell_orders.items():
            sell_orders_absolute_value.append((price, abs(volume)))

        return sorted(sell_orders_absolute_value)
