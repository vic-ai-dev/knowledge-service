# Requirements Specification / BRD→TRD Standard

> Reference: Alibaba Requirement Management Practices, Tencent TAPD R&D Collaboration Standards, Huawei IPD Requirement Management Process

## 1. Overview

### 1.1 Purpose
Standardize the translation process from Business Requirements Documents (BRD) to Technical Requirements Documents (TRD) for insurance core systems (underwriting, claims, renewal, policy servicing, etc.), ensuring accurate, traceable, and verifiable requirement delivery.

### 1.2 Scope
Applies to all business requirements undertaken by the Insurance Technology Development Department, including core systems, channel systems, data platforms, etc.

### 1.3 Terminology

| Term | Definition |
|------|-----------|
| BRD | Business Requirements Document, produced by business stakeholders |
| TRD | Technical Requirements Document, produced by the technology development team |
| Requirements Traceability Matrix | Mapping table from BRD items to TRD items to test cases |
| Requirement Change | Modification to a baselined requirement |

---

## 2. Input: BRD Requirements

### 2.1 Mandatory BRD Content
A BRD submitted by business stakeholders must include the following sections:

1. **Background & Objectives** — Business pain points, target users, expected benefits (quantified KPIs)
2. **Business Rule Description** — Underwriting/claims/renewal/policy servicing rules (with formulas, condition branches, edge cases)
3. **Business Process Flow** — BPMN 2.0 or Swimlane diagram
4. **Data Requirements** — Input fields, output fields, data sources, historical data migration requirements
5. **Non-Functional Requirements** — Response time, processing volume, availability requirements, compliance requirements
6. **Acceptance Criteria** — Quantifiable acceptance conditions

### 2.2 BRD Quality Gate

- [ ] All business rules cover normal flows and exception flows
- [ ] Items involving financial accounting include accounting entry examples
- [ ] Items involving regulatory reporting include sample regulatory message formats
- [ ] Confirmed by business owner (signature/email)

---

## 3. BRD → TRD Translation Standards

### 3.1 Translation Principles
Each BRD item must be translated into a complete technical solution in the TRD. Direct copying without analysis is not permitted.

| BRD Example | TRD Translation Requirements |
|-------------|-----------------------------|
| "Send reminder when renewal premium is insufficient" | Define: trigger timing (T+N days), notification channels (SMS/App Push/Email), frequency (daily/single), retry strategy on failure |
| "Underwriting engine supports loading (extra premium)" | Define: loading calculation rule table, factor table structure, min/max loading limits, linkage with rate tables |
| "Policy servicing payments go through new fund platform" | Define: interface protocol, message mapping table (core fields → fund platform fields), reconciliation mechanism, exception handling flow |

### 3.2 TRD Template Structure

```markdown
# TRD-[ID] [Title]

## 1. Requirement Summary
- Related BRD: [BRD-ID]
- Related Requirement Source: [Jira/Ticket ID]
- Affected Systems: [Core/Channel/Fund/Data Middle Platform]

## 2. Requirement Analysis
### 2.1 Business Process Analysis
### 2.2 Impact Analysis
### 2.3 Risk Assessment

## 3. Technical Solution
### 3.1 Solution Description
### 3.2 Interface Design
### 3.3 Database Design
### 3.4 Business Rule Implementation
### 3.5 Exception Handling

## 4. Non-Functional Requirements Implementation
## 5. Acceptance Criteria Mapping
## 6. Requirements Traceability
## 7. Change History
```

---

## 4. Review Process

### 4.1 Review Gates
1. **TRD Draft Review** (Technical Internal) — Architect + Lead Developer + QA
2. **Joint Review** (Business + Technology) — Business stakeholders confirm business rule translation accuracy
3. **TRD Baselining** — Locked after review approval, committed to code repository

### 4.2 Review Checklist

- [ ] Each BRD item has a corresponding TRD solution
- [ ] Pros/cons analysis provided when A/B options exist
- [ ] Interface definitions cover normal, timeout, and exception scenarios
- [ ] Database changes include rollback plans
- [ ] Non-functional requirements assessed and reflected in the solution
- [ ] Change impact scope clearly marked

---

## 5. Requirement Change Management

### 5.1 Change Classification

| Level | Definition | Approval Chain |
|-------|-----------|---------------|
| Level 1 | UI copy/non-functional adjustments, no impact on interfaces or data | Tech lead confirmation |
| Level 2 | Business logic adjustments involving interface changes | Tech lead + business stakeholder confirmation |
| Level 3 | Data model changes, process restructuring, new system integration | PMO + Architecture Review Board approval |

### 5.2 Change Process
1. Submit change request (linked to original BRD/TRD)
2. Impact assessment (output within 24h)
3. Change review
4. Update document baseline
5. Notify affected stakeholders

---

## 6. Appendix

### 6.1 Reference Documents
- *Insurance Business Terminology Standard*
- *Core System Data Model Design Standard*
- *Interface Business Specification Standard*

### 6.2 Tools & Templates
- TRD template location: [Internal document link]
- BRD submission portal: [Requirements management system link]
