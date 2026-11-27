# Predictive intelligence learning guide

The strategy module exposes the existing hybrid and three statistical methods through a shared pair-history contract. Every history is validated for unique daily observations and a common origin. The moving average and TSB give a constant multi-step forecast, while seasonal naive repeats the last recorded week.

An empirical interval starts by pretending each historical cutoff was the present. It forecasts the next horizon using only observations before that cutoff, then stores absolute errors by lead. The selected order statistic supplies a symmetric half-width around the current forecast. Bounds are clipped at zero. The calibration windows overlap, and 80% nominal coverage covered only 18 of 28 observations in the small synthetic example. Nominal coverage is a configuration, not an observed accuracy claim.

The batch service resolves catalog pairs, enforces the existing pair and forecast-row limits, extracts history, rejects invalid series and predicts chunks. A forecast run is recorded as an atomic JSON snapshot with an identifier and running, completed or failed status. Progress counts are updated after each chunk. The API performs execution synchronously; a second client may poll the run list. A process interruption can leave a run marked running. Failed runs preserve the completed-pair count but do not return incomplete forecasts as a complete result.

The anomaly detector compares each observation to only the prior window. Median and MAD reduce sensitivity to earlier spikes. When MAD is zero, the implementation uses explicit thresholds instead of division by zero. Fourteen consecutive zeros are flagged only after a positive observation with adequate preceding activity. Such a signal does not identify its cause.

The frontend lets users select forecasting methods, request an interval, see a band, save and retrieve bounded batch runs, and investigate demand or price signals. Report downloads reuse loaded results.

Study order: `src/decisionos/ml/strategies.py`, `backend/services/batch_forecast_service.py`, `backend/services/forecast_runs.py`, `src/decisionos/monitoring/anomalies.py`, the API routes and `frontend/src/Forecast.tsx`. The [evaluation](../research/predictive_intelligence_evaluation.md) describes the synthetic and live checks.
