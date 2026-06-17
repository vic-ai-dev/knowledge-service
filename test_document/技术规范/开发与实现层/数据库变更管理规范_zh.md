# 数据库变更管理规范

> 参考：阿里云 DMS 变更规范、美团数据库变更实践、Google 数据库 SRE 实践

## 1. 概述

### 1.1 目的
规范数据库结构变更的全流程管理，确保 DDL/DML 变更经过充分评审、可回滚、可审计，降低因数据库变更导致的生产事故风险。

### 1.2 适用范围
适用于所有与数据库相关的结构变更：表结构变更（DDL）、索引变更、数据迁移脚本、配置数据变更（DML）等。

### 1.3 术语定义

| 术语 | 定义 |
| --- | --- |
| DDL | 数据定义语言（CREATE/ALTER/DROP TABLE 等） |
| DML | 数据操作语言（INSERT/UPDATE/DELETE） |
| Online DDL | 在线 DDL 工具（如 gh-ost / pt-online-schema-change） |
| 回滚脚本 | 用于撤销变更的反向 SQL 脚本 |
| 数据迁移 | 数据表拆分 / 字段类型变更等需要做数据转换的场景 |

---

## 2. DDL 审批流程

### 2.1 变更分级

| 级别 | 定义 | 审批人 | 执行窗口 |
| --- | --- | --- | --- |
| L1：低风险 | 新增字段（可空/有默认值）、新增索引、新增普通表 | 技术负责人（Leader） | 工作时间内 |
| L2：中风险 | 修改字段类型/长度、新增 NOT NULL 字段、新增唯一索引 | 技术负责人 + 架构师 | 预发布窗口 |
| L3：高风险 | 删除字段/表/索引、修改主键、大表结构变更、分库分表 | 架构评审委员会 | 变更窗口（小黑窗） |

### 2.2 审批流程

```
开发者提交 > Leader 初审 > (L2/L3) 架构评审 > DBA 复审 > 排期执行
```

### 2.3 审批要求

- 所有 DDL 必须通过工单系统（如阿里云 DMS / Yearning / Archery）提交
- 每个 DDL 工单必须包含：
  - 变更目的与背景（关联需求编号）
  - 完整的 DDL 语句（含 IF NOT EXISTS / IF EXISTS）
  - 回滚脚本（反向 SQL）
  - 影响行数预估（对大表尤其重要）
  - Online DDL 工具使用说明（如适用）
- 大表（超过 1000 万行）DDL 必须使用 Online DDL 工具

---

## 3. DDL 变更规范

### 3.1 新增表

```sql
CREATE TABLE IF NOT EXISTS t_policy_endorsement (
    id             BIGINT       NOT NULL COMMENT 'Primary key ID',
    policy_no      VARCHAR(20)  NOT NULL COMMENT 'Policy number',
    endorsement_no VARCHAR(20)  NOT NULL COMMENT 'Endorsement number',
    change_type    TINYINT      NOT NULL COMMENT 'Change type: 1-Info 2-Reduction 3-Increase',
    old_value      JSON         NULL     COMMENT 'Value before change',
    new_value      JSON         NULL     COMMENT 'Value after change',
    status         TINYINT      NOT NULL DEFAULT 0 COMMENT 'Status: 0-Pending 1-Applied 2-Reversed',
    create_time    DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3) COMMENT 'Creation time',
    update_time    DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3) COMMENT 'Update time',
    deleted        TINYINT      NOT NULL DEFAULT 0 COMMENT 'Soft delete',
    PRIMARY KEY (id),
    INDEX idx_policy_no (policy_no),
    INDEX idx_create_time (create_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Policy endorsement table';
```

### 3.2 修改表结构

