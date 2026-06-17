# IFRS 17 Compliance Guide

## 1. Overview

This document defines IFRS 17 "Insurance Contracts" implementation requirements for insurance technology systems, covering data collection, measurement models, allocation calculations, and disclosure reporting. It is intended for developers and operators of data platforms, actuarial systems, and financial systems.

## 2. IFRS 17 Core Concepts

### 2.1 Key Changes

| Aspect | IFRS 4 (Old) | IFRS 17 (New) |
|--------|--------------|----------------|
| Revenue Recognition | Premiums received | Based on insurance service provision |
| Profit Recognition | Day-1 profit recognized fully | Gradual release via CSM |
| Discount Rate | Not mandatory | Must reflect time value |
| Assumption Updates | Not locked | Regular updates required |
| Disclosures | Limited | Significantly expanded |

### 2.2 Key Metrics

| Term | Abbr | Description |
|------|------|-------------|
| Contractual Service Margin | CSM | Unearned profit, released as service provided |
| Insurance Revenue | - | Revenue based on services provided |
| Insurance Service Expenses | - | Claims and expenses incurred |
| Insurance Finance Income/Expenses | - | Financial impact of discount rate changes |
| Onerous Contract | - | Expected losses > income |
| Fulfillment Cash Flows | FCF | PV of future cash flows + risk adjustment |

## 3. Measurement Models

| Model | Applicability | Key Features |
|-------|---------------|--------------|
| GMM/BBA | Default model | Periodic CSM release, regular assumption updates |
| PAA | Coverage ≤ 1 year | Simplified, approximates premium revenue |
| VFA | Direct participating contracts | CSM reflects investment volatility |

## 4. Technical System Requirements

### 4.1 Data Requirements

| Data Dimension | Description | Source System |
|---------------|-------------|---------------|
| Policy-level data | Cash flow projections per policy | Underwriting/Policy |
| Grouping | Annual/cohort grouping | Grouping rules engine |
| Actuarial assumptions | Mortality, lapse, expense | Actuarial system |
| Discount curve | Yield curves by tenor | Investment/Market data |
| Actual experience | Actual claims, lapses, expenses | Claims/Policy/Finance |
| Contract modification | Policy change records | Servicing system |

### 4.2 Calculation Flow

```
Data Collection → Grouping → Cash Flow Projection → Discounting → Risk Adjustment → CSM Calculation → P&L Recognition → Report Generation
```

### 4.3 System Architecture

```
Source Systems → IFRS 17 Calculation Engine → General Ledger → Disclosure Reports
```

## 5. Disclosure Requirements

| Disclosure | Technical Implementation |
|------------|------------------------|
| Insurance contract reconciliation | Opening → Changes → Closing |
| Revenue analysis | By product/channel/region |
| CSM reconciliation | Opening → additions → interest → release → experience → closing |
| Onerous contract details | Initial recognition and subsequent measurement |
| Discount rate assumptions | Yield curve by tenor |
| Risk adjustment | Methodology, confidence level |
| Claims development triangle | Historical claims development |

## 6. Implementation Checklist

| Task | Owner | Milestone |
|------|-------|-----------|
| Data requirements analysis | Data Architect | T+0 |
| Calculation engine selection | Tech Architect | T+15 |
| Source system interface changes | System Teams | T+60 |
| Data pipeline (ODS→DWD→DWS) | Data Platform | T+90 |
| Engine deployment & testing | Actuarial + Dev | T+120 |
| Financial reconciliation | Dev + Finance | T+150 |
| UAT sign-off | Actuarial + Finance + Audit | T+180 |
