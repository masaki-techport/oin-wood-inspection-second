CREATE TABLE IF NOT EXISTS t_inspection_presentation (
    id SERIAL PRIMARY KEY,
    inspection_id INTEGER NOT NULL,
    group_name VARCHAR(1) NOT NULL,  -- 'A', 'B', 'C', 'D', or 'E'
    image_path VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_inspection_id 
        FOREIGN KEY (inspection_id)
        REFERENCES t_inspection (inspection_id)
        ON DELETE CASCADE
);

-- Create an index for faster lookups by inspection_id
CREATE INDEX IF NOT EXISTS idx_presentation_inspection_id ON t_inspection_presentation (inspection_id);

-- Create a unique constraint to ensure one image per group per inspection
CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_group_per_inspection ON t_inspection_presentation (inspection_id, group_name);

COMMENT ON TABLE t_inspection_presentation IS 'Stores representative images for each inspection group (A-E)';
COMMENT ON COLUMN t_inspection_presentation.group_name IS 'Presentation group name (A, B, C, D, or E)';
COMMENT ON COLUMN t_inspection_presentation.image_path IS 'Path to the image file'; 