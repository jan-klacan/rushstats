import math
import statistics

import pytest
from rushstats import analyze


def test_complete_known_dataset(csv_file):
    path = csv_file(
        "x,y,city,ok\n1,2,Paris,true\n2,4,London,false\n3,6,Paris,TRUE\n4,8,,false\n"
    )
    result = analyze(path, analyses=["all"], correlation=["pearson", "spearman"])
    d = result.data
    assert d["rows"] == 4
    assert d["total_missing"] == 1
    assert [c["type"] for c in d["columns"]] == [
        "integer",
        "integer",
        "categorical",
        "boolean",
    ]
    x = d["sections"]["describe"][0]
    for key, expected in {
        "mean": 2.5,
        "variance": 5 / 3,
        "std": math.sqrt(5 / 3),
        "min": 1,
        "max": 4,
        "range": 3,
        "q1": 1.75,
        "median": 2.5,
        "q3": 3.25,
        "iqr": 1.5,
    }.items():
        assert x[key] == pytest.approx(expected)
    for method in ("pearson", "spearman"):
        assert d["sections"]["correlation"][method]["cells"][0][1][
            "value"
        ] == pytest.approx(1)
    dist = d["sections"]["distribution"][0]
    assert dist["skewness"] == pytest.approx(0)
    assert dist["excess_kurtosis"] == pytest.approx(-1.2)
    cat = d["sections"]["categorical"][0]
    assert cat["mode"] == "Paris"
    assert cat["mode_count"] == 2
    assert cat["top"][0]["percentage"] == pytest.approx(200 / 3)
    assert (
        result.to_markdown()
        == analyze(
            path, analyses=["all"], correlation=["pearson", "spearman"]
        ).to_markdown()
    )


@pytest.mark.parametrize(
    "text",
    [
        "",
        "a,b\n",
        "a,a\n1,2\n",
        "a,b\n1\n",
        "a\n1,2\n",
        'a\n"oops',
        'a\n"x"z\n',
        'a\nx"y\n',
        ",b\n1,2\n",
    ],
)
def test_invalid_csv(csv_file, text):
    with pytest.raises(ValueError):
        analyze(csv_file(text))


@pytest.mark.parametrize("value", ["inf", "-Infinity", "1e999"])
def test_nonfinite_rejected(csv_file, value):
    path = csv_file(f"x\n{value}\n")
    with pytest.raises(ValueError, match="non-finite"):
        analyze(path)
    assert (
        analyze(path, types={"x": "categorical"}).data["columns"][0]["type"]
        == "categorical"
    )


def test_missing_and_mixed(csv_file):
    d = analyze(
        csv_file("x,y,z\n1,NA,word\n,NaN,3\n2,null,4\nN/A,,5\n"), analyses=["all"]
    ).data
    assert [c["type"] for c in d["columns"]] == ["integer", "unknown", "categorical"]
    assert d["columns"][0]["missing_percentage"] == 50
    assert d["sections"]["describe"][0]["mean"] == 1.5
    assert d["sections"]["cardinality"][1]["unique_percentage"] is None


def test_all_missing_numeric_override(csv_file):
    result = analyze(csv_file("x\nNA\nnull\n"), types={"x": "float"}, analyses=["all"])
    x = result.data["sections"]["describe"][0]
    assert x["count"] == 0 and x["mean"] is None
    assert "—" in result.to_markdown()


@pytest.mark.parametrize(
    "values",
    [
        [1],
        [2, 2, 2, 2],
        [-9, -1, 0, 2, 10],
        [1e12 + 1, 1e12 + 2, 1e12 + 3],
        [1e-150, 2e-150, 3e-150],
    ],
)
def test_reference_statistics(csv_file, values):
    x = analyze(csv_file("x\n" + "\n".join(map(str, values)))).data["sections"][
        "describe"
    ][0]
    assert x["mean"] == pytest.approx(statistics.mean(values), rel=1e-12, abs=0)
    assert x["median"] == statistics.median(values)
    if len(values) > 1:
        assert x["variance"] == pytest.approx(
            statistics.variance(values), rel=1e-12, abs=0
        )
        assert x["std"] == pytest.approx(statistics.stdev(values), rel=1e-12, abs=0)
    else:
        assert x["std"] is None


def test_extreme_and_constant(csv_file):
    r = analyze(csv_file("x,c\n-1e308,2\n1e308,2\n"), analyses=["all"])
    x = r.data["sections"]["describe"][0]
    assert x["mean"] == 0
    assert x["std"] == pytest.approx(math.sqrt(2) * 1e308)
    assert x["variance"] is None
    assert "zero variance" in r.to_markdown()


