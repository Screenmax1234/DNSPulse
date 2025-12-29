"""
Workload generator for DNS benchmarking.

Generates realistic DNS query workloads based on:
- Top 100 most visited websites
- Common third-party resources (CDNs, APIs, fonts)
- Random subdomain generation for cache bypass
- CNAME chain simulation
"""

import random
import secrets
import string
from pathlib import Path
from typing import Iterator, Optional

from .models import RecordType


# Common third-party domains loaded by websites
COMMON_THIRD_PARTY = [
    # CDNs
    "cdn.jsdelivr.net",
    "cdnjs.cloudflare.com",
    "unpkg.com",
    "ajax.googleapis.com",
    "code.jquery.com",
    "stackpath.bootstrapcdn.com",
    "maxcdn.bootstrapcdn.com",
    # Fonts
    "fonts.googleapis.com",
    "fonts.gstatic.com",
    "use.fontawesome.com",
    "use.typekit.net",
    # Analytics & Tracking
    "www.google-analytics.com",
    "www.googletagmanager.com",
    "connect.facebook.net",
    "platform.twitter.com",
    "snap.licdn.com",
    "s.pinimg.com",
    "static.ads-twitter.com",
    # APIs & Services
    "api.stripe.com",
    "js.stripe.com",
    "www.paypal.com",
    "apis.google.com",
    "maps.googleapis.com",
    "www.gstatic.com",
    "ssl.gstatic.com",
    # Media & Images
    "images.unsplash.com",
    "i.imgur.com",
    "pbs.twimg.com",
    "scontent.xx.fbcdn.net",
    # Security
    "www.google.com",  # ReCAPTCHA
    "challenges.cloudflare.com",
    "static.cloudflareinsights.com",
]

# Common subdomain prefixes for realistic simulation
COMMON_SUBDOMAINS = [
    "www",
    "api",
    "cdn",
    "static",
    "assets",
    "media",
    "img",
    "images",
    "m",
    "mobile",
    "app",
    "login",
    "auth",
    "secure",
    "mail",
]


