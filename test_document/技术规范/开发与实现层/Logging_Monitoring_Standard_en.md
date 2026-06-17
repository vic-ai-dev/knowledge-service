# Logging & Monitoring Standard

> Reference: Google SRE Practices, Alibaba Cloud SLS Best Practices, ELK Community Standards, Prometheus Best Practices

## 1. Overview

### 1.1 Purpose
Standardize logging and monitoring alert practices to ensure comprehensive observability coverage, supporting rapid fault localization, business metric monitoring, and capacity planning.

### 1.2 Scope
This standard applies to all internally developed systems' logging, metrics collection, and alert rule definitions within the Technology Development Department.

### 1.3 Terminology

| Term | Definition |
| --- | --- |
| Logging | Discrete event records |
| Metrics | Aggregatable numerical indicators |
| Tracing | Request-level trace tracking |
| Observability | Logging + Metrics + Tracing combined |
| Instrumentation | Embedding log/metric collection points in code |

---

## 2. Logging Standards

### 2.1 Log Level Definitions

| Level | Usage | Example | Handling |
| --- | --- | --- | --- |
| TRACE | Development debugging details | SQL parameters, loop intermediate values | Development only |
| DEBUG | Diagnostic information | Request params/results, state transitions | Off by default, on-demand |
| INFO | Key business events | Policy issuance, payment callback, task start/stop | Written to log files, long-term retention |
| WARN | Unexpected but recoverable | Retry triggered, rate limiting, config degradation | Written to files, triggers alert |
| ERROR | Feature unavailable / data error | DB connection failure, interface error, accounting imbalance | Immediate alert, on-call handling |
| FATAL | System crash | OOM, main thread exit | Immediate response, restart |

### 2.2 Log Format Standards

**Text Log Format:**

```
[%d{yyyy-MM-dd HH:mm:ss.SSS}] [%thread] [%-5level] [%logger{36}] [%X{traceId}] - %msg%n
```

**Example Output:**

```
[2024-06-15 10:30:15.123] [http-nio-8080-exec-1] [INFO ] [c.c.i.underwriting.PolicyService] [t-abc123] - Policy issued successfully, policyNo=P2024000001
```

**JSON Log Format (recommended for production):**

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

### 2.3 Key Instrumentation Points

| Domain | Event | Level | Required Fields |
| --- | --- | --- | --- |
| Underwriting | Proposal submitted | INFO | proposalNo, productCode, channelCode |
| Underwriting | Decision completed | INFO | proposalNo, decision, reason |
| Policy Issuance | Policy issued success | INFO | policyNo, premium, effectiveDate |
| Policy Issuance | Policy issued failure | ERROR | policyNo, errorCode, errorMessage |
| Claims | Claim reported | INFO | claimNo, policyNo, incidentType |
| Claims | Claim settled | INFO | claimNo, payoutAmount, closeReason |
| Payment | Payment request sent | INFO | paymentId, amount, channel |
| Payment | Payment callback received | INFO | paymentId, status, channelOrderNo |
| Payment | Reconciliation mismatch | ERROR | paymentId, systemAmount, channelAmount |
| Renewal | Renewal reminder sent | INFO | policyNo, remindDate, channel |
| Renewal | Renewal payment result | INFO | policyNo, result, failReason |
| Policy Servicing | Endorsement received | INFO | endorsementNo, changeType, policyNo |
| Policy Servicing | Endorsement applied | INFO | endorsementNo, status, effectiveDate |

### 2.4 Logging Governance Rules

- **No sensitive information** in logs: ID numbers, phone numbers, bank cards, passwords, tokens must be masked
- **No logging inside loops**: aggregate first, then log
- **No logging ERROR then rethrowing**: avoid duplicate logging
- **Exceptions must include full stack trace**: `log.error("msg", exception)`
- **Every log entry must include traceId**: for full trace correlation

### 2.5 Data Masking Rules

| Data Type | Masking Method | Example |
| --- | --- | --- |
| ID Number | Keep first 6, last 4 | 110101********1234 |
| Phone Number | Keep first 3, last 4 | 138****5678 |
| Bank Card | Keep first 4, last 4 | 6222********1234 |
| Password/Token | Full mask | ****** |
| Name | Keep surname | J*** |

---

## 3. Monitoring Standards

### 3.1 Four-Tier Monitoring

| Layer | Metrics | Goal |
| --- | --- | --- |
| Infrastructure | CPU, Memory, Disk, Network, GC | Resource levels, capacity planning |
| Application | QPS, RT, Error rate, Thread pool | Service quality (SLO) |
| Business | Issuance volume, Premium income, Payment success rate | Business health |
| UX | Page load time, API TTFB | User experience |

### 3.2 Core Metrics Definition

**RED Metrics (Rate / Errors / Duration):**

