# Round 4 Order Flow Informed-Trader Study

Inputs: public trades and top-of-book mid prices from days 1-3 in `/Users/giordanmasen/Desktop/projects/prosperity/prosperity_rust_backtester/datasets/round4`.

Method:
- Each public trade is split into a buyer event and a seller event.
- Buyer direction is `+1`, seller direction is `-1`.
- Edge is `direction * future_mid_change`, so positive edge means following that trader's side was profitable.
- Scores are quantity-weighted edge divided by `sqrt(quantity)`, which rewards repeatable edge without letting one large trader completely dominate.
- Same-product tables use the traded product's future mid. Voucher cross tables use voucher trades as a signal for future `VELVETFRUIT_EXTRACT` mid moves.

## Same-Product Positive Flow, Horizon 5

| product             | trader  | events   | qty      | q_mean_edge | score   | hit_rate | t_stat |
| ------------------- | ------- | -------- | -------- | ----------- | ------- | -------- | ------ |
| VELVETFRUIT_EXTRACT | Mark 67 | 165.000  | 1510.000 | 1.955       | 75.968  | 0.830    | 12.941 |
| HYDROGEL_PACK       | Mark 14 | 1003.000 | 4022.000 | 0.160       | 10.139  | 0.457    | 0.889  |
| VELVETFRUIT_EXTRACT | Mark 01 | 504.000  | 2792.000 | 0.157       | 8.318   | 0.490    | 1.560  |
| VELVETFRUIT_EXTRACT | Mark 55 | 1198.000 | 6551.000 | 0.065       | 5.251   | 0.442    | 1.165  |
| HYDROGEL_PACK       | Mark 38 | 1022.000 | 4096.000 | -0.104      | -6.648  | 0.461    | -0.484 |
| VELVETFRUIT_EXTRACT | Mark 14 | 647.000  | 3524.000 | -0.144      | -8.541  | 0.388    | -1.766 |
| VELVETFRUIT_EXTRACT | Mark 22 | 126.000  | 843.000  | -1.296      | -37.628 | 0.222    | -5.716 |
| VELVETFRUIT_EXTRACT | Mark 49 | 122.000  | 1186.000 | -1.869      | -64.376 | 0.139    | -9.686 |

## Same-Product Negative Flow, Horizon 5

| product             | trader  | events   | qty      | q_mean_edge | score   | hit_rate | t_stat |
| ------------------- | ------- | -------- | -------- | ----------- | ------- | -------- | ------ |
| VELVETFRUIT_EXTRACT | Mark 49 | 122.000  | 1186.000 | -1.869      | -64.376 | 0.139    | -9.686 |
| VELVETFRUIT_EXTRACT | Mark 22 | 126.000  | 843.000  | -1.296      | -37.628 | 0.222    | -5.716 |
| VELVETFRUIT_EXTRACT | Mark 14 | 647.000  | 3524.000 | -0.144      | -8.541  | 0.388    | -1.766 |
| HYDROGEL_PACK       | Mark 38 | 1022.000 | 4096.000 | -0.104      | -6.648  | 0.461    | -0.484 |
| VELVETFRUIT_EXTRACT | Mark 55 | 1198.000 | 6551.000 | 0.065       | 5.251   | 0.442    | 1.165  |
| VELVETFRUIT_EXTRACT | Mark 01 | 504.000  | 2792.000 | 0.157       | 8.318   | 0.490    | 1.560  |
| HYDROGEL_PACK       | Mark 14 | 1003.000 | 4022.000 | 0.160       | 10.139  | 0.457    | 0.889  |
| VELVETFRUIT_EXTRACT | Mark 67 | 165.000  | 1510.000 | 1.955       | 75.968  | 0.830    | 12.941 |

## Voucher Flow Predicting VFE, Horizon 5

| source_product | trader  | events  | qty     | q_mean_edge | score  | hit_rate | t_stat |
| -------------- | ------- | ------- | ------- | ----------- | ------ | -------- | ------ |
| VEV_4000       | Mark 67 | 26.000  | 244.000 | 1.867       | 29.160 | 0.846    | 5.650  |
| VEV_6500       | Mark 01 | 125.000 | 505.000 | 0.578       | 12.994 | 0.504    | 1.947  |
| VEV_6000       | Mark 01 | 121.000 | 437.000 | 0.582       | 12.174 | 0.529    | 2.196  |
| VEV_6500       | Mark 55 | 88.000  | 484.000 | 0.492       | 10.818 | 0.557    | 2.121  |
| VEV_5500       | Mark 01 | 131.000 | 514.000 | 0.355       | 8.050  | 0.511    | 1.054  |
| VEV_5300       | Mark 55 | 35.000  | 189.000 | 0.495       | 6.801  | 0.543    | 1.424  |
| VEV_5500       | Mark 14 | 160.000 | 672.000 | 0.161       | 4.185  | 0.419    | 0.908  |
| VEV_6000       | Mark 38 | 112.000 | 381.000 | 0.199       | 3.894  | 0.446    | -0.250 |
| VEV_4000       | Mark 01 | 186.000 | 751.000 | 0.127       | 3.485  | 0.435    | 1.259  |
| VEV_6000       | Mark 14 | 155.000 | 604.000 | 0.118       | 2.889  | 0.445    | 0.660  |
| VEV_6500       | Mark 14 | 159.000 | 680.000 | 0.109       | 2.838  | 0.503    | 0.594  |
| VEV_5500       | Mark 55 | 82.000  | 434.000 | 0.111       | 2.304  | 0.451    | 0.326  |

