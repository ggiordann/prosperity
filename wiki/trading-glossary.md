# Trading glossary

Source: https://imc-prosperity.notion.site/trading-glossary

The aim of this page is to introduce players to real world trading concepts and jargon which they will also encounter in the world of prosperity.

### Exchange

A central marketplace where buyers and sellers meet to arrange trades in certain products. These products can be a wide range of things. Commodities, Stocks, Bonds, ETFs, Derivatives, Currencies, Cryptocurrencies. Modern exchanges are often heavily relying on digital infrastructure, and to a large extent match buyers and sellers using automated matching of BUY and SELL orders.

### Order

An order is a binding message sent by a market participant to indicate a willingness to buy or sell a certain amount (e.g. 1 stock) of a specified product (e.g., NVIDIA) on an exchange (e.g., NASDAQ). There are essentially 3 types of orders:

> 

> 

> 

Some general properties of an order:

- Participant / Account (Owner)b: who sent the order.

- Productb: the product the participant wants to trade.

- Quantityb: how much of the product the participant wants to trade.

- Sideb: whether the order is a BUY or a SELL order.

- Priceb: the price associated with the order.

- Validityb: how long the order remains active in the market.

Depending on the context, orders may have additional properties, but the ones above are the most fundamental. If a BUY order and a SELL order are compatible — meaning that a trade can be arranged where both the conditions of the SELL as well as the BUY order are met (e.g., price) — they are matchedb, and a trade is executedb. (More about order matching below.)

In Prosperity, we focus on limit orders sent to Prosperity’s own exchange. 

### Bid Order

A bid order, is financial jargon for a BUY order. The price of such a bid order is typically referred to as the “bid” or the “bid price”. If traders refer to the “best bid”, they typically refer to the price corresponding to the highest active buy order for a certain product, which is the highest price another market participant can decide to sell the product at.

### Ask Order / Offer

Similar to “Bid Orders”, but referring to SELL orders.

### Order Matching

How order execution works on Prosperity’s exchange (and on most real-world exchanges):

A BUY order will be immediately executed if there is an active SELL order in the market with an associated price equal to or lower than the price associated with the BUY order (the lower the sell price the better it is for the buyer). In that case the buyer will buy an amount equal to the minimum of the two order quantities, at the price of the SELL order. If the SELL order quantity was lower than the BUY order, that means only part of the BUY order gets executed, and a resting order (equal to the BUY order quantity minus the SELL order quantity) remains in the market. If there is no SELL order with a price equal or lower than the price of the BUY order, the full order remains in the market. If an order remains in the market, the bots might decide to send crossing sell orders at a later point, which would then mean that at that point the order still trades.

By symmetry, SELL orders will trade immediately against any BUY orders with a price equal or higher than the price associated with the SELL order (the higher the buy price the better it is for the seller). Beside from that SELL orders behave in the exact same way as BUY orders.

### Order Book

Orders for a certain product are collected in something called an Order Book. While there are multiple ways to visualize an Order Book, a common representation is shown below. The middle of the book shows the different price levels. The left side, or bid side, shows the combined quantity of all the BUY orders which have the same price associated with them. On the right side, or ask side, the combined quantity of all the sell orders per price level is represented. As described above, once there are buy and sell orders at the same price level, or even buy orders at a price level above the price level of the lowest sell order, orders are matched and trading takes place. We would call an order book with no bid orders at or above the level of the lowest ask order “uncrossed”. No trading is then possible. If there are buy orders above the lowest price level with ask orders, we would call the book “crossed” and trading is possible.

Order Book.png

### Priority

Sometimes an incoming order could be matched to several existing orders. In that case the priority rules of the exchange determine at which the order will be executed. The most common priority rule, also enforced on Prosperity’s exchange, is “price-time priority”. This means that the incoming order is first matched against the existing order with the most attractive price (from the perspective of the incoming order) at the price level of the existing order. If there are multiple orders at that price level, the oldest order is executed first. If we take the right most order book in the figure above as an example and assume that the sell order with a quantity of 2 at price level 4 was the last order to be entered in the book, we see that this order could be matched either against the buy orders at price level 4 or the buy orders at price level 5. Selling at a price of 5 is more attractive from the perspective of the incoming order so the order will match with buy orders on that level. If the aggregate quantity of 3 on the bid side at price level 5 consists of multiple orders, the ask order will first be executed against the oldest order at that level. If any quantity of the incoming order remains after that trade it is executed against the second oldest order at that price level.

### Market Making

A trading strategy where the trader does not necessarily have a strong opinion on the direction in which they expect the price to move, but conduct business through the (attempt of) simultaneous buying and selling of certain products. An example is a currency exchange shop at the airport where at any point in time they are willing to buy people’s dollars at 0.95 Euro, and sell dollars to people at 1.05. Even if the relative value of euros and dollars doesn’t change, the currency shop will make a living as long as they sell approximately as many dollars as they buy, making a 10ct profit on every buy-sell pair while they provide liquidity to travellers. These travellers are happy as well, as even though they had to make a small financial investment, they now have the right currency required to go about their business. IMC does the same thing in financial derivatives, just as you’d be wise to consider doing a bit of market making yourself in the exciting world of Prosperity!

The aim of this page is to introduce players to real world trading concepts and jargon which they will also encounter in the world of prosperity.

### 



