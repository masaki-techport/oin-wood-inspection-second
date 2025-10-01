"""
Network troubleshooting utilities and error message generation.
"""

import socket
import subprocess
import platform
import logging
import time
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from network_config import network_config

logger = logging.getLogger(__name__)

@dataclass
class TroubleshootingStep:
    """Represents a troubleshooting step with description and action."""
    title: str
    description: str
    action: str
    priority: str  # "critical", "high", "medium", "low"
    category: str  # "network", "firewall", "configuration", "system"

class NetworkTroubleshooter:
    """Network troubleshooting utility class."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def diagnose_connection_issue(self, client_ip: str, error_details: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Diagnose network connection issues and provide troubleshooting steps.
        
        Args:
            client_ip: IP address of the client experiencing issues
            error_details: Additional error information
            
        Returns:
            Dict containing diagnosis and troubleshooting steps
        """
        diagnosis = {
            "client_ip": client_ip,
            "client_type": self._determine_client_type(client_ip),
            "issues_detected": [],
            "troubleshooting_steps": [],
            "system_info": self._get_system_info(),
            "network_status": network_config.get_network_status()
        }
        
        # Analyze client type and potential issues
        if diagnosis["client_type"] == "localhost":
            diagnosis["issues_detected"].extend(self._diagnose_localhost_issues())
        elif diagnosis["client_type"] == "local_network":
            diagnosis["issues_detected"].extend(self._diagnose_local_network_issues(client_ip))
        elif diagnosis["client_type"] == "external":
            diagnosis["issues_detected"].extend(self._diagnose_external_issues(client_ip))
        
        # Add general network issues
        diagnosis["issues_detected"].extend(self._diagnose_general_issues())
        
        # Generate troubleshooting steps based on detected issues
        diagnosis["troubleshooting_steps"] = self._generate_troubleshooting_steps(
            diagnosis["issues_detected"], 
            diagnosis["client_type"]
        )
        
        return diagnosis
    
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
    
    def _get_system_info(self) -> Dict[str, Any]:
        """Get system information for troubleshooting."""
        return {
            "platform": platform.platform(),
            "python_version": platform.python_version(),
            "hostname": socket.gethostname(),
            "fqdn": socket.getfqdn()
        }
    
    def _diagnose_localhost_issues(self) -> List[str]:
        """Diagnose issues specific to localhost connections."""
        issues = []
        
        # Test if server is actually running
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1)
                result = s.connect_ex(('127.0.0.1', 8000))
                if result != 0:
                    issues.append("server_not_running")
        except Exception:
            issues.append("server_connection_failed")
        
        return issues
    
    def _diagnose_local_network_issues(self, client_ip: str) -> List[str]:
        """Diagnose issues specific to local network connections."""
        issues = []
        
        # Check if server is bound to 0.0.0.0
        binding_valid, _ = network_config.validate_network_binding()
        if not binding_valid:
            issues.append("server_not_bound_to_all_interfaces")
        
        # Check if client IP is reachable
        if not self._test_ping(client_ip):
            issues.append("client_not_reachable")
        
        # Check firewall (Windows specific)
        if platform.system() == "Windows":
            if not self._check_windows_firewall():
                issues.append("windows_firewall_blocking")
        
        return issues
    
    def _diagnose_external_issues(self, client_ip: str) -> List[str]:
        """Diagnose issues specific to external connections."""
        issues = []
        
        # External connections should generally not happen unless specifically configured
        issues.append("external_connection_unexpected")
        
        # Check if this might be a misconfigured local network client
        if self._is_likely_local_network(client_ip):
            issues.append("possible_local_network_misconfiguration")
        
        return issues
    
    def _diagnose_general_issues(self) -> List[str]:
        """Diagnose general network issues."""
        issues = []
        
        # Check external connectivity
        external_test = network_config.test_external_connectivity()
        if not external_test["success"]:
            issues.append("no_external_connectivity")
        
        # Check if any external interfaces are active
        interfaces = network_config.get_network_interfaces()
        external_active = any(iface.is_active and iface.is_external for iface in interfaces)
        if not external_active:
            issues.append("no_active_external_interfaces")
        
        return issues
    
    def _test_ping(self, ip: str) -> bool:
        """Test if an IP address is reachable via ping."""
        try:
            if platform.system() == "Windows":
                result = subprocess.run(
                    ["ping", "-n", "1", "-w", "1000", ip],
                    capture_output=True,
                    timeout=5
                )
            else:
                result = subprocess.run(
                    ["ping", "-c", "1", "-W", "1", ip],
                    capture_output=True,
                    timeout=5
                )
            return result.returncode == 0
        except Exception:
            return False
    
    def _check_windows_firewall(self) -> bool:
        """Check if Windows Firewall might be blocking connections."""
        try:
            # This is a simplified check - in practice, you'd need more sophisticated firewall detection
            result = subprocess.run(
                ["netsh", "advfirewall", "show", "allprofiles", "state"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return "ON" not in result.stdout
        except Exception:
            return True  # Assume firewall is not blocking if we can't check
    
    def _is_likely_local_network(self, ip: str) -> bool:
        """Check if an IP might be from a local network with unusual configuration."""
        # This is a heuristic - you might want to expand this based on your network setup
        return (
            ip.startswith("192.168.") or 
            ip.startswith("10.") or 
            ip.startswith("172.") or
            ip.startswith("169.254.")  # Link-local
        )
    
    def _generate_troubleshooting_steps(self, issues: List[str], client_type: str) -> List[TroubleshootingStep]:
        """Generate troubleshooting steps based on detected issues."""
        steps = []
        
        # Issue-specific steps
        issue_steps = {
            "server_not_running": TroubleshootingStep(
                title="Start Backend Server",
                description="The backend server is not running on port 8000",
                action="Start the backend server using 'python main.py' in the src-api/source directory",
                priority="critical",
                category="system"
            ),
            "server_not_bound_to_all_interfaces": TroubleshootingStep(
                title="Configure Server Binding",
                description="Server is not bound to accept external connections",
                action="Ensure server is configured to bind to 0.0.0.0:8000, not localhost:8000",
                priority="critical",
                category="configuration"
            ),
            "windows_firewall_blocking": TroubleshootingStep(
                title="Configure Windows Firewall",
                description="Windows Firewall may be blocking incoming connections",
                action="Add an exception for port 8000 in Windows Firewall settings",
                priority="high",
                category="firewall"
            ),
            "client_not_reachable": TroubleshootingStep(
                title="Check Network Connectivity",
                description="Cannot reach the client device from the server",
                action="Verify both devices are on the same network and can ping each other",
                priority="high",
                category="network"
            ),
            "no_external_connectivity": TroubleshootingStep(
                title="Check Internet Connection",
                description="Server has no external internet connectivity",
                action="Verify internet connection and network configuration",
                priority="medium",
                category="network"
            ),
            "no_active_external_interfaces": TroubleshootingStep(
                title="Activate Network Interface",
                description="No active external network interfaces found",
                action="Check network adapter settings and ensure network interface is active",
                priority="high",
                category="network"
            )
        }
        
        # Add steps for detected issues
        for issue in issues:
            if issue in issue_steps:
                steps.append(issue_steps[issue])
        
        # Add client-type specific steps
        if client_type == "local_network":
            steps.extend([
                TroubleshootingStep(
                    title="Verify Network Configuration",
                    description="Ensure both devices are on the same network",
                    action="Check that both server and client are connected to the same WiFi/network",
                    priority="medium",
                    category="network"
                ),
                TroubleshootingStep(
                    title="Test Direct Connection",
                    description="Test if the client can reach the server directly",
                    action=f"Try accessing http://{network_config.get_host_ip()}:8000/health from the client device",
                    priority="medium",
                    category="network"
                )
            ])
        
        # Sort steps by priority
        priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        steps.sort(key=lambda x: priority_order.get(x.priority, 3))
        
        return steps

def generate_error_message(error_type: str, client_ip: str, additional_info: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Generate user-friendly error messages with troubleshooting information.
    
    Args:
        error_type: Type of error encountered
        client_ip: IP address of the client
        additional_info: Additional error information
        
    Returns:
        Dict containing error message and troubleshooting info
    """
    troubleshooter = NetworkTroubleshooter()
    diagnosis = troubleshooter.diagnose_connection_issue(client_ip, additional_info)
    
    error_messages = {
        "connection_refused": {
            "title": "Connection Refused",
            "message": "Unable to connect to the backend server. The server may not be running or may not be accepting connections.",
            "user_action": "Please check that the backend server is running and try again."
        },
        "timeout": {
            "title": "Connection Timeout",
            "message": "The connection to the backend server timed out. This may indicate network connectivity issues.",
            "user_action": "Please check your network connection and try again."
        },
        "network_unreachable": {
            "title": "Network Unreachable",
            "message": "The backend server is not reachable from your device. This may be a network configuration issue.",
            "user_action": "Please verify that both devices are on the same network."
        },
        "cors_error": {
            "title": "Cross-Origin Request Blocked",
            "message": "Your request was blocked due to CORS policy. This is a security feature.",
            "user_action": "Please contact the administrator to configure CORS settings."
        }
    }
    
    error_info = error_messages.get(error_type, {
        "title": "Network Error",
        "message": "An unknown network error occurred.",
        "user_action": "Please try again or contact support."
    })
    
    return {
        "error": error_info,
        "diagnosis": diagnosis,
        "timestamp": time.time()
    }

# Global troubleshooter instance
network_troubleshooter = NetworkTroubleshooter()
