# 日志与监控规范

> 参考：Google SRE 实践、阿里云 SLS 最佳实践、ELK 社区规范、Prometheus 最佳实践

## 1. 概述

### 1.1 目的
统一日志记录和监控告警标准，确保系统可观测性（Observability）覆盖全面，支持故障快速定位、业务指标监控和容量规划。

### 1.2 适用范围
本规范适用于技术开发部所有自研系统的日志记录、Metrics 采集和告警规则定义。

### 1.3 术语定义

| 术语 | 定义 |
| --- | --- |
| Logging | 离散的事件记录 |
| Metrics | 可聚合的数值指标 |
| Tracing | 请求级别的链路追踪 |
| 可观测性 | Logging + Metrics + Tracing 三者结合 |
| 埋点 | 在代码中嵌入日志/指标采集点的行为 |

---

## 2. 日志规范

### 2.1 日志级别定义

| 级别 | 使用场景 | 示例 | 处理方式 |
| --- | --- | --- | --- |
| TRACE | 开发调试细节 | SQL 参数、循环中间值 | 仅开发环境开启 |
| DEBUG | 诊断问题信息 | 请求入参/出参、状态变迁 | 默认关闭，按需开启 |
| INFO | 关键业务事件 | 出单成功、支付回调、任务启停 | 写入日志文件，长期保存 |
| WARN | 非预期但可恢复 | 重试触发、限流开始、配置降级 | 写入日志文件，触发告警 |
| ERROR | 功能不可用/数据错误 | 数据库连接失败、接口异常、账务不平 | 立即告警，值班处理 |
| FATAL | 系统级崩溃 | 内存溢出、主线程退出 | 立刻响应，重启恢复 |

### 2.2 日志格式标准

**文本日志格式：**
```
[%d{yyyy-MM-dd HH:mm:ss.SSS}] [%thread] [%-5level] [%logger{36}] [%X{traceId}] - %msg%n
```

**示例输出：**
```
[2024-06-15 10:30:15.123] [http-nio-8080-exec-1] [INFO ] [c.c.i.underwriting.PolicyService] [t-abc123] - Policy issued successfully, policyNo=P2024000001
```

**JSON 日志格式（推荐生产环境）：**
```json
{
  "timestamp": "2024-06-15T10:30:15.123+08:00",
  "level": "INFO",
  "thread": "http-nio-8080-exec-1",
  "logger": "c.c.i.underwriting.PolicyService",
  "traceId": "t-abc123",
  "message": "Policy issued successfully",
  "context": {
    "policyNo": "P2024000001",
    "amount": 1000.00,
    "duration": 152
  }
}
```

### 2.3 关键埋点清单

| 业务域 | 埋点事件 | 日志级别 | 必填字段 |
| --- | --- | --- | --- |
| 核保 | 投保单提交 | INFO | proposalNo, productCode, channelCode |
| 核保 | 核保决策完成 | INFO | proposalNo, decision, reason |
| 出单 | 保单签发成功 | INFO | policyNo, premium, effectiveDate |
| 出单 | 保单签发失败 | ERROR | policyNo, errorCode, errorMessage |
| 理赔 | 理赔报案 | INFO | claimNo, policyNo, incidentType |
| 理赔 | 理赔结案 | INFO | claimNo, payoutAmount, closeReason |
| 支付 | 支付请求发出 | INFO | paymentId, amount, channel |
| 支付 | 支付回调收到 | INFO | paymentId, status, channelOrderNo |
| 支付 | 支付对账不平 | ERROR | paymentId, systemAmount, channelAmount |
| 续期 | 续期提醒发送 | INFO | policyNo, remindDate, channel |
| 续期 | 续期扣费结果 | INFO | policyNo, result, failReason |
| 保全 | 保全受理 | INFO | endorsementNo, changeType, policyNo |
| 保全 | 保全生效 | INFO | endorsementNo, status, effectiveDate |

### 2.4 日志治理规则

- **禁止打印敏感信息**：身份证号、手机号、银行卡号、密码、Token 必须脱敏后记录
- **禁止在循环中打印日志**：使用计数器汇总后打印
- **禁止在 ERROR 级别记录后又抛异常**：避免重复日志
- **异常必须记录完整堆栈**：`log.error("msg", exception)`
- **每条日志必须包含 traceId**：用于全链路关联

### 2.5 脱敏规则

| 数据类型 | 脱敏方式 | 示例 |
| --- | --- | --- |
| 身份证号 | 保留前6后4 | 110101********1234 |
| 手机号 | 保留前3后4 | 138****5678 |
| 银行卡号 | 保留前4后4 | 6222********1234 |
| 密码/Token | 全部遮盖 | ****** |
| 姓名 | 保留姓氏 | 张* |

---

## 3. 监控规范

### 3.1 监控四层体系

| 层 | 指标 | 目标 |
| --- | --- | --- |
| 基础设施层 | CPU、内存、磁盘、网络、GC | 资源水位，容量规划 |
| 应用层 | QPS、RT、错误率、线程池状态 | 服务质量（SLO） |
| 业务层 | 出单量、保费收入、支付成功率 | 业务健康度 |
| 用户体验层 | 页面加载时间、API 首字节时间 | 用户体验 |

