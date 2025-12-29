# DNSPulse

A comprehensive DNS resolver benchmarking tool that measures **real-world performance**, not synthetic benchmarks.

## Why This Tool?

### ICMP Ping is Misleading for DNS Benchmarking

🚫 **What ping measures:** Network latency to a host

❌ **What ping does NOT measure:**
- DNS query processing time
- DNSSEC validation overhead
- Cache hit/miss behavior
- Protocol-specific overhead (DoH/DoT handshakes)
- Upstream resolution time when cache misses

A resolver with a 10ms ping can have 200ms DNS response times. **This tool measures actual DNS performance.**

## Features

- 🎯 **True DNS Timing** - Measures actual query round-trip time with nanosecond precision
- 🔄 **Cache Bypass** - Generates random subdomains to force upstream resolution
- 🌐 **Top 100 Websites** - Automatic workload from most visited sites + CDNs/APIs/trackers
- 📊 **Statistical Analysis** - min/max/avg/median, p95/p99, jitter, packet loss
- 🔐 **Multiple Transports** - UDP, TCP, DoT (DNS over TLS), DoH (DNS over HTTPS)
- ⚡ **Burst Testing** - Simulates page load with 10-40 parallel queries
- 📈 **Multiple Output Formats** - JSON, CSV, rich console tables

## Installation

```bash
# Clone the repository
cd dns-speedchecker

# Install in development mode
pip install -e .

# Or install with graph support
pip install -e ".[graphs]"
```

## Quick Start

```bash
# Run default benchmark (Cloudflare vs Google vs Quad9)
dns-speedchecker run

# Compare specific resolvers
dns-speedchecker run -r cloudflare -r google -r nextdns

# Test with DNS over HTTPS
dns-speedchecker run -r cloudflare -t doh

# Comprehensive test (cold, warm, burst modes)
dns-speedchecker run --mode comprehensive

# Export results to JSON
dns-speedchecker run -o results.json

# Quiet mode with JSON output
dns-speedchecker run --quiet --json > results.json
```

## Commands

### `run` - Execute Benchmark

```bash
dns-speedchecker run [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `-r, --resolver NAME` | Resolver to test (can repeat) |
| `-c, --custom-resolver IP` | Custom resolver IP |
| `-t, --transport TYPE` | Protocol: udp, tcp, dot, doh |
| `-m, --mode MODE` | Test mode: cold, warm, burst, comprehensive |
| `-d, --domains N` | Number of domains to test (default: 30) |
| `-n, --runs N` | Test iterations (default: 2) |
| `-p, --parallel N` | Concurrent queries (default: 10) |
| `-o, --output FILE` | Save results to file (.json or .csv) |
| `--no-dnssec` | Disable DNSSEC validation |
| `--flush-cache` | Flush OS DNS cache before testing |
| `-q, --quiet` | Suppress progress output |
| `--json` | Output JSON to stdout |

### `list` - Show Available Resolvers

```bash
dns-speedchecker list-available
```

### `flush` - Flush DNS Cache

```bash
dns-speedchecker flush
```

### `info` - Show System DNS Config

```bash
dns-speedchecker info
```

## Built-in Resolvers

| Name | IP | DoT | DoH | Description |
|------|-----|-----|-----|-------------|
| cloudflare | 1.1.1.1 | ✓ | ✓ | Privacy-focused |
| google | 8.8.8.8 | ✓ | ✓ | Google Public DNS |
| quad9 | 9.9.9.9 | ✓ | ✓ | Malware blocking |
| nextdns | 45.90.28.0 | ✓ | ✓ | Configurable filtering |
| controld | 76.76.2.0 | ✓ | ✓ | Free unfiltered |
| opendns | 208.67.222.222 | ✗ | ✓ | Cisco OpenDNS |
| adguard | 94.140.14.14 | ✓ | ✓ | Ad blocking |

## Test Modes

### Cold Start (`--mode cold`)
- Generates random subdomains to bypass resolver cache
- Measures actual upstream resolution performance
- Most realistic for new domain lookups

### Warm Cache (`--mode warm`)
- First warms resolver cache, then measures
- Tests cached response performance
- Represents repeat visits to sites

### Burst (`--mode burst`)
- Simulates page load with parallel queries
- Tests resolver under concurrent load
- Includes main site + CDN + API + third-party

### Comprehensive (`--mode comprehensive`)
- Runs all test modes
- Complete performance profile
- Best for detailed analysis

## Output Example

```
═══════════════════════════════════════════════════════════════════════
                    DNS RESOLVER BENCHMARK RESULTS
═══════════════════════════════════════════════════════════════════════

  Test Mode: COLD
  Duration: 12.3s
  Domains Tested: 30
  Runs: 2

───────────────────────────────────────────────────────────────────────

  Cloudflare (1.1.1.1)
  Transport: UDP
  ├── Queries: 240 | Success: 238 (99.2%)
  ├── Latency: min=8.2ms, avg=24.1ms, max=156.3ms
  ├── Percentiles: p50=18.4ms, p95=45.2ms, p99=89.1ms
  └── Jitter: 12.3ms | Timeouts: 2

  Google (8.8.8.8)
  Transport: UDP
  ├── Queries: 240 | Success: 239 (99.6%)
  ├── Latency: min=12.1ms, avg=31.2ms, max=203.4ms
  ├── Percentiles: p50=25.3ms, p95=62.1ms, p99=112.5ms
  └── Jitter: 18.7ms | Timeouts: 1

───────────────────────────────────────────────────────────────────────

  🏆 WINNER: Cloudflare
     Average Latency: 24.1ms
     Success Rate: 99.2%

  Performance Comparison:
     vs Google: 22.8% faster

═══════════════════════════════════════════════════════════════════════
```

## Programmatic Usage

```python
import asyncio
from dns_speedchecker import TestRunner
from dns_speedchecker.resolvers import get_resolver
from dns_speedchecker.models import Transport

async def benchmark():
    resolvers = [
        get_resolver("cloudflare"),
        get_resolver("google"),
    ]
    
    runner = TestRunner(
        resolvers=resolvers,
        transports=[Transport.UDP, Transport.DOH],
    )
    
    result = await runner.run_cold_test(domain_count=50, runs=3)
    
    print(f"Winner: {result.winner.resolver.name}")
    print(f"Avg latency: {result.winner.avg_latency:.1f}ms")
    
    await runner.close()

asyncio.run(benchmark())
```

## Methodology

### Timing Accuracy
- Uses `time.perf_counter_ns()` for nanosecond precision
- Separates connection/handshake time from query time
- Measures actual DNS protocol round-trip, not OS shortcuts

### Cache Bypass
- Random subdomain prefixes (e.g., `abc123.www.google.com`)
- Forces resolver to query upstream
- Ensures fair comparison between resolvers

### Statistical Validity
- Multiple runs reduce randomness
- Calculates percentiles (p95, p99) for tail latency
- Measures jitter for consistency analysis

### Workload Realism
- Top 100 websites as base
- Common CDNs, APIs, and third-party resources
- Both A and AAAA records tested

## Limitations

1. **Network Conditions** - Results depend on current network state
2. **Anycast Variability** - Resolver performance varies by location
3. **Python Overhead** - Async overhead included (documented)
4. **Intermediate Caching** - ISP/network caches may affect results

## License

MIT License
