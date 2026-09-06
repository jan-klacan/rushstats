use std::{error::Error, fmt};

/// Failures are separated into operating-system and invalid-data errors.
#[derive(Debug)]
pub enum StatsError {
    Io(std::io::Error),
    Invalid(String),
}
impl fmt::Display for StatsError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Io(e) => write!(f, "{e}"),
            Self::Invalid(s) => f.write_str(s),
        }
    }
}
impl Error for StatsError {}
impl From<std::io::Error> for StatsError {
    fn from(e: std::io::Error) -> Self {
        Self::Io(e)
    }
}
impl From<csv::Error> for StatsError {
    fn from(e: csv::Error) -> Self {
        Self::Invalid(e.to_string())
    }
}
pub type Result<T> = std::result::Result<T, StatsError>;
pub fn invalid(message: impl Into<String>) -> StatsError {
    StatsError::Invalid(message.into())
}
