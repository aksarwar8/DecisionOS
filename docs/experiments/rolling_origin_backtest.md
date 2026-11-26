# Rolling-Origin Backtesting — DecisionOS

## 1. Objective

Evaluate the consistency of the hybrid demand forecasting strategy across multiple forecast origins.

## 2. Experimental Setup

- Dataset: M5 sales dataset
- Historical data: January 29 – April 28, 2011
- Forecast horizon: 7 days per fold
- Number of folds: 4
- Total forecast period: April 1–28, 2011
- Evaluation metrics: MAE, RMSE, WAPE

At each forecast origin, the Random Forest was retrained using only the historical data available up to that date.

## 3. Forecast Windows

| Fold | Historical cutoff | Forecast period |
|---|---|---|
| 1 | March 31 | April 1–7 |
| 2 | April 7 | April 8–14 |
| 3 | April 14 | April 15–21 |
| 4 | April 21 | April 22–28 |

## 4. Average Results

| Model | MAE | RMSE | WAPE |
|---|---:|---:|---:|
| Hybrid | **0.5866** | **1.8579** | **73.2290%** |
| Historical Mean | 0.6378 | 2.0575 | 79.7727% |
| Seasonal Naive | 0.6934 | 2.3980 | 86.5833% |
| Random Forest | 0.7492 | 1.8934 | 93.7327% |

Note: WAPE is the arithmetic average of the four fold-level WAPE values.

## 5. Key Findings

1. Hybrid achieved the best MAE, RMSE and WAPE in all four folds.
2. Hybrid consistently outperformed Historical Mean.
3. Random Forest alone showed weaker MAE and WAPE performance than the hybrid strategy.
4. Hybrid achieved an average MAE of 0.5866 and average WAPE of 73.2290%.
5. Results support using demand-segment-based model selection.

## 6. Limitations

- The four folds cover consecutive weeks within one month.
- Additional backtesting across different seasons and demand regimes is required.
- The average WAPE is a macro-average of fold-level WAPE values, not a pooled WAPE.
- Item-level prediction errors may remain substantial.

## 7. Conclusion

The hybrid forecasting strategy is the leading candidate for DecisionOS based on the current rolling-origin experiment. It outperformed the three comparison models across all four forecast windows.

Further testing across longer historical periods is recommended before treating the model as production-ready.
