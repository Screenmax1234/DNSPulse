"""
Output formatting for DNS benchmark results.

Provides multiple output formats:
- JSON: Machine-readable full results
- CSV: Spreadsheet-compatible timing data
- Human-readable: Rich terminal tables and summaries
"""

import csv
import json
from datetime import datetime
from io import StringIO
from pathlib import Path
from typing import Optional, TextIO

from .models import BenchmarkResult, ResolverStats, Transport
from .statistics import StatisticsEngine


class JSONOutput:
    """JSON output formatter."""
    
    @staticmethod
    def format(result: BenchmarkResult, indent: int = 2) -> str:
        """
        Format benchmark result as JSON.
        
        Args:
            result: BenchmarkResult to format
            indent: JSON indentation level
            
        Returns:
            JSON string
        """
        data = {
            "metadata": {
                "started_at": result.started_at.isoformat(),
                "completed_at": result.completed_at.isoformat(),
                "duration_seconds": result.duration_seconds,
                "test_mode": result.test_mode,
                "domains_tested": result.domains_tested,
                "queries_per_resolver": result.queries_per_resolver,
                "runs": result.runs,
                "parallel_queries": result.parallel_queries,
            },
            "resolvers": [],
        }
        
        for stats in result.resolver_stats:
            resolver_data = {
                "name": stats.resolver.name,
                "ip": stats.resolver.ipv4,
                "transport": stats.transport.value,
                "queries": {
                    "total": stats.total_queries,
                    "successful": stats.successful_queries,
                    "failed": stats.failed_queries,
                    "success_rate_pct": round(stats.success_rate, 2),
                },
                "latency_ms": {
                    "min": round(stats.min_latency, 3),
                    "max": round(stats.max_latency, 3),
                    "avg": round(stats.avg_latency, 3),
                    "median": round(stats.median_latency, 3),
                    "p95": round(stats.p95_latency, 3),
                    "p99": round(stats.p99_latency, 3),
                    "stddev": round(stats.stddev_latency, 3),
                    "jitter": round(stats.jitter_ms, 3),
                },
                "failures": {
                    "timeouts": stats.timeout_count,
                    "nxdomain": stats.nxdomain_count,
                    "errors": stats.error_count,
                },
            }
            data["resolvers"].append(resolver_data)
        
        # Add comparison
        comparison = StatisticsEngine.compare_resolvers(result.resolver_stats)
        if comparison["winner"]:
            data["winner"] = {
                "name": comparison["winner"].resolver.name,
                "avg_latency_ms": round(comparison["winner"].avg_latency, 3),
                "improvements_pct": {
                    k: round(v, 2) for k, v in comparison.get("improvements", {}).items()
                },
            }
        
        return json.dumps(data, indent=indent)
    
    @staticmethod
    def save(result: BenchmarkResult, path: Path) -> None:
        """Save benchmark result to JSON file."""
        with open(path, "w") as f:
            f.write(JSONOutput.format(result))


