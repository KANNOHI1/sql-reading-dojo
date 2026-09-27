-- ミツキ化粧品（架空の化粧品卸）— 教材データの唯一の元データ
-- BigQuery 表記では `dojo.customers` のように参照する。
-- 罠を踏ませるための仕掛けを意図的に埋め込んである（各表のコメント参照）。
-- 数値は円。sale_ts は UTC の TIMESTAMP（BigQuery の既定と同じ）。

CREATE SCHEMA IF NOT EXISTS dojo;

-- 得意先。C005 は region が NULL、C006 / C007 は売上ゼロ（C007 は目標だけある）
CREATE TABLE dojo.customers (
  customer_id   STRING  NOT NULL,
  customer_name STRING  NOT NULL,
  channel       STRING  NOT NULL,   -- ドラッグ / GMS / 百貨店 / EC
  region        STRING,             -- NULL あり
  is_active     BOOL    NOT NULL
);
INSERT INTO dojo.customers VALUES
  ('C001', 'ツルバ薬局',         'ドラッグ', '北海道', TRUE),
  ('C002', 'サンライズドラッグ', 'ドラッグ', '関東',   TRUE),
  ('C003', 'まるみ百貨店',       '百貨店',   '関東',   TRUE),
  ('C004', 'ライフモール',       'GMS',      '関西',   TRUE),
  ('C005', 'ビューティ通販',     'EC',       NULL,     TRUE),
  ('C006', 'ひまわり薬局',       'ドラッグ', '九州',   FALSE),
  ('C007', 'ノース百貨店',       '百貨店',   '北海道', TRUE),
  ('C008', 'みなと商店',         'GMS',      '関西',   TRUE);

-- 店舗。1 得意先に複数店舗（1 対多）。S10 / S11 は売上なし
CREATE TABLE dojo.stores (
  store_id    STRING NOT NULL,
  customer_id STRING NOT NULL,
  store_name  STRING NOT NULL,
  prefecture  STRING NOT NULL,
  opened_date DATE   NOT NULL
);
INSERT INTO dojo.stores VALUES
  ('S01', 'C001', '札幌本店',   '北海道', DATE '2015-04-01'),
  ('S02', 'C001', '旭川店',     '北海道', DATE '2019-10-01'),
  ('S03', 'C002', '新宿店',     '東京都', DATE '2012-03-01'),
  ('S04', 'C002', '横浜店',     '神奈川県', DATE '2016-07-01'),
  ('S05', 'C002', '大宮店',     '埼玉県', DATE '2026-05-01'),
  ('S06', 'C003', '銀座本店',   '東京都', DATE '1998-11-01'),
  ('S07', 'C004', '梅田店',     '大阪府', DATE '2008-09-01'),
  ('S08', 'C004', '神戸店',     '兵庫県', DATE '2014-02-01'),
  ('S09', 'C005', 'オンライン', '東京都', DATE '2020-06-01'),
  ('S10', 'C006', '博多店',     '福岡県', DATE '2010-05-01'),
  ('S11', 'C007', '札幌店',     '北海道', DATE '2005-08-01'),
  ('S12', 'C008', '難波店',     '大阪府', DATE '2018-12-01');

