"""
Streaming Administration API Endpoints
Provides administrative functions for managing streaming services, active streams, and diagnostics
"""

from fastapi import APIRouter, HTTPException, Query, Body
from fastapi.responses import JSONResponse
from typing import Dict, Any, Optional, List
import logging
from datetime import datetime
import asyncio

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/streaming/admin", tags=["streaming-admin"])


@router.get("/streams", response_model=Dict[str, Any])
async def list_active_streams():
    """
    List all active streams across all streaming services
    
    Returns:
        List of all active streams with their details
    """
    try:
        from streaming.monitoring import get_metrics_collector
        
        collector = get_metrics_collector()
        stream_metrics = collector.get_all_stream_metrics()
        
        # Get additional details from streaming services
        streams_data = []
        
        for stream_id, metrics in stream_metrics.items():
            stream_info = {
                "stream_id": stream_id,
                "stream_type": metrics.stream_type,
                "start_time": metrics.start_time.isoformat(),
                "duration_seconds": metrics.connection_duration,
                "bytes_sent": metrics.bytes_sent,
                "messages_sent": metrics.messages_sent,
                "error_count": metrics.error_count,
                "client_count": metrics.client_count,
                "last_activity": metrics.last_activity.isoformat(),
                "avg_throughput_bps": metrics.avg_throughput_bps,
                "peak_throughput_bps": metrics.peak_throughput_bps,
                "status": "active"
            }
            streams_data.append(stream_info)
        
        # Group by stream type
        by_type = {}
        for stream in streams_data:
            stream_type = stream["stream_type"]
            if stream_type not in by_type:
                by_type[stream_type] = []
            by_type[stream_type].append(stream)
        
        return {
            "success": True,
            "data": {
                "total_streams": len(streams_data),
                "streams": streams_data,
                "by_type": by_type,
                "timestamp": datetime.now().isoformat()
            }
        }
        
    except Exception as e:
        logger.error(f"Error listing active streams: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/streams/{stream_id}", response_model=Dict[str, Any])
