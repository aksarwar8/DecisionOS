"""Create pooled comparison tables and plots from saved research predictions."""

import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from src.decisionos.evaluation.characterize import aggregate_level, summarize


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("directory")
    args = parser.parse_args()
    output = Path(args.directory)
    predictions = pd.read_csv(output / "predictions.csv", parse_dates=["date", "origin"])
    predictions["step"] = (predictions.date - predictions.origin).dt.days
    cumulative = pd.concat([predictions[predictions.step <= horizon].assign(horizon=horizon)
                            for horizon in (7, 14, 28)], ignore_index=True)
    predictions["horizon_bucket"] = pd.cut(predictions.step, bins=[0, 7, 14, 28], labels=["1-7", "8-14", "15-28"])
    tables = {
        "horizon_bucket": summarize(predictions, ["method", "horizon_bucket"]),
        "overall": summarize(predictions, ["method"]),
        "horizon": summarize(cumulative, ["method", "horizon"]),
        "origin": summarize(predictions, ["method", "origin"]),
        "segment": summarize(predictions, ["method", "segment"]),
        "intermittency": summarize(predictions, ["method", "classification"]),
        "category": summarize(predictions, ["method", "category"]),
        "state": summarize(predictions, ["method", "state"]),
    }
    levels = {"product_store": ["product_id", "store_id"],"product": ["product_id"], "store": ["store_id"], "category": ["category"],
              "state": ["state"], "sample_total": []}
    hierarchy = []
    for level, dimensions in levels.items():
        table = summarize(aggregate_level(predictions, dimensions), ["method"])
        table["level"] = level
        hierarchy.append(table)
    tables["hierarchy"] = pd.concat(hierarchy, ignore_index=True)
    for name, table in tables.items():
        table.to_csv(output / f"summary_{name}.csv", index=False)
    series = pd.read_csv(output / "series_metrics.csv")
    labels = predictions[["origin", "product_id", "store_id", "segment", "classification",
                          "category", "state"]].drop_duplicates()
    series["origin"] = pd.to_datetime(series["origin"])
    series = series.merge(labels, on=["origin", "product_id", "store_id"], validate="many_to_one")
    for dimension in ("segment", "classification", "category", "state"):
        series.groupby(["method", "horizon", dimension], dropna=False).agg(
            mean_rmsse=("rmsse", "mean"), valid=("rmsse", "count"), total=("rmsse", "size"),
        ).assign(undefined=lambda frame: frame.total - frame.valid).to_csv(output / f"rmsse_{dimension}.csv")
    series.groupby(["method", "horizon"], dropna=False).agg(
        mean_rmsse=("rmsse", "mean"), valid=("rmsse", "count"), total=("rmsse", "size"),
    ).assign(undefined=lambda frame: frame.total - frame.valid).to_csv(output / "summary_rmsse.csv")

    def bars(table, title, filename):
        ax = table.set_index("method")["wape"].sort_values().plot.bar(figsize=(9, 4))
        ax.set(title=title, ylabel="Pooled WAPE (%)", xlabel="")
        plt.tight_layout()
        plt.savefig(output / filename, dpi=130)
        plt.close()

    bars(tables["overall"], "Forecast comparison, sampled cohort", "overall.png")
    for name, column in (("segment", "segment"), ("intermittency", "classification"),
                         ("origin", "origin"), ("hierarchy", "level")):
        pivot = tables[name].pivot(index=column, columns="method", values="wape")
        ax = pivot.plot.bar(figsize=(11, 5), width=0.85)
        ax.set(ylabel="Pooled WAPE (%)", title=name.title())
        ax.legend(fontsize=6, ncol=3)
        plt.tight_layout()
        plt.savefig(output / f"{name}.png", dpi=130)
        plt.close()
    pivot = tables["horizon"].pivot(index="horizon", columns="method", values="wape")
    ax = pivot.plot(marker=".", figsize=(9, 4))
    ax.set(xlabel="Cumulative forecast days", ylabel="Pooled WAPE (%)")
    ax.legend(fontsize=6, ncol=3)
    plt.tight_layout()
    plt.savefig(output / "horizon.png", dpi=130)
    plt.close()
    ax = tables["overall"].set_index("method")["bias"].sort_values().plot.bar(figsize=(9, 4))
    ax.set(ylabel="Mean prediction minus actual (units)", title="Forecast bias")
    plt.tight_layout()
    plt.savefig(output / "bias.png", dpi=130)
    plt.close()
    timings = pd.read_csv(output / "fold_metrics.csv").groupby("method", as_index=False).prediction_seconds.sum()
    performance = tables["overall"].merge(timings, on="method")
    ax = performance.plot.scatter(x="prediction_seconds", y="wape", figsize=(8, 5))
    for row in performance.itertuples():
        ax.annotate(row.method, (row.prediction_seconds, row.wape), fontsize=7)
    ax.set(xlabel="Total inference seconds", ylabel="Pooled WAPE (%)")
    plt.tight_layout()
    plt.savefig(output / "accuracy_latency.png", dpi=130)
    plt.close()
    # Pick a measured high-error pair, using the forest for diagnostic selection.
    forest = predictions[predictions.method == "random_forest"].copy()
    forest["ae"] = (forest.sales_quantity - forest.prediction).abs()
    case = forest.groupby(["product_id", "store_id", "origin"]).ae.sum().idxmax()
    subset = predictions[(predictions.product_id == case[0]) & (predictions.store_id == case[1])
                         & (predictions.origin == case[2])]
    pivot = subset.pivot(index="date", columns="method", values="prediction")
    pivot["actual"] = subset.groupby("date").sales_quantity.first()
    ax = pivot[["actual", "random_forest", "tsb", "moving_average"]].plot(figsize=(10, 4))
    ax.set(ylabel="Units", title=f"High-error forest case: pair {case[0]}/{case[1]}, {case[2].date()}")
    plt.tight_layout()
    plt.savefig(output / "failure_case.png", dpi=130)
    plt.close()


if __name__ == "__main__":
    main()
