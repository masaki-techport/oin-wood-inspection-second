DROP TABLE IF EXISTS t_inspection_result;

CREATE TABLE t_inspection_result (
  inspection_id BIGINT UNSIGNED NOT NULL COMMENT '検査ID（外部キー）', 
  discoloration BOOLEAN NOT NULL DEFAULT FALSE COMMENT '変色 (0)',
  hole          BOOLEAN NOT NULL DEFAULT FALSE COMMENT '穴 (1)',
  knot          BOOLEAN NOT NULL DEFAULT FALSE COMMENT '節 (2)',
  dead_knot     BOOLEAN NOT NULL DEFAULT FALSE COMMENT '流れ節_死 (3)',
  live_knot     BOOLEAN NOT NULL DEFAULT FALSE COMMENT '流れ節_生 (4)',
  tight_knot    BOOLEAN NOT NULL DEFAULT FALSE COMMENT '生き節 (5)',
  length        FLOAT DEFAULT NULL COMMENT '欠点の長さ（mm）',

  PRIMARY KEY (inspection_id),
  CONSTRAINT FK_inspection_result_id
    FOREIGN KEY (inspection_id)
    REFERENCES t_inspection (inspection_id)
    ON DELETE CASCADE
    ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='検査結果詳細テーブル';
