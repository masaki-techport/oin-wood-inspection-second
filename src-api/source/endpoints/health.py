"""
Health check and network diagnostics endpoints.
Provides comprehensive health monitoring and network connectivity testing.
"""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from typing import Dict, Any, Optional
import logging
import time
import platform
import psutil
from network_config import network_config
from monitoring.network_monitor import network_monitor

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["health"])

@router.get("/health")
async def api_health_check():
    """
    Basic API health check endpoint.
    
    Returns:
        Dict: Basic health status
    """
    return {
        "status": "ok",
        "message": "API is running and accessible",
        "timestamp": time.time()
    }

@router.get("/health/detailed")
async def detailed_health_check(request: Request):
    """
    Detailed health check with system information.
    
    Args:
        request: FastAPI request object
        
    Returns:
        Dict: Detailed health status including system info
    """
    try:
        # Get client information
        client_host = request.client.host if request.client else "unknown"
        
        # Get system information
        system_info = {
            "platform": platform.platform(),
            "python_version": platform.python_version(),
            "cpu_count": psutil.cpu_count(),
            "memory_total": psutil.virtual_memory().total,
            "memory_available": psutil.virtual_memory().available,
            "disk_usage": psutil.disk_usage('/').percent if platform.system() != "Windows" else psutil.disk_usage('C:').percent
        }
        
        return {
            "status": "ok",
            "message": "Detailed health check successful",
            "client_ip": client_host,
            "server_info": system_info,
            "timestamp": time.time()
        }
        
    except Exception as e:
        logger.error(f"Error in detailed health check: {e}")
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")

@router.get("/network/status")
async def network_status(request: Request):
    """
    Get comprehensive network status and configuration.
    
    Args:
        request: FastAPI request object
        
    Returns:
        Dict: Network status information
    """
    try:
        # Get client information
        client_host = request.client.host if request.client else "unknown"
        
        # Get network status from network_config
        status = network_config.get_network_status()
        
        # Add client information
        status["client_info"] = {
            "ip": client_host,
            "user_agent": request.headers.get("user-agent", "unknown"),
            "is_external_client": client_host not in ["127.0.0.1", "localhost", "::1"]
        }
        
        # Add server binding information
        status["server_config"] = {
            "host": "0.0.0.0",
            "port": 8000,
            "cors_enabled": True,
            "allows_external_access": True
        }
        
        logger.info(f"Network status requested by {client_host}")
        return status
        
    except Exception as e:
        logger.error(f"Error getting network status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get network status: {str(e)}")

@router.get("/network/interfaces")
async def network_interfaces():
    """
    Get detailed information about network interfaces.
    
    Returns:
        Dict: Network interfaces information
    """
    try:
        interfaces = network_config.get_network_interfaces()
        
        return {
            "status": "ok",
            "interfaces": [
                {
                    "name": iface.name,
                    "ip": iface.ip,
                    "is_active": iface.is_active,
                    "is_external": iface.is_external,
                    "netmask": iface.netmask,
                    "broadcast": iface.broadcast
                }
                for iface in interfaces
            ],
            "primary_ip": network_config.get_host_ip(),
            "timestamp": time.time()
        }
        
    except Exception as e:
        logger.error(f"Error getting network interfaces: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get network interfaces: {str(e)}")

@router.get("/network/test")
async def network_connectivity_test(
    target_host: Optional[str] = "8.8.8.8",
    target_port: Optional[int] = 53,
    timeout: Optional[int] = 5
):
    """
    Test network connectivity to external hosts.
    
    Args:
        target_host: Host to test connectivity to
        target_port: Port to test connectivity to
        timeout: Connection timeout in seconds
        
    Returns:
        Dict: Connectivity test results
    """
    try:
        # Validate parameters
        if timeout > 30:
            timeout = 30  # Cap timeout at 30 seconds
            
        # Test external connectivity
        external_test = network_config.test_external_connectivity(
            target_host=target_host,
            target_port=target_port,
            timeout=timeout
        )
        
        # Test local API connectivity
        host_ip = network_config.get_host_ip()
        local_test = network_config.test_local_api_connectivity(host_ip, 8000)
        
        return {
            "status": "ok",
            "tests": {
                "external_connectivity": external_test,
                "local_api_connectivity": local_test
            },
            "summary": {
                "external_reachable": external_test["success"],
                "local_api_reachable": local_test["success"],
                "overall_status": "healthy" if external_test["success"] and local_test["success"] else "degraded"
            },
            "timestamp": time.time()
        }
        
    except Exception as e:
        logger.error(f"Error in network connectivity test: {e}")
        raise HTTPException(status_code=500, detail=f"Network test failed: {str(e)}")

