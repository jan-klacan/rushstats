//! Row selection over already parsed columns; types remain those of the full CSV.
use crate::data::{Column, ColumnType, Dataset};
use std::collections::BTreeMap;

/// Build one temporary group at a time, without rereading or reparsing numeric data.
pub fn subset(data: &Dataset, indices: &[usize]) -> Dataset {
    let columns = data
        .columns
        .iter()
        .map(|col| {
            let numbers = col
                .numbers
                .as_ref()
                .map(|xs| indices.iter().map(|&i| xs[i]).collect::<Vec<_>>());
            let mut counts = BTreeMap::new();
            let missing = if let Some(xs) = &numbers {
                xs.iter().filter(|v| v.is_none()).count()
            } else {
                let mut missing = 0;
                if let Some(labels) = &col.labels {
                    for &i in indices {
                        if let Some(s) = &labels[i] {
                            let key = if col.kind == ColumnType::Boolean {
                                s.trim().to_ascii_lowercase()
                            } else {
                                s.clone()
                            };
                            *counts.entry(key).or_insert(0) += 1;
                        } else {
                            missing += 1;
                        }
                    }
                }
                missing
            };
            Column {
                name: col.name.clone(),
                kind: col.kind,
                numbers,
                counts,
                missing,
                labels: None,
            }
        })
        .collect();
    Dataset {
        columns,
        rows: indices.len(),
        groups: BTreeMap::new(),
        duplicate_flags: data
            .duplicate_flags
            .as_ref()
            .map(|flags| indices.iter().map(|&i| flags[i]).collect()),
    }
}