class CSVOutput:
    """CSV output formatter."""
    
    @staticmethod
    def format(result: BenchmarkResult) -> str:
        """
        Format benchmark result as CSV.
        
        Args:
            result: BenchmarkResult to format
            
        Returns:
            CSV string
        """
        output = StringIO()
        writer = csv.writer(output)
        
        # Header
        writer.writerow([
            "resolver",
            "ip",
            "transport",
            "total_queries",
            "successful",
            "failed",
            "success_rate_pct",
            "min_ms",
            "max_ms",
            "avg_ms",
            "median_ms",
            "p95_ms",
            "p99_ms",
            "stddev_ms",
            "jitter_ms",
            "timeouts",
            "errors",
        ])
        
        # Data rows
        for stats in result.resolver_stats:
            writer.writerow([
                stats.resolver.name,
                stats.resolver.ipv4,
                stats.transport.value,
                stats.total_queries,
                stats.successful_queries,
                stats.failed_queries,
                round(stats.success_rate, 2),
                round(stats.min_latency, 3),
                round(stats.max_latency, 3),
                round(stats.avg_latency, 3),
                round(stats.median_latency, 3),
                round(stats.p95_latency, 3),
                round(stats.p99_latency, 3),
                round(stats.stddev_latency, 3),
                round(stats.jitter_ms, 3),
                stats.timeout_count,
                stats.error_count,
            ])
        
        return output.getvalue()
    
    @staticmethod
    def format_raw(result: BenchmarkResult) -> str:
        """
        Format raw query results as CSV.
        
        Includes every individual query with full timing data.
        
        Args:
            result: BenchmarkResult with raw_results
            
        Returns:
            CSV string
        """
        output = StringIO()
        writer = csv.writer(output)
        
        # Header
        writer.writerow([
            "timestamp",
            "resolver",
            "transport",
            "domain",
            "record_type",
            "status",
            "total_ms",
            "connection_ms",
            "query_ms",
            "ttl",
            "answer_count",
        ])
        
        # Data rows
        for query in result.raw_results:
            writer.writerow([
                query.timestamp.isoformat(),
                query.resolver.name,
                query.transport.value,
                query.domain,
                query.record_type.value,
                query.status.value,
                round(query.timing.total_ms, 3),
                round(query.timing.connection_ms, 3),
                round(query.timing.query_ms, 3),
                query.ttl or "",
                len(query.answers),
            ])
        
        return output.getvalue()
    
    @staticmethod
    def save(result: BenchmarkResult, path: Path, include_raw: bool = False) -> None:
        """Save benchmark result to CSV file(s)."""
        with open(path, "w", newline="") as f:
            f.write(CSVOutput.format(result))
        
        if include_raw:
            raw_path = path.with_suffix(".raw.csv")
            with open(raw_path, "w", newline="") as f:
                f.write(CSVOutput.format_raw(result))


class ConsoleOutput:
    """Rich console output formatter."""
    
    @staticmethod
    def format(result: BenchmarkResult) -> str:
        """
        Format benchmark result for console display.
        
        Uses rich formatting for tables and colors.
        
        Args:
            result: BenchmarkResult to format
            
        Returns:
            Formatted string for console output
        """
        lines = []
        
        # Header
        lines.append("")
        lines.append("=" * 70)
        lines.append("                DNS RESOLVER BENCHMARK RESULTS")
        lines.append("=" * 70)
        lines.append("")
        
        # Metadata
        lines.append(f"  Test Mode: {result.test_mode.upper()}")
        lines.append(f"  Duration: {result.duration_seconds:.1f}s")
        lines.append(f"  Domains Tested: {result.domains_tested}")
        lines.append(f"  Runs: {result.runs}")
        lines.append(f"  Parallel Queries: {result.parallel_queries}")
        lines.append("")
        lines.append("-" * 70)
        
        # Results per resolver
        for stats in result.resolver_stats:
            lines.append("")
            lines.append(f"  {stats.resolver.name} ({stats.resolver.ipv4})")
            lines.append(f"  Transport: {stats.transport.value.upper()}")
            lines.append(f"  ├── Queries: {stats.total_queries} | "
                        f"Success: {stats.successful_queries} ({stats.success_rate:.1f}%)")
            lines.append(f"  ├── Latency: min={stats.min_latency:.1f}ms, "
                        f"avg={stats.avg_latency:.1f}ms, "
                        f"max={stats.max_latency:.1f}ms")
            lines.append(f"  ├── Percentiles: "
                        f"p50={stats.median_latency:.1f}ms, "
                        f"p95={stats.p95_latency:.1f}ms, "
                        f"p99={stats.p99_latency:.1f}ms")
            lines.append(f"  └── Jitter: {stats.jitter_ms:.1f}ms | "
                        f"Timeouts: {stats.timeout_count}")
            lines.append("")
        
        lines.append("-" * 70)
        
        # Winner
        comparison = StatisticsEngine.compare_resolvers(result.resolver_stats)
        winner = comparison.get("winner")
        
        if winner:
            lines.append("")
            lines.append(f"  🏆 WINNER: {winner.resolver.name}")
            lines.append(f"     Average Latency: {winner.avg_latency:.1f}ms")
            lines.append(f"     Success Rate: {winner.success_rate:.1f}%")
            
            improvements = comparison.get("improvements", {})
            if improvements:
                lines.append("")
                lines.append("  Performance Comparison:")
                for name, pct in improvements.items():
                    lines.append(f"     vs {name}: {pct:.1f}% faster")
        else:
            lines.append("")
            lines.append("  ⚠️  No successful queries - cannot determine winner")
        
        lines.append("")
        lines.append("=" * 70)
        lines.append("")
        
        return "\n".join(lines)
    
    @staticmethod
    def print(result: BenchmarkResult) -> None:
        """Print benchmark result to console."""
        print(ConsoleOutput.format(result))


