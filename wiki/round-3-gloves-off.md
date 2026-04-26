# Round 3 - “Gloves Off”b 

Source: https://imc-prosperity.notion.site/

Welcome to Solvenar! A prosperous and highly developed planet known for technological innovation, a robust economy, and thriving cultural sectors.

This awe-inspiring society will be the stage for the Great Orbital Ascension Trialsbi (GOAT). In this Great Galactic Trade-Off, you will face other trading crews head-on as you compete for the coveted title of Trading Champion of the Galaxy. This trading round marks the start of GOAT, where all teams begin with zero PnL and the leaderboard is resetbi.

You will develop a new Python program and incorporate your strategy for trading Hydrogel Packsbi (HYDROGEL_PACKc), Velvetfruit Extractbi (VELVETFRUIT_EXTRACTc), and 10 Velvetfruit Extract Vouchersbi (VELVETFRUIT_EXTRACT_VOUCHERc). These vouchers give you the right to buy Velvetfruit Extract at a later point for a specific strike price.

To kick off GOAT, the Celestial Gardeners’ Guild is making a rare appearance, offering you the opportunity to buy Ornamental Bio-Podsbi from them. You may submit two offers and trade with as many of the so-called “Guardeners” as aligns with your strategy for maximum profitability. Secure those Bio-Pods, and they will be automatically converted into profit before the next trading round begins.

Be aware that trading rounds on Solvenar (Solvenarian days) last only 48 hoursbi. Be decisive, thorough, and fast, and make this first step toward the ultimate title count.

# Round Objectiveb

Create a new Python program that algorithmically trades HYDROGEL_PACKc, VELVETFRUIT_EXTRACTc, and VELVETFRUIT_EXTRACT_VOUCHERc on your behalf and generates your first profit in this final phase.

In addition, manually submit two orders to trade Ornamental Bio-Pods with members of the Celestial Gardeners’ Guild, then automatically sell your acquired Bio-Pods to generate additional profit.

# Algorithmic trading challenge: “Options Require Decisions”b

There are 2 ‘asset classes’ in the three products you trade. The HYDROGEL_PACKc and VELVETFRUIT_EXTRACTc are “delta 1” products, similar to the products in the tutorial and rounds 1 and 2. The 10 VELVETFRUIT_EXTRACT_VOUCHERc products (each with a different strike price) are options, and thus follow different dynamics. All products are traded independently, even though the price of VELVETFRUIT_EXTRACT_VOUCHERc might be related to that of VELVETFRUIT_EXTRACTc due to the nature of options.

The vouchers are labeled VEV_4000c, VEV_4500c, VEV_5000c, VEV_5100c, VEV_5200c, VEV_5300c, VEV_5400c, VEV_5500c, VEV_6000c, VEV_6500c, where VEV stands for Vbelvetfruit Ebxtract Vboucher, and the number represents the strike price. They all have a 7-day expiration deadline starting from round 1, where each round represents 1 day. Thus, the ‘time till expiry’ (TTE) is 7 days at the start of round 1 (TTE=7d), 6 days at the start of round 2, 5 days at the start of round 3, and so on.

The position limits (see the Position Limits page for extra context and troubleshootingahttps://imc-prosperity.notion.site/writing-an-algorithm-in-python#328e8453a09380cfb53edaa112e960a9) are:

- HYDROGEL_PACKc: 200

- VELVETFRUIT_EXTRACTc: 200

- VELVETFRUIT_EXTRACT_VOUCHERc: 300 for each of the 10 vouchers.

> 

Vouchers cannot be exercised before their expiry, and inventory does not carry over into the next round. Like in previous rounds, any open positions are automatically liquidated against a hidden fair value at the end of the round.

# Manual trading challenge: “The Celestial Gardeners’ Guild”b

You trade against a secret number of counterparties that all have a reserve priceb ranging between 670b and 920b. You trade at most once with each counterparty. On the next trading day, you’re able to sell all the product for a fair price, 920b.

The distribution of the bids is uniformly distributedb at increments of 5b between 670b and 920 b(inclusive on both ends). 

> 

You may submit two bidsb. If the first bid is higher bthan the reserve price, they trade with you at your first bid. If your second bid is higher bthan the reserve price of a counterparty and higher bthan the mean of second bids of all players you trade at your second bid. If your second bid is higher bthan the reserve price, but lower bthan or equalb to the mean of second bids of all players, the chance of a trade rapidly decreases: you will trade at your second bid but byour PNL is penalised by 

\left(\frac{920 - \text{avg\_b2}}{920 - b2}\right)^3

## Submit your ordersb

Submit your two bids directly in the Manual Challenge Overview window and click the “Submit” button. You can re-submit new bids until the end of the trading round. When the round ends, the last submitted bids will be offered to the members of the Celestial Gardeners' Guild.




