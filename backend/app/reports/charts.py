from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt


def create_metric_chart(
    values: list[tuple[str, float]],
    output_path: Path,
    title: str,
    ylabel: str,
) -> Path | None:
    if not values:
        return None

    if not all(
        isinstance(value, (int, float))
        for _, value in values
    ):
        return None

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    labels = [
        label
        for label, _ in values
    ]

    numbers = [
        float(number)
        for _, number in values
    ]

    figure, axis = plt.subplots(
        figsize=(8, 4.5)
    )

    axis.bar(
        labels,
        numbers,
    )

    axis.set_title(title)
    axis.set_ylabel(ylabel)
    axis.tick_params(
        axis="x",
        rotation=30,
    )

    figure.tight_layout()
    figure.savefig(
        output_path,
        dpi=160,
    )

    plt.close(figure)

    return output_path