use crate::{
    data::{Dataset, LoadOptions},
    error::{Result, invalid},
};
use serde::Deserialize;
use serde_json::{Value, json};

pub const ANALYSES: &[&str] = &[
    "overview",
    "describe",
    "missing",
    "correlation",
    "distribution",
    "categorical",
    "outliers",
    "cardinality",
];
#[derive(Debug, Deserialize)]
#[serde(default, deny_unknown_fields)]
pub struct Options {
    pub load: LoadOptions,
    pub analyses: Vec<String>,
    pub correlation: Vec<String>,
    pub percentiles: Vec<f64>,
    pub top: usize,
}
impl Default for Options {
    fn default() -> Self {
        Self {
            load: LoadOptions::default(),
            analyses: vec!["overview".into(), "describe".into(), "missing".into()],
            correlation: vec!["pearson".into()],
            percentiles: vec![0., 25., 50., 75., 100.],
            top: 10,
        }
    }
}
impl Options {
    pub fn validate(&self) -> Result<()> {
        if self.analyses.is_empty()
            || self
                .analyses
                .iter()
                .any(|s| !ANALYSES.contains(&s.as_str()))
        {
            return Err(invalid("select at least one known analysis"));
        }
        if self.top == 0 || self.top > 1000 {
            return Err(invalid("top must be between 1 and 1000"));
        }
        if self.percentiles.len() > 100
            || self
                .percentiles
                .iter()
                .any(|p| !p.is_finite() || !(0. ..=100.).contains(p))
        {
            return Err(invalid(
                "percentiles must be finite values from 0 to 100 (at most 100)",
            ));
        }
        if self.correlation.is_empty()
            || self
                .correlation
                .iter()
                .any(|m| !["pearson", "spearman"].contains(&m.as_str()))
        {
            return Err(invalid("correlation methods must be pearson or spearman"));
        }
        Ok(())
    }
}
fn categorical(column: &crate::data::Column, rows: usize, top: usize) -> Value {
    let mut counts: Vec<_> = column.counts.iter().collect();
    counts.sort_by(|(a, x), (b, y)| y.cmp(x).then(a.cmp(b)));
    let count = rows - column.missing;
    json!({"count": count, "missing":column.missing,"unique":counts.len(),
        "mode":counts.first().map(|(s,_)|s.as_str()),"mode_count":counts.first().map(|(_,n)|**n),
        "top":counts.iter().take(top).map(|(s,n)|json!({"value":s,"count":n,"percentage":100. * **n as f64 / count as f64})).collect::<Vec<_>>()})
}

/// Dispatch each analysis over shared numeric summaries, in canonical order.
pub fn run(data: &Dataset, options: &Options) -> Value {
    use crate::statistics::{Numeric, correlation};
    let selected = |name: &str| options.analyses.iter().any(|s| s == name);
    let need_numeric = ["describe", "distribution", "outliers", "cardinality"]
        .iter()
        .any(|s| selected(s));
    let numeric: Vec<Option<Numeric>> = data
        .columns
        .iter()
        .map(|c| {
            if need_numeric {
                c.numbers.as_ref().map(|v| Numeric::new(v))
            } else {
                None
            }
        })
        .collect();
    let columns: Vec<Value> = data.columns.iter().map(|c| json!({"name":c.name,"type":c.kind,"total":data.rows,"count":data.rows-c.missing,"missing":c.missing,"missing_percentage":100. * c.missing as f64 / data.rows as f64})).collect();
    let mut sections = serde_json::Map::new();
    for &analysis in ANALYSES {
        if !selected(analysis) || analysis == "overview" {
            continue;
        }
        if analysis == "missing" {
            sections.insert(analysis.into(), json!(columns));
            continue;
        }
        if analysis == "correlation" {
            let cols: Vec<_> = data
                .columns
                .iter()
                .filter(|c| c.numbers.is_some())
                .collect();
            let mut matrices = serde_json::Map::new();
            for method in ["pearson", "spearman"] {
                if !options.correlation.iter().any(|m| m == method) {
                    continue;
                }
                let mut cells = vec![vec![Value::Null; cols.len()]; cols.len()];
                for i in 0..cols.len() {
                    for j in i..cols.len() {
                        if let (Some(a), Some(b)) = (&cols[i].numbers, &cols[j].numbers) {
                            let value = correlation(a, b, method);
                            cells[i][j] = value.clone();
                            cells[j][i] = value;
                        }
                    }
                }
                matrices.insert(method.into(),json!({"columns":cols.iter().map(|c|&c.name).collect::<Vec<_>>(),"cells":cells}));
            }
            sections.insert(analysis.into(), json!(matrices));
            continue;
        }
        let mut results = Vec::new();
        for (i, col) in data.columns.iter().enumerate() {
            let n = numeric[i].as_ref();
            let result = match analysis {
                "describe" => n.map(|n| n.describe(col.missing, &options.percentiles)),
                "distribution" => n.map(Numeric::distribution),
                "outliers" => n.map(Numeric::outliers),
                "categorical" if col.numbers.is_none() => {
                    Some(categorical(col, data.rows, options.top))
                }
                "cardinality" => {
                    let unique = n.map_or(col.counts.len(), Numeric::unique);
                    let count = data.rows - col.missing;
                    Some(
                        json!({"count":count,"missing":col.missing,"unique":unique,"unique_percentage":if count>0 {Some(100.*unique as f64/count as f64)} else {None},"constant":unique==1,"likely_identifier":count==data.rows && count>=20 && unique==count}),
                    )
                }
                _ => None,
            };
            if let Some(mut value) = result {
                value["name"] = json!(col.name);
                results.push(value);
            }
        }
        sections.insert(analysis.into(), json!(results));
    }
    json!({"schema_version":1,"rows":data.rows,"column_count":data.columns.len(),"total_missing":data.columns.iter().map(|c|c.missing).sum::<usize>(),"columns":columns,"analyses":ANALYSES.iter().filter(|s|selected(s)).collect::<Vec<_>>(),"sections":sections})
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn category_counts_and_selection() {
        let d = crate::data::load(
            "city,n\nParis,1\nLondon,2\nParis,3\nNA,4\n".as_bytes(),
            &LoadOptions::default(),
        )
        .unwrap();
        let o = Options {
            analyses: vec!["categorical".into(), "cardinality".into()],
            top: 1,
            ..Options::default()
        };
        let r = run(&d, &o);
        assert_eq!(r["sections"]["categorical"][0]["mode"], "Paris");
        assert_eq!(r["sections"]["categorical"][0]["top"][0]["count"], 2);
        assert_eq!(r["sections"]["cardinality"][1]["unique"], 4);
        assert!(r["sections"].get("describe").is_none());
    }
}
