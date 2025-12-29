"""
Command-line interface for DNS Speed Checker.

Provides a user-friendly CLI for running DNS benchmarks
with various options and output formats.
"""

import asyncio
import sys
from pathlib import Path
from typing import Optional

import click

from . import __version__
from .cache_utils import flush_dns_cache, check_elevated_privileges
from .models import RecordType, Transport
from .output import ConsoleOutput, CSVOutput, JSONOutput, RichConsoleOutput
from .resolvers import (
    RESOLVERS,
    DEFAULT_RESOLVERS,
    get_resolver,
    create_custom_resolver,
    list_resolvers,
)
from .runner import TestRunner


def create_progress_callback():
    """Create a progress callback using rich if available."""
    try:
        from rich.progress import Progress, SpinnerColumn, TextColumn
        from rich.console import Console
        
        console = Console()
        progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=True,
        )
        
        task_id = None
        
        def callback(message: str, current: int, total: int):
            nonlocal task_id
            if task_id is None:
                progress.start()
                task_id = progress.add_task(message, total=total)
            progress.update(task_id, description=message, completed=current)
        
        return progress, callback
    except ImportError:
        # Fallback to simple print
        def callback(message: str, current: int, total: int):
            print(f"\r{message} ({current}/{total})", end="", flush=True)
        
        return None, callback


@click.group()
@click.version_option(__version__)
def main():
    """
    DNS Speed Checker - Real-world DNS resolver benchmarking.
    
    Measures actual DNS resolution performance, not synthetic benchmarks.
    Uses Top 100 websites for realistic workload simulation.
    """
    pass


