# 数据架构规范

## 1. 概述

本文档定义保险公司数据架构的总体规范，包括数据分层、数据建模、数据存储选型、数据流转、数据治理等内容。参考阿里巴巴数据中台方法论、蚂蚁集团数据治理实践。

## 2. 数据架构原则

1. **统一标准**：全域数据遵循统一命名、类型、编码规范
2. **分层解耦**：数据按 ODS → DWD → DWS → ADS 分层，每一层职责明确
3. **数据闭环**：每条数据链路具备端到端可追溯能力
4. **就近计算**：尽量将计算下推到存储层或离数据最近的位置
5. **最小权限**：数据访问遵循按需授权、最小够用原则

## 3. 数据分层规范

| 层级 | 英文 | 职责 | 存储 | 保留周期 |
|------|------|------|------|---------|
| ODS | Operational Data Store | 源系统数据全量接入 | HDFS / Kafka | 30天 |
| DWD | Data Warehouse Detail | 清洗后明细数据，业务事实+维度 | Hive / Iceberg | 按监管要求 |
| DWS | Data Warehouse Summary | 轻度汇总，业务主题宽表 | ClickHouse | 按监管要求 |
| ADS | Application Data Store | 应用级数据集市 | MySQL / ClickHouse | 按业务需求 |
| DIM | Dimension | 公共维度数据 | MySQL / Redis | 长期保留 |
| STG | Staging | 临时中间结果 | HDFS / OSS | T+7后清理 |

## 4. 数据模型设计规范

### 4.1 模型分层设计

**ODS 层**
- 表结构 1:1 映射源系统
- 增量/全量两种同步方式
- 保留原始数据，不做清洗或合并

**DWD 层**
- 遵循 3NF 或 Data Vault 模型
- 字段进行标准化（统一编码、日期格式）
- 保持明细粒度，不做预聚合

**DWS 层**
- 按主题组织（承保主题、理赔主题、客户主题）
- 轻度聚合，减少查询扫描量
- 宽表设计，常用维度退化到事实表

**ADS 层**
- 面向具体应用场景（监管报表、经营分析、风控模型）
- 可根据性能需要做适度冗余
- 大宽表或星型模型

### 4.2 核心数据模型举例

**保单事实表 DWD（承保主题）**
```sql
CREATE TABLE dwd_policy_fact (
    policy_id         STRING COMMENT '保单号',
    application_id    STRING COMMENT '投保单号',
    product_code      STRING COMMENT '产品编码',
    channel_code      STRING COMMENT '渠道编码',
    applicant_id      STRING COMMENT '投保人ID',
    insured_id        STRING COMMENT '被保人ID',
    premium_amount    DECIMAL(18,2) COMMENT '保费金额',
    sum_insured       DECIMAL(18,2) COMMENT '保额',
    policy_status     STRING COMMENT '保单状态',
    effective_date    DATE COMMENT '生效日期',
    expire_date       DATE COMMENT '到期日期',
    uw_result         STRING COMMENT '核保结论',
    issue_datetime    TIMESTAMP COMMENT '出单时间',
    etl_time          TIMESTAMP COMMENT 'ETL时间'
) PARTITIONED BY (dt STRING)
  STORED AS PARQUET;
```

## 5. 数据存储选型

| 数据类型 | 存储引擎 | 适用场景 |
|---------|---------|---------|
| 在线事务(OLTP) | MySQL 8.0 / PolarDB | 核心业务数据 |
| 缓存 | Redis Cluster | 热数据、会话、计数器 |
| 搜索引擎 | Elasticsearch | 保单全文检索、日志 |
| 时序数据 | Prometheus / VictoriaMetrics | 监控指标 |
| 离线分析 | Spark + Hive/Iceberg | ETL、数仓 |
| 实时分析 | Flink + ClickHouse | 实时报表、大屏 |
| 对象存储 | MinIO / OSS / S3 | 影像、文件 |
| 消息队列 | RocketMQ / Kafka | 异步事件、流处理 |

## 6. 数据流转规范

### 6.1 实时同步链路
```
MySQL(Binlog) → Canal → Kafka → Flink → ClickHouse / Redis
```
- 适用场景：保单状态实时更新、实时风控、实时大屏
- 一致性要求：至少一次投递，业务侧做幂等

### 6.2 离线同步链路
```
MySQL(Sqoop/DataX) → HDFS → Hive(ODS) → Spark(DWD/DWS) → ClickHouse(ADS)
```
- 适用场景：监管报送、经营分析、精算定价

## 7. 数据治理规范

| 治理领域 | 规范要求 | 工具 |
|---------|---------|------|
| 数据质量 | 非空率、唯一性、格式合规自动化监控 | Great Expectations / Deequ |
| 数据血缘 | 字段级血缘自动追踪 | Atlas / DataHub |
| 元数据管理 | 表结构、字段注释、变更历史 | 自研元数据平台 |
| 数据安全 | 敏感数据自动发现 + 脱敏 + 加密 | 数据安全平台 |
| 生命周期 | 冷热数据自动分层，过期自动清理 | 生命周期管理策略 |

## 8. 监管报送数据规范

- 监管报送数据单独从 ODS/DWD 层加工，不经过 ADS 层
- 所有报送数据保留至少 7 年
- 每次报送前需要核对产出数据与源系统数据的一致性
- 报送接口只增不删，历史报送接口需保留兼容
