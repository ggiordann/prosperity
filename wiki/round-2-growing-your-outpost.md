# Round 2 - “Growing Your Outpost”b 

Source: https://imc-prosperity.notion.site/

It is the second trading round, and your final opportunity to reach the threshold goal of a net PnL of 200,000 XIRECs or more before the leaderboard resets for Phase 2. These first 2 rounds act as qualifiers for the final mission. Trading activity has accelerated significantly since your arrival. With you and the other outposts actively trading Ash-Coated Osmiumbi and Intarian Pepper Rootbi, the market has become increasingly competitive and dynamic.

In this second and final trading round on Intara, you will continue trading ASH_COATED_OSMIUMc and INTARIAN_PEPPER_ROOTc. This time, however, you have the opportunity to gain access to additional market volume. To compete for this increased capacity, you must incorporate a Market Access Feebi bid into your Python program.

Of course, you should also analyze your previous round’s performance and refine your algorithm accordingly.

Additionally, XIREN has provided a 50bi,b000 XIRECs investment budgetbi for you to allocate across three growth pillars in order to accelerate the development of your outpost. You must decide how to distribute this budget strategically to maximize your profit once the trading round closes.

# Round Objectiveb

Optimize your Python program to trade ASH_COATED_OSMIUMc and INTARIAN_PEPPER_ROOTc, and incorporate a Market Access Feebi to potentially gain access to additional market volume.

In addition to refining your trading algorithm, allocate your 50,000 XIRECs investment budgetbi across the three growth pillars to strengthen your outpost’s performance.

# Algorithmic trading challenge: “limited Market Access”b

Wiki_ROUND_2_data.zip

The products INTARIAN_PEPPER_ROOTc and ASH_COATED_OSMIUMc are the same, but the challenge now primarily lies in deciding how much to bid for extra market access, as well as refining your algorithm. The position limits (see the Position Limits page for extra context and troubleshootingahttps://imc-prosperity.notion.site/writing-an-algorithm-in-python#328e8453a09380cfb53edaa112e960a9) are again

- ASH_COATED_OSMIUMc: 80

- INTARIAN_PEPPER_ROOTc: 80

In this round, you can bid for 25% more quotes in the order book. The volumes and prices of these quotes fit perfectly in the distribution of the already available quotes. A simple example:

> 

You bid for extra market access by incorporating a bid()c function inside your class Traderc implementation:

class Trader:
    def bid(self):
        return 15

    def run(self, state: TradingState):
        (Implementation)

The Market Access Fee (MAF) is a one-time feei at the start of Round 2 paid only iif your bid is accepted. It only determines who gets extra market access, and is not used in the simulation dynamics whatsoever. The top 50% of bids across all participants are accepted.

> 

The accepted bids are subtracted from Round 2 profits to compute the final PnL. To be explicit,

> 

The MAF is unique to Round 2, and does not apply to any other round; any bid()c function in Rounds 1,3,4,5 is ignored. It is also ignored during testing of round 2, since bids are only compared on our end when the final simulation of Round 2 starts. In that sense, it’s a “blind auction” for extra flow.

During testing of round 2, the default set of quotes you interact with is 80% of all quotes we generated (i.e., no extra market access). This 80% has been slightly randomized for every submission to reflect real-world conditions where not all patterns in trading behavior are up 100% of the time. While you could optimize the PnL by submitting the same file many times, this has very limited payoff and your effort is much better put into improving your algorithm ;).

### Game theoryb

To get extra market access, you just need to be in the top 50% of bidders, not necessarily the highest bidder. Placing an extremely high bid will almost certainly yield full market access, but perhaps you could save (a lot of) XIRECs by bidding less while staying in the top 50% of bidders.

### Added for extra clarification based on FAQs:

- Median is computed from submitted trader.pyahttp://trader.py/ files - if no bid(), we consider it 0; we neglect the teams with no trader.pyahttp://trader.py/ submission for the purposes of median() 

- For the bid and computing PnL, please note negative bids will be processed as bid=0. For example, if you bid -100, we consider this bidding 0. Therefore, in PnL = Profit - Bidc, the bid can never be negative

# Manual trading challenge: “Invest & Expand”b

You are expanding your outpost into a true market making firm with a budget of 50 000c XIRECs. You need to allocate this budget across three pillars:

- Researchb

- Scaleb

- Speedb

You choose percentages for each pillar between 0–100%. Total allocation cannot exceed 100%. Your final PnL (Profit and Loss) score is:

> 

### The pillarsb

Research_b determines how strong your trading edge is. It grows logarithmicallyb from 0c (for 0c invested) to 200 000c  (for 100c invested). The exact formula is research(x) = 200_000 * np.log(1 + x) / np.log(1 + 100)c. Here, np.logc is a python function from NumPy package for natural logarithm.

Scale_b _determines how broadly you deploy your strategy across markets. It grows linearlyb from 0c (for 0c invested) to 7c (for 100c invested).

Speed_b _determines how often you win the trades you target. It is rank-basedb across all players:

- Highest speed investment receives a 0.9c multiplier.

- Lowest receives 0.1c.

- Everyone in between is scaled linearly by rank, equal investments share the same rank.

- For example, if people invested 70, 70, 70, 50, 40, 40, 30c, they get the following ranks: 1, 1, 1, 4, 5, 5, 7c. First three players get 0.9c for hit rate multiplier, last player gets 0.1c, and everybody in between gets linearly scaled between top and bottom rank. Another example, if you have three players investing 95, 20, 10c, their ranks are 1, 2, 3c, and their hit rates are 0.9, 0.5, 0.1c.

Your Research, Scale, and Speed outcomes are multiplied together to form your gross PnL, after which the used part of your budget is deducted.

Every decision you make reflects a real trade-off faced by modern market makers: capital is finite, competition is relentless, and edge alone is never enough. Good luck!

### Submit your ordersb

Choose the distribution of your budget by assigning percentages to the three pillars directly in the Manual Challenge Overview window and click the “Submit” button. You can re-submit new distributions until the end of the trading round. When the round ends, the last submitted distribution will be locked in and processed.

### Added for clarification based on FAQs: 

- Teams who do not submit their Manual solution will notb be used when determining speed ranks from those that did. Speed rank will be calculated only with those that submitted something for Manual

- The multipliers will retain "infinite" precision until the very end (when your PnL is rounded). You see them rounded to 1 decimal in the platform because it's just an indication, and we can't really fit too many digits there. This is not to be confused with your % inputs (investments), which are int.



