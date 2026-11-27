"""Bounded descriptive drift diagnostics; these do not prove model degradation."""

import numpy as np


def distribution_drift(reference, recent, *, bins=10, min_samples=20):
    """Compare finite samples using reference quantile bins and empirical CDFs.

    Missing and infinite values are excluded and counted. PSI uses smoothing;
    constant reference distributions use a single split at the constant value.
    """
    reference = np.asarray(reference, dtype=float).reshape(-1)
    recent = np.asarray(recent, dtype=float).reshape(-1)
    r = reference[np.isfinite(reference)]
    s = recent[np.isfinite(recent)]
    result = {"reference_count": len(r), "recent_count": len(s),
              "reference_missing": len(reference) - len(r), "recent_missing": len(recent) - len(s)}
    if len(r) < min_samples or len(s) < min_samples:
        return {**result, "status": "insufficient_data", "psi": None, "ks": None}
    edges = np.unique(np.quantile(r, np.linspace(0, 1, bins + 1))[1:-1])
    if r.min() == r.max():
        edges = np.array([np.nextafter(r[0], np.inf)])
    edges = np.concatenate(([-np.inf], edges, [np.inf]))
    expected = np.histogram(r, bins=edges)[0].astype(float) + 0.5
    observed = np.histogram(s, bins=edges)[0].astype(float) + 0.5
    expected /= expected.sum()
    observed /= observed.sum()
    psi = np.sum((observed - expected) * np.log(observed / expected))
    values = np.sort(np.concatenate((r, s)))
    ks = np.max(np.abs(np.searchsorted(np.sort(r), values, side="right") / len(r)
                       - np.searchsorted(np.sort(s), values, side="right") / len(s)))
    return {**result, "status": "ok", "psi": float(psi), "ks": float(ks)}
