//! Statistical engine independent of the Python CLI and report renderer.
pub mod analysis;
pub mod data;
pub mod error;
pub mod grouping;
pub mod statistics;

use pyo3::{
    exceptions::{PyOSError, PyValueError},
    prelude::*,
};
use std::path::PathBuf;

/// Read a CSV once in Rust; return only the versioned summary as JSON.
#[pyfunction]
fn analyze_json(py: Python<'_>, path: PathBuf, options_json: &str) -> PyResult<String> {
    let options: analysis::Options =
        serde_json::from_str(options_json).map_err(|e| PyValueError::new_err(e.to_string()))?;
    options.validate().map_err(to_python)?;
    let filename = path.to_string_lossy().into_owned();
    py.detach(move || {
        let file = std::fs::File::open(&path).map_err(error::StatsError::from)?;
        let result = analysis::analyze(file, options)?;
        serde_json::to_string(&result).map_err(|e| error::invalid(e.to_string()))
    })
    .map_err(|e| match e {
        error::StatsError::Io(e) => {
            PyOSError::new_err((e.raw_os_error().unwrap_or(5), e.to_string(), filename))
        }
        other => to_python(other),
    })
}
fn to_python(error: error::StatsError) -> PyErr {
    match error {
        error::StatsError::Io(e) => {
            PyOSError::new_err((e.raw_os_error().unwrap_or(5), e.to_string()))
        }
        error::StatsError::Invalid(s) => PyValueError::new_err(s),
    }
}
#[pymodule]
fn _core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(analyze_json, m)?)?;
    Ok(())
}
