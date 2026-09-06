# Dataset Statistical Report

## Dataset Overview

| Property | Value |
| --- | --- |
| Rows | 5 |
| Columns | 4 |
| Missing values | 2 |

## Column Overview

| Column | Type | Non&#45;missing | Missing |
| --- | --- | --- | --- |
| age | integer | 4 | 1 |
| income | integer | 4 | 1 |
| city | categorical | 5 | 0 |
| active | boolean | 5 | 0 |

## Descriptive Statistics

| Column | Count | Missing | Mean | Std | Variance | Min | Q1 | Median | Q3 | Max | Range | IQR |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| age | 4 | 1 | 30.75 | 8.01561 | 64.25 | 25 | 25 | 28 | 33.75 | 42 | 17 | 8.75 |
| income | 4 | 1 | 58250 | 10210.3 | 1.0425e+08 | 50000 | 50000 | 56000 | 64250 | 71000 | 21000 | 14250 |

### Selected Percentiles

| Column | Percentile | Value |
| --- | --- | --- |
| age | 0 | 25 |
| age | 25 | 25 |
| age | 50 | 28 |
| age | 75 | 33.75 |
| age | 100 | 42 |
| income | 0 | 50000 |
| income | 25 | 50000 |
| income | 50 | 56000 |
| income | 75 | 64250 |
| income | 100 | 71000 |

## Missing Data

| Column | Non&#45;missing | Missing | Missing % | Total |
| --- | --- | --- | --- | --- |
| age | 4 | 1 | 20 | 5 |
| income | 4 | 1 | 20 | 5 |
| city | 5 | 0 | 0 | 5 |
| active | 5 | 0 | 0 | 5 |

## Correlations

### Pearson

| Column | age | income |
| --- | --- | --- |
| age | 1 | 1 |
| income | 1 | 1 |

Complete-pair counts:

| Column | age | income |
| --- | --- | --- |
| age | 4 | 3 |
| income | 3 | 4 |

### Spearman

| Column | age | income |
| --- | --- | --- |
| age | 1 | 1 |
| income | 1 | 1 |

Complete-pair counts:

| Column | age | income |
| --- | --- | --- |
| age | 4 | 3 |
| income | 3 | 4 |

## Distributions

| Column | Count | Unique | Zeros | Skewness | Excess kurtosis | Q1 | Median | Q3 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| age | 4 | 3 | 0 | 1.35096 | 1.19965 | 25 | 28 | 33.75 |
| income | 4 | 3 | 0 | 0.627805 | -2.49242 | 50000 | 56000 | 64250 |

## Categorical Variables

### city

| Count | Missing | Unique | Mode | Mode count | Dominant % | Entropy &#40;bits&#41; |
| --- | --- | --- | --- | --- | --- | --- |
| 5 | 0 | 3 | London | 3 | 60 | 1.37095 |

| Category | Count | Percentage |
| --- | --- | --- |
| London | 3 | 60 |
| Berlin | 1 | 20 |
| Paris | 1 | 20 |

### active

| Count | Missing | Unique | Mode | Mode count | Dominant % | Entropy &#40;bits&#41; |
| --- | --- | --- | --- | --- | --- | --- |
| 5 | 0 | 2 | true | 4 | 80 | 0.721928 |

| Category | Count | Percentage |
| --- | --- | --- |
| true | 4 | 80 |
| false | 1 | 20 |

## IQR Outliers

| Column | Lower bound | Upper bound | Outliers | Outliers % |
| --- | --- | --- | --- | --- |
| age | 11.875 | 46.875 | 0 | 0 |
| income | 28625 | 85625 | 0 | 0 |

## Cardinality

| Column | Non&#45;missing | Missing | Unique | Unique % | Constant | Likely identifier &#40;heuristic&#41; |
| --- | --- | --- | --- | --- | --- | --- |
| age | 4 | 1 | 3 | 75 | No | No |
| income | 4 | 1 | 3 | 75 | No | No |
| city | 5 | 0 | 3 | 60 | No | No |
| active | 5 | 0 | 2 | 40 | No | No |

## Robust Statistics

| Column | Count | MAD | Trimmed mean | Trim fraction per tail | Removed per tail | Retained |
| --- | --- | --- | --- | --- | --- | --- |
| age | 4 | 3 | 30.75 | 0.1 | 0 | 4 |
| income | 4 | 6000 | 58250 | 0.1 | 0 | 4 |

## Duplicate Rows

| Property | Value |
| --- | --- |
| Repeated rows after first occurrence | 1 |
| Duplicate percentage | 20 |
| Unique rows | 4 |

## Methodology

- Missing tokens: empty/whitespace-only, NA, N/A, null, NaN (case-insensitive after trimming). No imputation.
- Count excludes missing values. Missing percentages use all rows; category, outlier and unique percentages use non-missing observations.
- Variance and standard deviation use the sample denominator n−1. Quantiles use Hyndman–Fan type 7 (linear interpolation at (n−1)p).
- Pearson uses centered complete pairs. Spearman ranks those same pairs with average ranks for ties, then applies Pearson. Constant paired columns and fewer than two pairs give undefined correlation. Pairwise deletion can yield a matrix that is not positive semidefinite.
- Skewness is adjusted Fisher–Pearson: sqrt(n(n−1))/(n−2) × m3/m2^(3/2), for n≥3. Excess kurtosis is (n−1)/((n−2)(n−3)) × ((n+1)(m4/m2²−3)+6), for n≥4. Here mk is the mean kth centered power. Both are undefined for constant columns.
- Outliers lie strictly outside Q1−1.5×IQR and Q3+1.5×IQR. A likely identifier has at least 20 rows, no missing values and all values unique; this never changes its type.
- Numeric uniqueness compares float64 values (signed zeros are equal); boolean values are case-normalized; categorical strings preserve whitespace and case. Category ties sort lexicographically.
- MAD is the median absolute deviation from the median, without normal-distribution scaling. The trimmed mean removes floor(n × trim_fraction) observations from each tail; missing values are excluded first.
- Categorical entropy is −Σ p log2(p) in bits over all non-missing categories, regardless of the top-N display limit. A constant has zero entropy; an empty column is undefined. Dominant percentage uses the most frequent category.
- Duplicate rows match all decoded CSV fields exactly, including whitespace and missing-token spelling. Quoting style and record line endings do not affect equality. Counts exclude the first occurrence; percentages use all rows. No rows are dropped.
- Groups use exact decoded key strings, with all missing tokens combined into an explicit missing key. Numeric spellings and boolean case remain distinct group keys. Groups retain the full dataset's column types and are ordered lexicographically, with missing keys first. Each group's percentages and statistics use only its rows.
- Reports use six significant digits and a fixed section order, with no timestamp.

## Notes

— means undefined, insufficient observations, or a result outside the finite float64 range. All-missing columns have unknown type unless overridden. Dates remain text. Numeric calculations use float64; integers beyond 2^53 may lose precision. Outliers and identifier suggestions are heuristics, not proof of data errors. Duplicate rows are retained in all analyses.
