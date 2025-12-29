"""
Cross-platform DNS cache utilities.

Provides functions to flush the OS DNS cache on
Windows, Linux, and macOS.
"""

import platform
import subprocess
import sys
from typing import Tuple


def get_platform() -> str:
    """Get the current platform name."""
    system = platform.system().lower()
    if system == "darwin":
        return "macos"
    return system  # "windows" or "linux"


def flush_dns_cache() -> Tuple[bool, str]:
    """
    Attempt to flush the OS DNS cache.
    
    Returns:
        Tuple of (success: bool, message: str)
        
    Note:
        This typically requires elevated privileges.
    """
    system = get_platform()
    
    try:
        if system == "windows":
            result = subprocess.run(
                ["ipconfig", "/flushdns"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                return True, "Windows DNS cache flushed successfully"
            return False, f"Failed to flush: {result.stderr}"
        
        elif system == "linux":
            # Try systemd-resolve first (modern systems)
            result = subprocess.run(
                ["systemd-resolve", "--flush-caches"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                return True, "Linux DNS cache flushed (systemd-resolve)"
            
            # Try resolvectl (alternative)
            result = subprocess.run(
                ["resolvectl", "flush-caches"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                return True, "Linux DNS cache flushed (resolvectl)"
            
            # Try service restart (older systems)
            result = subprocess.run(
                ["sudo", "service", "nscd", "restart"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                return True, "Linux DNS cache flushed (nscd restart)"
            
            return False, "Could not flush DNS cache - try manually"
        
        elif system == "macos":
            # macOS has different commands for different versions
            commands = [
                ["sudo", "dscacheutil", "-flushcache"],
                ["sudo", "killall", "-HUP", "mDNSResponder"],
            ]
            
            for cmd in commands:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
            
            return True, "macOS DNS cache flush attempted"
        
        else:
            return False, f"Unsupported platform: {system}"
    
    except subprocess.TimeoutExpired:
        return False, "DNS cache flush timed out"
    except FileNotFoundError as e:
        return False, f"Command not found: {e}"
    except PermissionError:
        return False, "Elevated privileges required to flush DNS cache"
    except Exception as e:
        return False, f"Error flushing DNS cache: {e}"


def check_elevated_privileges() -> bool:
    """Check if running with elevated privileges."""
    system = get_platform()
    
    if system == "windows":
        try:
            import ctypes
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except Exception:
            return False
    else:
        import os
        return os.geteuid() == 0


def get_system_dns_servers() -> list[str]:
    """
    Get the currently configured system DNS servers.
    
    Returns:
        List of DNS server IPs
    """
    system = get_platform()
    servers = []
    
    try:
        if system == "windows":
            result = subprocess.run(
                ["netsh", "interface", "ip", "show", "dns"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            # Parse output for DNS server IPs
            import re
            for line in result.stdout.split("\n"):
                matches = re.findall(r'\d+\.\d+\.\d+\.\d+', line)
                servers.extend(matches)
        
        elif system in ("linux", "macos"):
            try:
                with open("/etc/resolv.conf", "r") as f:
                    import re
                    for line in f:
                        if line.strip().startswith("nameserver"):
                            match = re.search(r'\d+\.\d+\.\d+\.\d+', line)
                            if match:
                                servers.append(match.group())
            except FileNotFoundError:
                pass
    
    except Exception:
        pass
    
    return list(set(servers))  # Remove duplicates