### 3.2 核心指标定义

**RED 指标（Rate / Errors / Duration）：**

| 指标 | 定义 | 聚合方式 | 告警阈值 |
| --- | --- | --- | --- |
| Rate | 每秒请求数（QPS） | Sum | 超过容量的 80% |
| Errors | 错误请求数/率 | Sum / Rate | 错误率超过 1% |
| Duration | 响应时间 P50/P95/P99 | Histogram | P99 超过 1000ms |

**USE 指标（Utilization / Saturation / Errors）：**

| 指标 | 定义 | 适用对象 |
| --- | --- | --- |
| Utilization | 资源利用率 | CPU / 内存 / 磁盘 / 连接池 |
| Saturation | 资源饱和度（排队长度） | 线程池 / 连接池 / 队列 |
| Errors | 错误计数 | 所有资源 |

### 3.3 业务监控指标

| 指标名称 | 指标说明 | 统计口径 | P1 告警阈值 |
| --- | --- | --- | --- |
| policy_issued_total | 保单签发总数 | COUNT | 连续 5 分钟为 0 |
| premium_total | 保费收入总额 | SUM | 较昨日同期下降 50% |
| payment_success_rate | 支付成功率 | rate(success)/rate(total) | 低于 99% |
| underwriting_completion_time | 核保完成耗时 | HISTOGRAM | P99 超过 30s |
| claim_settlement_time | 理赔结案耗时 | HISTOGRAM | P99 超过 72h |

### 3.4 Metrics 命名规范

```
{namespace}_{component}_{metric_name}_{unit}

示例：
insurance_underwriting_qps_total
insurance_payment_duration_seconds
insurance_core_db_connections_active
```

- 使用下划线分隔
- 单位放在最后：`_seconds`、`_bytes`、`_total`
- 所有指标包含标签（labels）：`service`、`environment`、`instance`

---

## 4. 告警规则

### 4.1 告警分级

| 级别 | 定义 | 响应时间 | 通知方式 |
| --- | --- | --- | --- |
| P0（紧急） | 核心功能完全不可用/资损 | 5 分钟内响应 | 电话 + 短信 + 即时消息 |
| P1（严重） | 核心功能受损/大面积慢 | 15 分钟内响应 | 短信 + 即时消息 |
| P2（警告） | 非核心功能异常/容量预警 | 1 小时内响应 | 即时消息 |
| P3（提醒） | 非业务异常/需关注趋势 | 24 小时内响应 | 邮件 |

### 4.2 告警规则模板

```yaml
groups:
  - name: insurance.core.rules
    rules:
      # P0: 核心服务宕机
      - alert: CoreServiceDown
        expr: up{service="policy-service"} == 0
        for: 1m
        labels:
          severity: P0
        annotations:
          summary: "Policy service is down"
          description: "Instance {{ $labels.instance }} has been down for 1 minute"

      # P1: 错误率过高
      - alert: HighErrorRate
        expr: rate(http_requests_total{status=~"5.."}[5m]) / rate(http_requests_total[5m]) > 0.01
        for: 5m
        labels:
          severity: P1

      # P2: 支付成功率下降
      - alert: PaymentSuccessRateDrop
        expr: payment_success_rate < 0.99
        for: 10m
        labels:
          severity: P2

      # P3: 慢查询增加
      - alert: SlowQueryIncrease
        expr: rate(mysql_slow_queries_total[15m]) > 10
        for: 15m
        labels:
          severity: P3
```

### 4.3 告警治理

- 禁止设置无阈值的告警规则
- 每个告警必须有明确的排查文档（Runbook）
- 每周进行告警回顾，清理无效规则
- 告警静默必须有截止时间，禁止永久静默
- 告警通知必须关联到值班排班表

---

## 5. 附录

### 5.1 参考文档
- Google SRE Book
- Prometheus Best Practices
- OpenTelemetry Specification
- 《编码规范》日志相关章节

### 5.2 工具栈

| 领域 | 推荐工具 | 备选 |
| --- | --- | --- |
| 日志采集 | Filebeat / Fluentd | Logstash |
| 日志存储 | Elasticsearch / Loki | ClickHouse |
| 日志分析 | Kibana / Grafana Explore | --- |
| Metrics 采集 | Prometheus / VictoriaMetrics | --- |
| Metrics 展示 | Grafana | --- |
| 链路追踪 | Jaeger / Zipkin | SkyWalking |
| 告警管理 | AlertManager / Grafana Alerting | --- |
| 值班排班 | OnCall（PagerDuty/云杉） | --- |

### 5.3 日志关键字告警规则

| 关键字 | 级别 | 说明 |
| --- | --- | --- |
| OutOfMemoryError | P0 | OOM 立即响应 |
| Connection refused | P1 | 服务连接失败 |
| Deadlock | P1 | 死锁导致服务不可用 |
| Timeout | P2 | 超时异常需关注 |
| Retry exhausted | P2 | 重试耗尽需人工介入 |
| Circuit breaker opened | P2 | 熔断器打开 |
| Degraded | P3 | 服务降级需记录 |
