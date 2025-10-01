"""
Centralized logging setup.

Requirements:
- Use logging.getLogger and proper levels
- Save logs to ./log
- Daily rotation at 00:00, keep 7 days (configurable)
- Console output goes through logger

Log Level Categories:
- DEBUG: Development logs (sensor status, init routes, internal state changes)
- INFO: User-relevant information (startup/shutdown, camera capture start, analysis start, image save)
- WARNING: Non-critical warnings that don't prevent program continuation
- ERROR: Critical failures that prevent program continuation
- EXCEPTION: Exception handling and stack traces
"""

import os
import glob
import logging
from logging.handlers import TimedRotatingFileHandler
from typing import Optional
from datetime import time, datetime

# Add custom EXCEPTION level (between ERROR and CRITICAL)
EXCEPTION_LEVEL = 45
logging.addLevelName(EXCEPTION_LEVEL, 'EXCEPTION')

def exception(self, message, *args, **kwargs):
    """Log a message with severity 'EXCEPTION'."""
    if self.isEnabledFor(EXCEPTION_LEVEL):
        self._log(EXCEPTION_LEVEL, message, args, **kwargs)

# Add the exception method to Logger class
logging.Logger.exception = exception


def _ensure_directory(dir_path: str) -> None:
    try:
        os.makedirs(dir_path, exist_ok=True)
    except Exception:
        # Fall back silently; handler will raise on failure when used
        pass


def _generate_log_filename(name_as: Optional[str] = None) -> str:
    """Generate log filename with today's date.
    
    Args:
        name_as: Custom name prefix. If provided, uses 'name_as_YYYY-MM-DD.log'.
                 If not provided, uses 'YYYY-MM-DD.log'.
    
    Returns:
        Log filename with today's date.
    """
    today = datetime.now().strftime("%Y-%m-%d")
    
    if name_as:
        # Remove any file extension if provided
        name_as = name_as.replace('.log', '').replace('.txt', '')
        return f"{name_as}_{today}.log"
    else:
        return f"{today}.log"


def setup_logging(
    *,
    log_dir: Optional[str] = None,
    log_level: str = "INFO",
    when: str = "midnight",
    interval: int = 1,
    # Time-based retention only
    max_save_days: int = 7,
    fmt: str = "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt: str = "%Y-%m-%d %H:%M:%S",
    at_time: Optional[str] = None,
    name_as: Optional[str] = None,
) -> logging.Logger:
    """Configure root logger with console and timed-rotating file handlers.

    Args:
        log_dir: Directory to store log files. Defaults to './log'.
        log_level: Root log level.
        when: Rotation interval unit (e.g., 'midnight', 'H').
        interval: Rotation interval count.
        backup_count: Number of rotated files to keep.
        fmt: Log message format.
        datefmt: Timestamp format.
        at_time: Time for rotation in 24H format (e.g., '14:30' for 2:30 PM).
        name_as: Custom name for log file. If provided, uses 'name_as_YYYY-MM-DD.log'.
                 If not provided, uses 'YYYY-MM-DD.log'.

    Returns:
        The configured root logger.
    """
    if log_dir is None:
        log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "log")

    # Resolve relative paths relative to current working directory
    if not os.path.isabs(log_dir):
        log_dir = os.path.abspath(os.path.join(os.getcwd(), log_dir))

    _ensure_directory(log_dir)

    root_logger = logging.getLogger()
    
    # Handle custom EXCEPTION level
    if log_level.upper() == "EXCEPTION":
        root_logger.setLevel(EXCEPTION_LEVEL)
    else:
        root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Clear existing handlers to avoid duplicates when reloading
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    formatter = logging.Formatter(fmt=fmt, datefmt=datefmt)

    # Console handler
    console_handler = logging.StreamHandler()
    if log_level.upper() == "EXCEPTION":
        console_handler.setLevel(EXCEPTION_LEVEL)
    else:
        console_handler.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # File handler with timed rotation
    log_filename = _generate_log_filename(name_as)
    log_file_path = os.path.join(log_dir, log_filename)
    
    # Parse at_time if provided (24H format: HH:MM)
    at_time_obj = None
    if at_time:
        try:
            hour, minute = map(int, at_time.split(':'))
            at_time_obj = time(hour, minute)
        except (ValueError, IndexError):
            # Invalid format, use default
            pass
    
    file_handler = TimedRotatingFileHandler(
        log_file_path, 
        when=when, 
        interval=interval, 
        backupCount=0, 
        encoding="utf-8",
        atTime=at_time_obj
    )
    if log_level.upper() == "EXCEPTION":
        file_handler.setLevel(EXCEPTION_LEVEL)
    else:
        file_handler.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    # Enforce time-based retention proactively
    try:
        enforce_log_retention_by_days(log_dir, max_save_days, log_filename)
    except Exception:
        # Do not break startup for retention issues
        root_logger.debug("Log retention enforcement skipped due to exception", exc_info=True)

    root_logger.debug(
        "Logging initialized dir=%s level=%s when=%s interval=%s max_save_days=%s",
        log_dir,
        log_level,
        when,
        interval,
        max_save_days,
    )

    return root_logger