| Metric | Definition | Aggregation | Alert Threshold |
| --- | --- | --- | --- |
| Rate | Requests per second (QPS) | Sum | Exceeds 80% capacity |
| Errors | Error count/rate | Sum / Rate | Error rate exceeds 1% |
| Duration | Response time P50/P95/P99 | Histogram | P99 exceeds 1000ms |

**USE Metrics (Utilization / Saturation / Errors):**

| Metric | Definition | Applicable To |
| --- | --- | --- |
| Utilization | Resource utilization | CPU / Memory / Disk / Connection pool |
| Saturation | Queue length | Thread pool / Connection pool / Queue |
| Errors | Error count | All resources |

### 3.3 Business Monitoring Metrics

| Metric Name | Description | Aggregation | P1 Alert Threshold |
| --- | --- | --- | --- |
| policy_issued_total | Total policies issued | COUNT | Zero for 5 consecutive minutes |
| premium_total | Total premium income | SUM | 50% drop vs same time yesterday |
| payment_success_rate | Payment success rate | rate(success)/rate(total) | Below 99% |
| underwriting_completion_time | Underwriting completion time | HISTOGRAM | P99 exceeds 30s |
| claim_settlement_time | Claim settlement time | HISTOGRAM | P99 exceeds 72h |

### 3.4 Metrics Naming Convention

```
{namespace}_{component}_{metric_name}_{unit}

Examples:
insurance_underwriting_qps_total
insurance_payment_duration_seconds
insurance_core_db_connections_active
```

- Use underscore separators
- Unit at the end: `_seconds`, `_bytes`, `_total`
- All metrics include labels: `service`, `environment`, `instance`

---

## 4. Alert Rules

### 4.1 Alert Severity Levels

| Level | Definition | Response Time | Notification |
| --- | --- | --- | --- |
| P0 (Critical) | Core feature completely unavailable / financial loss | 5 minutes | Phone + SMS + IM |
| P1 (Severe) | Core feature impaired / widespread slowness | 15 minutes | SMS + IM |
| P2 (Warning) | Non-core feature abnormal / capacity warning | 1 hour | IM |
| P3 (Info) | Non-business anomaly / trend to watch | 24 hours | Email |

### 4.2 Alert Rule Template

```yaml
# PrometheusRule example
groups:
  - name: insurance.core.rules
    rules:
      # P0: Core service down
      - alert: CoreServiceDown
        expr: up{service="policy-service"} == 0
        for: 1m
        labels:
          severity: P0
        annotations:
          summary: "Policy service is down"
          description: "Instance {{ $labels.instance }} has been down for 1 minute"

      # P1: High error rate
      - alert: HighErrorRate
        expr: rate(http_requests_total{status=~"5.."}[5m]) / rate(http_requests_total[5m]) > 0.01
        for: 5m
        labels:
          severity: P1

      # P2: Payment success rate drop
      - alert: PaymentSuccessRateDrop
        expr: payment_success_rate < 0.99
        for: 10m
        labels:
          severity: P2

      # P3: Slow query increase
      - alert: SlowQueryIncrease
        expr: rate(mysql_slow_queries_total[15m]) > 10
        for: 15m
        labels:
          severity: P3
```

### 4.3 Alert Governance

- Do not create alert rules without thresholds
- Every alert must have a corresponding Runbook
- Weekly alert review to clean up ineffective rules
- Alert silences must have an expiry time; permanent silence is prohibited
- Alert notifications must be tied to the on-call schedule

---

## 5. Appendix

### 5.1 Reference Documents
- Google SRE Book
- Prometheus Best Practices
- OpenTelemetry Specification
- *Coding Standards* (Logging section)

### 5.2 Tool Stack

| Domain | Recommended Tools | Alternatives |
| --- | --- | --- |
| Log collection | Filebeat / Fluentd | Logstash |
| Log storage | Elasticsearch / Loki | ClickHouse |
| Log analysis | Kibana / Grafana Explore | — |
| Metrics collection | Prometheus / VictoriaMetrics | — |
| Metrics visualization | Grafana | — |
| Distributed tracing | Jaeger / Zipkin | SkyWalking |
| Alert management | AlertManager / Grafana Alerting | — |
| On-call scheduling | OnCall (PagerDuty) | — |

### 5.3 Log Keyword Alert Rules

| Keyword | Severity | Description |
| --- | --- | --- |
| OutOfMemoryError | P0 | OOM requires immediate response |
| Connection refused | P1 | Service connection failure |
| Deadlock | P1 | Deadlock causing service unavailability |
| Timeout | P2 | Timeout anomaly requires attention |
| Retry exhausted | P2 | Manual intervention needed |
| Circuit breaker opened | P2 | Circuit breaker tripped |
| Degraded | P3 | Service degradation, log for record |
