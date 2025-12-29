"""
Statistical analysis engine for DNS benchmark results.

Calculates comprehensive statistics including:
- Basic stats: min, max, average, median
- Percentiles: p95, p99
- Reliability: jitter, variance, packet loss
- Per-record-type breakdown
"""

import numpy as np
from typing import Optional

from .models import (
    QueryResult,
    QueryStatus,
    RecordType,
    RecordTypeStats,
    ResolverConfig,
    ResolverStats,
    Transport,
)


class StatisticsEngine:
    """Calculates comprehensive statistics from query results."""
    
    @staticmethod
    def calculate_resolver_stats(
        results: list[QueryResult],
        resolver: ResolverConfig,
        transport: Transport,
    ) -> ResolverStats:
        """
        Calculate aggregated statistics for a resolver.
        
        Args:
            results: List of query results for this resolver
            resolver: Resolver configuration
            transport: Transport used for these results
            
        Returns:
            ResolverStats with all metrics calculated
        """
        if not results:
            return ResolverStats(
                resolver=resolver,
                transport=transport,
                total_queries=0,
                successful_queries=0,
                failed_queries=0,
                min_latency=0,
                max_latency=0,
                avg_latency=0,
                median_latency=0,
                p95_latency=0,
                p99_latency=0,
                stddev_latency=0,
                timeout_count=0,
                nxdomain_count=0,
                error_count=0,
                jitter_ms=0,
            )
        
        # Separate successful and failed queries
        successful = [r for r in results if r.is_success]
        failed = [r for r in results if not r.is_success]
        
        # Count failure types
        timeouts = sum(1 for r in results if r.status == QueryStatus.TIMEOUT)
        nxdomains = sum(1 for r in results if r.status == QueryStatus.NXDOMAIN)
        errors = sum(1 for r in results if r.status in (QueryStatus.ERROR, QueryStatus.SERVFAIL, QueryStatus.REFUSED))
        
        # Calculate latency statistics from successful queries
        if successful:
            latencies = np.array([r.latency_ms for r in successful])
            
            min_lat = float(np.min(latencies))
            max_lat = float(np.max(latencies))
            avg_lat = float(np.mean(latencies))
            median_lat = float(np.median(latencies))
            p95_lat = float(np.percentile(latencies, 95))
            p99_lat = float(np.percentile(latencies, 99))
            stddev_lat = float(np.std(latencies))
            
            # Calculate jitter (average difference between consecutive queries)
            if len(latencies) > 1:
                diffs = np.abs(np.diff(latencies))
                jitter = float(np.mean(diffs))
            else:
                jitter = 0.0
        else:
            min_lat = max_lat = avg_lat = median_lat = 0.0
            p95_lat = p99_lat = stddev_lat = jitter = 0.0
        
        return ResolverStats(
            resolver=resolver,
            transport=transport,
            total_queries=len(results),
            successful_queries=len(successful),
            failed_queries=len(failed),
            min_latency=min_lat,
            max_latency=max_lat,
            avg_latency=avg_lat,
            median_latency=median_lat,
            p95_latency=p95_lat,
            p99_latency=p99_lat,
            stddev_latency=stddev_lat,
            timeout_count=timeouts,
            nxdomain_count=nxdomains,
            error_count=errors,
            jitter_ms=jitter,
        )
    
    @staticmethod
    def calculate_record_type_stats(
        results: list[QueryResult],
    ) -> list[RecordTypeStats]:
        """
        Calculate statistics broken down by record type.
        
        Args:
            results: List of query results
            
        Returns:
            List of RecordTypeStats, one per record type
        """
        # Group by record type
        by_type: dict[RecordType, list[QueryResult]] = {}
        
        for result in results:
            if result.record_type not in by_type:
                by_type[result.record_type] = []
            by_type[result.record_type].append(result)
        
        stats = []
        for record_type, type_results in by_type.items():
            successful = [r for r in type_results if r.is_success]
            
            if successful:
                latencies = [r.latency_ms for r in successful]
                avg_lat = sum(latencies) / len(latencies)
            else:
                avg_lat = 0.0
            
            success_rate = (len(successful) / len(type_results)) * 100 if type_results else 0.0
            
            stats.append(RecordTypeStats(
                record_type=record_type,
                count=len(type_results),
                avg_latency=avg_lat,
                success_rate=success_rate,
            ))
        
        return stats
    
    @staticmethod
    def compare_resolvers(
        stats_list: list[ResolverStats],
    ) -> dict:
        """
        Compare multiple resolvers and determine rankings.
        
        Args:
            stats_list: List of ResolverStats from different resolvers
            
        Returns:
            Dictionary with comparison results and rankings
        """
        if not stats_list:
            return {"rankings": [], "winner": None}
        
        # Filter to only resolvers with successful queries
        valid_stats = [s for s in stats_list if s.successful_queries > 0]
        
        if not valid_stats:
            return {"rankings": [], "winner": None}
        
        # Rank by average latency (lower is better)
        by_latency = sorted(valid_stats, key=lambda s: s.avg_latency)
        
        # Rank by reliability (higher success rate is better)
        by_reliability = sorted(valid_stats, key=lambda s: s.success_rate, reverse=True)
        
        # Calculate composite score (weighted)
        # 60% latency, 40% reliability
        def composite_score(stats: ResolverStats) -> float:
            # Normalize latency (inverse, lower is better)
            max_lat = max(s.avg_latency for s in valid_stats)
            min_lat = min(s.avg_latency for s in valid_stats)
            
            if max_lat == min_lat:
                lat_score = 1.0
            else:
                lat_score = 1 - ((stats.avg_latency - min_lat) / (max_lat - min_lat))
            
            # Normalize reliability (already 0-100)
            rel_score = stats.success_rate / 100
            
            return (lat_score * 0.6) + (rel_score * 0.4)
        
        by_composite = sorted(valid_stats, key=composite_score, reverse=True)
        
        winner = by_composite[0] if by_composite else None
        
        # Calculate improvement percentages
        improvements = {}
        if winner and len(by_composite) > 1:
            for stats in by_composite[1:]:
                if stats.avg_latency > 0:
                    improvement = ((stats.avg_latency - winner.avg_latency) / stats.avg_latency) * 100
                    improvements[stats.resolver.name] = improvement
        
        return {
            "rankings": {
                "by_latency": [(s.resolver.name, s.avg_latency) for s in by_latency],
                "by_reliability": [(s.resolver.name, s.success_rate) for s in by_reliability],
                "by_composite": [(s.resolver.name, composite_score(s)) for s in by_composite],
            },
            "winner": winner,
            "improvements": improvements,
        }
    
    @staticmethod
    def calculate_protocol_comparison(
        results: list[QueryResult],
        resolver: ResolverConfig,
    ) -> dict[Transport, dict]:
        """
        Compare performance across different transport protocols.
        
        Args:
            results: All query results for a resolver
            resolver: Resolver configuration
            
        Returns:
            Dictionary mapping transport to performance stats
        """
        by_transport: dict[Transport, list[QueryResult]] = {}
        
        for result in results:
            if result.transport not in by_transport:
                by_transport[result.transport] = []
            by_transport[result.transport].append(result)
        
        comparison = {}
        for transport, transport_results in by_transport.items():
            successful = [r for r in transport_results if r.is_success]
            
            if successful:
                latencies = [r.latency_ms for r in successful]
                connection_times = [r.timing.connection_ms for r in successful]
                query_times = [r.timing.query_ms for r in successful]
                
                comparison[transport] = {
                    "total_queries": len(transport_results),
                    "successful": len(successful),
                    "avg_total_ms": sum(latencies) / len(latencies),
                    "avg_connection_ms": sum(connection_times) / len(connection_times),
                    "avg_query_ms": sum(query_times) / len(query_times),
                    "protocol_overhead_pct": (
                        (sum(connection_times) / sum(latencies)) * 100
                        if sum(latencies) > 0 else 0
                    ),
                }
            else:
                comparison[transport] = {
                    "total_queries": len(transport_results),
                    "successful": 0,
                    "avg_total_ms": 0,
                    "avg_connection_ms": 0,
                    "avg_query_ms": 0,
                    "protocol_overhead_pct": 0,
                }
        
        return comparison
