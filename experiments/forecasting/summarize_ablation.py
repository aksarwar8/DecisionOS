"""Summarize matched experimental forecasts and saved statistical references."""

import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.decisionos.evaluation.characterize import aggregate_level, summarize


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("directory")
    parser.add_argument("--reference", default="research_output/stratified_60/predictions.csv")
    args = parser.parse_args()
    output = Path(args.directory)
    data = pd.read_csv(output / "predictions.csv", parse_dates=["date", "origin"])
    reference = pd.read_csv(args.reference, parse_dates=["date", "origin"])
    reference = reference[reference.method.isin(["tsb", "moving_average", "random_forest", "hybrid", "lightgbm"])]
    reference["method"] = "V141_" + reference["method"]
    keys = ["origin", "product_id", "store_id", "date", "sales_quantity"]
    actual = data[data.method == "A_canonical"][keys]
    observed = reference[reference.method == "V141_tsb"][keys]
    aligned = actual.merge(observed, on=keys, validate="one_to_one", how="outer", indicator=True)
    if not aligned["_merge"].eq("both").all():
        raise ValueError("Reference targets do not match ablation targets.")
    # V1.4.1 classifications are recalculated from each training window.
    stats = reference[reference.method == "V141_tsb"][
        ["origin", "product_id", "store_id", "segment", "classification"]
    ].drop_duplicates()
    data = data.drop(columns=["segment", "classification"], errors="ignore").merge(
        stats, on=["origin", "product_id", "store_id"], validate="many_to_one")
    all_data = pd.concat([data, reference], ignore_index=True)
    all_data["step"] = (all_data.date - all_data.origin).dt.days
    cumulative = pd.concat([all_data[all_data.step <= n].assign(horizon=n) for n in (7, 14, 28)])
    for name, frame, groups in (
        ("overall", all_data, ["method"]),
        ("horizon", cumulative, ["method", "horizon"]),
        ("origin", all_data, ["method", "origin"]),
        ("segment", all_data, ["method", "segment"]),
        ("classification", all_data, ["method", "classification"]),
    ):
        summarize(frame, groups).to_csv(output / f"summary_{name}.csv", index=False)
    hierarchy = []
    for level, dimensions in {"product_store": ["product_id", "store_id"], "product": ["product_id"],
                               "store": ["store_id"], "category": ["category"], "state": ["state"],
                               "sample_total": []}.items():
        result = summarize(aggregate_level(all_data, dimensions), ["method"])
        result["level"] = level
        hierarchy.append(result)
    pd.concat(hierarchy).to_csv(output / "summary_hierarchy.csv", index=False)
    scores = pd.read_csv(output / "series_metrics.csv")
    scores.groupby(["method", "horizon"]).agg(mean_rmsse=("rmsse", "mean"),
                                               valid=("rmsse", "count"),
                                               total=("rmsse", "size")).assign(
        undefined=lambda x: x.total - x.valid).to_csv(output / "summary_rmsse.csv")
    importance = pd.read_csv(output / "importance.csv")
    importance.groupby(["config", "feature"])[["gain", "split"]].sum().reset_index().to_csv(
        output / "summary_importance.csv", index=False)
    combined = importance[importance.config == "F_combined"].groupby("feature")["gain"].sum().nlargest(15)
    ax = combined.sort_values().plot.barh(figsize=(9, 5), color="#447a70")
    ax.set_xlabel("Total training gain across folds")
    ax.set_title("Combined-model feature importance")
    plt.tight_layout()
    plt.savefig(output / "feature_gain.png", dpi=140)
    plt.close()
    result = pd.read_csv(output / "summary_overall.csv").sort_values("wape")
    ax = result.set_index("method")["wape"].plot.bar(figsize=(10, 4), color="#405eae")
    ax.set_ylabel("Pooled WAPE (%)")
    ax.set_title("Matched development cohort")
    plt.tight_layout()
    plt.savefig(output / "ablation_comparison.png", dpi=140)
    plt.close()
    case = all_data[(all_data.product_id == 2948) & (all_data.store_id == 10)
                    & (all_data.origin == pd.Timestamp("2015-10-31"))]
    if not case.empty:
        pivot = case.pivot(index="date", columns="method", values="prediction")
        pivot["actual"] = case.groupby("date").sales_quantity.first()
        chosen = [x for x in ["actual", "A_canonical", "B_demand", "F_combined",
                              "V141_random_forest", "V141_tsb"] if x in pivot]
        ax = pivot[chosen].plot(figsize=(10, 4))
        ax.set_ylabel("Units")
        ax.set_title("Product 2948 / store 10 — exploratory failure case")
        plt.tight_layout()
        plt.savefig(output / "failure_2948_10.png", dpi=140)
        plt.close()
    print(result[["method", "mae", "rmse", "wape", "bias"]].round(3).to_string(index=False))
    print("Aligned target keys per method:", len(actual))
    print("Undefined mean RMSSE cases:", int(np.isnan(scores.rmsse).sum()))


if __name__ == "__main__":
    main()
