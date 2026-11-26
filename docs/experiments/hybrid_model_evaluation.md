# Hybrid Forecasting Model — Final Evaluation

## 1. Objective

Evaluate whether a segment-based hybrid forecasting strategy improves multi-step demand forecasting compared with Historical Mean, Seasonal Naive, and Random Forest models.

## 2. Evaluation Setup

- Dataset: M5 sales dataset
- Training/history period: Through March 31, 2011
- Forecast horizon: April 1–28, 2011
- Evaluation strategy: Recursive 28-day forecasting
- Test observations: 853,720
- Evaluation metrics: MAE, RMSE, WAPE

## 3. Model Selection Strategy

The hybrid model selects forecasting methods based on historical average demand segments.

| Demand Segment | Selected Model |
|---|---|
| Zero average | Historical Mean |
| Low demand | Random Forest |
| Medium demand | Random Forest |
| High demand | Random Forest |

The selection policy was established using validation results before evaluating the April test period.

## 4. Final Test Results

| Model | MAE | RMSE | WAPE |
|---|---:|---:|---:|
| Historical Mean | 0.6514 | 2.1198 | 80.96% |
| Seasonal Naive | 0.7080 | 2.4682 | 88.00% |
| Random Forest | 0.8111 | 2.0222 | 100.81% |
| Hybrid | **0.6198** | **1.9979** | **77.03%** |

## 5. Aggregate Demand Comparison

- Actual demand: 686,877
- Hybrid predicted demand: 699,214.24
- Aggregate overprediction: Approximately 1.80%

## 6. Key Findings

1. The hybrid model achieved the lowest MAE, RMSE, and WAPE among the four evaluated approaches.
2. Random Forest alone performed worse than Historical Mean on MAE and WAPE.
3. Segment-based model selection improved overall forecasting performance.
4. The hybrid model produced aggregate demand estimates close to actual demand.
5. The results are promising but require validation across multiple rolling-origin test periods.

## 7. Limitations

- Evaluation currently covers one 28-day test period.
- Demand-segment thresholds require further investigation.
- Low-demand model selection showed only a small validation advantage.
- Item-level errors may remain significant even when aggregate demand is well calibrated.

## 8. Conclusion

The hybrid forecasting strategy is the best-performing approach in the current experiment. It will be retained as the leading candidate for further backtesting, optimization, and eventual integration into DecisionOS.