-- 商品。P004 と P005 は同名で ID 違い（リニューアル）。P008 は未発売
CREATE TABLE dojo.products (
  product_id   STRING NOT NULL,
  product_name STRING NOT NULL,
  brand        STRING NOT NULL,   -- ルミナ / ハナ / ソラ
  category     STRING NOT NULL,   -- スキンケア / メイク / ボディ
  list_price   INT64  NOT NULL,
  launch_date  DATE   NOT NULL
);
INSERT INTO dojo.products VALUES
  ('P001', 'ルミナ 化粧水',       'ルミナ', 'スキンケア', 3800,  DATE '2025-03-01'),
  ('P002', 'ルミナ 乳液',         'ルミナ', 'スキンケア', 4200,  DATE '2025-03-01'),
  ('P003', 'ルミナ 美容液',       'ルミナ', 'スキンケア', 8800,  DATE '2026-04-15'),
  ('P004', 'ハナ リップルージュ', 'ハナ',   'メイク',     2500,  DATE '2025-09-01'),
  ('P005', 'ハナ リップルージュ', 'ハナ',   'メイク',     2800,  DATE '2026-05-01'),
  ('P006', 'ソラ 日焼け止め',     'ソラ',   'ボディ',     2200,  DATE '2025-04-01'),
  ('P007', 'ソラ ボディミルク',   'ソラ',   'ボディ',     1800,  DATE '2025-04-01'),
  ('P008', 'ルミナ クリーム',     'ルミナ', 'スキンケア', 12000, DATE '2026-10-01'),
  ('P009', 'ハナ アイシャドウ',   'ハナ',   'メイク',     3200,  DATE '2025-09-01'),
  ('P010', 'ソラ ハンドクリーム', 'ソラ',   'ボディ',     980,   DATE '2025-11-01');

-- 売上。sale_ts は UTC。T017 は JST 6/1 00:30（UTC では 5/31）。T021 は返品（負数）。T026 は amount NULL
CREATE TABLE dojo.sales (
  sale_id    STRING    NOT NULL,
  sale_ts    TIMESTAMP NOT NULL,
  store_id   STRING    NOT NULL,
  product_id STRING    NOT NULL,
  qty        INT64     NOT NULL,
  amount     INT64                -- NULL あり
);
INSERT INTO dojo.sales VALUES
  ('T001', TIMESTAMP '2026-04-03 02:10:00', 'S03', 'P001', 10,  38000),
  ('T002', TIMESTAMP '2026-04-05 05:40:00', 'S01', 'P006', 8,   17600),
  ('T003', TIMESTAMP '2026-04-12 01:15:00', 'S06', 'P002', 5,   21000),
  ('T004', TIMESTAMP '2026-04-20 07:00:00', 'S07', 'P004', 12,  30000),
  ('T005', TIMESTAMP '2026-04-28 03:30:00', 'S09', 'P003', 3,   26400),
  ('T006', TIMESTAMP '2026-05-02 04:00:00', 'S03', 'P002', 6,   25200),
  ('T007', TIMESTAMP '2026-05-06 06:20:00', 'S04', 'P001', 7,   26600),
  ('T008', TIMESTAMP '2026-05-09 02:45:00', 'S12', 'P007', 15,  27000),
  ('T009', TIMESTAMP '2026-05-15 01:00:00', 'S05', 'P005', 9,   25200),
  ('T010', TIMESTAMP '2026-05-18 08:10:00', 'S08', 'P006', 4,   8800),
  ('T011', TIMESTAMP '2026-05-22 03:05:00', 'S06', 'P003', 2,   17600),
  ('T012', TIMESTAMP '2026-05-25 05:50:00', 'S02', 'P010', 20,  19600),
  ('T013', TIMESTAMP '2026-05-30 02:30:00', 'S09', 'P009', 6,   19200),
  ('T014', TIMESTAMP '2026-06-01 01:00:00', 'S03', 'P001', 12,  45600),
  ('T015', TIMESTAMP '2026-06-04 06:15:00', 'S07', 'P002', 4,   16800),
  ('T016', TIMESTAMP '2026-06-08 03:40:00', 'S01', 'P001', 5,   19000),
  ('T017', TIMESTAMP '2026-05-31 15:30:00', 'S03', 'P004', 3,   7500),
  ('T018', TIMESTAMP '2026-06-12 02:20:00', 'S04', 'P006', 10,  22000),
  ('T019', TIMESTAMP '2026-06-15 04:55:00', 'S12', 'P001', 6,   22800),
  ('T020', TIMESTAMP '2026-06-18 01:30:00', 'S06', 'P003', 4,   35200),
  ('T021', TIMESTAMP '2026-06-19 07:10:00', 'S03', 'P001', -1,  -3800),
  ('T022', TIMESTAMP '2026-06-22 05:00:00', 'S08', 'P007', 8,   14400),
  ('T023', TIMESTAMP '2026-06-25 02:00:00', 'S05', 'P009', 5,   16000),
  ('T024', TIMESTAMP '2026-06-27 03:35:00', 'S09', 'P005', 7,   19600),
  ('T025', TIMESTAMP '2026-06-29 06:45:00', 'S02', 'P006', 3,   6600),
  ('T026', TIMESTAMP '2026-06-30 01:20:00', 'S07', 'P010', 10,  NULL),
  ('T027', TIMESTAMP '2026-07-02 02:50:00', 'S03', 'P002', 8,   33600),
  ('T028', TIMESTAMP '2026-07-06 04:30:00', 'S01', 'P003', 2,   17600),
  ('T029', TIMESTAMP '2026-07-10 01:45:00', 'S06', 'P001', 9,   34200),
  ('T030', TIMESTAMP '2026-07-14 06:00:00', 'S12', 'P009', 4,   12800);

