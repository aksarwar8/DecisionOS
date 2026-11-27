# Production performance evaluation

On 2026-11-26, in-process HTTP checks with the configured PostgreSQL returned readiness in 0.422 s, request metrics in 0.009 s, and a 90-day product 4/store 1 drift diagnostic in 0.253 s. The two 45-observation windows produced PSI 0.0635 and KS distance 0.0667. These are single measurements, not benchmarks or evidence of improved throughput. Previously reported store-risk latency of approximately 21 seconds is historical context.

The new descriptive drift utility reports reference-quantile PSI and a two-sample empirical KS distance on finite values. It explicitly reports insufficient sample sizes. PSI uses additive smoothing and is sensitive to binning and sample size. KS is a distribution distance, not proof of degraded forecast accuracy; see [SciPy's KS documentation](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.ks_2samp.html). Monitoring historical replays is not live production monitoring. Realized prediction error requires correctly aligned observed future targets.

The diagnostic accepts a configurable PSI threshold but is a historical replay, not continuous monitoring. Prediction interval validation, threshold calibration, query plans and batch benchmarks remain unverified.
