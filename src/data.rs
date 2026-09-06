use crate::error::{Result, invalid};
use serde::{Deserialize, Serialize};
use std::{
    collections::{BTreeMap, HashSet},
    io::{Cursor, Read},
};

#[derive(Clone, Copy, Debug, Deserialize, Serialize, PartialEq)]
#[serde(rename_all = "snake_case")]
pub enum ColumnType {
    Integer,
    Float,
    Boolean,
    Categorical,
    Unknown,
}

#[derive(Debug)]
pub struct Column {
    pub name: String,
    pub kind: ColumnType,
    pub numbers: Option<Vec<Option<f64>>>,
    pub counts: BTreeMap<String, usize>,
    pub missing: usize,
}
#[derive(Debug)]
pub struct Dataset {
    pub columns: Vec<Column>,
    pub rows: usize,
}

#[derive(Debug, Deserialize)]
#[serde(default, deny_unknown_fields)]
pub struct LoadOptions {
    pub delimiter: u8,
    pub headers: bool,
    pub types: BTreeMap<String, ColumnType>,
    pub max_bytes: u64,
}
impl Default for LoadOptions {
    fn default() -> Self {
        Self {
            delimiter: b',',
            headers: true,
            types: BTreeMap::new(),
            max_bytes: 512 * 1024 * 1024,
        }
    }
}

pub fn is_missing(s: &str) -> bool {
    matches!(
        s.trim().to_ascii_lowercase().as_str(),
        "" | "na" | "n/a" | "null" | "nan"
    )
}

// Validate quoting while the csv crate reads the same stream. csv intentionally
// accepts malformed quotes; this adapter enforces a strict, documented dialect.
struct StrictReader<R> {
    inner: R,
    state: u8,
    delimiter: u8,
    bytes: u64,
    limit: u64,
}
impl<R: Read> Read for StrictReader<R> {
    fn read(&mut self, buf: &mut [u8]) -> std::io::Result<usize> {
        use std::io::{Error, ErrorKind};
        if buf.is_empty() {
            return Ok(0);
        }
        let n = self.inner.read(buf)?;
        self.bytes += n as u64;
        if self.bytes > self.limit {
            return Err(Error::new(
                ErrorKind::InvalidData,
                "CSV exceeds max_bytes limit",
            ));
        }
        if n == 0 && self.state == 2 {
            return Err(Error::new(
                ErrorKind::InvalidData,
                "unterminated quoted CSV field",
            ));
        }
        for &b in &buf[..n] {
            self.state = match (self.state, b) {
                (0, b'"') => 2,
                (0 | 1, x) if x == self.delimiter || x == b'\r' || x == b'\n' => 0,
                (1, b'"') => {
                    return Err(Error::new(
                        ErrorKind::InvalidData,
                        "quote inside unquoted CSV field",
                    ));
                }
                (0 | 1, _) => 1,
                (2, b'"') => 3,
                (2, _) => 2,
                (3, b'"') => 2,
                (3, x) if x == self.delimiter || x == b'\r' || x == b'\n' => 0,
                _ => {
                    return Err(Error::new(
                        ErrorKind::InvalidData,
                        "unexpected character after closing CSV quote",
                    ));
                }
            };
        }
        Ok(n)
    }
}