@router.post("/network/test/custom")
async def custom_connectivity_test(test_config: Dict[str, Any]):
    """
    Run custom connectivity tests with user-defined parameters.
    
    Args:
        test_config: Test configuration dictionary
        
    Returns:
        Dict: Custom test results
    """
    try:
        results = []
        
        # Validate test configuration
        if "tests" not in test_config:
            raise HTTPException(status_code=400, detail="Missing 'tests' in configuration")
            
        for test in test_config["tests"]:
            if "host" not in test or "port" not in test:
                continue
                
            host = test["host"]
            port = test["port"]
            timeout = test.get("timeout", 5)
            test_type = test.get("type", "socket")
            
            if test_type == "socket":
                result = network_config.test_external_connectivity(host, port, timeout)
            elif test_type == "http":
                endpoint = test.get("endpoint", "/health")
                result = network_config.test_local_api_connectivity(host, port, endpoint)
            else:
                result = {"success": False, "error": f"Unknown test type: {test_type}"}
                
            result["test_name"] = test.get("name", f"{host}:{port}")
            results.append(result)
            
        return {
            "status": "ok",
            "custom_tests": results,
            "summary": {
                "total_tests": len(results),
                "successful_tests": sum(1 for r in results if r["success"]),
                "failed_tests": sum(1 for r in results if not r["success"])
            },
            "timestamp": time.time()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in custom connectivity test: {e}")
        raise HTTPException(status_code=500, detail=f"Custom test failed: {str(e)}")

@router.get("/network/diagnostics")
async def network_diagnostics(request: Request):
    """
    Comprehensive network diagnostics including troubleshooting information.
    
    Args:
        request: FastAPI request object
        
    Returns:
        Dict: Comprehensive network diagnostics
    """
    try:
        client_host = request.client.host if request.client else "unknown"
        
        # Get basic network status
        status = network_config.get_network_status()
        
        # Add diagnostics information
        diagnostics = {
            "client_diagnostics": {
                "client_ip": client_host,
                "is_localhost": client_host in ["127.0.0.1", "localhost", "::1"],
                "is_private_network": _is_private_ip(client_host),
                "connection_type": "local" if client_host in ["127.0.0.1", "localhost", "::1"] else "network"
            },
            "server_diagnostics": {
                "binding_host": "0.0.0.0",
                "binding_port": 8000,
                "accepts_external": True,
                "cors_configured": True
            },
            "troubleshooting": _generate_troubleshooting_tips(client_host, status)
        }
        
        return {
            "status": "ok",
            "network_status": status,
            "diagnostics": diagnostics,
            "timestamp": time.time()
        }
        
    except Exception as e:
        logger.error(f"Error in network diagnostics: {e}")
        raise HTTPException(status_code=500, detail=f"Diagnostics failed: {str(e)}")

def _is_private_ip(ip: str) -> bool:
    """Check if an IP address is in a private network range."""
    try:
        import ipaddress
        ip_obj = ipaddress.ip_address(ip)
        return ip_obj.is_private
    except:
        return False

def _generate_troubleshooting_tips(client_ip: str, network_status: Dict[str, Any]) -> Dict[str, Any]:
    """Generate troubleshooting tips based on network status."""
    tips = []
    
    # Check if client is external but having issues
    if client_ip not in ["127.0.0.1", "localhost", "::1"]:
        if not network_status.get("external_connectivity", {}).get("success", False):
            tips.append({
                "issue": "External connectivity issues detected",
                "solution": "Check firewall settings and network configuration",
                "priority": "high"
            })
            
    # Check binding validation
    if not network_status.get("binding_validation", {}).get("valid", False):
        tips.append({
            "issue": "Server binding validation failed",
            "solution": "Ensure port 8000 is available and not blocked",
            "priority": "critical"
        })
        
    # Check for active external interfaces
    external_interfaces = [
        iface for iface in network_status.get("interfaces", [])
        if iface.get("is_external", False) and iface.get("is_active", False)
    ]
    
    if not external_interfaces:
        tips.append({
            "issue": "No active external network interfaces found",
            "solution": "Check network adapter configuration and connectivity",
            "priority": "high"
        })
        
    return {
        "tips": tips,
        "client_type": "external" if client_ip not in ["127.0.0.1", "localhost", "::1"] else "local",
        "recommendations": [
            "Ensure backend server is running on 0.0.0.0:8000",
            "Verify firewall allows connections on port 8000",
            "Check that CORS is properly configured",
            "Confirm network connectivity between devices"
        ]
    }

@router.get("/network/monitoring/status")
async def network_monitoring_status():
    """
    Get network monitoring status and metrics.

    Returns:
        Dict: Network monitoring status
    """
    try:
        status_summary = network_monitor.get_status_summary()

        return {
            "status": "ok",
            "monitoring": {
                "is_running": network_monitor.is_running,
                "active_targets": len(network_monitor.targets),
                "monitoring_tasks": len(network_monitor.monitoring_tasks)
            },
            "network_status": status_summary,
            "timestamp": time.time()
        }

    except Exception as e:
        logger.error(f"Error getting network monitoring status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get monitoring status: {str(e)}")

@router.get("/network/monitoring/targets/{target_name}/metrics")
async def get_target_metrics(target_name: str, limit: int = 20):
    """
    Get metrics for a specific monitoring target.

    Args:
        target_name: Name of the monitoring target
        limit: Maximum number of metrics to return

    Returns:
        Dict: Target metrics
    """
    try:
        if target_name not in network_monitor.targets:
            raise HTTPException(status_code=404, detail=f"Target '{target_name}' not found")

        metrics = network_monitor.get_target_metrics(target_name, limit)
        target = network_monitor.targets[target_name]

        return {
            "status": "ok",
            "target": {
                "name": target_name,
                "url": target.url,
                "interval": target.interval,
                "enabled": target.enabled
            },
            "metrics": metrics,
            "timestamp": time.time()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting target metrics: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get target metrics: {str(e)}")