@main.command()
@click.option(
    "--resolver", "-r",
    multiple=True,
    help="Resolver to test (can specify multiple). Options: " + ", ".join(list_resolvers()),
)
@click.option(
    "--custom-resolver", "-c",
    multiple=True,
    help="Custom resolver IP address",
)
@click.option(
    "--transport", "-t",
    multiple=True,
    type=click.Choice(["udp", "tcp", "dot", "doh"]),
    help="Transport protocol to use (can specify multiple)",
)
@click.option(
    "--mode", "-m",
    type=click.Choice(["cold", "warm", "burst", "comprehensive"]),
    default="cold",
    help="Test mode: cold (cache bypass), warm (cached), burst (parallel load), comprehensive (all)",
)
@click.option(
    "--domains", "-d",
    type=int,
    default=30,
    help="Number of domains to test",
)
@click.option(
    "--runs", "-n",
    type=int,
    default=2,
    help="Number of test iterations",
)
@click.option(
    "--parallel", "-p",
    type=int,
    default=10,
    help="Maximum parallel queries",
)
@click.option(
    "--timeout",
    type=float,
    default=5.0,
    help="Query timeout in seconds",
)
@click.option(
    "--output", "-o",
    type=click.Path(),
    help="Output file path (JSON or CSV based on extension)",
)
@click.option(
    "--raw-csv",
    is_flag=True,
    help="Include raw query data in CSV output",
)
@click.option(
    "--no-dnssec",
    is_flag=True,
    help="Disable DNSSEC validation",
)
@click.option(
    "--flush-cache",
    is_flag=True,
    help="Attempt to flush OS DNS cache before testing",
)
@click.option(
    "--quiet", "-q",
    is_flag=True,
    help="Suppress progress output",
)
@click.option(
    "--json",
    is_flag=True,
    help="Output results as JSON to stdout",
)
def run(
    resolver: tuple,
    custom_resolver: tuple,
    transport: tuple,
    mode: str,
    domains: int,
    runs: int,
    parallel: int,
    timeout: float,
    output: Optional[str],
    raw_csv: bool,
    no_dnssec: bool,
    flush_cache: bool,
    quiet: bool,
    json: bool,
):
    """
    Run DNS benchmark tests.
    
    Examples:
    
    \b
      # Quick test with default resolvers
      dns-speedchecker run
    
    \b  
      # Compare specific resolvers
      dns-speedchecker run -r cloudflare -r google -r quad9
    
    \b
      # Test with DoH transport
      dns-speedchecker run -r cloudflare -t doh
    
    \b
      # Comprehensive test with all modes
      dns-speedchecker run --mode comprehensive -n 3
    
    \b
      # Export results to JSON
      dns-speedchecker run -o results.json
    """
    # Parse resolvers
    resolvers_list = []
    
    if resolver:
        for name in resolver:
            try:
                resolvers_list.append(get_resolver(name))
            except ValueError as e:
                click.echo(f"Error: {e}", err=True)
                sys.exit(1)
    
    for ip in custom_resolver:
        resolvers_list.append(create_custom_resolver(ip))
    
    if not resolvers_list:
        # Use defaults
        resolvers_list = [get_resolver(name) for name in DEFAULT_RESOLVERS]
    
    # Parse transports
    if transport:
        transports = [Transport(t) for t in transport]
    else:
        transports = [Transport.UDP]
    
    # Validate transport support
    for res in resolvers_list:
        for trans in transports:
            if not res.supports_transport(trans):
                click.echo(
                    f"Warning: {res.name} does not support {trans.value}",
                    err=True,
                )
    
    # Flush cache if requested
    if flush_cache:
        if not check_elevated_privileges():
            click.echo("Warning: Elevated privileges may be required to flush DNS cache", err=True)
        
        success, message = flush_dns_cache()
        if not quiet:
            click.echo(f"Cache flush: {message}")
    
    # Create progress callback
    progress_ctx, progress_callback = None, None
    if not quiet:
        progress_ctx, progress_callback = create_progress_callback()
    
    # Run benchmark
    runner = TestRunner(
        resolvers=resolvers_list,
        transports=transports,
        timeout=timeout,
        use_dnssec=not no_dnssec,
    )
    
    async def run_benchmark():
        try:
            if mode == "cold":
                return await runner.run_cold_test(
                    domain_count=domains,
                    runs=runs,
                    concurrency=parallel,
                    progress_callback=progress_callback,
                )
            elif mode == "warm":
                return await runner.run_warm_test(
                    domain_count=domains,
                    runs=runs,
                    concurrency=parallel,
                    progress_callback=progress_callback,
                )
            elif mode == "burst":
                return await runner.run_burst_test(
                    burst_size=domains,
                    parallel_queries=parallel,
                    runs=runs,
                    progress_callback=progress_callback,
                )
            elif mode == "comprehensive":
                results = await runner.run_comprehensive_test(
                    domain_count=domains,
                    runs=runs,
                    progress_callback=progress_callback,
                )
                # Return cold results for main display, but include all
                return results
        finally:
            await runner.close()
    
    # Run with progress
    if progress_ctx:
        with progress_ctx:
            results = asyncio.run(run_benchmark())
    else:
        results = asyncio.run(run_benchmark())
    
    if not quiet:
        print()  # Clear progress line
    
    # Handle comprehensive mode results
    if isinstance(results, dict):
        # Comprehensive mode returns multiple results
        for test_mode, result in results.items():
            if not quiet and not json:
                click.echo(f"\n{'=' * 40}")
                click.echo(f"   {test_mode.upper()} TEST RESULTS")
                click.echo(f"{'=' * 40}")
                RichConsoleOutput.print(result)
            
            if output:
                path = Path(output)
                mode_path = path.with_stem(f"{path.stem}_{test_mode}")
                if path.suffix.lower() == ".json":
                    JSONOutput.save(result, mode_path)
                elif path.suffix.lower() == ".csv":
                    CSVOutput.save(result, mode_path, include_raw=raw_csv)
    else:
        # Single result
        if json:
            click.echo(JSONOutput.format(results))
        elif not quiet:
            RichConsoleOutput.print(results)
        
        if output:
            path = Path(output)
            if path.suffix.lower() == ".json":
                JSONOutput.save(results, path)
                if not quiet:
                    click.echo(f"Results saved to {path}")
            elif path.suffix.lower() == ".csv":
                CSVOutput.save(results, path, include_raw=raw_csv)
                if not quiet:
                    click.echo(f"Results saved to {path}")
            else:
                # Default to JSON
                json_path = path.with_suffix(".json")
                JSONOutput.save(results, json_path)
                if not quiet:
                    click.echo(f"Results saved to {json_path}")


