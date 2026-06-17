# Insurance Regulatory Compliance Overview

## 1. Overview

This document provides a regulatory compliance overview for the insurance technology department, mapping key laws and regulatory requirements applicable to insurance technology. References include the National Financial Regulatory Administration (NFRA), People's Bank of China (PBOC), and related regulators.

## 2. Regulatory Framework

### 2.1 China Insurance Regulatory Structure

```
┌───────────────────────────────────────────────┐
│    National Financial Regulatory Admin (NFRA)  │
│   Unified financial supervision (insurance)   │
├───────────────────────────────────────────────┤
│         People's Bank of China (PBOC)          │
│    Payment settlement, AML, credit reporting   │
├───────────────────────────────────────────────┤
│    China Securities Regulatory Commission      │
│    Insurance fund investments                 │
├───────────────────────────────────────────────┤
│         China Insurance Association            │
│    Industry self-regulation, service rating    │
└───────────────────────────────────────────────┘
```

### 2.2 Key Regulations

| Regulation | Effective | Scope |
|-----------|-----------|-------|
| Insurance Law of PRC | 2021 amendment | All insurance business |
| Internet Insurance Regulation | Feb 2021 | Online insurance |
| C-ROSS Phase II | 2022 | Solvency management |
| PIPL | Nov 2021 | Personal information |
| Data Security Law | Sep 2021 | Data processing |
| Cybersecurity Law | Jun 2017 | Network security |
| MLPS 2.0 | Dec 2019 | Information security |
| Financial Data Security Classification | 2020 | Financial data grading |

## 3. Compliance Organization

| Role | Responsibilities | Tech Liaison |
|------|-----------------|--------------|
| Compliance Committee | Strategy, major approvals | Compliance assessment reports |
| Compliance Dept | Daily management, regulatory liaison | Review support, remediation |
| Legal Dept | Contract review, legal risk | System legal support |
| DPO | PIPL oversight | Data security tech review |
| IS Committee | Security strategy, incident response | Security architecture & ops |

## 4. Technology Compliance Points

### 4.1 Product Compliance
- Rates and clauses require actuarial and compliance approval
- Internet insurance products must be registered with regulator
- Application process must meet suitability management requirements

### 4.2 Data Compliance
- Personal info collection requires "notice-consent"
- Sensitive personal info requires separate consent
- Data export requires security assessment
- Policy data retention: ≥ 10 years after policy expiry

### 4.3 Channel Compliance
- Third-party platforms require insurance intermediary qualification
- Online sales must be traceable
- Auto-enrollment requires customer notification

### 4.4 Claims Compliance
- Claim assessment: within 30 days of complete materials
- Rejection requires written explanation
- Fast-track small claims: settlement within 24 hours

## 5. Regulatory Penalty Risks

| Violation | Example | Basis | Penalty |
|-----------|---------|-------|---------|
| Data breach | Unauthorized access to customer data | Insurance Law Art. 116 | Fine + suspension |
| Misleading sales | Exaggerated coverage/returns | Insurance Law Art. 162 | Fine 200K-1M |
| Improper rejection | No explanation for denial | Insurance Law Art. 23 | Fine + admin sanction |
| PIPL violation | Unconsented collection | PIPL Art. 66 | Fine up to 50M/5% revenue |

## 6. RegTech Applications

| RegTech | Technology | Application |
|---------|------------|-------------|
| Digital Regulatory Rules | DRL Engine | Auto compliance check for UW rules |
| Intelligent Compliance | NLP | Auto review of sales scripts |
| Data Security Audit | Big Data + UEBA | Real-time anomalous access alerts |
| Automated Reporting | ETL + Data Lineage | Auto regulatory filing |
| Sales Traceability | Screen recording + Blockchain | Internet insurance process recording |