pub fn load(reader: impl Read, options: &LoadOptions) -> Result<Dataset> {
    if !options.delimiter.is_ascii() || matches!(options.delimiter, 0 | b'"' | b'\r' | b'\n') {
        return Err(invalid(
            "delimiter must be one ASCII byte other than NUL, quote, CR or LF",
        ));
    }
    if options.max_bytes == 0 {
        return Err(invalid("max_bytes must be positive"));
    }
    // Consume a possible UTF-8 BOM before quote validation, even when the
    // underlying reader returns one byte at a time. It still counts toward the limit.
    let mut reader = reader;
    let mut prefix = Vec::with_capacity(3);
    reader.by_ref().take(3).read_to_end(&mut prefix)?;
    let bom_bytes = if prefix == b"\xef\xbb\xbf" {
        prefix.clear();
        3
    } else {
        0
    };
    let stream = StrictReader {
        inner: Cursor::new(prefix).chain(reader),
        state: 0,
        delimiter: options.delimiter,
        bytes: bom_bytes,
        limit: options.max_bytes,
    };
    let mut rdr = csv::ReaderBuilder::new()
        .delimiter(options.delimiter)
        .has_headers(options.headers)
        .from_reader(stream);
    let first = rdr.headers()?.clone();
    if first.is_empty() {
        return Err(invalid("empty CSV: no columns"));
    }
    let names: Vec<String> = if options.headers {
        first.iter().map(String::from).collect()
    } else {
        (1..=first.len()).map(|i| format!("column_{i}")).collect()
    };
    let mut seen = HashSet::new();
    for name in &names {
        if name.trim().is_empty() {
            return Err(invalid("column names must not be empty"));
        }
        if !seen.insert(name) {
            return Err(invalid(format!("duplicate column name: {name:?}")));
        }
    }
    for (name, kind) in &options.types {
        if !names.contains(name) {
            return Err(invalid(format!(
                "unknown column in type override: {name:?}"
            )));
        }
        if *kind == ColumnType::Unknown {
            return Err(invalid("unknown is not a valid type override"));
        }
    }
    // Infer over the whole column, retaining only category counts and parsed
    // numeric candidates; no raw table is copied into Python.
    let mut columns: Vec<Column> = names
        .into_iter()
        .map(|name| Column {
            name,
            kind: ColumnType::Unknown,
            numbers: Some(Vec::new()),
            counts: BTreeMap::new(),
            missing: 0,
        })
        .collect();
    let mut integers = vec![true; columns.len()];
    let mut booleans = vec![true; columns.len()];
    let mut rows = 0;
    for record in rdr.records() {
        let record = record?;
        rows += 1;
        for (i, (col, raw)) in columns.iter_mut().zip(record.iter()).enumerate() {
            if is_missing(raw) {
                col.missing += 1;
                if let Some(values) = &mut col.numbers {
                    values.push(None);
                }
                continue;
            }
            let s = raw.trim();
            let number = s.parse::<f64>().ok();
            if number.is_some_and(|n| !n.is_finite())
                && options.types.get(&col.name) != Some(&ColumnType::Categorical)
            {
                return Err(invalid(format!(
                    "non-finite numeric value in column {:?}, data row {rows}; use a categorical override to preserve as text",
                    col.name
                )));
            }
            integers[i] &= s.parse::<i64>().is_ok();
            booleans[i] &= matches!(s.to_ascii_lowercase().as_str(), "true" | "false");
            *col.counts.entry(raw.to_owned()).or_insert(0) += 1;
            if let Some(values) = &mut col.numbers {
                if let Some(n) = number {
                    values.push(Some(n));
                } else {
                    col.numbers = None;
                }
            }
        }
    }
    if rows == 0 {
        return Err(invalid("CSV contains no data rows"));
    }
    for (i, col) in columns.iter_mut().enumerate() {
        col.kind = if col.missing == rows {
            ColumnType::Unknown
        } else if booleans[i] {
            ColumnType::Boolean
        } else if col.numbers.is_some() {
            if integers[i] {
                ColumnType::Integer
            } else {
                ColumnType::Float
            }
        } else {
            ColumnType::Categorical
        };
        if let Some(&kind) = options.types.get(&col.name) {
            let valid = match kind {
                ColumnType::Integer => col.numbers.is_some() && integers[i],
                ColumnType::Float => col.numbers.is_some(),
                ColumnType::Boolean => booleans[i],
                ColumnType::Categorical => true,
                ColumnType::Unknown => false,
            };
            if !valid {
                return Err(invalid(format!(
                    "column {:?} cannot be interpreted as {kind:?}",
                    col.name
                )));
            }
            col.kind = kind;
        }
        if !matches!(col.kind, ColumnType::Float | ColumnType::Integer) {
            col.numbers = None;
        }
        // Numeric uniqueness uses the parsed values. Drop lexical frequency maps
        // before statistics allocate sorted copies and correlation workspaces.
        if col.numbers.is_some() {
            col.counts.clear();
        }
        // Canonicalize boolean categories; numeric uniqueness is computed from f64.
        if col.kind == ColumnType::Boolean {
            let old = std::mem::take(&mut col.counts);
            for (key, n) in old {
                *col.counts
                    .entry(key.trim().to_ascii_lowercase())
                    .or_default() += n;
            }
        }
    }
    Ok(Dataset { columns, rows })
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn inference_and_missing() {
        let d = load(
            "age,amount,ok,city,empty\r\n1,1.5,true,\"東京, JP\",NA\r\n,2,FALSE,Paris,null\r\n"
                .as_bytes(),
            &LoadOptions::default(),
        )
        .unwrap();
        assert_eq!(d.rows, 2);
        assert_eq!(
            d.columns.iter().map(|c| c.kind).collect::<Vec<_>>(),
            vec![
                ColumnType::Integer,
                ColumnType::Float,
                ColumnType::Boolean,
                ColumnType::Categorical,
                ColumnType::Unknown
            ]
        );
        assert_eq!(d.columns[0].missing, 1);
        assert_eq!(d.columns[3].counts["東京, JP"], 1);
    }
    #[test]
    fn malformed_and_empty() {
        for csv in [
            "",
            "a,b\n",
            "a,a\n1,2\n",
            "a,b\n1\n",
            "a\n\"unfinished",
            "a\nfoo\"bar",
            "a\n\"foo\"bar",
            "a\ninf",
        ] {
            assert!(
                load(csv.as_bytes(), &LoadOptions::default()).is_err(),
                "{csv:?}"
            );
        }
    }
    #[test]
    fn dialect_and_limits() {
        let mut o = LoadOptions {
            headers: false,
            delimiter: b';',
            ..LoadOptions::default()
        };
        let d = load("1;\"a\"\"b\nline\"\n2;x\n".as_bytes(), &o).unwrap();
        assert_eq!(d.rows, 2);
        assert_eq!(d.columns[1].counts["a\"b\nline"], 1);
        o.max_bytes = 2;
        assert!(load("1;2".as_bytes(), &o).is_err());
    }
    #[test]
    fn bom_chunk_boundaries_and_numeric_storage() {
        struct ByteReader<'a>(&'a [u8]);
        impl Read for ByteReader<'_> {
            fn read(&mut self, buf: &mut [u8]) -> std::io::Result<usize> {
                let len = buf.len().min(1);
                self.0.read(&mut buf[..len])
            }
        }
        let bytes = b"\xef\xbb\xbf\"x\",city\n1,Paris\n2,London\n";
        let d = load(ByteReader(bytes), &LoadOptions::default()).unwrap();
        assert_eq!(d.columns[0].name, "x");
        assert!(d.columns[0].counts.is_empty());
        assert_eq!(d.columns[0].numbers.as_ref().unwrap().len(), 2);
        assert_eq!(d.columns[1].counts.len(), 2);
        let options = LoadOptions {
            max_bytes: bytes.len() as u64 - 1,
            ..LoadOptions::default()
        };
        assert!(load(ByteReader(bytes), &options).is_err());
        let options = LoadOptions {
            max_bytes: bytes.len() as u64,
            ..LoadOptions::default()
        };
        assert!(load(ByteReader(bytes), &options).is_ok());
    }
    #[test]
    fn missing_tokens() {
        for s in ["", " ", "NA", "n/a", "NULL", " NaN "] {
            assert!(is_missing(s));
        }
        assert!(!is_missing("None"));
        assert!(!is_missing("unknown"));
    }
}
