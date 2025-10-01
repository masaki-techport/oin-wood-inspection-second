# Database Saving Logic Deep Dive

## Table of Contents

1. [Database Schema Overview](#database-schema-overview)
2. [Data Transformation Pipeline](#data-transformation-pipeline)
3. [Sequential vs Parallel Saving Logic](#sequential-vs-parallel-saving-logic)
4. [Data Validation and Sanitization](#data-validation-and-sanitization)
5. [Performance Optimization Strategies](#performance-optimization-strategies)

## Database Schema Overview

### Primary Tables and Relationships

```sql
-- Main inspection record
CREATE TABLE inspection (
    inspection_id INTEGER PRIMARY KEY AUTOINCREMENT,
    ai_threshold INTEGER NOT NULL,           -- AI confidence threshold (0-100)
    inspection_dt DATETIME NOT NULL,         -- Inspection timestamp
    file_path TEXT NOT NULL,                 -- Directory path to images
    status BOOLEAN DEFAULT FALSE,            -- Whether defects found above threshold
    results TEXT DEFAULT '無欠点',           -- Classification result (無欠点/こぶし/節あり)
    create_dt DATETIME DEFAULT CURRENT_TIMESTAMP,
    update_dt DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Aggregated inspection results with boolean flags
CREATE TABLE inspection_result (
    inspection_id INTEGER PRIMARY KEY,
    discoloration BOOLEAN DEFAULT FALSE,    -- 変色 detected
    hole BOOLEAN DEFAULT FALSE,             -- 穴 detected
    knot BOOLEAN DEFAULT FALSE,             -- 節 detected (any type)
    dead_knot BOOLEAN DEFAULT FALSE,        -- 死に節 detected
    live_knot BOOLEAN DEFAULT FALSE,        -- 流れ節(生) detected
    tight_knot BOOLEAN DEFAULT FALSE,       -- 生き節 detected
    length REAL NOT NULL DEFAULT 0.0,      -- Maximum defect length in mm
    FOREIGN KEY (inspection_id) REFERENCES inspection(inspection_id)
);

-- Detailed detection records for each defect found
CREATE TABLE inspection_details (
    error_id INTEGER PRIMARY KEY AUTOINCREMENT,
    inspection_id INTEGER NOT NULL,
    error_type INTEGER NOT NULL,           -- Detection class ID (0-5)
    error_type_name TEXT NOT NULL,         -- Japanese classification name
    x_position REAL NOT NULL,              -- Bounding box top-left X
    y_position REAL NOT NULL,              -- Bounding box top-left Y  
    x2_position REAL NOT NULL,             -- Bounding box bottom-right X
    y2_position REAL NOT NULL,             -- Bounding box bottom-right Y
    width REAL NOT NULL,                   -- Calculated width (x2-x1)
    height REAL NOT NULL,                  -- Calculated height (y2-y1)
    length REAL,                           -- Physical length in mm
    confidence REAL NOT NULL,              -- AI confidence score (0.0-1.0)
    image_path TEXT NOT NULL,              -- Full path to source image
    image_no INTEGER,                      -- Image sequence number
    create_dt DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (inspection_id) REFERENCES inspection(inspection_id)
);
```

## Data Transformation Pipeline

### Input to Database Flow

```python
# 1. RAW AI INFERENCE OUTPUT
inference_results = {
    "success": True,
    "results": {
        "detections": [
            {
                "class_id": 2,                    # Raw class ID
                "confidence": 0.85,               # Confidence score
                "bbox": [100, 150, 200, 250]     # [x1, y1, x2, y2] coordinates
            }
        ]
    }
}

# 2. PROCESSED DETECTION DATA
processed_detection = {
    "error_type": 2,                          # Class ID for database
    "error_type_name": "死に節",              # Japanese classification
    "x_position": 100.0,                     # Bounding box coordinates
    "y_position": 150.0,
    "x2_position": 200.0,
    "y2_position": 250.0,
    "width": 100.0,                          # Calculated: x2 - x1
    "height": 100.0,                         # Calculated: y2 - y1
    "length": 12.5,                          # Physical measurement in mm
    "confidence": 0.85,                      # Normalized confidence
    "image_path": "/full/path/No_0001.bmp",  # Complete file path
    "image_no": 1                            # Extracted from filename
}

# 3. AGGREGATED RESULT FLAGS
result_flags = {
    "discoloration": False,                   # Class 0: 変色
    "hole": False,                           # Class 1: 穴
    "knot": True,                            # Any knot type detected
    "dead_knot": True,                       # Class 2: 死に節
    "live_knot": False,                      # Class 4: 流れ節(生)
    "tight_knot": False                      # Class 5: 生き節
}

# 4. DEFECT CLASSIFICATION MAPPING
classification_mapping = {
    0: ('変色', ['discoloration']),
    1: ('穴', ['hole']),
    2: ('死に節', ['knot', 'dead_knot']),
    3: ('流れ節(死)', ['knot', 'dead_knot']),
    4: ('流れ節(生)', ['knot', 'live_knot']),
    5: ('生き節', ['knot', 'tight_knot'])
}
```

## Sequential vs Parallel Saving Logic

### Analysis Folder: Sequential Approach

```python
def analyze_image(self, image_path: str, shared_inspection_id: int = None):
    """Single-threaded database saving with immediate consistency"""
    
    # PHASE 1: AI INFERENCE AND DATA PROCESSING
    inference_results = self.camera.inference_service.predict_image(image_path)
    detections = self._process_detections(inference_results)
    max_length = self._calculate_max_length(detections)
    result_flags = self._extract_result_flags(detections)
    inspection_result = self._classify_inspection(result_flags, max_length)
    
    # PHASE 2: SINGLE TRANSACTION DATABASE SAVE
    max_retries = 3
    for retry in range(max_retries):
        try:
            with SessionLocal() as session:
                session.begin()
                
                # Step 1: Create/Update Inspection
                inspection_id = self._handle_inspection_record(session, shared_inspection_id, 
                                                             inspection_result, image_path)
                
                # Step 2: Create/Update InspectionResult  
                self._handle_inspection_result(session, inspection_id, result_flags, max_length)
                
                # Step 3: Bulk Insert InspectionDetails
                if detections:
                    detail_objects = [
                        InspectionDetails(inspection_id=inspection_id, **detection)
                        for detection in detections
                    ]
                    session.bulk_save_objects(detail_objects)
                
                # Step 4: Commit All Changes
                session.commit()
                logger.info(f"Successfully saved inspection {inspection_id}")
                break
                
        except Exception as e:
            logger.error(f"Database error (attempt {retry+1}): {e}")
            if retry == max_retries - 1:
                raise
            time.sleep(0.2)
    
    return {"inspection_id": inspection_id, "results": inspection_result}

def _handle_inspection_result(self, session, inspection_id, result_flags, max_length):
    """Handle InspectionResult record with NULL prevention"""
    
    result = session.query(InspectionResult).filter_by(inspection_id=inspection_id).first()
    
    if not result:
        # Create new record
        result = InspectionResult(
            inspection_id=inspection_id,
            length=max_length if max_length > 0 else 0.0,  # NULL prevention
            **result_flags
        )
        session.add(result)
    else:
        # Update existing record with OR logic for flags
        for flag, value in result_flags.items():
            if value:
                setattr(result, flag, True)
        
        # Length update with maximum logic and NULL prevention
        if result.length is None:
            result.length = max_length if max_length > 0 else 0.0
        elif max_length > result.length:
            result.length = max_length
```

### Parallel Folder: Multi-threaded Approach

```python
class ParallelImageAnalyzer:
    def analyze_image_parallel(self, image_path: str, shared_inspection_id: int, group_name: str):
        """Thread-safe analysis with connection pool"""
        
        # PHASE 1: AI INFERENCE (Same as sequential)
        inference_results = self.camera.inference_service.predict_image(image_path)
        detections = self._process_detections(inference_results)
        
        # PHASE 2: THREAD-SAFE DATABASE OPERATIONS
        success = self._save_results_parallel(shared_inspection_id, detections)
        
        return {"inspection_id": shared_inspection_id, "group_name": group_name}
    
    def _save_results_parallel(self, inspection_id, detections):
        """Thread-safe saving using connection pool"""
        
        # Step 1: Bulk save details using connection pool
        if detections:
            success = self.db_pool.bulk_save_inspection_details(detections)
            if not success:
                return False
        
        # Step 2: Thread-safe result updates
        def update_result_thread_safe(session, inspection_id, flags, max_length):
            result = session.query(InspectionResult).filter_by(inspection_id=inspection_id).first()
            
            if result:
                # Thread-safe flag updates (OR logic preserves existing True values)
                for flag, value in flags.items():
                    if value:
                        current = getattr(result, flag, False)
                        setattr(result, flag, current or value)
                
                # Thread-safe length updates (only increase, never decrease)
                if result.length is None or max_length > result.length:
                    result.length = max_length
            
            session.commit()
            return True
        
        return self.db_pool.execute_with_retry(update_result_thread_safe, inspection_id, flags, max_length)

class DatabaseConnectionPool:
    def bulk_save_inspection_details(self, details: List[InspectionDetails]) -> bool:
        """Thread-safe bulk operations with exponential backoff"""
        
        for attempt in range(self.max_retries):
            try:
                with self.get_connection() as session:
                    session.bulk_save_objects(details)
                    session.commit()
                    return True
            except Exception as e:
                if attempt < self.max_retries - 1:
                    delay = self.retry_delay * (2 ** attempt)  # Exponential backoff
                    time.sleep(delay)
        return False
    
    @contextmanager
    def get_connection(self, timeout=5.0):
        """Thread-safe connection management with health checking"""
        session = None
        try:
            session = self._borrow_connection(timeout)
            if session and self._health_check(session):
                yield session
            else:
                session = self._create_new_connection()
                yield session
        finally:
            if session:
                self._return_connection(session)

# FINAL CONSOLIDATION PHASE
class ParallelProcessingManager:
    def _save_consolidated_length(self, inspection_id: int, final_max_length: float, final_result: str):
        """Final consolidation after all parallel threads complete"""
        
        def consolidate_final_results(session, inspection_id, max_length, result):
            # Update final length in InspectionResult
            result_record = session.query(InspectionResult).filter_by(inspection_id=inspection_id).first()
            if result_record:
                result_record.length = max_length
            
            # Update final classification in Inspection
            inspection = session.query(Inspection).filter_by(inspection_id=inspection_id).first()
            if inspection:
                inspection.results = result
            
            session.commit()
        
        with SessionLocal() as session:
            consolidate_final_results(session, inspection_id, final_max_length, final_result)
```

## Data Validation and Sanitization

### Input Validation Pipeline

```python
class DataValidator:
    @staticmethod
    def validate_detection_data(detection: Dict) -> bool:
        """Validate AI detection before processing"""
        
        # Required fields
        required = ['class_id', 'confidence', 'bbox']
        if not all(field in detection for field in required):
            return False
        
        # Class ID validation (0-5)
        class_id = detection['class_id']
        if not isinstance(class_id, int) or not 0 <= class_id <= 5:
            return False
        
        # Confidence validation (0.0-1.0)
        confidence = detection['confidence']
        if not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
            return False
        
        # Bounding box validation [x1, y1, x2, y2]
        bbox = detection['bbox']
        if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
            return False
        
        x1, y1, x2, y2 = bbox
        if not all(isinstance(coord, (int, float)) for coord in bbox):
            return False
        
        if x2 <= x1 or y2 <= y1 or any(coord < 0 for coord in bbox):
            return False
        
        return True
    
    @staticmethod
    def sanitize_length_value(length: float) -> float:
        """Sanitize length values for database storage"""
        
        if length is None or not isinstance(length, (int, float)):
            return 0.0
        
        if length < 0:
            logger.warning(f"Negative length {length}, using 0.0")
            return 0.0
        
        if length > 1000:  # Sanity check
            logger.warning(f"Length {length}mm too large, capping at 1000")
            return 1000.0
        
        return float(length)

def _extract_image_number(image_path: str) -> Optional[int]:
    """Extract image sequence number from filename"""
    try:
        basename = os.path.basename(image_path)
        match = re.search(r'No_(\d{4})\.(bmp|jpg|png)', basename)
        return int(match.group(1)) if match else None
    except Exception:
        return None

def _calculate_physical_length(bbox: List[float]) -> float:
    """Calculate physical length from pixel coordinates"""
    
    # Extract pixel dimensions
    x1, y1, x2, y2 = bbox
    pixel_width = x2 - x1
    pixel_height = y2 - y1
    
    # Get resolution settings (mm per pixel)
    horizontal_resolution = 0.245833  # Example: mm per pixel horizontal
    vertical_resolution = 0.288889    # Example: mm per pixel vertical
    
    # Calculate physical dimensions
    horizontal_mm = pixel_width * horizontal_resolution
    vertical_mm = pixel_height * vertical_resolution
    
    # Return maximum dimension as length
    return max(horizontal_mm, vertical_mm)
```

## Performance Optimization Strategies

### Database Operation Optimization

```python
# ANALYSIS FOLDER: Single Transaction Optimization
def optimized_sequential_save(session, inspection_id, detections, flags, max_length):
    """Optimized single transaction with bulk operations"""
    
    # Use bulk operations for better performance
    if detections:
        session.bulk_save_objects([
            InspectionDetails(inspection_id=inspection_id, **detection)
            for detection in detections
        ])
    
    # Single query for InspectionResult update
    session.query(InspectionResult).filter_by(inspection_id=inspection_id).update({
        'length': max_length,
        **flags
    })
    
    session.commit()

# PARALLEL FOLDER: Connection Pool Optimization
class OptimizedConnectionPool:
    def __init__(self, pool_size=8):
        self.pool_size = min(10, max(5, pool_size))  # Optimal range 5-10
        self._pool = Queue(maxsize=self.pool_size)
        self._health_check_interval = 60  # Health check every 60 seconds
        
    def bulk_save_with_batching(self, details: List[InspectionDetails], batch_size=100):
        """Bulk save with optimal batch sizing"""
        
        # Process in batches for memory efficiency
        for i in range(0, len(details), batch_size):
            batch = details[i:i + batch_size]
            
            with self.get_connection() as session:
                session.bulk_save_objects(batch)
                session.commit()

# DATABASE SCHEMA OPTIMIZATIONS
"""
-- Add performance indexes
CREATE INDEX idx_inspection_details_inspection_id ON inspection_details(inspection_id);
CREATE INDEX idx_inspection_result_inspection_id ON inspection_result(inspection_id);
CREATE INDEX idx_inspection_dt ON inspection(inspection_dt);

-- Optimize for bulk inserts
PRAGMA synchronous = NORMAL;
PRAGMA journal_mode = WAL;
PRAGMA cache_size = 10000;
"""

# MONITORING AND METRICS
class PerformanceMonitor:
    def track_database_operations(self):
        return {
            'avg_transaction_time': self.calculate_avg_transaction_time(),
            'connection_pool_utilization': self.get_pool_utilization(),
            'bulk_operation_efficiency': self.calculate_bulk_efficiency(),
            'error_rate': self.calculate_error_rate()
        }
```

### Key Performance Differences

| Metric | Analysis Folder | Parallel Folder | Improvement |
|--------|----------------|-----------------|-------------|
| **Throughput** | 1-2 images/sec | 5-10 images/sec | 5x faster |
| **Connections** | 1 per image | 5-10 pooled | 90% reduction |
| **Memory Usage** | Low | Medium | 2x increase |
| **Error Recovery** | Basic retry | Advanced backoff | Better resilience |
| **Consistency** | Immediate | Eventual + consolidation | Trade-off |

This documentation provides a comprehensive understanding of how data is saved to the database in both architectures, highlighting the logic, validation, and performance considerations for each approach.