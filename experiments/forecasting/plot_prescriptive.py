"""Plot completed simulated policy comparisons from saved JSON."""

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("results")
    args = parser.parse_args()
    source = Path(args.results)
    data = json.loads(source.read_text(encoding="utf-8"))
    policies = data["simulation"]["policies"]
    plt.figure(figsize=(8, 4))
    plt.bar([p["policy"] for p in policies], [p["total_relevant_cost"] for p in policies], color="#496db2")
    plt.ylabel("Simulated cost units")
    plt.title("Historical policy simulation")
    plt.tight_layout()
    target = source.parent / "policy_comparison.png"
    plt.savefig(target, dpi=130)
    plt.close()
    print("Saved", target)


if __name__ == "__main__":
    main()