## Voucher Flow To Fade For VFE, Horizon 5

| source_product | trader  | events  | qty     | q_mean_edge | score   | hit_rate | t_stat |
| -------------- | ------- | ------- | ------- | ----------- | ------- | -------- | ------ |
| VEV_4000       | Mark 14 | 224.000 | 887.000 | -0.489      | -14.556 | 0.384    | -2.154 |
| VEV_5500       | Mark 22 | 112.000 | 433.000 | -0.615      | -12.807 | 0.402    | -2.249 |
| VEV_5400       | Mark 22 | 89.000  | 346.000 | -0.447      | -8.306  | 0.427    | -1.387 |
| VEV_5500       | Mark 38 | 109.000 | 356.000 | -0.261      | -4.929  | 0.349    | -2.101 |
| VEV_5200       | Mark 22 | 33.000  | 127.000 | -0.437      | -4.925  | 0.273    | -0.910 |
| VEV_5300       | Mark 22 | 67.000  | 265.000 | -0.245      | -3.993  | 0.388    | -1.147 |
| VEV_5400       | Mark 14 | 164.000 | 649.000 | -0.153      | -3.906  | 0.409    | -0.635 |
| VEV_6000       | Mark 22 | 135.000 | 510.000 | -0.164      | -3.697  | 0.444    | -0.388 |
| VEV_5200       | Mark 14 | 22.000  | 88.000  | -0.369      | -3.465  | 0.273    | -1.300 |
| VEV_6500       | Mark 22 | 133.000 | 499.000 | -0.141      | -3.156  | 0.504    | 0.248  |
| VEV_4000       | Mark 22 | 140.000 | 495.000 | -0.135      | -3.011  | 0.464    | 0.501  |
| VEV_5300       | Mark 01 | 57.000  | 239.000 | -0.190      | -2.943  | 0.316    | -1.661 |

## Repeated Counterparty Pairs, Horizon 5

| product             | buyer   | seller  | events  | qty      | q_mean_edge | score  | hit_rate | t_stat |
| ------------------- | ------- | ------- | ------- | -------- | ----------- | ------ | -------- | ------ |
| VELVETFRUIT_EXTRACT | Mark 67 | Mark 49 | 89.000  | 963.000  | 1.891       | 58.697 | 0.809    | 9.112  |
| VELVETFRUIT_EXTRACT | Mark 67 | Mark 22 | 75.000  | 546.000  | 2.071       | 48.402 | 0.867    | 9.306  |
| VELVETFRUIT_EXTRACT | Mark 55 | Mark 22 | 14.000  | 62.000   | 1.581       | 12.446 | 0.857    | 3.917  |
| VELVETFRUIT_EXTRACT | Mark 01 | Mark 55 | 260.000 | 1417.000 | 0.312       | 11.729 | 0.500    | 2.113  |
| VELVETFRUIT_EXTRACT | Mark 55 | Mark 14 | 331.000 | 1763.000 | 0.274       | 11.491 | 0.480    | 2.152  |
| HYDROGEL_PACK       | Mark 14 | Mark 38 | 496.000 | 1989.000 | 0.063       | 2.792  | 0.468    | 0.353  |
| VEV_4000            | Mark 38 | Mark 14 | 207.000 | 412.000  | 0.124       | 2.513  | 0.473    | 0.847  |
| VEV_5200            | Mark 01 | Mark 22 | 11.000  | 34.000   | 0.074       | 0.429  | 0.273    | -0.536 |
| VELVETFRUIT_EXTRACT | Mark 55 | Mark 01 | 244.000 | 1375.000 | 0.001       | 0.054  | 0.418    | -0.015 |
| VEV_6000            | Mark 01 | Mark 22 | 317.000 | 1105.000 | 0.000       | 0.000  | 0.000    |        |
| VEV_6500            | Mark 01 | Mark 22 | 317.000 | 1105.000 | 0.000       | 0.000  | 0.000    |        |
| VEV_5400            | Mark 01 | Mark 22 | 263.000 | 911.000  | -0.010      | -0.298 | 0.171    | -0.569 |

