"""Known-value and integration tests for robust, categorical and grouped reports."""

import csv
import io
import math

import pytest
from rushstats import analyze


def test_robust_statistics(csv_file):
    result = analyze(
        csv_file("x\n1\n2\n3\n4\n100\nNA\n"), analyses=["robust"], trim=0.2
    )
    row = result.data["sections"]["robust"][0]
    assert row == {
        "name": "x",
        "count": 5,
        "mad": 1.0,
        "trimmed_mean": 3.0,
        "trim_fraction": 0.2,
        "trimmed_each_tail": 1,
        "retained_count": 3,
    }
    assert "## Robust Statistics" in result.to_markdown()
    assert "## Descriptive Statistics" not in result.to_markdown()


@pytest.mark.parametrize(
    "values,mad,mean",
    [
        ([1], 0, 1),
        ([2, 2, 2, 2], 0, 2),
        ([-4, -2, 0, 2], 2, -1),
        ([-1e308, 1e308], 1e308, 0),
        ([1e12 + 1, 1e12 + 2, 1e12 + 3], 1, 1e12 + 2),
        ([1e-150, 2e-150, 3e-150], 1e-150, 2e-150),
    ],
)
def test_robust_edges(csv_file, values, mad, mean):
    path = csv_file("x\n" + "\n".join(map(str, values)))
    row = analyze(path, analyses=["robust"], trim=0).data["sections"]["robust"][0]
    assert row["mad"] == pytest.approx(mad, abs=0, rel=1e-12)
    assert row["trimmed_mean"] == pytest.approx(mean, abs=0, rel=1e-12)


def test_robust_all_missing(csv_file):
    row = analyze(
        csv_file("x\nNA\nnull\n"), analyses=["robust"], types={"x": "float"}
    ).data["sections"]["robust"][0]
    assert row["mad"] is None and row["trimmed_mean"] is None
    assert row["retained_count"] == 0


def test_trim_floor(csv_file):
    path = csv_file("x\n1\n2\n3\n4\n5\n")
    rows = [
        analyze(path, analyses=["robust"], trim=t).data["sections"]["robust"][0]
        for t in (0.1, 0.2, 0.49)
    ]
    assert [r["trimmed_each_tail"] for r in rows] == [0, 1, 2]
    assert [r["trimmed_mean"] for r in rows] == [3, 3, 3]


def test_entropy_and_dominance(csv_file):
    path = csv_file(
        "city,constant,missing,ok\na,same,NA,true\na,same,NA,TRUE\nb,same,NA,false\nb,same,NA,FALSE\n"
    )
    rows = analyze(path, analyses=["categorical"], top=1).data["sections"][
        "categorical"
    ]
    assert rows[0]["entropy_bits"] == 1
    assert rows[0]["dominant_percentage"] == 50
    assert len(rows[0]["top"]) == 1
    assert rows[1]["entropy_bits"] == 0
    assert rows[1]["dominant_percentage"] == 100
    assert rows[2]["entropy_bits"] is None
    assert rows[2]["dominant_percentage"] is None
    assert rows[3]["entropy_bits"] == 1
    biased = analyze(csv_file("c\na\na\na\nb\n"), analyses=["categorical"]).data[
        "sections"
    ]["categorical"][0]
    assert biased["entropy_bits"] == pytest.approx(
        -0.75 * math.log2(0.75) - 0.25 * math.log2(0.25)
    )


def test_duplicates_decoded_exact_fields(csv_file):
    # Quoting alone does not create a distinct row; missing spellings and numeric
    # spellings do. The extra rows in each class count, not every class member.
    path = csv_file('x,s\n1,NA\n"1",NA\n1,null\n1.0,NA\n1,NA\n1," NA "\n')
    result = analyze(path, analyses=["duplicates"])
    assert result.data["sections"]["duplicates"] == {
        "count": 2,
        "unique_rows": 4,
        "percentage": pytest.approx(100 / 3),
    }
    assert result.data["rows"] == 6
    assert "## Duplicate Rows" in result.to_markdown()
    assert "duplicates" not in analyze(path).data["sections"]


def test_duplicate_field_boundaries(csv_file):
    path = csv_file('a,b\n"a,b",c\na,"b,c"\n"a,b",c\n')
    assert (
        analyze(path, analyses=["duplicates"]).data["sections"]["duplicates"]["count"]
        == 1
    )


