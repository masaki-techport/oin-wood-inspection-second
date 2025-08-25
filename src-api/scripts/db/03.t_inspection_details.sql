DROP TABLE IF EXISTS t_inspection_details;

CREATE TABLE t_inspection_details (
  error_id          BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT 'エラー検出ID',
  inspection_id     BIGINT UNSIGNED NOT NULL COMMENT '検査ID（外部キー）',
  error_type        INT NOT NULL COMMENT 'エラータイプ (0:変色, 1:穴, 2:死に節, 3:流れ節_死, 4:流れ節_生, 5:生き節)',
  error_type_name   VARCHAR(50) NOT NULL COMMENT 'エラータイプ名',
  x_position        FLOAT NOT NULL COMMENT 'X座標',
  y_position        FLOAT NOT NULL COMMENT 'Y座標',
  width             FLOAT NOT NULL COMMENT '幅',
  height            FLOAT NOT NULL COMMENT '高さ',
  length            FLOAT NOT NULL DEFAULT 0 COMMENT '長さ (幅と高さの最大値)',
  confidence        FLOAT NOT NULL COMMENT '信頼度',
  image_path        VARCHAR(255) DEFAULT NULL COMMENT 'エラー画像のパス',
  image_no          INT DEFAULT NULL COMMENT '画像番号',
  create_dt         TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '作成日時',
  update_dt         TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新日時',

  PRIMARY KEY (error_id),
  CONSTRAINT FK_inspection_details_inspection_id
    FOREIGN KEY (inspection_id)
    REFERENCES t_inspection (inspection_id)
    ON DELETE CASCADE
    ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='検査詳細テーブル';

-- Index for faster queries by inspection_id
CREATE INDEX idx_inspection_details_inspection_id ON t_inspection_details(inspection_id); 