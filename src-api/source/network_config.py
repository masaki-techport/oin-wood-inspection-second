"""
Network configuration utilities for the wood inspection application.
Provides network interface detection, IP address resolution, and connectivity testing.
"""

import socket
import subprocess
import platform
import ipaddress
import requests
from typing import Dict, List, Any, Optional, Tuple
import logging
import psutil
import time
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class NetworkInterface:
    """Represents a network interface with its properties."""
    name: str
    ip: str
    is_active: bool
    is_external: bool
    netmask: Optional[str] = None
    broadcast: Optional[str] = None

class NetworkConfig:
    """Network configuration and utilities class."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
    def get_host_ip(self) -> str:
        """
        Get the primary IP address of the host machine.
        
        Returns:
            str: Primary IP address of the host
        """
        try:
            # Try to connect to a remote address to determine the local IP
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                # Connect to Google's DNS server (doesn't actually send data)
                s.connect(("8.8.8.8", 80))
                local_ip = s.getsockname()[0]
                self.logger.info(f"Detected primary host IP: {local_ip}")
                return local_ip
        except Exception as e:
            self.logger.warning(f"Failed to detect primary IP via socket: {e}")
            
        # Fallback: get the first non-localhost IP
        try:
            interfaces = self.get_network_interfaces()
            for interface in interfaces:
                if interface.is_external and interface.is_active:
                    self.logger.info(f"Using fallback IP from interface {interface.name}: {interface.ip}")
                    return interface.ip
        except Exception as e:
            self.logger.error(f"Failed to get network interfaces: {e}")
            
        # Last resort fallback
        self.logger.warning("Using localhost as fallback IP")
        return "127.0.0.1"
    
    def get_network_interfaces(self) -> List[NetworkInterface]:
        """
        Get all available network interfaces with their details.
        
        Returns:
            List[NetworkInterface]: List of network interfaces
        """
        interfaces = []
        
        try:
            # Get network interface statistics
            net_if_addrs = psutil.net_if_addrs()
            net_if_stats = psutil.net_if_stats()
            
            for interface_name, addresses in net_if_addrs.items():
                for addr in addresses:
                    if addr.family == socket.AF_INET:  # IPv4 only
                        ip_addr = addr.address
                        
                        # Skip invalid addresses
                        if not ip_addr or ip_addr == "0.0.0.0":
                            continue
                            
                        # Determine if interface is active
                        is_active = False
                        if interface_name in net_if_stats:
                            is_active = net_if_stats[interface_name].isup
                        
                        # Determine if this is an external (non-localhost) interface
                        is_external = not (
                            ip_addr.startswith("127.") or 
                            ip_addr.startswith("169.254.") or  # Link-local
                            ip_addr == "0.0.0.0"
                        )
                        
                        interface = NetworkInterface(
                            name=interface_name,
                            ip=ip_addr,
                            is_active=is_active,
                            is_external=is_external,
                            netmask=addr.netmask,
                            broadcast=addr.broadcast
                        )
                        interfaces.append(interface)
                        
        except Exception as e:
            self.logger.error(f"Error getting network interfaces: {e}")
            
        return interfaces
    
    def validate_network_binding(self, host: str = "0.0.0.0", port: int = 8000) -> Tuple[bool, str]:
        """
        Validate that the specified host and port can be bound to.
        
        Args:
            host: Host address to bind to
            port: Port number to bind to
            
        Returns:
            Tuple[bool, str]: (success, message)
        """
        try:
            # Test if we can bind to the specified address
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as test_socket:
                test_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                test_socket.bind((host, port))
                test_socket.listen(1)
                
                # Get the actual bound address
                bound_addr = test_socket.getsockname()
                message = f"Successfully validated binding to {bound_addr[0]}:{bound_addr[1]}"
                self.logger.info(message)
                return True, message
                
        except socket.error as e:
            message = f"Failed to bind to {host}:{port} - {e}"
            self.logger.error(message)
            return False, message
        except Exception as e:
            message = f"Unexpected error validating network binding: {e}"
            self.logger.error(message)
            return False, message
    
    def test_external_connectivity(self, target_host: str = "8.8.8.8", target_port: int = 53, timeout: int = 5) -> Dict[str, Any]:
        """
        Test external network connectivity.
        
        Args:
            target_host: Host to test connectivity to
            target_port: Port to test connectivity to
            timeout: Connection timeout in seconds
            
        Returns:
            Dict[str, Any]: Connectivity test results
        """
        result = {
            "success": False,
            "target": f"{target_host}:{target_port}",
            "response_time": None,
            "error": None,
            "timestamp": time.time()
        }
        
        try:
            start_time = time.time()
            
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as test_socket:
                test_socket.settimeout(timeout)
                test_socket.connect((target_host, target_port))
                
            end_time = time.time()
            response_time = (end_time - start_time) * 1000  # Convert to milliseconds
            
            result.update({
                "success": True,
                "response_time": round(response_time, 2)
            })
            
            self.logger.info(f"External connectivity test successful: {response_time:.2f}ms to {target_host}:{target_port}")
            
        except socket.timeout:
            result["error"] = f"Connection timeout after {timeout} seconds"
            self.logger.warning(f"External connectivity test timeout: {target_host}:{target_port}")
        except socket.error as e:
            result["error"] = f"Socket error: {e}"
            self.logger.error(f"External connectivity test failed: {e}")
        except Exception as e:
            result["error"] = f"Unexpected error: {e}"
            self.logger.error(f"Unexpected error in connectivity test: {e}")
            
        return result
    
    def test_local_api_connectivity(self, host: str, port: int, endpoint: str = "/health") -> Dict[str, Any]:
        """
        Test connectivity to the local API server.
        
        Args:
            host: API server host
            port: API server port
            endpoint: Endpoint to test
            
        Returns:
            Dict[str, Any]: API connectivity test results
        """
        result = {
            "success": False,
            "url": f"http://{host}:{port}{endpoint}",
            "status_code": None,
            "response_time": None,
            "error": None,
            "timestamp": time.time()
        }
        
        try:
            start_time = time.time()
            response = requests.get(result["url"], timeout=5)
            end_time = time.time()
            
            response_time = (end_time - start_time) * 1000
            
            result.update({
                "success": response.status_code == 200,
                "status_code": response.status_code,
                "response_time": round(response_time, 2)
            })
            
            if response.status_code != 200:
                result["error"] = f"HTTP {response.status_code}: {response.text[:100]}"
                
        except requests.exceptions.RequestException as e:
            result["error"] = f"Request error: {e}"
        except Exception as e:
            result["error"] = f"Unexpected error: {e}"
            
        return result
    
    def get_network_status(self) -> Dict[str, Any]:
        """
        Get comprehensive network status information.
        
        Returns:
            Dict[str, Any]: Network status information
        """
        interfaces = self.get_network_interfaces()
        host_ip = self.get_host_ip()
        
        # Test external connectivity
        external_test = self.test_external_connectivity()
        
        # Test binding validation
        binding_valid, binding_message = self.validate_network_binding()
        
        return {
            "host_ip": host_ip,
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
            "external_connectivity": external_test,
            "binding_validation": {
                "valid": binding_valid,
                "message": binding_message
            },
            "timestamp": time.time()
        }

# Global instance
network_config = NetworkConfig()
