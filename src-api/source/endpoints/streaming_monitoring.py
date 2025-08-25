"""
Streaming Monitoring API Endpoints
Provides REST API for streaming metrics, health checks, and monitoring data
"""

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from typing import Dict, Any, Optional, List
import logging
from datetime import datetime, timedelta

from streaming.monitoring import (
    get_metrics_collector,
    start_monitoring,
    stop_monitoring
)
from streaming.error_handling import get_health_checker

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/streaming/monitoring", tags=["streaming-monitoring"])


@router.get("/metrics", response_model=Dict[str, Any])
async def get_streaming_metrics():
    """
    Get current streaming metrics for all active streams
    
    Returns:
        Comprehensive streaming metrics
    """
    try:
        collector = get_metrics_collector()
        
        # Get aggregated metrics
        aggregated = collector.get_aggregated_metrics()
        
        # Get individual stream metrics
        stream_metrics = collector.get_all_stream_metrics()
        stream_data = {
            stream_id: metrics.to_dict() 
            for stream_id, metrics in stream_metrics.items()
        }
        
        return {
            "success": True,
            "data": {
                "aggregated": aggregated,
                "streams": stream_data,
                "timestamp": datetime.now().isoformat()
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting streaming metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/metrics/stream/{stream_id}", response_model=Dict[str, Any])
async def get_stream_metrics(stream_id: str):
    """
    Get metrics for a specific stream
    
    Args:
        stream_id: ID of the stream to get metrics for
        
    Returns:
        Stream-specific metrics
    """
    try:
        collector = get_metrics_collector()
        metrics = collector.get_stream_metrics(stream_id)
        
        if not metrics:
            raise HTTPException(status_code=404, detail=f"Stream {stream_id} not found")
        
        # Get throughput statistics
        throughput_stats = collector.calculate_throughput_stats(stream_id)
        
        return {
            "success": True,
            "data": {
                "metrics": metrics.to_dict(),
                "throughput_stats": throughput_stats,
                "timestamp": datetime.now().isoformat()
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting stream metrics for {stream_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/metrics/system", response_model=Dict[str, Any])
async def get_system_metrics(
    minutes: int = Query(default=60, ge=1, le=1440, description="Minutes of history to retrieve")
):
    """
    Get system metrics and history
    
    Args:
        minutes: Number of minutes of history to retrieve (1-1440)
        
    Returns:
        System metrics and historical data
    """
    try:
        collector = get_metrics_collector()
        
        # Get current system metrics
        current_metrics = collector.collect_system_metrics()
        
        # Get historical data
        history = collector.get_system_metrics_history(minutes)
        history_data = [metrics.to_dict() for metrics in history]
        
        return {
            "success": True,
            "data": {
                "current": current_metrics.to_dict(),
                "history": history_data,
                "history_minutes": minutes,
                "timestamp": datetime.now().isoformat()
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting system metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/metrics/throughput/{stream_id}", response_model=Dict[str, Any])
async def get_stream_throughput(
    stream_id: str,
    window_seconds: int = Query(default=60, ge=10, le=3600, description="Time window in seconds")
):
    """
    Get throughput statistics for a specific stream
    
    Args:
        stream_id: ID of the stream
        window_seconds: Time window for statistics (10-3600 seconds)
        
    Returns:
        Throughput statistics
    """
    try:
        collector = get_metrics_collector()
        
        # Check if stream exists
        if not collector.get_stream_metrics(stream_id):
            raise HTTPException(status_code=404, detail=f"Stream {stream_id} not found")
        
        # Get throughput statistics
        stats = collector.calculate_throughput_stats(stream_id, window_seconds)
        
        return {
            "success": True,
            "data": {
                "stream_id": stream_id,
                "throughput_stats": stats,
                "timestamp": datetime.now().isoformat()
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting throughput for stream {stream_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health", response_model=Dict[str, Any])
async def get_health_status():
    """
    Get overall health status of streaming services
    
    Returns:
        Comprehensive health status
    """
    try:
        checker = get_health_checker()
        
        # Perform health checks
        component_health = await checker.check_streaming_services_health()
        
        # Get overall health summary
        overall_health = checker.get_overall_health()
        
        return {
            "success": True,
            "data": {
                "overall": overall_health,
                "components": {name: health.to_dict() for name, health in component_health.items()},
                "timestamp": datetime.now().isoformat()
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting health status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health/{component}", response_model=Dict[str, Any])
async def get_component_health(component: str):
    """
    Get health status for a specific component
    
    Args:
        component: Name of the component to check
        
    Returns:
        Component-specific health status
    """
    try:
        checker = get_health_checker()
        
        # Map component names to check methods
        component_checks = {
            "camera_streaming": checker._check_camera_streaming,
            "sse_service": checker._check_sse_service,
            "file_streaming": checker._check_file_streaming,
            "data_streaming": checker._check_data_streaming,
            "system_resources": checker._check_system_resources
        }
        
        if component not in component_checks:
            raise HTTPException(
                status_code=404, 
                detail=f"Component '{component}' not found. Available: {list(component_checks.keys())}"
            )
        
        # Perform specific health check
        health_status = await component_checks[component]()
        
        return {
            "success": True,
            "data": {
                "component": component,
                "health": health_status.to_dict(),
                "timestamp": datetime.now().isoformat()
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting health for component {component}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats/summary", response_model=Dict[str, Any])
async def get_monitoring_summary():
    """
    Get a comprehensive monitoring summary
    
    Returns:
        Summary of all monitoring data
    """
    try:
        collector = get_metrics_collector()
        checker = get_health_checker()
        
        # Get aggregated metrics
        metrics_summary = collector.get_aggregated_metrics()
        
        # Get current system metrics
        system_metrics = collector.collect_system_metrics()
        
        # Get overall health
        overall_health = checker.get_overall_health()
        
        # Calculate uptime and performance indicators
        stream_metrics = collector.get_all_stream_metrics()
        
        # Calculate average connection duration
        avg_connection_duration = 0.0
        if stream_metrics:
            total_duration = sum(m.connection_duration for m in stream_metrics.values())
            avg_connection_duration = total_duration / len(stream_metrics)
        
        # Calculate error rate
        total_messages = metrics_summary.get("total_messages_sent", 0)
        total_errors = metrics_summary.get("total_errors", 0)
        error_rate = (total_errors / max(total_messages, 1)) * 100
        
        return {
            "success": True,
            "data": {
                "summary": {
                    "active_streams": metrics_summary.get("total_streams", 0),
                    "total_clients": metrics_summary.get("total_clients", 0),
                    "total_bytes_sent": metrics_summary.get("total_bytes_sent", 0),
                    "avg_throughput_bps": metrics_summary.get("avg_throughput_bps", 0.0),
                    "error_rate_percent": error_rate,
                    "avg_connection_duration": avg_connection_duration
                },
                "system": {
                    "cpu_percent": system_metrics.cpu_percent,
                    "memory_percent": system_metrics.memory_percent,
                    "memory_used_mb": system_metrics.memory_used_mb,
                    "disk_usage_percent": system_metrics.disk_usage_percent
                },
                "health": {
                    "overall_status": overall_health.get("status", "unknown"),
                    "healthy_components": overall_health.get("healthy_count", 0),
                    "total_components": overall_health.get("total_components", 0)
                },
                "by_stream_type": metrics_summary.get("by_stream_type", {}),
                "timestamp": datetime.now().isoformat()
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting monitoring summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/start", response_model=Dict[str, Any])
async def start_monitoring_services():
    """
    Start monitoring services (metrics collection and health checks)
    
    Returns:
        Success status
    """
    try:
        await start_monitoring()
        
        return {
            "success": True,
            "message": "Monitoring services started successfully",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error starting monitoring services: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stop", response_model=Dict[str, Any])
async def stop_monitoring_services():
    """
    Stop monitoring services
    
    Returns:
        Success status
    """
    try:
        await stop_monitoring()
        
        return {
            "success": True,
            "message": "Monitoring services stopped successfully",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error stopping monitoring services: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status", response_model=Dict[str, Any])
async def get_monitoring_status():
    """
    Get status of monitoring services themselves
    
    Returns:
        Monitoring service status
    """
    try:
        collector = get_metrics_collector()
        checker = get_health_checker()
        
        return {
            "success": True,
            "data": {
                "metrics_collection": {
                    "active": collector._is_collecting,
                    "task_running": collector._collection_task is not None and not collector._collection_task.done()
                },
                "health_checks": {
                    "active": checker._is_checking,
                    "task_running": checker._check_task is not None and not checker._check_task.done()
                },
                "registered_streams": len(collector.stream_metrics),
                "system_metrics_history_size": len(collector.system_metrics_history),
                "timestamp": datetime.now().isoformat()
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting monitoring status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/metrics/stream/{stream_id}", response_model=Dict[str, Any])
async def clear_stream_metrics(stream_id: str):
    """
    Clear metrics for a specific stream
    
    Args:
        stream_id: ID of the stream to clear metrics for
        
    Returns:
        Success status
    """
    try:
        collector = get_metrics_collector()
        
        if not collector.get_stream_metrics(stream_id):
            raise HTTPException(status_code=404, detail=f"Stream {stream_id} not found")
        
        collector.unregister_stream(stream_id)
        
        return {
            "success": True,
            "message": f"Metrics cleared for stream {stream_id}",
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error clearing metrics for stream {stream_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/metrics/history", response_model=Dict[str, Any])
async def clear_metrics_history():
    """
    Clear system metrics history
    
    Returns:
        Success status
    """
    try:
        collector = get_metrics_collector()
        collector.system_metrics_history.clear()
        
        return {
            "success": True,
            "message": "System metrics history cleared",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error clearing metrics history: {e}")
        raise HTTPException(status_code=500, detail=str(e))