class RichConsoleOutput:
    """Rich library console output with colors and tables."""
    
    @staticmethod
    def print(result: BenchmarkResult) -> None:
        """
        Print benchmark result using rich library.
        
        Falls back to ConsoleOutput if rich is not available.
        """
        try:
            from rich.console import Console
            from rich.panel import Panel
            from rich.table import Table
            from rich import box
        except ImportError:
            ConsoleOutput.print(result)
            return
        
        console = Console()
        
        # Header panel
        console.print()
        console.print(Panel.fit(
            "[bold blue]DNS RESOLVER BENCHMARK RESULTS[/bold blue]",
            border_style="blue",
        ))
        console.print()
        
        # Metadata
        console.print(f"  [dim]Test Mode:[/dim] [cyan]{result.test_mode.upper()}[/cyan]")
        console.print(f"  [dim]Duration:[/dim] {result.duration_seconds:.1f}s")
        console.print(f"  [dim]Domains:[/dim] {result.domains_tested} | "
                     f"[dim]Runs:[/dim] {result.runs} | "
                     f"[dim]Parallel:[/dim] {result.parallel_queries}")
        console.print()
        
        # Results table
        table = Table(
            title="Resolver Performance",
            box=box.ROUNDED,
            header_style="bold magenta",
        )
        
        table.add_column("Resolver", style="cyan")
        table.add_column("Transport", style="dim")
        table.add_column("Queries", justify="right")
        table.add_column("Success", justify="right")
        table.add_column("Avg (ms)", justify="right", style="green")
        table.add_column("p95 (ms)", justify="right", style="yellow")
        table.add_column("p99 (ms)", justify="right", style="red")
        table.add_column("Jitter", justify="right")
        
        for stats in result.resolver_stats:
            table.add_row(
                stats.resolver.name,
                stats.transport.value.upper(),
                str(stats.total_queries),
                f"{stats.success_rate:.1f}%",
                f"{stats.avg_latency:.1f}",
                f"{stats.p95_latency:.1f}",
                f"{stats.p99_latency:.1f}",
                f"{stats.jitter_ms:.1f}ms",
            )
        
        console.print(table)
        console.print()
        
        # Winner
        comparison = StatisticsEngine.compare_resolvers(result.resolver_stats)
        winner = comparison.get("winner")
        
        if winner:
            console.print(Panel(
                f"[bold green]🏆 WINNER: {winner.resolver.name}[/bold green]\n"
                f"Average Latency: {winner.avg_latency:.1f}ms | "
                f"Success Rate: {winner.success_rate:.1f}%",
                border_style="green",
            ))
        else:
            console.print(Panel(
                "[bold yellow]⚠️ No successful queries - cannot determine winner[/bold yellow]",
                border_style="yellow",
            ))
        
        console.print()
