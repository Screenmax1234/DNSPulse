"""
Test runner for DNS benchmarking.

Orchestrates test execution with support for:
- Cold start tests (cache bypass)
- Warm cache tests
- Burst query tests
- Multiple runs for statistical validity
"""

import asyncio
from datetime import datetime
from typing import Callable, Optional

from .models import (
    BenchmarkResult,
    QueryResult,
    RecordType,
    ResolverConfig,
    Transport,
)
from .query_engine import DNSQueryEngine
from .statistics import StatisticsEngine
from .workload import WorkloadGenerator


# Type for progress callback
ProgressCallback = Callable[[str, int, int], None]


class TestRunner:
    """
    Orchestrates DNS benchmark tests.
    
    Supports multiple test modes and ensures fair comparison
    by using identical workloads across resolvers.
    """
    
    def __init__(
        self,
        resolvers: list[ResolverConfig],
        transports: list[Transport] = None,
        timeout: float = 5.0,
        use_dnssec: bool = True,
    ):
        """
        Initialize the test runner.
        
        Args:
            resolvers: List of resolver configurations to test
            transports: Transports to use (default: UDP only)
            timeout: Query timeout in seconds
            use_dnssec: Whether to request DNSSEC validation
        """
        self.resolvers = resolvers
        self.transports = transports or [Transport.UDP]
        self.engine = DNSQueryEngine(timeout=timeout, use_dnssec=use_dnssec)
        self.workload = WorkloadGenerator()
    
    async def run_cold_test(
        self,
        domain_count: int = 50,
        runs: int = 3,
        record_types: Optional[list[RecordType]] = None,
        concurrency: int = 10,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> BenchmarkResult:
        """
        Run cold start benchmark (cache bypass).
        
        Uses random subdomains to force upstream resolution.
        
        Args:
            domain_count: Number of domains to test
            runs: Number of test iterations
            record_types: Record types to query
            concurrency: Parallel queries per batch
            progress_callback: Optional callback for progress updates
            
        Returns:
            BenchmarkResult with all statistics
        """
        if record_types is None:
            record_types = [RecordType.A, RecordType.AAAA]
        
        started_at = datetime.now()
        all_results: list[QueryResult] = []
        
        total_resolvers = len(self.resolvers) * len(self.transports)
        current = 0
        
        for run in range(runs):
            # Generate fresh queries for each run (new random prefixes)
            queries = self.workload.generate_cold_queries(
                count=domain_count,
                record_types=record_types,
            )
            
            for resolver in self.resolvers:
                for transport in self.transports:
                    if not resolver.supports_transport(transport):
                        continue
                    
                    current += 1
                    if progress_callback:
                        progress_callback(
                            f"Run {run + 1}/{runs}: {resolver.name} ({transport.value})",
                            current,
                            total_resolvers * runs,
                        )
                    
                    results = await self.engine.query_batch(
                        queries=queries,
                        resolver=resolver,
                        transport_type=transport,
                        concurrency=concurrency,
                    )
                    
                    all_results.extend(results)
        
        return self._build_result(
            all_results,
            started_at,
            "cold",
            domain_count,
            runs,
            concurrency,
        )
    
    async def run_warm_test(
        self,
        domain_count: int = 50,
        runs: int = 3,
        warmup_queries: int = 2,
        record_types: Optional[list[RecordType]] = None,
        concurrency: int = 10,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> BenchmarkResult:
        """
        Run warm cache benchmark.
        
        First warms the resolver cache, then measures cached responses.
        
        Args:
            domain_count: Number of domains to test
            runs: Number of test iterations
            warmup_queries: Queries to run before measuring
            record_types: Record types to query
            concurrency: Parallel queries per batch
            progress_callback: Optional callback for progress updates
            
        Returns:
            BenchmarkResult with all statistics
        """
        if record_types is None:
            record_types = [RecordType.A]
        
        started_at = datetime.now()
        all_results: list[QueryResult] = []
        
        # Generate consistent queries (no random prefix)
        queries = self.workload.generate_warm_queries(
            count=domain_count,
            record_types=record_types,
        )
        
        total_resolvers = len(self.resolvers) * len(self.transports)
        current = 0
        
        for resolver in self.resolvers:
            for transport in self.transports:
                if not resolver.supports_transport(transport):
                    continue
                
                current += 1
                
                # Warmup phase
                if progress_callback:
                    progress_callback(
                        f"Warming cache: {resolver.name} ({transport.value})",
                        current,
                        total_resolvers,
                    )
                
                for _ in range(warmup_queries):
                    await self.engine.query_batch(
                        queries=queries,
                        resolver=resolver,
                        transport_type=transport,
                        concurrency=concurrency,
                    )
                
                # Measurement runs
                for run in range(runs):
                    if progress_callback:
                        progress_callback(
                            f"Run {run + 1}/{runs}: {resolver.name} ({transport.value})",
                            current,
                            total_resolvers,
                        )
                    
                    results = await self.engine.query_batch(
                        queries=queries,
                        resolver=resolver,
                        transport_type=transport,
                        concurrency=concurrency,
                    )
                    
                    # Mark as cached
                    for r in results:
                        object.__setattr__(r, 'is_cached', True)
                    
                    all_results.extend(results)
        
        return self._build_result(
            all_results,
            started_at,
            "warm",
            domain_count,
            runs,
            concurrency,
        )
    
    async def run_burst_test(
        self,
        burst_size: int = 20,
        parallel_queries: int = 30,
        runs: int = 5,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> BenchmarkResult:
        """
        Run burst query benchmark simulating page loads.
        
        Tests resolver performance under concurrent load.
        
        Args:
            burst_size: Number of domains per burst
            parallel_queries: Concurrent queries
            runs: Number of burst iterations
            progress_callback: Optional callback for progress updates
            
        Returns:
            BenchmarkResult with all statistics
        """
        started_at = datetime.now()
        all_results: list[QueryResult] = []
        
        total_resolvers = len(self.resolvers) * len(self.transports)
        current = 0
        
        for run in range(runs):
            # Generate burst workload
            queries = self.workload.generate_burst_queries(burst_size=burst_size)
            
            for resolver in self.resolvers:
                for transport in self.transports:
                    if not resolver.supports_transport(transport):
                        continue
                    
                    current += 1
                    if progress_callback:
                        progress_callback(
                            f"Burst {run + 1}/{runs}: {resolver.name} ({transport.value})",
                            current,
                            total_resolvers * runs,
                        )
                    
                    results = await self.engine.query_batch(
                        queries=queries,
                        resolver=resolver,
                        transport_type=transport,
                        concurrency=parallel_queries,
                    )
                    
                    all_results.extend(results)
        
        return self._build_result(
            all_results,
            started_at,
            "burst",
            burst_size,
            runs,
            parallel_queries,
        )
    
    async def run_nxdomain_test(
        self,
        count: int = 20,
        runs: int = 3,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> BenchmarkResult:
        """
        Test resolver behavior with non-existent domains.
        
        Args:
            count: Number of NXDOMAIN queries per run
            runs: Number of test iterations
            progress_callback: Optional callback for progress updates
            
        Returns:
            BenchmarkResult with NXDOMAIN statistics
        """
        started_at = datetime.now()
        all_results: list[QueryResult] = []
        
        for run in range(runs):
            queries = self.workload.generate_nxdomain_queries(count=count)
            
            for resolver in self.resolvers:
                for transport in self.transports:
                    if not resolver.supports_transport(transport):
                        continue
                    
                    if progress_callback:
                        progress_callback(
                            f"NXDOMAIN {run + 1}/{runs}: {resolver.name}",
                            run + 1,
                            runs,
                        )
                    
                    results = await self.engine.query_batch(
                        queries=queries,
                        resolver=resolver,
                        transport_type=transport,
                        concurrency=10,
                    )
                    
                    all_results.extend(results)
        
        return self._build_result(
            all_results,
            started_at,
            "nxdomain",
            count,
            runs,
            10,
        )
    
    async def run_comprehensive_test(
        self,
        domain_count: int = 30,
        runs: int = 2,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> dict[str, BenchmarkResult]:
        """
        Run a comprehensive benchmark with all test types.
        
        Args:
            domain_count: Domains to test per type
            runs: Iterations per test type
            progress_callback: Optional callback for progress updates
            
        Returns:
            Dictionary of test type to BenchmarkResult
        """
        results = {}
        
        if progress_callback:
            progress_callback("Running cold start test...", 1, 4)
        results["cold"] = await self.run_cold_test(
            domain_count=domain_count,
            runs=runs,
            progress_callback=progress_callback,
        )
        
        if progress_callback:
            progress_callback("Running warm cache test...", 2, 4)
        results["warm"] = await self.run_warm_test(
            domain_count=domain_count,
            runs=runs,
            progress_callback=progress_callback,
        )
        
        if progress_callback:
            progress_callback("Running burst test...", 3, 4)
        results["burst"] = await self.run_burst_test(
            runs=runs,
            progress_callback=progress_callback,
        )
        
        if progress_callback:
            progress_callback("Running NXDOMAIN test...", 4, 4)
        results["nxdomain"] = await self.run_nxdomain_test(
            runs=runs,
            progress_callback=progress_callback,
        )
        
        return results
    
    def _build_result(
        self,
        results: list[QueryResult],
        started_at: datetime,
        test_mode: str,
        domains_tested: int,
        runs: int,
        parallel_queries: int,
    ) -> BenchmarkResult:
        """Build a BenchmarkResult from raw query results."""
        completed_at = datetime.now()
        
        # Calculate stats per resolver/transport combination
        resolver_stats = []
        record_type_stats = {}
        
        for resolver in self.resolvers:
            for transport in self.transports:
                if not resolver.supports_transport(transport):
                    continue
                
                # Filter results for this resolver/transport
                resolver_results = [
                    r for r in results
                    if r.resolver.name == resolver.name and r.transport == transport
                ]
                
                if resolver_results:
                    stats = StatisticsEngine.calculate_resolver_stats(
                        resolver_results,
                        resolver,
                        transport,
                    )
                    resolver_stats.append(stats)
                    
                    # Record type breakdown
                    key = f"{resolver.name}_{transport.value}"
                    record_type_stats[key] = StatisticsEngine.calculate_record_type_stats(
                        resolver_results
                    )
        
        return BenchmarkResult(
            started_at=started_at,
            completed_at=completed_at,
            test_mode=test_mode,
            domains_tested=domains_tested,
            queries_per_resolver=len(results) // max(len(resolver_stats), 1),
            runs=runs,
            parallel_queries=parallel_queries,
            resolver_stats=resolver_stats,
            raw_results=results,
            record_type_stats=record_type_stats,
        )
    
    async def close(self):
        """Clean up resources."""
        await self.engine.close()
