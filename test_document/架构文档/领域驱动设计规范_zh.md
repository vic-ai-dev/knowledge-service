# 领域驱动设计规范

## 1. 概述

本文档定义保险技术平台中应用领域驱动设计(DDD)的实践规范，包括战略设计和战术设计两个层次的指导原则。参考 Eric Evans 原著及蚂蚁集团、美团的 DDD 实践经验。

## 2. 战略设计

### 2.1 统一语言

所有项目成员使用统一语言沟通，词汇表存储在项目 Wiki 中。常见保险领域词汇示例：

| 术语 | 含义 | 英文 |
|------|------|------|
| 投保单 | 客户提交的投保申请（未生效） | Application |
| 保单 | 已生效的保险合同 | Policy |
| 保全 | 保单生效后的变更操作 | Endorsement / Servicing |
| 核保 | 风险评估决策过程 | Underwriting |
| 理赔 | 保险事故处理过程 | Claims |
| 保费 | 投保人缴纳的费用 | Premium |
| 保额 | 保险金额 | Sum Insured |
| 免赔额 | 自付部分 | Deductible |

### 2.2 限界上下文

保险核心领域上下文划分：

```
┌─────────────────────────────────────────────────────┐
│                  核心域 Core Domain                    │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────┐ │
│  │ 承保管理 │ │ 保单管理 │ │ 理赔管理 │ │ 产品管理│ │
│  │UW Context│ │Policy Ctx│ │Claims Ctx│ │Prod Ctx│ │
│  └──────────┘ └──────────┘ └──────────┘ └────────┘ │
├─────────────────────────────────────────────────────┤
│                 支撑域 Supporting Domain              │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐             │
│  │ 渠道管理 │ │ 收付费   │ │ 再保管理 │             │
│  │Chnl Ctx │ │Paymt Ctx│ │Reins Ctx│             │
│  └──────────┘ └──────────┘ └──────────┘             │
├─────────────────────────────────────────────────────┤
│                 通用域 Generic Domain                 │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐             │
│  │ 通知服务 │ │ 认证授权 │ │ 审计日志 │             │
│  └──────────┘ └──────────┘ └──────────┘             │
└─────────────────────────────────────────────────────┘
```

### 2.3 上下文映射

| 关系 | 模式 | 示例 |
|------|------|------|
| 合作关系 | Partnership | 承保上下文 ↔ 收付上下文 |
| 共享内核 | Shared Kernel | 保单 ↔ 客户共享客户模型 |
| 客户-供应商 | Customer-Supplier | 产品上下文 → 承保上下文 |
| 分离方式 | Separate Ways | 承保 vs 理赔，各自独立发版 |
| 防腐层 | Anti-Corruption Layer | 对接核心系统遗留系统时引入 |

## 3. 战术设计

### 3.1 聚合与聚合根

| 上下文 | 聚合根 | 实体 | 值对象 |
|--------|--------|------|--------|
| 承保 | Application | ApplicationItem, UnderwritingRecord | ApplicantInfo, RiskEvaluation |
| 保单 | Policy | PolicyInsured, PolicyBeneficiary, PolicyCoverage | PremiumAmount, CoveragePeriod |
| 理赔 | Claim | ClaimItem, AssessmentResult, PaymentRecord | DamageAssessment, SettlementAmount |
| 产品 | Product | ProductClause, ProductCoverage, RateTable | RateFactor, CommissionRule |
| 收付 | PaymentOrder | PaymentRecord, ReconciliationEntry | PaymentMethod, BankAccount |

### 3.2 聚合设计原则
1. 聚合内保证最终一致性，聚合间通过事件驱动
2. 跨聚合引用使用 ID，不直接持有对象引用
3. 事务边界不超出单个聚合
4. 一次请求最多修改一个聚合
5. 聚合大小控制在 1 次 DB 事务可覆盖的范围

### 3.3 仓储模式

每个聚合根对应一个 Repository 接口：

```java
public interface PolicyRepository {
    Policy findById(PolicyId id);
    void save(Policy policy);
    void delete(PolicyId id);
    // 领域查询方法
    Page<Policy> findByInsured(InsuredId insuredId, Pageable pageable);
}
```

### 3.4 领域事件

```java
// 事件定义
public class PolicyIssuedEvent implements DomainEvent {
    private final PolicyId policyId;
    private final Instant occurredOn;
    // ...
}

// 发布（在聚合根方法中）
public class Policy extends AggregateRoot {
    public void issue() {
        // ... 业务逻辑
        this.addDomainEvent(new PolicyIssuedEvent(this.id, Instant.now()));
    }
}
```

| 关键领域事件 | 触发场景 | 订阅者 |
|-------------|---------|--------|
| PolicyIssuedEvent | 保单签发 | 渠道(佣金)、再保(自动分保)、收付(应收) |
| PremiumPaidEvent | 保费到账 | 保单(状态变更)、续期(更新记录) |
| ClaimSettledEvent | 理赔结案 | 收付(支付)、再保(摊回) |
| PolicyLapsedEvent | 保单失效 | 续期(停止催缴)、渠道(佣金调整) |

## 4. 代码结构规范（推荐包结构）

```
com.company.insurance.underwriting
├── application           # 应用服务
│   └── UnderwritingAppService.java
├── domain                # 领域层
│   ├── aggregate
│   │   └── Application.java
│   ├── entity
│   ├── vo
│   ├── event
│   ├── repository
│   ├── service           # 领域服务
│   └── spec              # 规约模式
├── infrastructure        # 基础设施
│   ├── persistence
│   ├── mq
│   └── client
└── interfaces            # 接口层
    ├── rest
    ├── rpc
    └── job
```

## 5. 与现有系统集成

遗留系统采用防腐层(ACL)模式适配：

```
新服务(DDD) → Anti-Corruption Layer → 旧核心系统
```

ACL 职责：
- 翻译旧系统的数据结构到新领域模型
- 提供新服务期望的接口契约
- 隔离旧系统的变更影响
