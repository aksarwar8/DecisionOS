# Prescriptive intelligence learning guide

A point forecast estimates demand. Inventory position combines on-hand and incoming stock. Lead-time demand is the sum of the first L forecast days. The reorder point adds a user-supplied safety stock. If position is at or below that threshold, this prototype orders up to lead-time demand plus seven more forecast days and the buffer. Minimum order and multiples round the result upward.

The projection consumes forecast demand day by day. Incoming stock and new orders arrive after L days. Any demand exceeding stock becomes unfulfilled demand, with no backorders. Shortage exposure uses the supplied shortage cost; holding exposure sums daily stock times holding cost. These numbers are conditional on assumptions and point forecasts. The target service level is recorded for discussion and does not set the buffer or establish a probability.

A budget heuristic ranks estimated avoided shortage cost minus extra holding cost relative to procurement cost, then allocates quantities within the budget and order constraints. It is not an exact integer optimizer. The scenario endpoint can change demand, stock, lead time, procurement and holding costs, service level and budget, reusing the saved forecast.

The historical simulator starts with 28 days for warmup. At each subsequent day it computes demand estimates only from the trailing observed values, receives due orders, places new orders according to a chosen policy, and scores the observed sale. All policies use the same inputs. Historical sales may be censored by unavailable stock, so this evaluation cannot establish real demand or business savings.

Study `src/decisionos/inventory/decisions.py`, `simulation.py`, `backend/services/prescriptive_service.py`, `backend/api/routes/prescriptive.py`, and `frontend/src/Prescriptive.tsx`. The [evaluation](../research/prescriptive_intelligence_evaluation.md) contains the actual bounded example and reproduction commands.

The interval diagnostic used one observed pair before the consumed V1.4.3 final holdout. It does not establish segment-level or population coverage. The decision engine therefore uses deterministic point forecasts and user-specified buffers.

In the implementation, stockout is flagged when forecast demand exceeds available stock on a projected day. Overstock is flagged when inventory position exceeds the total forecast horizon demand plus safety stock. Estimated fill rate is the fraction of point forecast demand projected to be fulfilled; it is not a probability. An optional scenario budget constrains the order and the trajectory is recomputed for the feasible quantity.

A user may save and reload a simulated pair record. It is a local JSON snapshot and carries a simulated label. It is not a source of verified on-hand stock.
