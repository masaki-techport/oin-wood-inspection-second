SET CHARACTER_SET_CLIENT = utf8mb4;
SET CHARACTER_SET_CONNECTION = utf8mb4;

CREATE TABLE IF NOT EXISTS t_inspection_images (
    id SERIAL PRIMARY KEY,
    inspection_id BIGINT UNSIGNED NOT NULL,
    image_no INT NOT NULL DEFAULT 0 COMMENT 'Image sequence number',
    image_path VARCHAR(4096) NOT NULL COMMENT 'Path to stored image file',
    image_type VARCHAR(50) NOT NULL COMMENT 'Type of image (raw, processed, etc.)',
    capture_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT 'When the image was captured',
    image_metadata JSON DEFAULT NULL COMMENT 'Additional image metadata',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'Record creation time',
    CONSTRAINT fk_images_inspection
        FOREIGN KEY (inspection_id)
        REFERENCES t_inspection (inspection_id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='Stores images related to wood inspections';

-- Create an index for faster lookups by inspection_id
CREATE INDEX IF NOT EXISTS idx_images_inspection_id ON t_inspection_images (inspection_id);

-- Create an index for image_type for filtering
CREATE INDEX IF NOT EXISTS idx_images_type ON t_inspection_images (image_type);

COMMENT ON TABLE t_inspection_images IS 'Stores image files captured during inspection process';
COMMENT ON COLUMN t_inspection_images.image_path IS 'Full path to the stored image file';
COMMENT ON COLUMN t_inspection_images.image_type IS 'Classification of image (raw, processed, segmented, etc.)';
COMMENT ON COLUMN t_inspection_images.image_metadata IS 'JSON object containing additional image metadata';