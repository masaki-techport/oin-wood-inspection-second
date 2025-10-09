SET CHARACTER_SET_CLIENT = utf8mb4;
SET CHARACTER_SET_CONNECTION = utf8mb4;

DROP TABLE if exists t_inspection;
CREATE TABLE t_inspection (
  `inspection_id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '検査トランザクションID',
  `product_no` VARCHAR(10) NOT NULL COMMENT '品番',
  `serial` VARCHAR(20) NOT NULL COMMENT 'シリアル',
  `inspection_dt` TIMESTAMP COMMENT '検査日時',
  `inspection_result` BOOLEAN NOT NULL COMMENT '検査結果\n0:OK\n1:NG',
  `file_path` VARCHAR(4096) COMMENT 'ファイルパス',
  `create_dt` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '作成日時',
  `update_dt` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新日時',
  PRIMARY KEY (`inspection_id`),
  FOREIGN KEY FK_product_id (product_no) 
    REFERENCES t_product (product_no)
    ON UPDATE CASCADE
    ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='検査トランザクションテーブル';