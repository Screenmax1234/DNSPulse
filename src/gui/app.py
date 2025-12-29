"""
FastAPI application for DNS Speed Checker GUI.

Serves the web interface and provides API endpoints for benchmarking.
"""

import asyncio
import webbrowser
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import uvicorn

from ..models import Transport, RecordType
from ..resolvers import RESOLVERS, DEFAULT_RESOLVERS, get_resolver, create_custom_resolver
from ..runner import TestRunner
from ..output import JSONOutput


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    
    app = FastAPI(
        title="DNS Speed Checker",
        description="Real-world DNS resolver benchmarking",
        version="1.0.0",
    )
    
    # Static files directory
    static_dir = Path(__file__).parent / "static"
    
    # Store for active WebSocket connections
    active_connections: list[WebSocket] = []
    
    # Store for benchmark results
    latest_results = {}
    
    @app.get("/")
    async def root():
        """Serve the main HTML page."""
        return FileResponse(static_dir / "index.html")
    
    @app.get("/api/resolvers")
    async def get_resolvers():
        """Get list of available resolvers."""
        return {
            "resolvers": [
                {
                    "id": key,
                    "name": resolver.name,
                    "ip": resolver.ipv4,
                    "dot": resolver.dot_hostname is not None,
                    "doh": resolver.doh_url is not None,
                    "description": resolver.description,
                }
                for key, resolver in RESOLVERS.items()
            ],
            "defaults": DEFAULT_RESOLVERS,
        }
    
    @app.get("/api/config")
    async def get_config():
        """Get default configuration options."""
        return {
            "transports": [t.value for t in Transport],
            "modes": ["cold", "warm", "burst", "comprehensive"],
            "defaults": {
                "resolvers": DEFAULT_RESOLVERS,
                "transport": "udp",
                "mode": "cold",
                "domains": 30,
                "runs": 2,
                "parallel": 10,
            }
        }
    
    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        """WebSocket endpoint for real-time progress updates."""
        await websocket.accept()
        active_connections.append(websocket)
        
        try:
            while True:
                # Receive benchmark request
                data = await websocket.receive_json()
                
                if data.get("action") == "start_benchmark":
                    await run_benchmark(websocket, data)
                elif data.get("action") == "ping":
                    await websocket.send_json({"type": "pong"})
                    
        except WebSocketDisconnect:
            active_connections.remove(websocket)
        except Exception as e:
            try:
                await websocket.send_json({"type": "error", "message": str(e)})
            except:
                pass
            if websocket in active_connections:
                active_connections.remove(websocket)
    
    async def run_benchmark(websocket: WebSocket, config: dict):
        """Run benchmark and send progress updates via WebSocket."""
        
        # Parse configuration
        resolver_ids = config.get("resolvers", DEFAULT_RESOLVERS)
        transport_str = config.get("transport", "udp")
        mode = config.get("mode", "cold")
        domains = config.get("domains", 30)
        runs = config.get("runs", 2)
        parallel = config.get("parallel", 10)
        custom_ips = config.get("custom_resolvers", [])
        
        # Build resolver list
        resolvers = []
        for rid in resolver_ids:
            try:
                resolvers.append(get_resolver(rid))
            except ValueError:
                pass
        
        for ip in custom_ips:
            if ip.strip():
                resolvers.append(create_custom_resolver(ip.strip()))
        
        if not resolvers:
            await websocket.send_json({
                "type": "error",
                "message": "No valid resolvers selected"
            })
            return
        
        # Parse transport
        try:
            transport = Transport(transport_str)
        except ValueError:
            transport = Transport.UDP
        
        # Progress callback
        async def progress_callback(message: str, current: int, total: int):
            progress = (current / total * 100) if total > 0 else 0
            await websocket.send_json({
                "type": "progress",
                "message": message,
                "current": current,
                "total": total,
                "percent": round(progress, 1),
            })
        
        # Sync wrapper for async callback
        def sync_progress(message: str, current: int, total: int):
            asyncio.create_task(progress_callback(message, current, total))
        
        # Send start message
        await websocket.send_json({
            "type": "started",
            "mode": mode,
            "resolvers": [r.name for r in resolvers],
        })
        
        # Create runner
        runner = TestRunner(
            resolvers=resolvers,
            transports=[transport],
            timeout=5.0,
        )
        
        try:
            # Run appropriate test
            if mode == "cold":
                result = await runner.run_cold_test(
                    domain_count=domains,
                    runs=runs,
                    concurrency=parallel,
                    progress_callback=sync_progress,
                )
            elif mode == "warm":
                result = await runner.run_warm_test(
                    domain_count=domains,
                    runs=runs,
                    concurrency=parallel,
                    progress_callback=sync_progress,
                )
            elif mode == "burst":
                result = await runner.run_burst_test(
                    burst_size=domains,
                    parallel_queries=parallel,
                    runs=runs,
                    progress_callback=sync_progress,
                )
            else:  # comprehensive
                results = await runner.run_comprehensive_test(
                    domain_count=domains,
                    runs=runs,
                    progress_callback=sync_progress,
                )
                # Use cold result as main
                result = results.get("cold", list(results.values())[0])
            
            # Store and send results
            latest_results["last"] = result
            
            # Build response data
            resolver_data = []
            for stats in result.resolver_stats:
                resolver_data.append({
                    "name": stats.resolver.name,
                    "ip": stats.resolver.ipv4,
                    "transport": stats.transport.value,
                    "total": stats.total_queries,
                    "successful": stats.successful_queries,
                    "success_rate": round(stats.success_rate, 1),
                    "min": round(stats.min_latency, 2),
                    "max": round(stats.max_latency, 2),
                    "avg": round(stats.avg_latency, 2),
                    "median": round(stats.median_latency, 2),
                    "p95": round(stats.p95_latency, 2),
                    "p99": round(stats.p99_latency, 2),
                    "jitter": round(stats.jitter_ms, 2),
                    "timeouts": stats.timeout_count,
                    "errors": stats.error_count,
                })
            
            winner = result.winner
            winner_data = None
            if winner:
                winner_data = {
                    "name": winner.resolver.name,
                    "avg": round(winner.avg_latency, 2),
                    "success_rate": round(winner.success_rate, 1),
                }
            
            await websocket.send_json({
                "type": "complete",
                "duration": round(result.duration_seconds, 1),
                "mode": result.test_mode,
                "domains": result.domains_tested,
                "runs": result.runs,
                "resolvers": resolver_data,
                "winner": winner_data,
            })
            
        except Exception as e:
            await websocket.send_json({
                "type": "error",
                "message": str(e),
            })
        finally:
            await runner.close()
    
    @app.get("/api/results/json")
    async def get_results_json():
        """Get latest results as JSON."""
        if "last" in latest_results:
            return JSONOutput.format(latest_results["last"])
        return {"error": "No results available"}
    
    # Mount static files last (after other routes)
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
    
    return app


def run_gui(host: str = "127.0.0.1", port: int = 5000, open_browser: bool = True):
    """Run the GUI server."""
    app = create_app()
    
    if open_browser:
        # Open browser after a short delay
        import threading
        def open_browser_delayed():
            import time
            time.sleep(1)
            webbrowser.open(f"http://{host}:{port}")
        
        threading.Thread(target=open_browser_delayed, daemon=True).start()
    
    uvicorn.run(app, host=host, port=port, log_level="warning")
