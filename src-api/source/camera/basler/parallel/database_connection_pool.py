"""
Database Connection Pool for parallel processing.

This module provides a thread-safe connection pool for database operations
during parallel image analysis, with connection lifecycle management and
automatic recovery capabilities.
"""

import time
import logging
import threading
from typing import List, Optional, Dict, Any
from contextlib import contextmanager
from queue import Queue, Empty, Full
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError, DisconnectionError

from db.engine import SessionLocal
from db.inspection_details import InspectionDetails

logger = logging.getLogger('BaslerCamera.DatabaseConnectionPool')

class DatabaseConnectionPool:
    """
    Thread-safe database connection pool for parallel processing.
    
    Manages a pool of database connections with:
    - Configurable pool size (5-10 connections)
    - Connection health checking and automatic recovery
    - Bulk operation support with retry logic
    - Connection lifecycle management
    """
    
    def __init__(self, pool_size: int = 8, max_retries: int = 3, retry_delay: float = 0.1):
        """
        Initialize the database connection pool.
        
        Args:
            pool_size: Number of connections to maintain in the pool (5-10)
            max_retries: Maximum number of retry attempts for failed operations
            retry_delay: Delay between retry attempts in seconds
        """
        self.pool_size = min(10, max(5, pool_size))  # Constrain to 5-10 range
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        
        # Thread-safe connection pool
        self._pool = Queue(maxsize=self.pool_size)
        self._pool_lock = threading.Lock()
        self._active_connections = set()
        self._connection_stats = {
            'created': 0,
            'borrowed': 0,
            'returned': 0,
            'failed': 0,
            'health_checks': 0
        }
        
        # Initialize the pool
        self._initialize_pool()
        
        logger.info(f"DatabaseConnectionPool initialized with {self.pool_size} connections")
    
    def _initialize_pool(self):
        """Initialize the connection pool with fresh connections."""
        for _ in range(self.pool_size):
            try:
                session = SessionLocal()
                self._pool.put(session, block=False)
                self._connection_stats['created'] += 1
            except Exception as e:
                logger.error(f"Failed to create initial connection: {e}")
    
    @contextmanager
    def get_connection(self, timeout: float = 5.0):
        """
        Get a database connection from the pool with automatic return.
        
        Args:
            timeout: Maximum time to wait for a connection
            
        Yields:
            Session: Database session from the pool
        """
        session = None
        try:
            session = self._borrow_connection(timeout)
            if session and self._health_check(session):
                yield session
            else:
                # Create new connection if health check fails
                session = self._create_new_connection()
                yield session
        except Exception as e:
            logger.error(f"Error with database connection: {e}")
            if session:
                self._invalidate_connection(session)
                session = None
            raise
        finally:
            if session:
                self._return_connection(session)
    
    def _borrow_connection(self, timeout: float) -> Optional[Session]:
        """
        Borrow a connection from the pool.
        
        Args:
            timeout: Maximum time to wait for a connection
            
        Returns:
            Optional[Session]: Database session or None if timeout
        """
        try:
            session = self._pool.get(timeout=timeout)
            with self._pool_lock:
                self._active_connections.add(session)
            self._connection_stats['borrowed'] += 1
            return session
        except Empty:
            logger.warning(f"Connection pool timeout after {timeout}s")
            return None
    
    def _return_connection(self, session: Session):
        """
        Return a connection to the pool.
        
        Args:
            session: Database session to return
        """
        try:
            with self._pool_lock:
                self._active_connections.discard(session)
            
            # Check if connection is still valid before returning
            if self._health_check(session):
                self._pool.put(session, block=False)
                self._connection_stats['returned'] += 1
            else:
                # Close invalid connection and create a new one
                self._close_connection(session)
                new_session = self._create_new_connection()
                if new_session:
                    self._pool.put(new_session, block=False)
        except Full:
            # Pool is full, close the connection
            self._close_connection(session)
        except Exception as e:
            logger.error(f"Error returning connection to pool: {e}")
            self._close_connection(session)
    
    def _health_check(self, session: Session) -> bool:
        """
        Perform a health check on a database connection.
        
        Args:
            session: Database session to check
            
        Returns:
            bool: True if connection is healthy, False otherwise
        """
        try:
            # Simple query to test connection
            session.execute("SELECT 1")
            self._connection_stats['health_checks'] += 1
            return True
        except (SQLAlchemyError, DisconnectionError) as e:
            logger.warning(f"Connection health check failed: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error in health check: {e}")
            return False
    
    def _create_new_connection(self) -> Optional[Session]:
        """
        Create a new database connection.
        
        Returns:
            Optional[Session]: New database session or None if failed
        """
        try:
            session = SessionLocal()
            self._connection_stats['created'] += 1
            return session
        except Exception as e:
            logger.error(f"Failed to create new connection: {e}")
            self._connection_stats['failed'] += 1
            return None
    
    def _close_connection(self, session: Session):
        """
        Close a database connection.
        
        Args:
            session: Database session to close
        """
        try:
            session.close()
        except Exception as e:
            logger.warning(f"Error closing connection: {e}")
    
    def _invalidate_connection(self, session: Session):
        """
        Invalidate and remove a connection from active tracking.
        
        Args:
            session: Database session to invalidate
        """
        with self._pool_lock:
            self._active_connections.discard(session)
        self._close_connection(session)
        self._connection_stats['failed'] += 1
    
    def bulk_save_inspection_details(self, inspection_details: List[InspectionDetails]) -> bool:
        """
        Bulk save inspection details with retry logic and exponential backoff.
        
        Args:
            inspection_details: List of InspectionDetails objects to save
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not inspection_details:
            return True
        
        for attempt in range(self.max_retries):
            try:
                with self.get_connection() as session:
                    # Use bulk_save_objects for better performance
                    session.bulk_save_objects(inspection_details)
                    session.commit()
                    logger.debug(f"Bulk saved {len(inspection_details)} inspection details")
                    return True
                    
            except Exception as e:
                logger.warning(f"Bulk save attempt {attempt + 1} failed: {e}")
                if attempt < self.max_retries - 1:
                    # Exponential backoff
                    delay = self.retry_delay * (2 ** attempt)
                    time.sleep(delay)
                else:
                    logger.error(f"Bulk save failed after {self.max_retries} attempts")
                    return False
        
        return False
    
    def execute_with_retry(self, operation_func, *args, **kwargs) -> Any:
        """
        Execute a database operation with retry logic.
        
        Args:
            operation_func: Function to execute
            *args: Arguments for the function
            **kwargs: Keyword arguments for the function
            
        Returns:
            Any: Result of the operation
        """
        for attempt in range(self.max_retries):
            try:
                with self.get_connection() as session:
                    return operation_func(session, *args, **kwargs)
                    
            except Exception as e:
                logger.warning(f"Operation attempt {attempt + 1} failed: {e}")
                if attempt < self.max_retries - 1:
                    delay = self.retry_delay * (2 ** attempt)
                    time.sleep(delay)
                else:
                    logger.error(f"Operation failed after {self.max_retries} attempts")
                    raise
    
    def get_pool_stats(self) -> Dict[str, Any]:
        """
        Get connection pool statistics.
        
        Returns:
            Dict[str, Any]: Pool statistics
        """
        with self._pool_lock:
            active_count = len(self._active_connections)
        
        return {
            'pool_size': self.pool_size,
            'available_connections': self._pool.qsize(),
            'active_connections': active_count,
            'total_created': self._connection_stats['created'],
            'total_borrowed': self._connection_stats['borrowed'],
            'total_returned': self._connection_stats['returned'],
            'total_failed': self._connection_stats['failed'],
            'health_checks': self._connection_stats['health_checks']
        }
    
    def close_all_connections(self):
        """Close all connections in the pool and cleanup resources."""
        logger.info("Closing all database connections")
        
        # Close active connections
        with self._pool_lock:
            for session in list(self._active_connections):
                self._close_connection(session)
            self._active_connections.clear()
        
        # Close pooled connections
        while not self._pool.empty():
            try:
                session = self._pool.get_nowait()
                self._close_connection(session)
            except Empty:
                break
        
        logger.info("All database connections closed")
