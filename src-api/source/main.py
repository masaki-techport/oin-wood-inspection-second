import os
import sys
import logging
import configparser
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Setup logging first using settings.ini
from logging_setup import setup_logging_from_ini

_config = configparser.ConfigParser(interpolation=None)
_config_path = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "config", "settings.ini"
)
try:
    _config.read(_config_path, encoding="utf-8")
except Exception:
    # If reading fails, proceed with defaults inside setup
    pass

setup_logging_from_ini(_config)
logger = logging.getLogger(__name__)

# Import routers with error handling
try:
    logger.debug("Importing endpoint modules...")
    from endpoints import (
        inspections,
        camera,
        inference,
        webcam_camera,
        sensor_inspection,
        settings,
        temp_sections,
    )
except Exception as e:
    logger.exception(f"❌ Failed to import basic endpoint modules: {e}")
    raise

try:
    from endpoints.file_api import router as file_api_router
    from endpoints.streaming_endpoints import router as streaming_router
    from endpoints.streaming_config import router as streaming_config_router
    from endpoints.streaming_monitoring import (
        router as streaming_monitoring_router,
    )
    from endpoints.streaming_admin import router as streaming_admin_router
    from endpoints.health import router as health_router

    logger.debug("✅ Extended endpoint modules imported successfully")
except Exception as e:
    logger.exception(f"❌ Failed to import extended endpoint modules: {e}")
    raise

try:
    # inspections_watcher_task removed - no longer needed
    from starlette.staticfiles import StaticFiles
    from db.engine import initialize_database
    from app_config import APP_CONFIG
    from network_config import network_config
    from middleware.request_logging import RequestLoggingMiddleware
    from monitoring.network_monitor import network_monitor

    logger.debug("✅ Supporting modules imported successfully")
except Exception as e:
    logger.exception(f"❌ Failed to import supporting modules: {e}")
    raise

if not os.path.exists(APP_CONFIG["upload_folder_inspection"]):
    os.makedirs(APP_CONFIG["upload_folder_inspection"])

# create database tables
initialize_database()

# create FastAPI Instance
app = FastAPI(
    title="Wood Inspection API",
    description="API for wonpmod inspection application with network diagnostics",
    version="1.0.0",
)


# Network startup validation
def validate_network_startup():
    """Validate network configuration on startup."""
    logger.info("=== NETWORK STARTUP VALIDATION ===")

    # Get network status
    status = network_config.get_network_status()

    # Log host IP
    host_ip = status["host_ip"]
    logger.info(f"Primary host IP: {host_ip}")

    # Log network interfaces
    logger.info("Available network interfaces:")
    for interface in status["interfaces"]:
        status_str = "ACTIVE" if interface["is_active"] else "INACTIVE"
        type_str = "EXTERNAL" if interface["is_external"] else "LOCAL"
        logger.info(
            f"  - {interface['name']}: {interface['ip']} ({status_str}, {type_str})"
        )

    # Test binding validation
    binding_result = status["binding_validation"]
    if binding_result["valid"]:
        logger.info(
            f"✓ Network binding validation: {binding_result['message']}"
        )
    else:
        logger.error(
            f"✗ Network binding validation failed: {binding_result['message']}"
        )

    # Test external connectivity
    external_test = status["external_connectivity"]
    if external_test["success"]:

        logger.info(
            f"✓ External connectivity: {external_test['response_time']}ms to {external_test['target']}"
        )
    else:
        logger.warning(
            f"✗ External connectivity failed: {external_test['error']}"
        )

    logger.info("=== END NETWORK VALIDATION ===")
    return status


# Perform network validation
network_status = validate_network_startup()


# Add a simple health check endpoint for network testing (legacy)
@app.get("/health")
async def health_check():
    return {"status": "ok", "message": "Backend is running and accessible"}


# Include routers with appropriate prefixes
# Routers that don't have /api prefix - add it
try:
    logger.debug("Loading routers...")

    # Load each router with error handling
    logger.debug("Including inspections router...")
    app.include_router(inspections.router, prefix="/api")

    logger.debug("Including camera router...")
    app.include_router(camera.router, prefix="/api")

    logger.debug("Including webcam_camera router...")
    app.include_router(webcam_camera.router, prefix="/api")

    logger.debug("Including inference router...")
    app.include_router(inference.router, prefix="/api")

    logger.debug("Including sensor_inspection router...")
    app.include_router(sensor_inspection.router, prefix="/api")

    logger.debug("Including settings router...")
    app.include_router(settings.router, prefix="/api")

    logger.debug("Including temp_sections router...")
    app.include_router(temp_sections.router, prefix="/api")

    # Routers that already have /api prefix - include without additional prefix
    logger.debug("Including file_api_router...")
    app.include_router(file_api_router)  # Already has /api prefix

    logger.debug("Including streaming_router...")
    app.include_router(streaming_router)  # Already has /api/stream prefix

    logger.debug("Including streaming_config_router...")
    app.include_router(
        streaming_config_router
    )  # Already has /api/streaming/config prefix

    logger.debug("Including streaming_monitoring_router...")
    app.include_router(
        streaming_monitoring_router
    )  # Already has /api/streaming/monitoring prefix

    logger.debug("Including streaming_admin_router...")
    app.include_router(
        streaming_admin_router
    )  # Already has /api/streaming/admin prefix

    logger.debug("Including health_router...")
    app.include_router(health_router)  # Already has /api prefix

    logger.debug("✅ All routers loaded successfully")

    # Log all registered routes for debugging
    logger.debug("📋 Registered routes:")
    for route in app.routes:
        if hasattr(route, "path") and hasattr(route, "methods"):
            logger.debug(f"  {', '.join(route.methods)} {route.path}")

