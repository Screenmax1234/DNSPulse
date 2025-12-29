"""
DNS transport implementations.

Provides transport classes for different DNS protocols:
- UDP (standard DNS)
- TCP (DNS over TCP)
- DoT (DNS over TLS)
- DoH (DNS over HTTPS)

Each transport separately measures connection and query timing.
"""

import asyncio
import ssl
import struct
import time
from abc import ABC, abstractmethod
from typing import Optional

import dns.message
import dns.query
import dns.rdatatype
import httpx

from .models import TimingBreakdown, Transport


class BaseTransport(ABC):
    """Base class for DNS transports."""
    
    transport_type: Transport
    
    @abstractmethod
    async def query(
        self,
        message: dns.message.Message,
        resolver_ip: str,
        timeout: float = 5.0,
    ) -> tuple[dns.message.Message, TimingBreakdown, str]:
        """
        Send a DNS query and return the response.
        
        Returns:
            Tuple of (response, timing_breakdown, responding_ip)
        """
        pass


class UDPTransport(BaseTransport):
    """Standard DNS over UDP."""
    
    transport_type = Transport.UDP
    
    async def query(
        self,
        message: dns.message.Message,
        resolver_ip: str,
        timeout: float = 5.0,
    ) -> tuple[dns.message.Message, TimingBreakdown, str]:
        """Send DNS query over UDP."""
        start = time.perf_counter_ns()
        
        # Run the synchronous UDP query in a thread pool
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: dns.query.udp(
                message,
                resolver_ip,
                timeout=timeout,
                port=53,
            )
        )
        
        end = time.perf_counter_ns()
        total_ms = (end - start) / 1_000_000
        
        timing = TimingBreakdown(
            total_ms=total_ms,
            connection_ms=0.0,  # UDP is connectionless
            query_ms=total_ms,
        )
        
        return response, timing, resolver_ip


class TCPTransport(BaseTransport):
    """DNS over TCP."""
    
    transport_type = Transport.TCP
    
    async def query(
        self,
        message: dns.message.Message,
        resolver_ip: str,
        timeout: float = 5.0,
    ) -> tuple[dns.message.Message, TimingBreakdown, str]:
        """Send DNS query over TCP with timing breakdown."""
        # Measure connection time
        connect_start = time.perf_counter_ns()
        
        loop = asyncio.get_event_loop()
        
        # Open connection
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(resolver_ip, 53),
            timeout=timeout
        )
        
        connect_end = time.perf_counter_ns()
        connection_ms = (connect_end - connect_start) / 1_000_000
        
        try:
            # Measure query time
            query_start = time.perf_counter_ns()
            
            # DNS over TCP requires length prefix
            wire = message.to_wire()
            length = struct.pack("!H", len(wire))
            writer.write(length + wire)
            await writer.drain()
            
            # Read response length
            length_data = await asyncio.wait_for(
                reader.readexactly(2),
                timeout=timeout
            )
            response_length = struct.unpack("!H", length_data)[0]
            
            # Read response
            response_data = await asyncio.wait_for(
                reader.readexactly(response_length),
                timeout=timeout
            )
            
            query_end = time.perf_counter_ns()
            query_ms = (query_end - query_start) / 1_000_000
            
            response = dns.message.from_wire(response_data)
            
        finally:
            writer.close()
            await writer.wait_closed()
        
        timing = TimingBreakdown(
            total_ms=connection_ms + query_ms,
            connection_ms=connection_ms,
            query_ms=query_ms,
        )
        
        return response, timing, resolver_ip


