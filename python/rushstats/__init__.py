"""Rust-powered CSV statistics and deterministic Markdown reports."""

from .api import AnalysisResult, analyze

__version__ = "0.3.0"
__all__ = ["AnalysisResult", "analyze", "__version__"]