-- 施策。P001 の 2 施策は期間が重なる（JOIN で行が増える）
CREATE TABLE dojo.promotions (
  promo_id   STRING NOT NULL,
  promo_name STRING NOT NULL,
  product_id STRING NOT NULL,
  start_date DATE   NOT NULL,
  end_date   DATE   NOT NULL
);
INSERT INTO dojo.promotions VALUES
  ('PR01', '化粧水 初夏キャンペーン', 'P001', DATE '2026-06-01', DATE '2026-06-30'),
  ('PR02', 'ルミナ ボーナス施策',     'P001', DATE '2026-06-15', DATE '2026-07-15'),
  ('PR03', 'リップ 新色発売',         'P004', DATE '2026-05-01', DATE '2026-05-31'),
  ('PR04', '日焼け止め 夏本番',       'P006', DATE '2026-07-01', DATE '2026-08-31'),
  ('PR05', '美容液 発売記念',         'P003', DATE '2026-04-15', DATE '2026-05-15');

-- 月次目標。C007 は目標だけあって売上がない（LEFT JOIN の罠）
CREATE TABLE dojo.targets (
  customer_id   STRING NOT NULL,
  fiscal_month  DATE   NOT NULL,   -- 月初日
  target_amount INT64  NOT NULL
);
INSERT INTO dojo.targets VALUES
  ('C001', DATE '2026-06-01', 60000),
  ('C002', DATE '2026-06-01', 120000),
  ('C003', DATE '2026-06-01', 40000),
  ('C004', DATE '2026-06-01', 30000),
  ('C007', DATE '2026-06-01', 20000),
  ('C008', DATE '2026-06-01', 25000);

-- 在庫の日次スナップショット（最新 1 件を取る題材）
CREATE TABLE dojo.stock (
  store_id      STRING NOT NULL,
  product_id    STRING NOT NULL,
  snapshot_date DATE   NOT NULL,
  stock_qty     INT64  NOT NULL
);
INSERT INTO dojo.stock VALUES
  ('S03', 'P001', DATE '2026-06-28', 40),
  ('S03', 'P001', DATE '2026-06-29', 35),
  ('S03', 'P001', DATE '2026-06-30', 28),
  ('S03', 'P002', DATE '2026-06-28', 22),
  ('S03', 'P002', DATE '2026-06-29', 22),
  ('S03', 'P002', DATE '2026-06-30', 18),
  ('S07', 'P001', DATE '2026-06-28', 15),
  ('S07', 'P001', DATE '2026-06-29', 12),
  ('S07', 'P001', DATE '2026-06-30', 30),
  ('S01', 'P006', DATE '2026-06-28', 9),
  ('S01', 'P006', DATE '2026-06-29', 6),
  ('S01', 'P006', DATE '2026-06-30', 6);