def setup_logging_from_ini(config) -> logging.Logger:
    """Setup logging from a ConfigParser-like object with a [LOG] section.

    Recognized keys:
    - log_folder (default: ./log)
    - level (default: INFO)
    - when (default: midnight)
    - interval (default: 1)
    - max_save_days (time-based retention in days)
    - format (default formatter)
    - timestamp_format (datefmt)
    - at_time (24H format time for rotation, e.g., '14:30')
    - name_as (custom name for log file, e.g., 'app' -> 'app_2025-01-15.log')
    """
    log_section = "LOG"
    log_dir = None
    level = "INFO"
    when = "midnight"
    interval = 1
    max_save_days = 7
    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"
    at_time = None
    name_as = None

    try:
        if config.has_section(log_section):
            log_dir = config.get(log_section, "log_folder", fallback=None)
            level = config.get(log_section, "level", fallback=level)
            when = config.get(log_section, "when", fallback=when)
            # 'interval' optional; default 1 if not provided
            try:
                interval = config.getint(log_section, "interval", fallback=interval)
            except Exception:
                interval = 1
            # Time-based retention (in days)
            try:
                max_save_days = config.getint(log_section, "max_save_days", fallback=max_save_days)
                if max_save_days < 0:
                    max_save_days = 0
            except Exception:
                max_save_days = 0
            
            fmt = config.get(log_section, "format", fallback=fmt)
            datefmt = config.get(log_section, "timestamp_format", fallback=datefmt)
            
            at_time = config.get(log_section, "at_time", fallback=at_time)
            name_as = config.get(log_section, "name_as", fallback=name_as)
            
            # Validate log level (including custom EXCEPTION level)
            valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL", "EXCEPTION"]
            if level.upper() not in valid_levels:
                level = "INFO"  # Default to INFO if invalid level specified
    except Exception:
        # Use defaults on any parsing error
        pass

    return setup_logging(
        log_dir=log_dir or os.path.join(os.path.dirname(os.path.dirname(__file__)), "log"),
        log_level=level,
        when=when,
        interval=interval,
        max_save_days=max_save_days,
        fmt=fmt,
        datefmt=datefmt,
        at_time=at_time,
        name_as=name_as,
    )


def enforce_log_retention(log_dir: str, max_save_files: int, base_filename: str = "app.log") -> None:
    # Deprecated: retained for backward imports; no-op to favor time-based retention
    return

def enforce_log_retention_by_days(log_dir: str, max_save_days: int, base_filename: str = "app.log") -> None:
    """Prune log files older than max_save_days based on file creation time.

    Args:
        log_dir: Directory where logs are stored.
        max_save_days: Maximum age in days; files older than this are deleted.
        base_filename: The base log filename used to derive the glob pattern.
    """
    if max_save_days <= 0:
        return

    # Ensure log directory exists
    if not os.path.exists(log_dir):
        return

    # Build comprehensive patterns to cover all log files
    base_name = base_filename.replace('.log', '')
    import re
    patterns = set()
    # Always include date-only pattern
    patterns.add(os.path.join(log_dir, f"????-??-??.log*"))
    # Include any prefixed pattern
    underscore_date_pattern = r'_\d{4}-\d{2}-\d{2}$'
    if re.search(underscore_date_pattern, base_name):
        prefix = re.sub(underscore_date_pattern, '', base_name)
        if prefix:
            patterns.add(os.path.join(log_dir, f"{prefix}_*.log*"))
    # Also include a generic prefixed pattern to catch old files when name_as changed
    patterns.add(os.path.join(log_dir, f"*_????-??-??.log*"))
    # Include all .log files to ensure we catch everything
    patterns.add(os.path.join(log_dir, "*.log*"))

    files = []
    for _pattern in patterns:
        files.extend(glob.glob(_pattern))
    # De-duplicate
    files = list(set(files))
    if not files:
        return

    from datetime import timedelta
    logger = logging.getLogger(__name__)

    # Compute cutoff timestamp: delete files older than max_save_days
    # With max_save_days=1, keep files from today only, delete older
    # With max_save_days=7, keep files from the last 7 days, delete older
    # Use start of day to ensure proper retention
    now = datetime.now()
    start_of_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    
    if max_save_days == 1:
        # For 1 day, keep only today's files
        cutoff_time = start_of_today
    else:
        # For multiple days, keep files from the last N days
        # If max_save_days=7, keep files from today back to 7 days ago (inclusive)
        cutoff_time = start_of_today - timedelta(days=max_save_days)
    

    for path in files:
        try:
            # Use file creation time for retention decision
            file_ctime = os.path.getctime(path)
            file_time = datetime.fromtimestamp(file_ctime)
            
            # Check if file should be deleted based on creation time
            should_delete = file_time < cutoff_time
            
            # Additional check: if file doesn't match date pattern and is old, delete it
            filename = os.path.basename(path)
            if not _is_log_file_with_date_pattern(filename) and should_delete:
                should_delete = True
            
            if should_delete:
                try:
                    os.remove(path)
                    logger.debug("Retention: deleted old log %s (ctime=%s, cutoff=%s)", path, file_time, cutoff_time)
                except Exception:
                    logger.debug("Retention: failed to delete %s", path, exc_info=True)
            else:
                logger.debug("Retention: kept log %s (ctime=%s, cutoff=%s)", path, file_time, cutoff_time)
        except Exception:
            logger.debug("Retention: error processing %s", path, exc_info=True)


def _is_log_file_with_date_pattern(filename: str) -> bool:
    """Check if filename matches expected log file date patterns.
    
    Args:
        filename: The filename to check
        
    Returns:
        True if filename matches date patterns, False otherwise
    """
    import re
    
    # Pattern for YYYY-MM-DD.log format
    date_only_pattern = r'^\d{4}-\d{2}-\d{2}\.log$'
    if re.match(date_only_pattern, filename):
        return True
    
    # Pattern for prefix_YYYY-MM-DD.log format
    prefixed_date_pattern = r'^.+_\d{4}-\d{2}-\d{2}\.log$'
    if re.match(prefixed_date_pattern, filename):
        return True
    
    return False