# System Architecture Overview

## 1. Document Objective

This document defines the overall architectural view and design principles for the insurance company's technology landscape. It serves as a unified framework for all subsystems, technology decisions, and architecture governance. The audience includes architects, tech leads, and developers.

## 2. Architecture Design Principles

| Principle | Description | Reference |
|-----------|-------------|-----------|
| High Availability | Core system availability ≥ 99.99%, annual downtime < 53 min | Ant Cloud Standard |
| Disaster Recovery | Active-active across ≥ 3 data centers in ≥ 2 regions | Industry Best Practice |
| Distributed Microservices | Domain-oriented decomposition, independent deployment & scaling | Spring Cloud / K8s |
| Loose Coupling | Async messaging + standard APIs between domains, no direct DB sharing | DDD + CQRS |
| Observability | Full-trace Trace, Metrics, Logging pillars | OpenTelemetry |
| Security & Compliance | MLPS 2.0 / Personal Information Protection Law / C-ROSS | Regulatory requirements |

## 3. Architecture Layers

```
┌─────────────────────────────────────────────┐
│              Channel Access Layer            │
│   App · Web · Agent · Broker · Bank · 3rdP  │
└──────────────────────┬──────────────────────┘
                       │ API Gateway / WAF / CDN
┌──────────────────────┴──────────────────────┐
│           Business Middleware                │
│  ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐   │
│  │Product│Underw│Risk │Claims│Renew│         │
│  └─────┘ └─────┘ └─────┘ └─────┘ └─────┘   │
│  ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐           │
│  │Serv. │Reins.│Chnl.│Paymt│                  │
│  └─────┘ └─────┘ └─────┘ └─────┘           │
└──────────────────────┬──────────────────────┘
                       │
┌──────────────────────┴──────────────────────┐
│         Technology Middleware                │
│   Registry · Config · Gateway · MQ · Scheduler│
│   Logging · Monitoring · Tracing · CI/CD     │
└──────────────────────┬──────────────────────┘
                       │
┌──────────────────────┴──────────────────────┐
│             Data Platform                    │
│  OLTP → Canal → Kafka → Flink → ClickHouse   │
│  Data Lake · DWH · Metrics · AI/ML          │
└──────────────────────┬──────────────────────┘
                       │
┌──────────────────────┴──────────────────────┐
│            Infrastructure                    │
│   K8s · Storage · Network · Security · CDN   │
└─────────────────────────────────────────────┘
```

## 4. Core System Inventory

| System | Responsibilities | Key Capabilities |
|--------|-----------------|------------------|
| Product Center | Product definition, rate factors, clause management | Rule engine, pricing model |
| Underwriting Center | Application entry, risk assessment, policy issuance | UW rule engine, image OCR |
| Policy Servicing | Endorsement, reinstatement, cancellation | Service rules, fund calculation |
| Claims Center | FNOL, investigation, assessment, settlement | Risk model, anti-fraud engine |
| Renewal Center | Renewal reminders, grace period management | Payment interface, SMS |
| Reinsurance Center | Facultative/treaty, ceded/assumed | Contract management, billing |
| Channel Center | Agent, broker, bancassurance, online | Commission rules, channel agreements |
| Payment Center | Premium collection, claim payment, reconciliation | Funding channels, error handling |
| Customer 360 | Customer info, policy relationships, KYC | Unified customer view |
| Data Platform | DWH, reporting, regulatory, BI analytics | ETL, metric management |

## 5. Key Business Process Flows

### 5.1 Underwriting Main Flow
```
Sales → Application Entry → Auto/Manual UW → Payment → Policy Issue → Effective
```
- Cross-system dependency chain: Product → UW → Risk Engine/Image → Payment → Policy Issue
- Non-functional: Peak season TPS ≥ 2000, P99 < 500ms

### 5.2 Claims Main Flow
```
FNOL → Investigation → Case Open → Assessment → Calculation → Approval → Settlement → Payment
```
- Cross-system dependency: Claims → Risk Engine → Payment → Reinsurance (if exceed retention)
- Non-functional: Settlement completion ≤ 3 days (fast-track ≤ 1 day)

## 6. Architecture Governance

- **Architecture Review Board**: Monthly review of cross-domain designs and technology selections
- **ADR**: All decisions recorded with context, options, decision, and consequences
- **Tech Radar**: Quarterly update of technology adoption/retirement status
- **Compliance Check**: Architecture rule scanning integrated into CI pipeline

## 7. References

- Microservice Architecture Standard (this directory)
- Domain-Driven Design Standard (this directory)
- Data Architecture Standard (this directory)
- Security Architecture Standard (this directory)
- Technology Selection & ADR Standard (this directory)
