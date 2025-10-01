"""
Request logging middleware with client IP tracking and network diagnostics.
"""

import time
import logging
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
import json

logger = logging.getLogger(__name__)

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for comprehensive request logging with network diagnostics."""
    
    def __init__(self, app: ASGIApp, log_level: str = "INFO"):
        super().__init__(app)
        self.log_level = log_level.upper()
        
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with comprehensive logging."""
        start_time = time.time()
        
        # Extract client information
        client_info = self._extract_client_info(request)
        
        # Log incoming request
        self._log_request(request, client_info)
        
        # Process request
        try:
            response = await call_next(request)
            
            # Calculate processing time
            process_time = time.time() - start_time
            
            # Log response
            self._log_response(request, response, client_info, process_time)
            
            # Add custom headers for debugging
            response.headers["X-Process-Time"] = str(process_time)
            response.headers["X-Client-IP"] = client_info["ip"]
            
            return response
            
        except Exception as e:
            process_time = time.time() - start_time
            self._log_error(request, e, client_info, process_time)
            raise
    
    def _extract_client_info(self, request: Request) -> dict:
        """Extract comprehensive client information from request."""
        # Get client IP with fallback logic
        client_ip = "unknown"
        
        # Try various headers for client IP
        ip_headers = [
            "X-Forwarded-For",
            "X-Real-IP", 
            "X-Client-IP",
            "CF-Connecting-IP",  # Cloudflare
            "True-Client-IP"     # Akamai
        ]
        
        for header in ip_headers:
            if header in request.headers:
                ip_value = request.headers[header]
                # Take first IP if comma-separated
                client_ip = ip_value.split(',')[0].strip()
                break
        
        # Fallback to request.client if available
        if client_ip == "unknown" and request.client:
            client_ip = request.client.host
        
        # Determine client type
        client_type = self._determine_client_type(client_ip)
        
        return {
            "ip": client_ip,
            "type": client_type,
            "user_agent": request.headers.get("user-agent", "unknown"),
            "referer": request.headers.get("referer", "none"),
            "host": request.headers.get("host", "unknown"),
            "origin": request.headers.get("origin", "none"),
            "forwarded_for": request.headers.get("x-forwarded-for", "none"),
            "real_ip": request.headers.get("x-real-ip", "none")
        }
    
    def _determine_client_type(self, ip: str) -> str:
        """Determine the type of client based on IP address."""
        if ip in ["127.0.0.1", "localhost", "::1"]:
            return "localhost"
        elif ip.startswith("192.168.") or ip.startswith("10.") or ip.startswith("172."):
            return "local_network"
        elif ip == "unknown":
            return "unknown"
        else:
            return "external"
    
    def _log_request(self, request: Request, client_info: dict):
        """Log incoming request details."""
        log_data = {
            "event": "request_start",
            "method": request.method,
            "url": str(request.url),
            "path": request.url.path,
            "query_params": dict(request.query_params),
            "client": client_info,
            "timestamp": time.time()
        }
        
        if self.log_level == "DEBUG":
            log_data["headers"] = dict(request.headers)
        
        logger.debug(f"[REQUEST] {client_info['type'].upper()} {client_info['ip']} {request.method} {request.url.path}")
        
        if self.log_level == "DEBUG":
            logger.debug(f"[REQUEST DETAIL] {json.dumps(log_data, indent=2)}")
    
    def _log_response(self, request: Request, response: Response, client_info: dict, process_time: float):
        """Log response details."""
        log_data = {
            "event": "request_complete",
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "process_time": round(process_time * 1000, 2),  # Convert to milliseconds
            "client": client_info,
            "timestamp": time.time()
        }
        
        if self.log_level == "DEBUG":
            log_data["response_headers"] = dict(response.headers)
        
        # Determine log level based on status code
        if response.status_code >= 500:
            log_level = "ERROR"
        elif response.status_code >= 400:
            log_level = "WARNING"
        else:
            log_level = "DEBUG"
        
        logger.log(
            getattr(logging, log_level),
            f"[RESPONSE] {client_info['type'].upper()} {client_info['ip']} "
            f"{request.method} {request.url.path} -> {response.status_code} "
            f"({log_data['process_time']}ms)"
        )
        
        if self.log_level == "DEBUG":
            logger.debug(f"[RESPONSE DETAIL] {json.dumps(log_data, indent=2)}")
    
    def _log_error(self, request: Request, error: Exception, client_info: dict, process_time: float):
        """Log error details."""
        log_data = {
            "event": "request_error",
            "method": request.method,
            "path": request.url.path,
            "error_type": type(error).__name__,
            "error_message": str(error),
            "process_time": round(process_time * 1000, 2),
            "client": client_info,
            "timestamp": time.time()
        }
        
        logger.error(
            f"[ERROR] {client_info['type'].upper()} {client_info['ip']} "
            f"{request.method} {request.url.path} -> ERROR: {error}"
        )
        
        if self.log_level == "DEBUG":
            logger.debug(f"[ERROR DETAIL] {json.dumps(log_data, indent=2)}")

class NetworkDiagnosticsLogger:
    """Utility class for network-specific logging and diagnostics."""
    
    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.diagnostics")
    
    def log_network_event(self, event_type: str, details: dict):
        """Log network-related events."""
        log_entry = {
            "event_type": event_type,
            "timestamp": time.time(),
            "details": details
        }
        
        self.logger.info(f"[NETWORK] {event_type}: {json.dumps(details)}")
    
    def log_connection_attempt(self, client_ip: str, success: bool, details: dict = None):
        """Log connection attempts from clients."""
        event_details = {
            "client_ip": client_ip,
            "success": success,
            "client_type": self._determine_client_type(client_ip)
        }
        
        if details:
            event_details.update(details)
        
        self.log_network_event("connection_attempt", event_details)
    
    def log_cors_request(self, origin: str, method: str, allowed: bool):
        """Log CORS requests and their outcomes."""
        self.log_network_event("cors_request", {
            "origin": origin,
            "method": method,
            "allowed": allowed
        })
    
    def log_proxy_request(self, client_ip: str, target_url: str, success: bool, error: str = None):
        """Log proxy requests (for frontend integration)."""
        details = {
            "client_ip": client_ip,
            "target_url": target_url,
            "success": success
        }
        
        if error:
            details["error"] = error
        
        self.log_network_event("proxy_request", details)
    
    def _determine_client_type(self, ip: str) -> str:
        """Determine the type of client based on IP address."""
        if ip in ["127.0.0.1", "localhost", "::1"]:
            return "localhost"
        elif ip.startswith("192.168.") or ip.startswith("10.") or ip.startswith("172."):
            return "local_network"
        elif ip == "unknown":
            return "unknown"
        else:
            return "external"

# Global diagnostics logger instance
network_diagnostics = NetworkDiagnosticsLogger()