async def get_stream_details(stream_id: str):
    """
    Get detailed information about a specific stream
    
    Args:
        stream_id: ID of the stream to get details for
        
    Returns:
        Detailed stream information including diagnostics
    """
    try:
        from streaming.monitoring import get_metrics_collector
        
        collector = get_metrics_collector()
        metrics = collector.get_stream_metrics(stream_id)
        
        if not metrics:
            raise HTTPException(status_code=404, detail=f"Stream {stream_id} not found")
        
        # Get throughput statistics
        throughput_stats = collector.calculate_throughput_stats(stream_id, 300)  # 5 minutes
        
        # Get diagnostic information
        diagnostics = await _get_stream_diagnostics(stream_id, metrics.stream_type)
        
        return {
            "success": True,
            "data": {
                "stream_id": stream_id,
                "metrics": metrics.to_dict(),
                "throughput_stats": throughput_stats,
                "diagnostics": diagnostics,
                "timestamp": datetime.now().isoformat()
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting stream details for {stream_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/streams/{stream_id}", response_model=Dict[str, Any])
async def terminate_stream(stream_id: str):
    """
    Terminate a specific active stream
    
    Args:
        stream_id: ID of the stream to terminate
        
    Returns:
        Termination result
    """
    try:
        from streaming.monitoring import get_metrics_collector
        
        collector = get_metrics_collector()
        metrics = collector.get_stream_metrics(stream_id)
        
        if not metrics:
            raise HTTPException(status_code=404, detail=f"Stream {stream_id} not found")
        
        # Attempt to terminate the stream based on its type
        termination_result = await _terminate_stream_by_type(stream_id, metrics.stream_type)
        
        # Remove from monitoring
        collector.unregister_stream(stream_id)
        
        return {
            "success": True,
            "data": {
                "stream_id": stream_id,
                "stream_type": metrics.stream_type,
                "termination_result": termination_result,
                "message": f"Stream {stream_id} terminated successfully",
                "timestamp": datetime.now().isoformat()
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error terminating stream {stream_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/streams", response_model=Dict[str, Any])
async def terminate_all_streams(
    stream_type: Optional[str] = Query(None, description="Optional stream type filter")
):
    """
    Terminate all active streams or streams of a specific type
    
    Args:
        stream_type: Optional filter to terminate only streams of this type
        
    Returns:
        Termination results for all streams
    """
    try:
        from streaming.monitoring import get_metrics_collector
        
        collector = get_metrics_collector()
        stream_metrics = collector.get_all_stream_metrics()
        
        # Filter by stream type if specified
        streams_to_terminate = {}
        if stream_type:
            streams_to_terminate = {
                sid: metrics for sid, metrics in stream_metrics.items()
                if metrics.stream_type == stream_type
            }
        else:
            streams_to_terminate = stream_metrics
        
        if not streams_to_terminate:
            message = f"No streams found" + (f" of type {stream_type}" if stream_type else "")
            return {
                "success": True,
                "data": {
                    "terminated_count": 0,
                    "message": message,
                    "timestamp": datetime.now().isoformat()
                }
            }
        
        # Terminate each stream
        termination_results = []
        for stream_id, metrics in streams_to_terminate.items():
            try:
                result = await _terminate_stream_by_type(stream_id, metrics.stream_type)
                collector.unregister_stream(stream_id)
                
                termination_results.append({
                    "stream_id": stream_id,
                    "stream_type": metrics.stream_type,
                    "status": "terminated",
                    "result": result
                })
            except Exception as e:
                termination_results.append({
                    "stream_id": stream_id,
                    "stream_type": metrics.stream_type,
                    "status": "error",
                    "error": str(e)
                })
        
        successful_terminations = sum(1 for r in termination_results if r["status"] == "terminated")
        
        return {
            "success": True,
            "data": {
                "terminated_count": successful_terminations,
                "total_attempted": len(termination_results),
                "results": termination_results,
                "message": f"Terminated {successful_terminations} of {len(termination_results)} streams",
                "timestamp": datetime.now().isoformat()
            }
        }
        
    except Exception as e:
        logger.error(f"Error terminating streams: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/diagnostics", response_model=Dict[str, Any])
async def get_system_diagnostics():
    """
    Get comprehensive system diagnostics for streaming services
    
    Returns:
        System-wide diagnostic information
    """
    try:
        from streaming.monitoring import get_metrics_collector
        from streaming.error_handling import get_health_checker
        
        collector = get_metrics_collector()
        checker = get_health_checker()
        
        # Get system metrics
        system_metrics = collector.collect_system_metrics()
        
        # Get health status
        health_status = await checker.check_streaming_services_health()
        overall_health = checker.get_overall_health()
        
        # Get streaming service diagnostics
        service_diagnostics = await _get_service_diagnostics()
        
        # Get resource usage diagnostics
        resource_diagnostics = _get_resource_diagnostics(system_metrics)
        
        # Get configuration diagnostics
        config_diagnostics = _get_configuration_diagnostics()
        
        return {
            "success": True,
            "data": {
                "system_metrics": system_metrics.to_dict(),
                "health_status": {name: health.to_dict() for name, health in health_status.items()},
                "overall_health": overall_health,
                "service_diagnostics": service_diagnostics,
                "resource_diagnostics": resource_diagnostics,
                "configuration_diagnostics": config_diagnostics,
                "timestamp": datetime.now().isoformat()
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting system diagnostics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/diagnostics/stream/{stream_id}", response_model=Dict[str, Any])
async def get_stream_diagnostics(stream_id: str):
    """
    Get detailed diagnostics for a specific stream
    
    Args:
        stream_id: ID of the stream to diagnose
        
    Returns:
        Stream-specific diagnostic information
    """
    try:
        from streaming.monitoring import get_metrics_collector
        
        collector = get_metrics_collector()
        metrics = collector.get_stream_metrics(stream_id)
        
        if not metrics:
            raise HTTPException(status_code=404, detail=f"Stream {stream_id} not found")
        
        # Get comprehensive diagnostics
        diagnostics = await _get_stream_diagnostics(stream_id, metrics.stream_type)
        
        # Get performance analysis
        performance_analysis = _analyze_stream_performance(metrics, collector)
        
        return {
            "success": True,
            "data": {
                "stream_id": stream_id,
                "stream_type": metrics.stream_type,
                "metrics": metrics.to_dict(),
                "diagnostics": diagnostics,
                "performance_analysis": performance_analysis,
                "timestamp": datetime.now().isoformat()
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting stream diagnostics for {stream_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cleanup", response_model=Dict[str, Any])
async def cleanup_resources():
    """
    Perform cleanup of streaming resources (inactive streams, old metrics, etc.)
    
    Returns:
        Cleanup results
    """
    try:
        from streaming.monitoring import get_metrics_collector
        
        collector = get_metrics_collector()
        
        # Get current streams
        stream_metrics = collector.get_all_stream_metrics()
        
        # Find inactive streams (no activity for more than 5 minutes)
        inactive_threshold = datetime.now().timestamp() - 300  # 5 minutes
        inactive_streams = []
        
        for stream_id, metrics in stream_metrics.items():
            if metrics.last_activity.timestamp() < inactive_threshold:
                inactive_streams.append(stream_id)
        
        # Clean up inactive streams
        cleanup_results = []
        for stream_id in inactive_streams:
            try:
                collector.unregister_stream(stream_id)
                cleanup_results.append({
                    "stream_id": stream_id,
                    "status": "cleaned",
                    "reason": "inactive"
                })
            except Exception as e:
                cleanup_results.append({
                    "stream_id": stream_id,
                    "status": "error",
                    "error": str(e)
                })
        
        # Clear old system metrics (keep only last 1000 entries)
        initial_history_size = len(collector.system_metrics_history)
        # The deque already limits to 1000, but we can force cleanup if needed
        
        return {
            "success": True,
            "data": {
                "inactive_streams_cleaned": len([r for r in cleanup_results if r["status"] == "cleaned"]),
                "cleanup_errors": len([r for r in cleanup_results if r["status"] == "error"]),
                "cleanup_results": cleanup_results,
                "system_metrics_history_size": len(collector.system_metrics_history),
                "message": f"Cleanup completed: {len(cleanup_results)} streams processed",
                "timestamp": datetime.now().isoformat()
            }
        }
        
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/restart-service", response_model=Dict[str, Any])
async def restart_streaming_service(
    service_name: str = Body(..., description="Name of the service to restart")
):
    """
    Restart a specific streaming service
    
    Args:
        service_name: Name of the service to restart
        
    Returns:
        Restart result
    """
    try:
        restart_result = await _restart_streaming_service(service_name)
        
        return {
            "success": True,
            "data": {
                "service_name": service_name,
                "restart_result": restart_result,
                "message": f"Service {service_name} restart completed",
                "timestamp": datetime.now().isoformat()
            }
        }
        
    except Exception as e:
        logger.error(f"Error restarting service {service_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Helper functions

async def _get_stream_diagnostics(stream_id: str, stream_type: str) -> Dict[str, Any]:
    """Get diagnostic information for a specific stream"""
    diagnostics = {
        "stream_id": stream_id,
        "stream_type": stream_type,
        "service_status": "unknown",
        "connection_info": {},
        "resource_usage": {},
        "errors": []
    }
    
    try:
        if stream_type.startswith("camera"):
            from streaming.camera_stream import camera_stream_manager
            service_stats = camera_stream_manager.get_stream_stats()
            diagnostics["service_status"] = "active" if service_stats["active_streams"] > 0 else "idle"
            diagnostics["connection_info"] = {
                "total_streams": service_stats["active_streams"],
                "total_bytes_sent": service_stats["total_bytes_sent"]
            }
            
        elif stream_type == "sensor_sse":
            from streaming.sensor_sse import sensor_broadcaster
            diagnostics["service_status"] = "monitoring" if sensor_broadcaster.is_monitoring else "idle"
            diagnostics["connection_info"] = {
                "connection_count": sensor_broadcaster.get_connection_count(),
                "is_monitoring": sensor_broadcaster.is_monitoring
            }
            
        elif stream_type.startswith("file"):
            from streaming.file_stream import file_stream_service
            service_stats = file_stream_service.get_stream_stats()
            diagnostics["service_status"] = "active" if service_stats["active_streams"] > 0 else "idle"
            
        elif stream_type.startswith("inspection") or stream_type.startswith("analysis"):
            diagnostics["service_status"] = "active"
            
    except Exception as e:
        diagnostics["errors"].append(f"Error getting service diagnostics: {str(e)}")
    
    return diagnostics


async def _terminate_stream_by_type(stream_id: str, stream_type: str) -> Dict[str, Any]:
    """Terminate a stream based on its type"""
    result = {"method": "generic", "success": False}
    
    try:
        if stream_type.startswith("camera"):
            from streaming.camera_stream import camera_stream_manager
            await camera_stream_manager.cleanup_stream(stream_id)
            result = {"method": "camera_cleanup", "success": True}
            
        elif stream_type == "sensor_sse":
            from streaming.sensor_sse import sensor_broadcaster
            # SSE streams are typically self-terminating when clients disconnect
            result = {"method": "sse_cleanup", "success": True}
            
        elif stream_type.startswith("file"):
            from streaming.file_stream import file_stream_service
            await file_stream_service.cleanup_stream(stream_id)
            result = {"method": "file_cleanup", "success": True}
            
        elif stream_type.startswith("inspection"):
            from streaming.inspection_stream import inspection_streamer
            await inspection_streamer.cleanup_stream(stream_id)
            result = {"method": "inspection_cleanup", "success": True}
            
        elif stream_type.startswith("analysis"):
            from streaming.analysis_stream import analysis_streamer
            await analysis_streamer.cleanup_stream(stream_id)
            result = {"method": "analysis_cleanup", "success": True}
            
        else:
            result = {"method": "unknown_type", "success": False, "error": f"Unknown stream type: {stream_type}"}
            
    except Exception as e:
        result = {"method": "error", "success": False, "error": str(e)}
    
    return result


async def _get_service_diagnostics() -> Dict[str, Any]:
    """Get diagnostics for all streaming services"""
    services = {}
    
    # Camera streaming service
    try:
        from streaming.camera_stream import camera_stream_manager
        stats = camera_stream_manager.get_stream_stats()
        services["camera_streaming"] = {
            "status": "available",
            "active_streams": stats.get("active_streams", 0),
            "total_bytes_sent": stats.get("total_bytes_sent", 0)
        }
    except Exception as e:
        services["camera_streaming"] = {"status": "error", "error": str(e)}
    
    # SSE service
    try:
        from streaming.sensor_sse import sensor_broadcaster
        services["sse_service"] = {
            "status": "available",
            "connection_count": sensor_broadcaster.get_connection_count(),
            "is_monitoring": sensor_broadcaster.is_monitoring
        }
    except Exception as e:
        services["sse_service"] = {"status": "error", "error": str(e)}
    
    # File streaming service
    try:
        from streaming.file_stream import file_stream_service
        stats = file_stream_service.get_stream_stats()
        services["file_streaming"] = {
            "status": "available",
            "active_streams": stats.get("active_streams", 0)
        }
    except Exception as e:
        services["file_streaming"] = {"status": "error", "error": str(e)}
    
    # Inspection streaming service
    try:
        from streaming.inspection_stream import inspection_streamer
        stats = inspection_streamer.get_stream_stats()
        services["inspection_streaming"] = {
            "status": "available",
            "active_streams": stats.get("active_streams", 0)
        }
    except Exception as e:
        services["inspection_streaming"] = {"status": "error", "error": str(e)}
    
    # Analysis streaming service
    try:
        from streaming.analysis_stream import analysis_streamer
        stats = analysis_streamer.get_stream_stats()
        services["analysis_streaming"] = {
            "status": "available",
            "active_streams": stats.get("active_streams", 0)
        }
    except Exception as e:
        services["analysis_streaming"] = {"status": "error", "error": str(e)}
    
    return services


def _get_resource_diagnostics(system_metrics) -> Dict[str, Any]:
    """Get resource usage diagnostics"""
    diagnostics = {
        "cpu_status": "normal",
        "memory_status": "normal",
        "disk_status": "normal",
        "network_status": "normal",
        "recommendations": []
    }
    
    # CPU diagnostics
    if system_metrics.cpu_percent > 90:
        diagnostics["cpu_status"] = "critical"
        diagnostics["recommendations"].append("CPU usage is very high. Consider reducing concurrent streams.")
    elif system_metrics.cpu_percent > 70:
        diagnostics["cpu_status"] = "warning"
        diagnostics["recommendations"].append("CPU usage is elevated. Monitor for performance issues.")
    
    # Memory diagnostics
    if system_metrics.memory_percent > 90:
        diagnostics["memory_status"] = "critical"
        diagnostics["recommendations"].append("Memory usage is very high. Consider restarting services or reducing stream quality.")
    elif system_metrics.memory_percent > 70:
        diagnostics["memory_status"] = "warning"
        diagnostics["recommendations"].append("Memory usage is elevated. Monitor for memory leaks.")
    
    # Disk diagnostics
    if system_metrics.disk_usage_percent > 95:
        diagnostics["disk_status"] = "critical"
        diagnostics["recommendations"].append("Disk space is critically low. Clean up old files immediately.")
    elif system_metrics.disk_usage_percent > 85:
        diagnostics["disk_status"] = "warning"
        diagnostics["recommendations"].append("Disk space is running low. Consider cleanup or expansion.")
    
    return diagnostics


def _get_configuration_diagnostics() -> Dict[str, Any]:
    """Get configuration diagnostics"""
    diagnostics = {
        "config_status": "unknown",
        "issues": [],
        "recommendations": []
    }
    
    try:
        from streaming.config import get_streaming_config
        config = get_streaming_config()
        
        # Validate configuration
        validation_errors = config.validate()
        
        if validation_errors:
            diagnostics["config_status"] = "invalid"
            diagnostics["issues"] = validation_errors
            diagnostics["recommendations"].append("Fix configuration validation errors")
        else:
            diagnostics["config_status"] = "valid"
        
        # Check for performance recommendations
        if config.camera.frame_rate > 30:
            diagnostics["recommendations"].append("High camera frame rate may impact performance")
        
        if config.file.chunk_size < 4096:
            diagnostics["recommendations"].append("Small file chunk size may reduce throughput")
        
        if config.data.batch_size > 1000:
            diagnostics["recommendations"].append("Large data batch size may increase memory usage")
            
    except Exception as e:
        diagnostics["config_status"] = "error"
        diagnostics["issues"].append(f"Error reading configuration: {str(e)}")
    
    return diagnostics


def _analyze_stream_performance(metrics, collector) -> Dict[str, Any]:
    """Analyze stream performance and provide recommendations"""
    analysis = {
        "performance_rating": "unknown",
        "issues": [],
        "recommendations": [],
        "statistics": {}
    }
    
    try:
        # Calculate performance metrics
        duration = metrics.connection_duration
        error_rate = (metrics.error_count / max(metrics.messages_sent, 1)) * 100
        
        analysis["statistics"] = {
            "duration_minutes": duration / 60,
            "error_rate_percent": error_rate,
            "avg_throughput_mbps": metrics.avg_throughput_bps / (1024 * 1024),
            "messages_per_second": metrics.messages_sent / max(duration, 1)
        }
        
        # Performance rating
        if error_rate > 10:
            analysis["performance_rating"] = "poor"
            analysis["issues"].append(f"High error rate: {error_rate:.1f}%")
        elif error_rate > 5:
            analysis["performance_rating"] = "fair"
            analysis["issues"].append(f"Elevated error rate: {error_rate:.1f}%")
        elif metrics.avg_throughput_bps > 0:
            analysis["performance_rating"] = "good"
        else:
            analysis["performance_rating"] = "unknown"
        
        # Recommendations
        if error_rate > 5:
            analysis["recommendations"].append("Investigate error causes and improve error handling")
        
        if metrics.avg_throughput_bps < 1024:  # Less than 1KB/s
            analysis["recommendations"].append("Low throughput detected, check network conditions")
        
        if duration > 3600:  # More than 1 hour
            analysis["recommendations"].append("Long-running stream, monitor for memory leaks")
            
    except Exception as e:
        analysis["issues"].append(f"Error analyzing performance: {str(e)}")
    
    return analysis


async def _restart_streaming_service(service_name: str) -> Dict[str, Any]:
    """Restart a specific streaming service"""
    result = {"service": service_name, "success": False, "actions": []}
    
    try:
        if service_name == "monitoring":
            from streaming.monitoring import stop_monitoring, start_monitoring
            await stop_monitoring()
            result["actions"].append("Stopped monitoring services")
            await start_monitoring()
            result["actions"].append("Started monitoring services")
            result["success"] = True
            
        elif service_name == "sse":
            from streaming.sensor_sse import sensor_broadcaster
            await sensor_broadcaster.stop_monitoring()
            result["actions"].append("Stopped SSE monitoring")
            await sensor_broadcaster.start_monitoring()
            result["actions"].append("Started SSE monitoring")
            result["success"] = True
            
        else:
            result["error"] = f"Unknown service: {service_name}"
            
    except Exception as e:
        result["error"] = str(e)
    
    return result