except Exception as e:
    logger.exception(f"❌ Error loading routers: {e}")


# Enhanced CORS configuration for network access
def setup_cors():
    """Setup CORS middleware with network-aware configuration."""

    # Get network interfaces to determine allowed origins
    interfaces = network_config.get_network_interfaces()
    host_ip = network_config.get_host_ip()

    # Build list of allowed origins
    allowed_origins = [
        "*",  # Allow all origins for maximum compatibility
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        f"http://{host_ip}:3000",
    ]

    # Add origins for all active external interfaces
    for interface in interfaces:
        if interface.is_active and interface.is_external:
            allowed_origins.append(f"http://{interface.ip}:3000")

    logger.info(f"CORS configured with origins: {allowed_origins}")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Use wildcard for maximum compatibility
        allow_credentials=True,
        allow_methods=["*"],  # Allonpws all methods
        allow_headers=["*"],  # Allows all headers
        expose_headers=["*"],  # Expose all headers
    )


setup_cors()

# Add request logging middleware
app.add_middleware(RequestLoggingMiddleware, log_level="INFO")

from __init__ import ROOT_DIR

app.mount(
    "/data", StaticFiles(directory=os.path.join(ROOT_DIR, "data")), name="data"
)

if __name__ == "__main__":
    import uvicorn
    import asyncio

    async def main():
        # バックエンドサーバーのタスク
        async def start_fastapi():
            # Enhanced server configuration with network logging
            host = os.getenv("API_HOST", "0.0.0.0")
            port = int(os.getenv("API_PORT", "8000"))

            logger.info("=== STARTING FASTAPI SERVER ===")
            logger.info(f"Server binding to: {host}:{port}")
            logger.info(
                f"Server will accept connections from any network interface"
            )

            # Log accessible URLs
            host_ip = network_config.get_host_ip()
            logger.info(f"Server accessible at:")
            logger.info(f"  - Local: http://localhost:{port}")
            logger.info(f"  - Network: http://{host_ip}:{port}")

            # Log network interfaces where server will be accessible
            interfaces = network_config.get_network_interfaces()
            for interface in interfaces:
                if interface.is_active and interface.is_external:
                    logger.info(
                        f"  - {interface.name}: http://{interface.ip}:{port}"
                    )

            logger.info("=== SERVER STARTUP COMPLETE ===")

            try:
                config = uvicorn.Config(
                    app,
                    host=host,
                    port=port,
                    log_level="info",
                    access_log=True,
                )
                server = uvicorn.Server(config)
                await server.serve()
            except Exception as e:
                logger.error(f"Failed to start FastAPI server: {e}")
                raise

        # Background tasks removed - no longer needed

        # Start streaming monitoring services
        async def start_streaming_monitoring():
            try:
                from streaming.monitoring import start_monitoring

                await start_monitoring()
            except Exception as e:
                logger.warning(f"Failed to start streaming monitoring: {e}")
                # Don't re-raise to prevent server shutdown

        # Start network monitoring
        async def start_network_monitoring():
            try:
                await network_monitor.start_monitoring()
                logger.info("Network monitoring started successfully")
            except Exception as e:
                logger.error(f"Failed to start network monitoring: {e}")
                # Don't re-raise to prevent server shutdown

        # Start FastAPI server first
        server_task = asyncio.create_task(start_fastapi())

        # Start background tasks (non-blocking)
        background_tasks = []

        # No background tasks currently defined

        try:
            background_tasks.append(
                asyncio.create_task(start_streaming_monitoring())
            )
        except Exception as e:
            logger.warning(f"Failed to start streaming monitoring: {e}")

        try:
            background_tasks.append(
                asyncio.create_task(start_network_monitoring())
            )
        except Exception as e:
            logger.warning(f"Failed to start network monitoring: {e}")

        # Wait for server and background tasks
        try:
            await asyncio.gather(
                server_task, *background_tasks, return_exceptions=True
            )
        except Exception as e:
            logger.error(f"Error in main task execution: {e}")
            raise

    asyncio.run(main())
