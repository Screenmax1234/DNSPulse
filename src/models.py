"""
Data models for DNS Speed Checker.

Defines structured types for query results, resolver configurations,
and benchmark outputs.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class Transport(Enum):
    """DNS transport protocols."""
    UDP = "udp"
    TCP = "tcp"
    DOT = "dot"  # DNS over TLS
    DOH = "doh"  # DNS over HTTPS


class RecordType(Enum):
    """DNS record types to query."""
    A = "A"
    AAAA = "AAAA"
    CNAME = "CNAME"
    MX = "MX"
    TXT = "TXT"
    NS = "NS"


class QueryStatus(Enum):
    """Result status of a DNS query."""
    SUCCESS = "success"
    TIMEOUT = "timeout"
    NXDOMAIN = "nxdomain"
    SERVFAIL = "servfail"
    REFUSED = "refused"
    ERROR = "error"


@dataclass
class ResolverConfig:
    """Configuration for a DNS resolver."""
    name: str
    ipv4: str
    ipv6: Optional[str] = None
    dot_hostname: Optional[str] = None
    doh_url: Optional[str] = None
    description: Optional[str] = None
    
    def supports_transport(self, transport: Transport) -> bool:
        """Check if this resolver supports the given transport."""
        if transport in (Transport.UDP, Transport.TCP):
            return True
        if transport == Transport.DOT:
            return self.dot_hostname is not None
        if transport == Transport.DOH:
            return self.doh_url is not None
        return False


@dataclass
class TimingBreakdown:
    """Detailed timing breakdown for a query."""
    total_ms: float
    connection_ms: float = 0.0  # TCP/TLS handshake time
    query_ms: float = 0.0       # DNS query round-trip
    
    @property
    def overhead_ms(self) -> float:
        """Protocol overhead (connection setup)."""
        return self.connection_ms


@dataclass
class QueryResult:
    """Result of a single DNS query."""
    domain: str
    record_type: RecordType
    resolver: ResolverConfig
    transport: Transport
    status: QueryStatus
    timing: TimingBreakdown
    timestamp: datetime = field(default_factory=datetime.now)
    
    # Response data
    answers: list[str] = field(default_factory=list)
    ttl: Optional[int] = None
    
    # Metadata
    responding_ip: Optional[str] = None  # Actual IP that responded (anycast)
    is_cached: bool = False
    error_message: Optional[str] = None
    
    @property
    def is_success(self) -> bool:
        """Check if query was successful."""
        return self.status == QueryStatus.SUCCESS
    
    @property
    def latency_ms(self) -> float:
        """Total latency in milliseconds."""
        return self.timing.total_ms


@dataclass
class ResolverStats:
    """Aggregated statistics for a resolver."""
    resolver: ResolverConfig
    transport: Transport
    total_queries: int
    successful_queries: int
    failed_queries: int
    
    # Latency stats (in milliseconds)
    min_latency: float
    max_latency: float
    avg_latency: float
    median_latency: float
    p95_latency: float
    p99_latency: float
    stddev_latency: float
    
    # Reliability stats
    timeout_count: int
    nxdomain_count: int
    error_count: int
    
    # Jitter (variation between consecutive queries)
    jitter_ms: float
    
    @property
    def success_rate(self) -> float:
        """Percentage of successful queries."""
        if self.total_queries == 0:
            return 0.0
        return (self.successful_queries / self.total_queries) * 100
    
    @property
    def packet_loss_rate(self) -> float:
        """Percentage of failed/timed out queries."""
        if self.total_queries == 0:
            return 0.0
        return (self.failed_queries / self.total_queries) * 100


@dataclass
class RecordTypeStats:
    """Statistics broken down by record type."""
    record_type: RecordType
    count: int
    avg_latency: float
    success_rate: float


@dataclass
class BenchmarkResult:
    """Complete benchmark result for all resolvers."""
    started_at: datetime
    completed_at: datetime
    test_mode: str  # "cold", "warm", "burst"
    
    # Configuration used
    domains_tested: int
    queries_per_resolver: int
    runs: int
    parallel_queries: int
    
    # Results per resolver
    resolver_stats: list[ResolverStats] = field(default_factory=list)
    
    # Detailed results (optional, for export)
    raw_results: list[QueryResult] = field(default_factory=list)
    
    # Per record-type breakdown
    record_type_stats: dict[str, list[RecordTypeStats]] = field(default_factory=dict)
    
    @property
    def duration_seconds(self) -> float:
        """Total benchmark duration in seconds."""
        return (self.completed_at - self.started_at).total_seconds()
    
    @property
    def winner(self) -> Optional[ResolverStats]:
        """Resolver with best average latency (if any succeeded)."""
        successful = [s for s in self.resolver_stats if s.successful_queries > 0]
        if not successful:
            return None
        return min(successful, key=lambda s: s.avg_latency)
