/*
 Navicat Premium Dump SQL

 Source Server         : postgre
 Source Server Type    : PostgreSQL
 Source Server Version : 160008 (160008)
 Source Host           : localhost:5432
 Source Catalog        : label
 Source Schema         : public

 Target Server Type    : PostgreSQL
 Target Server Version : 160008 (160008)
 File Encoding         : 65001

 Date: 17/05/2025 20:20:10
*/



-- ----------------------------
-- Table structure for dataset
-- ----------------------------
DROP TABLE IF EXISTS "public"."dataset";
CREATE TABLE "public"."dataset" (
  "dataset_id" int4 NOT NULL DEFAULT nextval('dataset_seq'::regclass),
  "name" varchar(255) COLLATE "pg_catalog"."default",
  "set_dess" text COLLATE "pg_catalog"."default",
  "thumb_url" path,
  "num" int4,
  "contact" varchar(255) COLLATE "pg_catalog"."default",
  "email" varchar(255) COLLATE "pg_catalog"."default",
  "sorts" varchar COLLATE "pg_catalog"."default",
  "user_id" int4,
  "goal" int4,
  "class" varchar(255) COLLATE "pg_catalog"."default",
  "task_name" varchar(255) COLLATE "pg_catalog"."default"
)
;

-- ----------------------------
-- Table structure for dataset_store
-- ----------------------------
DROP TABLE IF EXISTS "public"."dataset_store";
CREATE TABLE "public"."dataset_store" (
  "sample_id" int4 NOT NULL DEFAULT nextval('datasetstore_seq'::regclass),
  "sample_name" varchar(255) COLLATE "pg_catalog"."default",
  "task_id" int4,
  "is_public" int4
)
;
COMMENT ON COLUMN "public"."dataset_store"."is_public" IS '1公开，0不公开';

-- ----------------------------
-- Table structure for file
-- ----------------------------
DROP TABLE IF EXISTS "public"."file";
CREATE TABLE "public"."file" (
  "file_id" int4 NOT NULL DEFAULT nextval('fileid_seq'::regclass),
  "file_name" varchar(255) COLLATE "pg_catalog"."default",
  "update_time" varchar(255) COLLATE "pg_catalog"."default",
  "status" int4,
  "size" varchar(255) COLLATE "pg_catalog"."default",
  "user_id" int4
)
;
COMMENT ON COLUMN "public"."file"."status" IS '1 已发布 ，0 未发布';

-- ----------------------------
-- Table structure for mark
-- ----------------------------
DROP TABLE IF EXISTS "public"."mark";
CREATE TABLE "public"."mark" (
  "id" int4 NOT NULL DEFAULT nextval('mark_seq'::regclass),
  "task_id" int4,
  "user_id" int4,
  "type_id" int4,
  "geom" json,
  "status" int4
)
;
COMMENT ON COLUMN "public"."mark"."task_id" IS '任务ID';
COMMENT ON COLUMN "public"."mark"."user_id" IS '用户ID';
COMMENT ON COLUMN "public"."mark"."type_id" IS '类型ID';
COMMENT ON COLUMN "public"."mark"."geom" IS '标注信息，是标注区域的坐标字符串，长度过长不限定长度';
COMMENT ON COLUMN "public"."mark"."status" IS '0 未通过，1 通过';

-- ----------------------------
-- Table structure for model
-- ----------------------------
DROP TABLE IF EXISTS "public"."model";
CREATE TABLE "public"."model" (
  "model_id" int8 NOT NULL DEFAULT nextval('model_seq'::regclass),
  "model_name" text COLLATE "pg_catalog"."default" NOT NULL,
  "user_id" int4 NOT NULL,
  "model_des" varchar(255) COLLATE "pg_catalog"."default",
  "path" text COLLATE "pg_catalog"."default" NOT NULL,
  "input_num" int4 NOT NULL,
  "output_num" int4 NOT NULL,
  "status" int4 NOT NULL,
  "model_type" varchar(255) COLLATE "pg_catalog"."default" NOT NULL,
  "task_type" text COLLATE "pg_catalog"."default" NOT NULL
)
;
COMMENT ON COLUMN "public"."model"."status" IS '区分系统模型(.pth)和用户上传模型(.pt)';

-- ----------------------------
-- Table structure for role
-- ----------------------------
DROP TABLE IF EXISTS "public"."role";
CREATE TABLE "public"."role" (
  "id" int4 NOT NULL,
  "rolename" varchar(80) COLLATE "pg_catalog"."default",
  "rolecode" int4 NOT NULL
)
;

-- ----------------------------
-- Table structure for sample_img
-- ----------------------------
DROP TABLE IF EXISTS "public"."sample_img";
CREATE TABLE "public"."sample_img" (
  "img_id" int4 NOT NULL DEFAULT nextval('sampleimg_seq'::regclass),
  "sample_id" int4,
  "img_src" varchar(255) COLLATE "pg_catalog"."default",
  "type_id" int4
)
;

