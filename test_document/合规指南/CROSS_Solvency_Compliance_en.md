# C-ROSS Compliance Guide

## 1. Overview

This document defines technical compliance requirements under China Risk-Oriented Solvency System (C-ROSS Phase II), covering solvency data collection, calculation, reporting, and system integration. It is intended for developers and operators of the data platform, core systems, and actuarial systems.

## 2. C-ROSS Framework

### 2.1 Three Pillars

| Pillar | Content | Tech Impact |
|--------|---------|-------------|
| Pillar 1 Quantitative | Capital requirements, actual/minimum capital | Actuarial models, data platform |
| Pillar 2 Qualitative | Risk management, SARMRA | Risk management systems, controls |
| Pillar 3 Market Discipline | Information disclosure | Reporting systems, data publishing |

### 2.2 Key Metrics

| Metric | Definition | Requirement |
|--------|------------|-------------|
| Comprehensive Solvency Ratio | Actual Capital / Minimum Capital | ≥ 100% |
| Core Solvency Ratio | Core Capital / Minimum Capital | ≥ 50% |
| Comprehensive Risk Rating | Integrated risk assessment | A/B/C/D grades |

## 3. Technical System Requirements

### 3.1 Data Collection & Validation

| Source | Data | Frequency | Quality |
|--------|------|-----------|---------|
| Underwriting | Policy details, premium | T+1 | 100% accuracy, ≥99.9% completeness |
| Claims | Paid/pending claims | T+1 | 100% accuracy |
| Finance | Assets, liabilities, P&L | T+1 | Matches general ledger |
| Actuarial | Reserve assessment | Monthly | Actuarial report validation |
| Investment | Asset allocation, returns | T+1 | Custodian bank reconciliation |

### 3.2 Data Quality Requirements

| Dimension | Requirement | Monitoring |
|-----------|-------------|------------|
| Completeness | Key field non-null ≥ 99.9% | Data quality platform |
| Accuracy | 100% match with source | Cross-validation rules |
| Timeliness | T+1 10:00 AM completion | Timeliness monitoring |
| Consistency | Cross-system metric alignment | Consistency checks |
| Traceability | Back to source documents | Data lineage |
| Stability | No abnormal fluctuation | Volatility monitoring |

## 4. Reporting

| Report | Frequency | Deadline | System |
|--------|-----------|----------|--------|
| Quarterly Solvency Report | Quarterly | D+30 | Regulatory system |
| Annual Solvency Report | Annual | Apr 30 | Regulatory system |
| Interim Solvency Report | Triggered | D+3 | Regulatory system |
| Risk Rating Report | Quarterly | D+30 | Regulatory system |
| SARMRA Report | Annual | June | Regulatory system |

## 5. System Integration Architecture

```
Business Systems → Data Platform → Solvency Engine → Validation → Report Generation → Regulatory Submission
```

## 6. IT Compliance Checklist

| Check | Requirement | Cadence |
|-------|-------------|---------|
| Source data completeness | No missing key fields | Daily |
| Reconciliation | Financial vs business = 0 diff | Daily |
| Report backup | Encrypted archive | Quarterly |
| Calculation change control | Versioned + approved | Per change |
| Data access audit | Quarterly review | Quarterly |