def test_grouped_all(csv_file):
    path = csv_file(
        "g,x,city,ok\nA,1,p,true\nA,3,p,FALSE\nA,3,p,FALSE\nB,10,q,true\nB,NA,q,true\nNA,7,r,false\nnull,9,r,false\n"
    )
    result = analyze(
        path, analyses=["all"], group_by=["g"], correlation=["pearson", "spearman"]
    )
    groups = result.data["groups"]
    assert groups["by"] == ["g"]
    assert [g["key"] for g in groups["items"]] == [[None], ["A"], ["B"]]
    missing, a, b = [g["result"] for g in groups["items"]]
    assert [g["rows"] for g in (missing, a, b)] == [2, 3, 2]
    assert a["sections"]["describe"][0]["mean"] == pytest.approx(7 / 3)
    assert a["sections"]["duplicates"]["count"] == 1
    assert a["sections"]["categorical"][2]["mode"] == "false"
    assert b["sections"]["describe"][0]["count"] == 1
    assert b["sections"]["describe"][0]["std"] is None
    assert b["sections"]["missing"][1]["missing_percentage"] == 50
    assert missing["columns"][0]["type"] == "categorical"
    assert missing["sections"]["categorical"][0]["entropy_bits"] is None
    text = result.to_markdown()
    assert "## Grouped Summaries" in text
    assert "#### Descriptive Statistics" in text
    assert text.count("## Methodology") == 1
    assert (
        result.to_markdown()
        == analyze(
            path, analyses=["all"], group_by=["g"], correlation=["pearson", "spearman"]
        ).to_markdown()
    )


def test_group_keys_are_exact_and_multicolumn(csv_file):
    path = csv_file("a,b,x\n01,p,1\n1,p,2\n01,q,3\n01,p,4\n")
    groups = analyze(path, group_by=["a", "b"]).data["groups"]["items"]
    assert [g["key"] for g in groups] == [["01", "p"], ["01", "q"], ["1", "p"]]
    assert groups[0]["result"]["rows"] == 2


def test_group_preserves_global_types(csv_file):
    path = csv_file("g,mixed,n\nA,1,NA\nA,2,null\nB,word,3\n")
    result = analyze(path, analyses=["all"], group_by=["g"])
    a = result.data["groups"]["items"][0]["result"]
    assert [c["type"] for c in a["columns"]] == [
        "categorical",
        "categorical",
        "integer",
    ]
    assert a["sections"]["describe"][0]["mean"] is None
    assert a["sections"]["categorical"][1]["unique"] == 2


def test_group_key_markdown_safety(csv_file):
    content = io.StringIO()
    writer = csv.writer(content)
    writer.writerow(["g", "x"])
    writer.writerow(["<script>|\n# Heading", 1])
    result = analyze(csv_file(content.getvalue()), group_by=["g"])
    text = result.to_markdown()
    assert "<script>" not in text
    assert "\n# Heading" not in text
    assert "&#124;" in text


@pytest.mark.parametrize(
    "kwargs",
    [
        {"trim": -0.1},
        {"trim": 0.5},
        {"trim": float("inf")},
        {"group_by": "g"},
        {"group_by": ["absent"]},
        {"group_by": ["g", "g"]},
        {"max_groups": 0},
        {"max_groups": 10001},
        {"max_groups": 1, "group_by": ["g"]},
    ],
)
def test_invalid_extension_options(csv_file, kwargs):
    with pytest.raises(ValueError):
        analyze(csv_file("g,x\nA,1\nB,2\n"), **kwargs)


def test_group_matches_independent_analysis(csv_file):
    first = "A,1,true,p\nA,3,FALSE,q\nA,3,FALSE,q\nA,NA,true,p\n"
    path = csv_file("g,x,ok,city\n" + first + "B,100,true,z\n")
    options = {"analyses": ["all"], "correlation": ["pearson", "spearman"], "trim": 0.2}
    grouped = analyze(path, group_by=["g"], **options).data["groups"]["items"][0][
        "result"
    ]
    alone = analyze(csv_file("g,x,ok,city\n" + first, name="alone.csv"), **options).data
    assert grouped["sections"] == alone["sections"]


def test_group_without_headers(csv_file):
    result = analyze(
        csv_file("A;1\nA;2\nB;3\n"),
        headers=False,
        delimiter=";",
        group_by=["column_1"],
        max_groups=2,
    )
    assert [g["result"]["rows"] for g in result.data["groups"]["items"]] == [2, 1]