```sql
-- New column (low risk)
ALTER TABLE t_policy_info
    ADD COLUMN channel_code VARCHAR(10) NULL COMMENT 'Channel code' AFTER product_code;

-- Modify column (medium risk, requires Online DDL)
ALTER TABLE t_policy_info
    MODIFY COLUMN premium DECIMAL(18,4) NOT NULL COMMENT 'Premium amount';

-- New index (low risk)
ALTER TABLE t_policy_info
    ADD INDEX idx_channel_status (channel_code, status);
```

### 3.3 回滚脚本要求

每个 DDL 变更必须附带回滚脚本，回滚脚本在变更执行后保留至少 30 天。

```sql
-- Forward
ALTER TABLE t_policy_info ADD COLUMN channel_code VARCHAR(10) NULL;

-- Rollback
ALTER TABLE t_policy_info DROP COLUMN channel_code;
```

```sql
-- Forward: Change VARCHAR to JSON
ALTER TABLE t_policy_info MODIFY COLUMN extra_info JSON NULL;

-- Rollback: Convert JSON back to VARCHAR (note data loss risk)
ALTER TABLE t_policy_info MODIFY COLUMN extra_info VARCHAR(500) NULL;
```

---

## 4. 数据迁移方案

### 4.1 迁移类型

| 迁移类型 | 适用场景 | 工具 |
| --- | --- | --- |
| 逻辑迁移 | 字段拆分、数据清洗、表合并 | SQL 脚本 + 应用双写 |
| 物理迁移 | 分库分表、换库 | DataX / Canal + 双写 |
| 全量+增量 | 不停机迁移 | Binlog 订阅 + 双写校验 |

### 4.2 迁移模板

**迁移背景**：[关联需求/问题描述]

**迁移范围**：
- 源表/源库：
- 目标表/目标库：
- 影响行数：
- 条件过滤：

**迁移步骤**：
1. 预检查（数据量、空值率、主键冲突）
2. 备份源数据
3. 执行数据转换
4. 校验目标数据（行数对比+抽样校验）
5. 切换读写流量

**回滚方案**：[详述回滚步骤和数据恢复方式]

**应急预案**：[出现问题时的处置流程]

### 4.3 双写迁移规范

| 阶段 | 操作 | 验证方式 |
| --- | --- | --- |
| 开启双写 | 应用层同时对旧表和新表写入 | 日志确认双写无异常 |
| 历史数据迁移 | 批处理脚本迁移历史数据 | 行数对比 + 抽样校验 |
| 数据校验 | 逐行对比新旧表数据 | 不一致自动告警并修正 |
| 流量切换 | 逐步将读流量切换到新表 | 观察 3-7 天 |
| 旧表下线 | 清理旧表代码引用和数据库对象 | 观察期无问题后操作 |

---

## 5. 变更执行规范

### 5.1 执行前置检查

- [ ] 已获取 DBA 审批
- [ ] 已准备回滚脚本
- [ ] 已评估影响行数，大表变更使用 Online DDL
- [ ] 已通知相关开发/运维人员
- [ ] 已备份受影响表（mysqldump 或快照）

### 5.2 执行时间

- L1 变更：工作日 9:00-17:00
- L2 变更：预发布窗口（如每周二、四 14:00-16:00）
- L3 变更：小黑窗（如每周四 22:00-24:00）

### 5.3 执行后验证

- [ ] 监控慢查询是否异常增加
- [ ] 检查应用错误日志
- [ ] 验证核心业务流程（出单/理赔/保全）
- [ ] 检查主从同步延迟
- [ ] 回滚脚本存档

---

## 6. 附录

### 6.1 参考文档
- 《编码规范（数据库对象命名部分）》
- gh-ost / pt-osc 使用手册
- MySQL 官方 Online DDL 文档

### 6.2 工具
- Online DDL：gh-ost（推荐） / pt-online-schema-change
- DDL 审批：Archery / Yearning / 阿里云 DMS
- 数据迁移：DataX / Canal / Flink CDC
- 数据校验：pt-table-checksum

### 6.3 DDL 工单模板
见 `DDL工单模板.md`