@main.command()
def list_available():
    """List all available DNS resolvers."""
    try:
        from rich.console import Console
        from rich.table import Table
        from rich import box
        
        console = Console()
        table = Table(
            title="Available DNS Resolvers",
            box=box.ROUNDED,
            header_style="bold cyan",
        )
        
        table.add_column("Name", style="green")
        table.add_column("IP", style="cyan")
        table.add_column("DoT", style="yellow")
        table.add_column("DoH", style="magenta")
        table.add_column("Description")
        
        for name, resolver in sorted(RESOLVERS.items()):
            table.add_row(
                name,
                resolver.ipv4,
                "✓" if resolver.dot_hostname else "✗",
                "✓" if resolver.doh_url else "✗",
                resolver.description or "",
            )
        
        console.print(table)
        console.print()
        console.print("[dim]Default resolvers:[/dim]", ", ".join(DEFAULT_RESOLVERS))
        
    except ImportError:
        # Fallback without rich
        click.echo("Available DNS Resolvers:")
        click.echo("-" * 60)
        
        for name, resolver in sorted(RESOLVERS.items()):
            dot = "DoT" if resolver.dot_hostname else ""
            doh = "DoH" if resolver.doh_url else ""
            protocols = ", ".join(filter(None, [dot, doh]))
            click.echo(f"  {name:20} {resolver.ipv4:15} [{protocols}]")
        
        click.echo()
        click.echo(f"Default: {', '.join(DEFAULT_RESOLVERS)}")


@main.command()
def flush():
    """Flush the OS DNS cache."""
    if not check_elevated_privileges():
        click.echo("Warning: This may require elevated privileges", err=True)
    
    success, message = flush_dns_cache()
    if success:
        click.echo(f"✓ {message}")
    else:
        click.echo(f"✗ {message}", err=True)
        sys.exit(1)


@main.command()
def info():
    """Show system DNS configuration."""
    from .cache_utils import get_system_dns_servers, get_platform
    
    click.echo(f"Platform: {get_platform()}")
    click.echo(f"Elevated: {check_elevated_privileges()}")
    click.echo()
    
    servers = get_system_dns_servers()
    if servers:
        click.echo("System DNS Servers:")
        for server in servers:
            click.echo(f"  • {server}")
    else:
        click.echo("Could not detect system DNS servers")


@main.command()
@click.option(
    "--port", "-p",
    type=int,
    default=5000,
    help="Port to run the GUI server on",
)
@click.option(
    "--host",
    default="127.0.0.1",
    help="Host to bind the server to",
)
@click.option(
    "--no-browser",
    is_flag=True,
    help="Don't automatically open browser",
)
def gui(port: int, host: str, no_browser: bool):
    """
    Launch the web-based GUI.
    
    Opens a modern web interface in your browser for running
    DNS benchmarks with interactive charts and real-time progress.
    
    Examples:
    
    \\b
      # Launch GUI on default port
      dns-speedchecker gui
    
    \\b
      # Use custom port
      dns-speedchecker gui --port 8080
    """
    try:
        from .gui import run_gui
    except ImportError as e:
        click.echo("GUI dependencies not installed.", err=True)
        click.echo("Install with: pip install dns-speedchecker[gui]", err=True)
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    
    click.echo(f"Starting DNS Speed Checker GUI...")
    click.echo(f"Open http://{host}:{port} in your browser")
    click.echo("Press Ctrl+C to stop the server")
    
    run_gui(host=host, port=port, open_browser=not no_browser)


if __name__ == "__main__":
    main()
