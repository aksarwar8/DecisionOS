"""Lock the predeclared candidate selection using development scores only."""

import argparse
import json
from pathlib import Path

import pandas as pd


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("development_directory")
    args = parser.parse_args()
    root = Path(args.development_directory)
    target = root / "locked_candidates.json"
    if target.exists():
        raise FileExistsError("The existing selection must remain immutable.")
    table = pd.read_csv(root / "summary_overall.csv")
    winners = []
    for prefix in ("tsb_", "sba_", "moving_", "lgb_"):
        group = table[table.method.str.startswith(prefix)]
        if group.empty or group.wape.isna().any():
            raise ValueError(f"Missing or undefined development scores for {prefix}.")
        winners.append(group.sort_values(["wape", "method"]).iloc[0]["method"])
    methods = sorted(set(winners + ["zero", "adaptive", "hurdle", "direct",
                                    "tsb_0.1", "moving_28", "lgb_poisson"]))
    selection = {"selection": "lowest pooled development WAPE by family, plus prespecified policy, "
                               "reference methods, hurdle, direct, and Poisson for development RMSE",
                 "methods": methods, "holdout_origin": "2016-03-27"}
    target.write_text(json.dumps(selection, indent=2), encoding="utf-8")
    print(target)


if __name__ == "__main__":
    main()