-- ----------------------------
-- Table structure for server
-- ----------------------------
DROP TABLE IF EXISTS "public"."server";
CREATE TABLE "public"."server" (
  "ser_id" int4 NOT NULL DEFAULT nextval('serverid_seq'::regclass),
  "ser_name" varchar(255) COLLATE "pg_catalog"."default" NOT NULL,
  "ser_desc" varchar(255) COLLATE "pg_catalog"."default",
  "ser_year" varchar(255) COLLATE "pg_catalog"."default",
  "publisher" varchar(255) COLLATE "pg_catalog"."default",
  "publish_time" varchar(100) COLLATE "pg_catalog"."default",
  "publish_url" varchar(255) COLLATE "pg_catalog"."default",
  "set_name" varchar(32) COLLATE "pg_catalog"."default",
  "user_id" int4
)
;
COMMENT ON COLUMN "public"."server"."publish_time" IS '发布日期';
COMMENT ON COLUMN "public"."server"."publish_url" IS '发布地址';


-- ----------------------------
-- Table structure for sys_user
-- ----------------------------
DROP TABLE IF EXISTS "public"."sys_user";
CREATE TABLE "public"."sys_user" (
  "user_id" int4 NOT NULL DEFAULT nextval('sys_user_id_sequence'::regclass),
  "username" varchar(255) COLLATE "pg_catalog"."default" NOT NULL,
  "user_password" varchar(255) COLLATE "pg_catalog"."default",
  "is_admin" int4 NOT NULL,
  "finished_num" int4,
  "unfinished_num" int4,
  "team_id" int4,
  "score" int8
)
;
COMMENT ON COLUMN "public"."sys_user"."user_id" IS '用户标识符';

-- ----------------------------
-- Table structure for task
-- ----------------------------
DROP TABLE IF EXISTS "public"."task";
CREATE TABLE "public"."task" (
  "task_id" int4 NOT NULL DEFAULT nextval('taskid_seq'::regclass),
  "date_range" varchar(255) COLLATE "pg_catalog"."default",
  "task_name" varchar(255) COLLATE "pg_catalog"."default",
  "task_type" varchar(32) COLLATE "pg_catalog"."default",
  "map_server" varchar(255) COLLATE "pg_catalog"."default",
  "status" int4,
  "mark_id" text COLLATE "pg_catalog"."default",
  "audit_feedback" varchar(255) COLLATE "pg_catalog"."default",
  "task_class" int4,
  "user_id" int4,
  "score" int4,
  "submitter_id" int4
)
;
COMMENT ON COLUMN "public"."task"."task_id" IS '任务ID';
COMMENT ON COLUMN "public"."task"."date_range" IS '日期范围';
COMMENT ON COLUMN "public"."task"."task_name" IS '任务名';
COMMENT ON COLUMN "public"."task"."task_type" IS '类型';
COMMENT ON COLUMN "public"."task"."map_server" IS '地图服务';
COMMENT ON COLUMN "public"."task"."status" IS '状态,0 审核中，1 审核通过，2 审核未通过，3 未提交';
COMMENT ON COLUMN "public"."task"."mark_id" IS '标记ID';
COMMENT ON COLUMN "public"."task"."audit_feedback" IS '审核反馈';
COMMENT ON COLUMN "public"."task"."task_class" IS '0为团队任务；1为非团队任务';

-- ----------------------------
-- Table structure for task_accepted
-- ----------------------------
DROP TABLE IF EXISTS "public"."task_accepted";
CREATE TABLE "public"."task_accepted" (
  "id" int4 DEFAULT nextval('taskaccept_seq'::regclass),
  "task_id" int4 NOT NULL,
  "username" varchar(255) COLLATE "pg_catalog"."default",
  "type_arr" varchar(255) COLLATE "pg_catalog"."default"
)
;
COMMENT ON COLUMN "public"."task_accepted"."id" IS 'id';
COMMENT ON COLUMN "public"."task_accepted"."task_id" IS '任务ID';
COMMENT ON COLUMN "public"."task_accepted"."username" IS '用户名';
COMMENT ON COLUMN "public"."task_accepted"."type_arr" IS '类型';
COMMENT ON TABLE "public"."task_accepted" IS '已接受任务';

-- ----------------------------
-- Table structure for team_table
-- ----------------------------
DROP TABLE IF EXISTS "public"."team_table";
CREATE TABLE "public"."team_table" (
  "team_id" int4 NOT NULL DEFAULT nextval('team_seq'::regclass),
  "name" varchar(255) COLLATE "pg_catalog"."default",
  "code" varchar(255) COLLATE "pg_catalog"."default",
  "score" int8
)
;

-- ----------------------------
-- Table structure for type
-- ----------------------------
DROP TABLE IF EXISTS "public"."type";
CREATE TABLE "public"."type" (
  "type_id" int4 NOT NULL DEFAULT nextval('typeid_seq'::regclass),
  "type_name" varchar(255) COLLATE "pg_catalog"."default",
  "type_color" varchar(255) COLLATE "pg_catalog"."default",
  "user_id" int4
)
;