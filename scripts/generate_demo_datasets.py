from __future__ import annotations

import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"


def generate_housing_sample() -> None:
    """Generate a deterministic housing-style table for demo and tests.

    The values are synthetic, not real personal or commercial data. They are
    designed to look like a small public housing dataset: one row per district,
    with a continuous house price target and several explanatory variables.
    """

    EXAMPLES.mkdir(exist_ok=True)
    output = EXAMPLES / "housing_sample.csv"
    regions = ["east", "west", "north", "south"]
    rows: list[dict[str, object]] = []
    for index in range(120):
        income = round(35 + (index % 40) * 1.35 + (index // 40) * 4.2, 2)
        rooms = round(2.2 + (index % 7) * 0.45, 2)
        house_age = 4 + (index * 3) % 36
        distance_to_center = round(1.5 + (index % 18) * 0.8, 2)
        region = regions[index % len(regions)]
        region_effect = {"east": 22, "west": 8, "north": -6, "south": 4}[region]
        price = round(95 + income * 2.6 + rooms * 18 - house_age * 0.85 - distance_to_center * 2.4 + region_effect, 2)
        rows.append(
            {
                "district_id": f"D{index + 1:03d}",
                "median_house_price": price,
                "median_income": income,
                "avg_rooms": rooms,
                "house_age": house_age,
                "distance_to_center": distance_to_center,
                "region": region,
            }
        )

    with output.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"已生成：{output}")


def main() -> None:
    generate_housing_sample()


if __name__ == "__main__":
    main()
