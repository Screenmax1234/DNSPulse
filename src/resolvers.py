"""
Built-in resolver configurations.

Provides pre-configured profiles for popular public DNS resolvers
with support for UDP, TCP, DoT, and DoH.
"""

from .models import ResolverConfig


# Pre-configured resolver profiles
RESOLVERS: dict[str, ResolverConfig] = {
    "cloudflare": ResolverConfig(
        name="Cloudflare",
        ipv4="1.1.1.1",
        ipv6="2606:4700:4700::1111",
        dot_hostname="cloudflare-dns.com",
        doh_url="https://cloudflare-dns.com/dns-query",
        description="Cloudflare's privacy-focused DNS resolver"
    ),
    "cloudflare-secondary": ResolverConfig(
        name="Cloudflare Secondary",
        ipv4="1.0.0.1",
        ipv6="2606:4700:4700::1001",
        dot_hostname="cloudflare-dns.com",
        doh_url="https://cloudflare-dns.com/dns-query",
        description="Cloudflare's secondary DNS resolver"
    ),
    "google": ResolverConfig(
        name="Google",
        ipv4="8.8.8.8",
        ipv6="2001:4860:4860::8888",
        dot_hostname="dns.google",
        doh_url="https://dns.google/dns-query",
        description="Google Public DNS"
    ),
    "google-secondary": ResolverConfig(
        name="Google Secondary",
        ipv4="8.8.4.4",
        ipv6="2001:4860:4860::8844",
        dot_hostname="dns.google",
        doh_url="https://dns.google/dns-query",
        description="Google Public DNS secondary"
    ),
    "quad9": ResolverConfig(
        name="Quad9",
        ipv4="9.9.9.9",
        ipv6="2620:fe::fe",
        dot_hostname="dns.quad9.net",
        doh_url="https://dns.quad9.net/dns-query",
        description="Quad9 with malware blocking"
    ),
    "quad9-unsecured": ResolverConfig(
        name="Quad9 Unsecured",
        ipv4="9.9.9.10",
        ipv6="2620:fe::10",
        dot_hostname="dns10.quad9.net",
        doh_url="https://dns10.quad9.net/dns-query",
        description="Quad9 without malware blocking"
    ),
    "nextdns": ResolverConfig(
        name="NextDNS",
        ipv4="45.90.28.0",
        ipv6="2a07:a8c0::",
        dot_hostname="dns.nextdns.io",
        doh_url="https://dns.nextdns.io/dns-query",
        description="NextDNS (requires configuration ID for full features)"
    ),
    "nextdns-secondary": ResolverConfig(
        name="NextDNS Secondary",
        ipv4="45.90.30.0",
        ipv6="2a07:a8c1::",
        dot_hostname="dns.nextdns.io",
        doh_url="https://dns.nextdns.io/dns-query",
        description="NextDNS secondary resolver"
    ),
    "controld": ResolverConfig(
        name="Control D",
        ipv4="76.76.2.0",
        ipv6="2606:1a40::",
        dot_hostname="p0.freedns.controld.com",
        doh_url="https://freedns.controld.com/p0",
        description="Control D free unfiltered DNS"
    ),
    "controld-malware": ResolverConfig(
        name="Control D Malware",
        ipv4="76.76.2.1",
        ipv6="2606:1a40::1",
        dot_hostname="p1.freedns.controld.com",
        doh_url="https://freedns.controld.com/p1",
        description="Control D with malware blocking"
    ),
    "opendns": ResolverConfig(
        name="OpenDNS",
        ipv4="208.67.222.222",
        ipv6="2620:119:35::35",
        dot_hostname=None,  # OpenDNS doesn't support DoT
        doh_url="https://doh.opendns.com/dns-query",
        description="Cisco OpenDNS"
    ),
    "adguard": ResolverConfig(
        name="AdGuard",
        ipv4="94.140.14.14",
        ipv6="2a10:50c0::ad1:ff",
        dot_hostname="dns.adguard-dns.com",
        doh_url="https://dns.adguard-dns.com/dns-query",
        description="AdGuard DNS with ad blocking"
    ),
    "cleanbrowsing": ResolverConfig(
        name="CleanBrowsing Security",
        ipv4="185.228.168.9",
        ipv6="2a0d:2a00:1::2",
        dot_hostname="security-filter-dns.cleanbrowsing.org",
        doh_url="https://doh.cleanbrowsing.org/doh/security-filter/",
        description="CleanBrowsing security filter"
    ),
}

# Default resolvers for quick comparison
DEFAULT_RESOLVERS = ["cloudflare", "google", "quad9"]


def get_resolver(name: str) -> ResolverConfig:
    """Get a resolver by name (case-insensitive)."""
    key = name.lower()
    if key in RESOLVERS:
        return RESOLVERS[key]
    raise ValueError(f"Unknown resolver: {name}. Available: {list(RESOLVERS.keys())}")


def create_custom_resolver(
    ip: str,
    name: str = "Custom",
    dot_hostname: str | None = None,
    doh_url: str | None = None,
) -> ResolverConfig:
    """Create a custom resolver configuration."""
    return ResolverConfig(
        name=name,
        ipv4=ip,
        dot_hostname=dot_hostname,
        doh_url=doh_url,
        description=f"Custom resolver at {ip}"
    )


def list_resolvers() -> list[str]:
    """List all available resolver names."""
    return list(RESOLVERS.keys())