class DoTTransport(BaseTransport):
    """DNS over TLS (DoT)."""
    
    transport_type = Transport.DOT
    
    def __init__(self, hostname: str):
        """
        Initialize DoT transport.
        
        Args:
            hostname: TLS hostname for certificate verification
        """
        self.hostname = hostname
    
    async def query(
        self,
        message: dns.message.Message,
        resolver_ip: str,
        timeout: float = 5.0,
    ) -> tuple[dns.message.Message, TimingBreakdown, str]:
        """Send DNS query over TLS."""
        # Create SSL context
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = True
        ssl_context.verify_mode = ssl.CERT_REQUIRED
        
        # Measure TLS handshake time
        connect_start = time.perf_counter_ns()
        
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(
                resolver_ip,
                853,  # DoT port
                ssl=ssl_context,
                server_hostname=self.hostname,
            ),
            timeout=timeout
        )
        
        connect_end = time.perf_counter_ns()
        connection_ms = (connect_end - connect_start) / 1_000_000
        
        try:
            # Measure query time
            query_start = time.perf_counter_ns()
            
            # DNS over TCP/TLS requires length prefix
            wire = message.to_wire()
            length = struct.pack("!H", len(wire))
            writer.write(length + wire)
            await writer.drain()
            
            # Read response
            length_data = await asyncio.wait_for(
                reader.readexactly(2),
                timeout=timeout
            )
            response_length = struct.unpack("!H", length_data)[0]
            
            response_data = await asyncio.wait_for(
                reader.readexactly(response_length),
                timeout=timeout
            )
            
            query_end = time.perf_counter_ns()
            query_ms = (query_end - query_start) / 1_000_000
            
            response = dns.message.from_wire(response_data)
            
        finally:
            writer.close()
            await writer.wait_closed()
        
        timing = TimingBreakdown(
            total_ms=connection_ms + query_ms,
            connection_ms=connection_ms,
            query_ms=query_ms,
        )
        
        return response, timing, resolver_ip


class DoHTransport(BaseTransport):
    """DNS over HTTPS (DoH)."""
    
    transport_type = Transport.DOH
    
    def __init__(self, url: str):
        """
        Initialize DoH transport.
        
        Args:
            url: DoH endpoint URL (e.g., https://dns.google/dns-query)
        """
        self.url = url
        self._client: Optional[httpx.AsyncClient] = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP/2 client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                http2=True,
                timeout=httpx.Timeout(10.0, connect=5.0),
            )
        return self._client
    
    async def query(
        self,
        message: dns.message.Message,
        resolver_ip: str,  # Not used for DoH, URL determines endpoint
        timeout: float = 5.0,
    ) -> tuple[dns.message.Message, TimingBreakdown, str]:
        """Send DNS query over HTTPS."""
        client = await self._get_client()
        
        # Measure full request time (includes connection if not pooled)
        start = time.perf_counter_ns()
        
        # Prepare DNS wire format
        wire = message.to_wire()
        
        # Send POST request with DNS wire format
        response = await client.post(
            self.url,
            content=wire,
            headers={
                "Content-Type": "application/dns-message",
                "Accept": "application/dns-message",
            },
            timeout=timeout,
        )
        
        end = time.perf_counter_ns()
        total_ms = (end - start) / 1_000_000
        
        response.raise_for_status()
        
        dns_response = dns.message.from_wire(response.content)
        
        # For DoH, we can't easily separate connection from query time
        # without more complex HTTP/2 stream tracking
        timing = TimingBreakdown(
            total_ms=total_ms,
            connection_ms=0.0,  # Included in total
            query_ms=total_ms,
        )
        
        # Return the resolved IP from the URL, not resolver_ip
        return dns_response, timing, self.url
    
    async def close(self):
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None


def create_transport(transport_type: Transport, resolver) -> BaseTransport:
    """
    Create a transport instance for the given type and resolver.
    
    Args:
        transport_type: Type of transport to create
        resolver: ResolverConfig instance
        
    Returns:
        Appropriate transport instance
    """
    if transport_type == Transport.UDP:
        return UDPTransport()
    elif transport_type == Transport.TCP:
        return TCPTransport()
    elif transport_type == Transport.DOT:
        if not resolver.dot_hostname:
            raise ValueError(f"Resolver {resolver.name} does not support DoT")
        return DoTTransport(resolver.dot_hostname)
    elif transport_type == Transport.DOH:
        if not resolver.doh_url:
            raise ValueError(f"Resolver {resolver.name} does not support DoH")
        return DoHTransport(resolver.doh_url)
    else:
        raise ValueError(f"Unknown transport type: {transport_type}")