def test_pairwise_tied_spearman(csv_file):
    d = analyze(
        csv_file("x,y\n1,1\n1,2\n2,3\n3,NA\nNA,10\n"),
        analyses=["correlation"],
        correlation=["spearman"],
    ).data
    pair = d["sections"]["correlation"]["spearman"]["cells"][0][1]
    assert pair["count"] == 3
    assert pair["value"] == pytest.approx(math.sqrt(3) / 2)


def test_outliers_cardinality_duplicates(csv_file):
    d = analyze(csv_file("x,s\n0,a\n0,a\n1,a\n2,b\n100,c\n"), analyses=["all"]).data
    assert d["rows"] == 5
    assert d["sections"]["outliers"][0]["count"] == 1
    assert d["sections"]["outliers"][0]["percentage"] == 20
    assert d["sections"]["cardinality"][0]["unique"] == 4
    assert d["sections"]["cardinality"][0]["unique_percentage"] == 80


def test_identifier_and_numeric_canonicalization(csv_file):
    d = analyze(
        csv_file("id\n" + "\n".join(map(str, range(20)))), analyses=["cardinality"]
    ).data
    assert d["sections"]["cardinality"][0]["likely_identifier"]
    d = analyze(csv_file("x\n0\n-0\n1\n1.0\n"), analyses=["cardinality"]).data
    assert d["sections"]["cardinality"][0]["unique"] == 2


def test_override_dialect_metadata(csv_file):
    path = csv_file('001;"Paris; FR"\n002;Tokyo\n')
    r = analyze(
        path,
        headers=False,
        delimiter=";",
        types={"column_1": "categorical"},
        target="column_1",
        date_column="column_2",
        description="Example",
    )
    assert r.data["rows"] == 2
    assert "metadata only" in r.to_markdown()
    assert "Example" in r.to_markdown()


@pytest.mark.parametrize(
    "kwargs",
    [
        {"analyses": []},
        {"analyses": ["oops"]},
        {"analyses": "all"},
        {"types": {"absent": "float"}},
        {"types": {"x": "date"}},
        {"types": {"x": "unknown"}},
        {"top": 0},
        {"top": 1001},
        {"percentiles": [-1]},
        {"percentiles": [101]},
        {"percentiles": [float("nan")]},
        {"delimiter": "💡"},
        {"delimiter": "\n"},
        {"delimiter": ""},
        {"correlation": ["kendall"]},
        {"correlation": "pearson"},
        {"target": "absent"},
        {"date_column": "absent"},
        {"max_bytes": 1},
    ],
)
def test_bad_options(csv_file, kwargs):
    with pytest.raises(ValueError):
        analyze(csv_file("x\n1\n"), **kwargs)


def test_invalid_override(csv_file):
    with pytest.raises(ValueError, match="cannot be interpreted"):
        analyze(csv_file("x\nword\n"), types={"x": "float"})


def test_file_errors(tmp_path):
    with pytest.raises(FileNotFoundError):
        analyze(tmp_path / "absent.csv")
    path = tmp_path / "bad.csv"
    path.write_bytes(b"x\n\xff\n")
    with pytest.raises(ValueError):
        analyze(path)


@pytest.mark.parametrize("headers", [True, False])
def test_utf8_bom_quoted_first_field(csv_file, headers):
    path = csv_file('\ufeff"x",y\n1,2\n')
    result = analyze(path, headers=headers)
    assert result.data["rows"] == (1 if headers else 2)
    assert result.data["columns"][0]["name"] == ("x" if headers else "column_1")


def test_extreme_outlier_fence_cancellation(csv_file):
    path = csv_file("x\n-1.7e308\n-1.7e308\n-1e308\n-4e307\n1.7e308\n")
    row = analyze(path, analyses=["outliers"]).data["sections"]["outliers"][0]
    assert row["lower"] is None
    assert row["upper"] == pytest.approx(1.55e308)
    assert row["count"] == 1
    assert row["percentage"] == 20


@pytest.mark.parametrize("seed", range(8))
def test_deterministic_differential_statistics(csv_file, seed):
    import random

    rng = random.Random(seed)
    xs = [rng.uniform(-1000, 1000) for _ in range(50)]
    ys = [0.3 * x + rng.uniform(-200, 200) for x in xs]
    path = csv_file("x,y\n" + "\n".join(f"{x},{y}" for x, y in zip(xs, ys)))
    result = analyze(path, analyses=["describe", "correlation"])
    x = result.data["sections"]["describe"][0]
    assert x["mean"] == pytest.approx(statistics.mean(xs), rel=1e-12, abs=1e-12)
    assert x["variance"] == pytest.approx(statistics.variance(xs), rel=1e-12)
    assert [x["q1"], x["median"], x["q3"]] == pytest.approx(
        statistics.quantiles(xs, method="inclusive"), rel=1e-12, abs=1e-12
    )
    pair = result.data["sections"]["correlation"]["pearson"]["cells"][0][1]
    assert pair["value"] == pytest.approx(statistics.correlation(xs, ys), abs=1e-12)