## Same-Product Stability By Day, Horizon 5

| day   | product             | trader  | events  | qty      | q_mean_edge | score   | hit_rate |
| ----- | ------------------- | ------- | ------- | -------- | ----------- | ------- | -------- |
| 1.000 | HYDROGEL_PACK       | Mark 14 | 370.000 | 1467.000 | 0.404       | 15.469  | 0.476    |
| 2.000 | HYDROGEL_PACK       | Mark 14 | 303.000 | 1212.000 | 0.258       | 8.991   | 0.455    |
| 3.000 | HYDROGEL_PACK       | Mark 14 | 330.000 | 1343.000 | -0.195      | -7.163  | 0.436    |
| 1.000 | HYDROGEL_PACK       | Mark 22 | 5.000   | 18.000   | -0.139      | -0.589  | 0.400    |
| 2.000 | HYDROGEL_PACK       | Mark 22 | 8.000   | 32.000   | -3.656      | -20.683 | 0.250    |
| 3.000 | HYDROGEL_PACK       | Mark 22 | 6.000   | 24.000   | -4.083      | -20.004 | 0.167    |
| 1.000 | HYDROGEL_PACK       | Mark 38 | 375.000 | 1485.000 | -0.397      | -15.310 | 0.456    |
| 2.000 | HYDROGEL_PACK       | Mark 38 | 311.000 | 1244.000 | -0.158      | -5.557  | 0.453    |
| 3.000 | HYDROGEL_PACK       | Mark 38 | 336.000 | 1367.000 | 0.264       | 9.750   | 0.473    |
| 1.000 | VELVETFRUIT_EXTRACT | Mark 14 | 211.000 | 1143.000 | 0.000       | 0.000   | 0.436    |
| 2.000 | VELVETFRUIT_EXTRACT | Mark 14 | 210.000 | 1169.000 | -0.272      | -9.301  | 0.338    |
| 3.000 | VELVETFRUIT_EXTRACT | Mark 14 | 226.000 | 1212.000 | -0.156      | -5.429  | 0.389    |
| 1.000 | VELVETFRUIT_EXTRACT | Mark 22 | 50.000  | 335.000  | -1.709      | -31.279 | 0.180    |
| 2.000 | VELVETFRUIT_EXTRACT | Mark 22 | 46.000  | 292.000  | -1.509      | -25.778 | 0.174    |
| 3.000 | VELVETFRUIT_EXTRACT | Mark 22 | 30.000  | 216.000  | -0.368      | -5.409  | 0.367    |
| 1.000 | VELVETFRUIT_EXTRACT | Mark 49 | 40.000  | 380.000  | -1.903      | -37.089 | 0.125    |
| 2.000 | VELVETFRUIT_EXTRACT | Mark 49 | 43.000  | 440.000  | -1.622      | -34.015 | 0.163    |
| 3.000 | VELVETFRUIT_EXTRACT | Mark 49 | 39.000  | 366.000  | -2.133      | -40.797 | 0.128    |
| 1.000 | VELVETFRUIT_EXTRACT | Mark 67 | 58.000  | 519.000  | 2.242       | 51.072  | 0.897    |
| 2.000 | VELVETFRUIT_EXTRACT | Mark 67 | 61.000  | 567.000  | 1.728       | 41.135  | 0.852    |
| 3.000 | VELVETFRUIT_EXTRACT | Mark 67 | 46.000  | 424.000  | 1.908       | 39.289  | 0.717    |

## Voucher-To-VFE Stability By Day, Horizon 5

