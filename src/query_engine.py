"""
Core DNS query engine.

Provides the main interface for executing DNS queries with
high-resolution timing and detailed result collection.
"""

import asyncio
from datetime import datetime
from typing import Optional

import dns.message
import dns.name
import dns.rcode
import dns.rdatatype

from .models import (
    QueryResult,
    QueryStatus,
    RecordType,
    ResolverConfig,
    TimingBreakdown,
    Transport,
)
from .transports import BaseTransport, create_transport


class DNSQueryEngine:
    """
    High-performance DNS query engine.
    
    Executes DNS queries using various transport protocols with
    nanosecond-precision timing.
    """
    
    def __init__(
        self,
        timeout: float = 5.0,
        retries: int = 1,
        use_dnssec: bool = True,
    ):
        """
        Initialize the query engine.
        
        Args:
            timeout: Query timeout in seconds
            retries: Number of retries on failure
            use_dnssec: Whether to request DNSSEC validation
        """
        self.timeout = timeout
        self.retries = retries
        self.use_dnssec = use_dnssec
        self._transports: dict[tuple, BaseTransport] = {}
    
    def _get_transport(
        self,
        transport_type: Transport,
        resolver: ResolverConfig,
    ) -> BaseTransport:
        """Get or create a transport for the given type and resolver."""
        key = (transport_type, resolver.name)
        if key not in self._transports:
            self._transports[key] = create_transport(transport_type, resolver)
        return self._transports[key]
    
    def _create_query_message(
        self,
        domain: str,
        record_type: RecordType,
    ) -> dns.message.Message:
        """Create a DNS query message."""
        rdtype = dns.rdatatype.from_text(record_type.value)
        message = dns.message.make_query(
            domain,
            rdtype,
            want_dnssec=self.use_dnssec,
        )
        return message
    
    def _parse_response_status(
        self,
        response: dns.message.Message,
    ) -> QueryStatus:
        """Parse the response status from a DNS response."""
        rcode = response.rcode()
        
        if rcode == dns.rcode.NOERROR:
            return QueryStatus.SUCCESS
        elif rcode == dns.rcode.NXDOMAIN:
            return QueryStatus.NXDOMAIN
        elif rcode == dns.rcode.SERVFAIL:
            return QueryStatus.SERVFAIL
        elif rcode == dns.rcode.REFUSED:
            return QueryStatus.REFUSED
        else:
            return QueryStatus.ERROR
    
    def _extract_answers(
        self,
        response: dns.message.Message,
    ) -> tuple[list[str], Optional[int]]:
        """Extract answer strings and TTL from response."""
        answers = []
        ttl = None
        
        for rrset in response.answer:
            if ttl is None:
                ttl = rrset.ttl
            for rdata in rrset:
                answers.append(str(rdata))
        
        return answers, ttl
    
    async def query(
        self,
        domain: str,
        record_type: RecordType,
        resolver: ResolverConfig,
        transport_type: Transport = Transport.UDP,
    ) -> QueryResult:
        """
        Execute a single DNS query.
        
        Args:
            domain: Domain name to query
            record_type: Type of DNS record to request
            resolver: Resolver configuration to use
            transport_type: Transport protocol to use
            
        Returns:
            QueryResult with timing and response data
        """
        message = self._create_query_message(domain, record_type)
        transport = self._get_transport(transport_type, resolver)
        
        last_error: Optional[Exception] = None
        
        for attempt in range(self.retries + 1):
            try:
                response, timing, responding_ip = await transport.query(
                    message,
                    resolver.ipv4,
                    timeout=self.timeout,
                )
                
                status = self._parse_response_status(response)
                answers, ttl = self._extract_answers(response)
                
                return QueryResult(
                    domain=domain,
                    record_type=record_type,
                    resolver=resolver,
                    transport=transport_type,
                    status=status,
                    timing=timing,
                    timestamp=datetime.now(),
                    answers=answers,
                    ttl=ttl,
                    responding_ip=responding_ip,
                    is_cached=False,  # We can't reliably detect this
                    error_message=None,
                )
                
            except asyncio.TimeoutError:
                last_error = asyncio.TimeoutError(f"Query timed out after {self.timeout}s")
            except Exception as e:
                last_error = e
            
            # Wait briefly before retry
            if attempt < self.retries:
                await asyncio.sleep(0.1)
        
        # All retries exhausted
        return QueryResult(
            domain=domain,
            record_type=record_type,
            resolver=resolver,
            transport=transport_type,
            status=QueryStatus.TIMEOUT if isinstance(last_error, asyncio.TimeoutError) else QueryStatus.ERROR,
            timing=TimingBreakdown(total_ms=self.timeout * 1000),
            timestamp=datetime.now(),
            answers=[],
            ttl=None,
            responding_ip=None,
            is_cached=False,
            error_message=str(last_error),
        )
    
    async def query_batch(
        self,
        queries: list[tuple[str, RecordType]],
        resolver: ResolverConfig,
        transport_type: Transport = Transport.UDP,
        concurrency: int = 10,
    ) -> list[QueryResult]:
        """
        Execute multiple DNS queries with controlled concurrency.
        
        Args:
            queries: List of (domain, record_type) tuples
            resolver: Resolver configuration to use
            transport_type: Transport protocol to use
            concurrency: Maximum concurrent queries
            
        Returns:
            List of QueryResult objects
        """
        semaphore = asyncio.Semaphore(concurrency)
        
        async def limited_query(domain: str, record_type: RecordType) -> QueryResult:
            async with semaphore:
                return await self.query(domain, record_type, resolver, transport_type)
        
        tasks = [
            limited_query(domain, record_type)
            for domain, record_type in queries
        ]
        
        return await asyncio.gather(*tasks)
    
    async def close(self):
        """Close all transport connections."""
        for transport in self._transports.values():
            if hasattr(transport, 'close'):
                await transport.close()
        self._transports.clear()
