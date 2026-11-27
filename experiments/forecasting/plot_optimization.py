"""Generate charts for the completed optimization comparison."""

import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("directory")
    output = Path(parser.parse_args().directory)
    overall = pd.read_csv(output / "summary_overall.csv").sort_values("wape")
    ax = overall.set_index("method")["wape"].plot.bar(figsize=(11, 4), color="#445fb0")
    ax.set_ylabel("Pooled WAPE (%)")
    plt.tight_layout()
    plt.savefig(output / "model_comparison.png", dpi=130)
    plt.close()
    horizon = pd.read_csv(output / "summary_horizon.csv")
    leaders = overall.method.head(5).tolist()
    ax = horizon[horizon.method.isin(leaders)].pivot(index="horizon", columns="method",
                                                     values="wape").plot(marker="o", figsize=(9, 4))
    ax.set(xlabel="Cumulative forecast days", ylabel="Pooled WAPE (%)")
    plt.tight_layout()
    plt.savefig(output / "horizon_comparison.png", dpi=130)
    plt.close()
    ax = overall.set_index("method")["bias"].sort_values().plot.bar(figsize=(11, 4))
    ax.set_ylabel("Mean prediction minus actual")
    plt.tight_layout()
    plt.savefig(output / "forecast_bias.png", dpi=130)
    plt.close()


if __name__ == "__main__":
    main()
