# Prescriptive intelligence evaluation

## Research question and data

Can a simple forecast-driven inventory policy improve a simulated stock trajectory compared with fixed and reorder-point rules? The M5 database contains historical sales, not verified inventory, supplier lead times, procurement costs or stockout labels. The values in this experiment are simulated assumptions. Historical observed sales are a proxy for demand and can understate demand when availability was constrained.

The bounded experiment used product 4/store 1, a TSB forecast originating 2016-04-24 and a 28-day horizon. Simulated inputs were stock 12, incoming 0, lead time 7 days, safety stock 8, minimum order 5, order multiple 5, unit cost 2, daily holding cost 0.02 and shortage cost 4. Costs are abstract units because currency metadata is not established. The historical simulation used 2016-02-23 to 2016-04-24 after 28 days of warmup. It uses the trailing 28 actual observations available before each simulated day to make a demand estimate. Demand after that point is used only to score that day. Policies share the same initial assumptions.

| Policy | Fill rate | Stockout days | Unfulfilled units | Ordered units | Holding | Shortage | Procurement | Total cost units |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| No replenishment | 10.3% | 39 | 105 | 0 | 0.78 | 420 | 0 | 420.78 |
| Fixed order | 96.6% | 2 | 4 | 125 | 22.00 | 16 | 250 | 288.00 |
| Reorder point | 98.3% | 2 | 2 | 135 | 22.30 | 8 | 270 | 300.30 |
| Forecast-driven | 99.1% | 1 | 1 | 130 | 19.46 | 4 | 260 | 283.46 |
| Budget-capped forecast | 99.1% | 1 | 1 | 130 | 19.46 | 4 | 260 | 283.46 |

The budget was 500 cost units and did not bind in this run. The results are a single historical replay, not evidence of real savings, reliable service levels or future performance. A different assumed cost structure or initial stock can change rankings. Open orders at the end are charged as procurement but their future stock and value are not included. There is no salvage value or backorder model.

Using the saved forecast, the base recommendation was 30 units, with a 12-unit inventory position and 16.13 units of forecast lead-time demand. The projected 28-day unfulfilled demand was 22.54 units. With demand multiplied by 1.25 and lead time increased by two days, the unconstrained recommendation was 45 and projected shortage 23.67. Applying a budget of 40 cost units limited the order to 20 and increased projected shortage to 48.67. These are deterministic scenarios, not stockout probabilities.

Reorder point is forecast demand over the supplier lead time plus explicitly supplied safety stock. Inventory position is current stock plus incoming stock, with no backorders in this model. The order-up-to target adds seven further forecast days. Reorders are rounded up to the minimum and order multiple. Incoming stock and a new order both arrive after the assumed lead time. A service-level input is recorded but does not calculate safety stock. The [Utah inventory guidance](https://finance.utah.gov/state-agency-resources/policy/08-06_00/) discusses demand, lead time and safety stock in reorder settings. The [University of Texas lost-sales model](https://utw11041.utweb.utexas.edu/ORMM/omie/operation/unit/inventory/deterministic/deter_inf_lost.html) provides context for lost demand and fill rate.

The budget allocation sorts recommendations by estimated shortage-cost reduction less incremental holding cost per procurement cost, then greedily allocates feasible multiples. This is a transparent heuristic with no global optimality guarantee. Its priority uses the full recommended order's simulated benefit; it does not guarantee that a partial order has the same per-unit benefit. The historical budget policy caps orders for one series; it does not solve cross-item allocation over time.

Run locally with the existing configured database:

```powershell
.\.venv\Scripts\python.exe -m experiments.forecasting.prescriptive_evaluation --output research_output/prescriptive_new
.\.venv\Scripts\python.exe -m experiments.forecasting.plot_prescriptive research_output/prescriptive_new/results.json
```

The actual saved data and chart are under ignored `research_output/prescriptive_checks/`. The run does not train or promote a model.

## Predictive dependency diagnostic

A bounded real-data diagnostic used TSB for product 4/store 1 with calibration ending 2016-02-24 and 28 target days 2016-02-25 through 2016-03-23. With 35 calibration origins, the nominal 80% interval achieved 85.71% coverage, mean width 4.19 and interval score 5.40. The nominal 95% interval achieved 100% coverage, width 8.44 and interval score 8.44. This is one selected pair and a historical diagnostic, not an untouched independent holdout or evidence of broad calibration. Deterministic decisions use point forecasts and do not use these bounds.

The direct saved forecast run exposed origin 2016-04-24, complete single-pair coverage, method TSB and builtin model version. The prescriptive service checks each forecast date is consecutive from that origin. An eight-week-old user-supplied scenario may be historical; the response shows the actual origin.

As a cost sensitivity check, reducing the simulated shortage penalty from 4 to 1 per unit changed total cost units to 105.78 for no replenishment, 276.00 for fixed, 294.30 for reorder, and 280.46 for forecast and budget policies. No replenishment still filled only 10.3% of observed sales. This illustrates a cost-versus-service trade-off under chosen assumptions, not a recommendation to accept lost sales.

A temporary local FastAPI instance loaded the current code. A real HTTP POST to the single-pair policy simulation endpoint returned HTTP 200 in 1.659 seconds using PostgreSQL data and produced five policy results. The temporary instance was stopped after verification.