| day   | source_product | trader  | events | qty     | q_mean_edge | score   | hit_rate |
| ----- | -------------- | ------- | ------ | ------- | ----------- | ------- | -------- |
| 1.000 | VEV_4000       | Mark 01 | 59.000 | 243.000 | 0.502       | 7.826   | 0.441    |
| 2.000 | VEV_4000       | Mark 01 | 56.000 | 232.000 | -0.841      | -12.802 | 0.286    |
| 3.000 | VEV_4000       | Mark 01 | 71.000 | 276.000 | 0.611       | 10.143  | 0.549    |
| 1.000 | VEV_4000       | Mark 14 | 83.000 | 306.000 | 0.005       | 0.086   | 0.434    |
| 2.000 | VEV_4000       | Mark 14 | 69.000 | 306.000 | -1.033      | -18.065 | 0.304    |
| 3.000 | VEV_4000       | Mark 14 | 72.000 | 275.000 | -0.433      | -7.176  | 0.403    |
| 1.000 | VEV_4000       | Mark 22 | 43.000 | 150.000 | -0.483      | -5.920  | 0.465    |
| 2.000 | VEV_4000       | Mark 22 | 42.000 | 171.000 | 0.193       | 2.524   | 0.452    |
| 3.000 | VEV_4000       | Mark 22 | 55.000 | 174.000 | -0.158      | -2.085  | 0.473    |
| 1.000 | VEV_4000       | Mark 55 | 44.000 | 244.000 | 0.109       | 1.696   | 0.432    |
| 2.000 | VEV_4000       | Mark 55 | 51.000 | 272.000 | 0.110       | 1.819   | 0.431    |
| 3.000 | VEV_4000       | Mark 55 | 36.000 | 196.000 | -0.378      | -5.286  | 0.444    |
| 1.000 | VEV_4000       | Mark 67 | 11.000 | 102.000 | 1.745       | 17.625  | 0.818    |
| 2.000 | VEV_4000       | Mark 67 | 8.000  | 74.000  | 2.655       | 22.843  | 1.000    |
| 3.000 | VEV_4000       | Mark 67 | 7.000  | 68.000  | 1.191       | 9.823   | 0.714    |
| 1.000 | VEV_5500       | Mark 01 | 38.000 | 150.000 | 0.087       | 1.061   | 0.500    |
| 2.000 | VEV_5500       | Mark 01 | 37.000 | 145.000 | 0.600       | 7.225   | 0.514    |
| 3.000 | VEV_5500       | Mark 01 | 56.000 | 219.000 | 0.377       | 5.575   | 0.518    |
| 1.000 | VEV_5500       | Mark 14 | 48.000 | 188.000 | 0.072       | 0.985   | 0.417    |
| 2.000 | VEV_5500       | Mark 14 | 52.000 | 224.000 | 0.221       | 3.307   | 0.385    |
| 3.000 | VEV_5500       | Mark 14 | 60.000 | 260.000 | 0.175       | 2.822   | 0.450    |
| 1.000 | VEV_5500       | Mark 22 | 28.000 | 123.000 | -0.862      | -9.558  | 0.321    |
| 2.000 | VEV_5500       | Mark 22 | 39.000 | 137.000 | -0.752      | -8.800  | 0.385    |
| 3.000 | VEV_5500       | Mark 22 | 45.000 | 173.000 | -0.332      | -4.372  | 0.467    |

## Candidate Alpha Interpretation

The JSON weight file maps each product/trader to a directional coefficient. A positive value means follow that trader's public side; a negative value means fade their side. In live code this becomes:

`flow_signal[product] += quantity * (weight[buyer] - weight[seller])`

For VEV voucher rows, the same calculation can be added to a `VELVETFRUIT_EXTRACT` lead signal because a call voucher buy is directionally bullish the underlying.

Candidate file: `candidate_alpha_weights.json`

```json
{
  "same_product_horizon": 5,
  "same_product_weights": {
    "HYDROGEL_PACK": {
      "Mark 14": 0.1599,
      "Mark 38": -0.1039
    },
    "VELVETFRUIT_EXTRACT": {
      "Mark 67": 1.955,
      "Mark 49": -1.8693,
      "Mark 22": -1.296,
      "Mark 14": -0.1439,
      "Mark 01": 0.1574,
      "Mark 55": 0.0649
    }
  },
  "voucher_underlying_target": "VELVETFRUIT_EXTRACT",
  "voucher_underlying_horizon": 5,
  "voucher_underlying_weights": {
    "VEV_4000": {
      "Mark 67": 1.8668,
      "Mark 14": -0.4887,
      "Mark 01": 0.1272,
      "Mark 22": -0.1354,
      "Mark 38": -0.0428,
      "Mark 55": -0.0246
    },
    "VEV_5200": {
      "Mark 22": -0.437,
      "Mark 14": -0.3693
    },
    "VEV_5300": {
      "Mark 55": 0.4947,
      "Mark 22": -0.2453,
      "Mark 01": -0.1904,
      "Mark 14": -0.1312,
      "Mark 38": -0.0353
    },
    "VEV_5400": {
      "Mark 22": -0.4465,
      "Mark 14": -0.1533,
      "Mark 38": -0.0872,
      "Mark 55": -0.0444,
      "Mark 01": 0.0303
    },
    "VEV_5500": {
      "Mark 22": -0.6155,
      "Mark 01": 0.3551,
      "Mark 38": -0.2612,
      "Mark 14": 0.1615,
      "Mark 55": 0.1106
    },
    "VEV_6000": {
      "Mark 01": 0.5824,
      "Mark 38": 0.1995,
      "Mark 22": -0.1637,
      "Mark 14": 0.1175,
      "Mark 55": -0.0371
    },
    "VEV_6500": {
      "Mark 01": 0.5782,
      "Mark 55": 0.4917,
      "Mark 22": -0.1413,
      "Mark 14": 0.1088,
      "Mark 38": 0.1185
    }
  },
  "formula": "signal += quantity * (weight[buyer] - weight[seller])"
}
```
