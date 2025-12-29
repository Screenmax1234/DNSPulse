"""
DNS Speed Checker - Real-world DNS resolver benchmarking tool.

Measures actual DNS resolution performance, not synthetic benchmarks.
"""

__version__ = "1.0.0"
__author__ = "DNS Speed Checker Team"

from .models import QueryResult, ResolverConfig, BenchmarkResult
from .query_engine import DNSQueryEngine
from .runner import TestRunner

__all__ = [
    "__version__",
    "QueryResult",
    "ResolverConfig", 
    "BenchmarkResult",
    "DNSQueryEngine",
    "TestRunner",
]