class WorkloadGenerator:
    """Generates DNS query workloads for benchmarking."""
    
    def __init__(
        self,
        domains: Optional[list[str]] = None,
        include_third_party: bool = True,
        cache_bypass: bool = True,
        subdomain_expansion: bool = True,
    ):
        """
        Initialize the workload generator.
        
        Args:
            domains: Custom domain list (uses Top 100 if None)
            include_third_party: Include common third-party resources
            cache_bypass: Generate random subdomains to bypass cache
            subdomain_expansion: Expand domains with common prefixes
        """
        self.domains = domains or self._load_top_100()
        self.include_third_party = include_third_party
        self.cache_bypass = cache_bypass
        self.subdomain_expansion = subdomain_expansion
    
    def _load_top_100(self) -> list[str]:
        """Load the bundled Top 100 sites list."""
        data_file = Path(__file__).parent / "data" / "top100.txt"
        
        if data_file.exists():
            with open(data_file, "r") as f:
                return [
                    line.strip()
                    for line in f
                    if line.strip() and not line.startswith("#")
                ]
        
        # Fallback if file doesn't exist
        return [
            "google.com",
            "youtube.com",
            "facebook.com",
            "amazon.com",
            "wikipedia.org",
            "twitter.com",
            "instagram.com",
            "linkedin.com",
            "reddit.com",
            "netflix.com",
        ]
    
    def _generate_random_prefix(self, length: int = 8) -> str:
        """Generate a random subdomain prefix for cache bypass."""
        chars = string.ascii_lowercase + string.digits
        return ''.join(secrets.choice(chars) for _ in range(length))
    
    def _expand_domain(self, domain: str) -> list[str]:
        """Expand a domain with common subdomain prefixes."""
        expanded = [domain]
        
        if self.subdomain_expansion:
            # Add common subdomains
            for prefix in random.sample(COMMON_SUBDOMAINS, min(3, len(COMMON_SUBDOMAINS))):
                expanded.append(f"{prefix}.{domain}")
        
        return expanded
    
    def generate_cold_queries(
        self,
        count: Optional[int] = None,
        record_types: Optional[list[RecordType]] = None,
    ) -> list[tuple[str, RecordType]]:
        """
        Generate cold start queries with cache bypass.
        
        Cache bypass is achieved by prepending random subdomains,
        which forces resolvers to query upstream.
        
        Args:
            count: Maximum number of queries (uses all if None)
            record_types: Record types to query (default: A and AAAA)
            
        Returns:
            List of (domain, record_type) tuples
        """
        if record_types is None:
            record_types = [RecordType.A, RecordType.AAAA]
        
        queries = []
        
        # Process main domains
        domains_to_use = self.domains[:count] if count else self.domains
        
        for domain in domains_to_use:
            expanded = self._expand_domain(domain)
            
            for subdomain in expanded:
                for record_type in record_types:
                    if self.cache_bypass:
                        # Add random prefix to bypass cache
                        prefix = self._generate_random_prefix()
                        query_domain = f"{prefix}.{subdomain}"
                    else:
                        query_domain = subdomain
                    
                    queries.append((query_domain, record_type))
        
        # Add third-party domains
        if self.include_third_party:
            for domain in COMMON_THIRD_PARTY:
                for record_type in record_types:
                    if self.cache_bypass:
                        # For third-party, we can't add random prefixes
                        # as they won't resolve. Use as-is.
                        pass
                    queries.append((domain, record_type))
        
        return queries
    
    def generate_warm_queries(
        self,
        count: Optional[int] = None,
        record_types: Optional[list[RecordType]] = None,
    ) -> list[tuple[str, RecordType]]:
        """
        Generate warm cache queries (no random prefixes).
        
        These queries use standard domain names that are likely
        to be cached by resolvers.
        
        Args:
            count: Maximum number of queries
            record_types: Record types to query
            
        Returns:
            List of (domain, record_type) tuples
        """
        if record_types is None:
            record_types = [RecordType.A, RecordType.AAAA]
        
        queries = []
        domains_to_use = self.domains[:count] if count else self.domains
        
        for domain in domains_to_use:
            # Use www. prefix for maximum cache hit probability
            www_domain = f"www.{domain}"
            
            for record_type in record_types:
                queries.append((www_domain, record_type))
        
        if self.include_third_party:
            for domain in COMMON_THIRD_PARTY:
                for record_type in record_types:
                    queries.append((domain, record_type))
        
        return queries
    
    def generate_burst_queries(
        self,
        burst_size: int = 20,
        record_types: Optional[list[RecordType]] = None,
    ) -> list[tuple[str, RecordType]]:
        """
        Generate a burst of queries simulating page load.
        
        Selects a random subset of domains and expands them
        to simulate the DNS requests during a typical page load.
        
        Args:
            burst_size: Number of domains to include in burst
            record_types: Record types to query
            
        Returns:
            List of (domain, record_type) tuples
        """
        if record_types is None:
            record_types = [RecordType.A, RecordType.AAAA]
        
        queries = []
        
        # Select random domains
        burst_domains = random.sample(
            self.domains,
            min(burst_size, len(self.domains))
        )
        
        for domain in burst_domains:
            # Simulate full page load with various resources
            page_domains = [
                f"www.{domain}",
                f"cdn.{domain}",
                f"api.{domain}",
                f"static.{domain}",
            ]
            
            for page_domain in page_domains:
                for record_type in record_types:
                    queries.append((page_domain, record_type))
        
        # Add some third-party resources
        third_party = random.sample(
            COMMON_THIRD_PARTY,
            min(10, len(COMMON_THIRD_PARTY))
        )
        
        for domain in third_party:
            queries.append((domain, RecordType.A))
        
        return queries
    
    def generate_nxdomain_queries(
        self,
        count: int = 10,
    ) -> list[tuple[str, RecordType]]:
        """
        Generate queries that will return NXDOMAIN.
        
        Used to test resolver behavior with non-existent domains.
        
        Args:
            count: Number of queries to generate
            
        Returns:
            List of (domain, record_type) tuples
        """
        queries = []
        
        for _ in range(count):
            # Generate completely random domain that won't exist
            random_part = self._generate_random_prefix(16)
            domain = f"{random_part}.invalid-domain-test.example"
            queries.append((domain, RecordType.A))
        
        return queries
    
    def generate_cname_chain_queries(self) -> list[tuple[str, RecordType]]:
        """
        Generate queries likely to involve CNAME chains.
        
        Many CDN and cloud-hosted sites use CNAME records.
        
        Returns:
            List of (domain, record_type) tuples
        """
        # Domains known to have CNAME chains
        cname_domains = [
            "www.github.com",
            "www.cloudflare.com",
            "www.aws.amazon.com",
            "www.azure.microsoft.com",
            "www.heroku.com",
            "www.netlify.com",
            "www.vercel.com",
            "www.pages.github.io",
        ]
        
        queries = []
        for domain in cname_domains:
            queries.append((domain, RecordType.CNAME))
            queries.append((domain, RecordType.A))
        
        return queries
    
    def get_domain_count(self) -> int:
        """Get the number of base domains."""
        return len(self.domains)
    
    def get_total_query_estimate(
        self,
        record_types: Optional[list[RecordType]] = None,
    ) -> int:
        """Estimate total queries for a full workload."""
        if record_types is None:
            record_types = [RecordType.A, RecordType.AAAA]
        
        base = len(self.domains) * len(record_types)
        
        if self.subdomain_expansion:
            base *= 4  # Approximate expansion factor
        
        if self.include_third_party:
            base += len(COMMON_THIRD_PARTY) * len(record_types)
        
        return base
