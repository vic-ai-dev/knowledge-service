# Release & Change Management Standard

> Reference: ITIL Change Management Best Practices, Tencent Change Management Standards, Google SRE Change Management

## 1. Overview

### 1.1 Purpose
Standardize the change management process within the Technology Development Department, ensuring all changes are classified, reviewed, approved, and executed in a controlled manner, reducing the risk of production incidents.

### 1.2 Scope
Applies to all changes affecting the production environment, including but not limited to: application releases, database changes, configuration modifications, infrastructure changes, and third-party service switches.

### 1.3 Terminology

| Term | Definition |
| --- | --- |
| Change | Any modification to production or staging environments |
| CAB | Change Advisory Board |
| Change Window | Fixed time period for executing high-risk changes (blackout window) |
| RTO | Recovery Time Objective |
| RPO | Recovery Point Objective |

---

## 2. Change Classification

### 2.1 Change Categories

| Category | Definition | Example |
| --- | --- | --- |
| Standard | Pre-authorized, low-risk, fixed process | Routine config changes, IP whitelist |
| Normal | Requires review and approval | Feature release, DDL changes |
| Emergency | Quick execution for incident fix | P0/P1 hotfix, security patch |
| Major | High-risk, cross-team, broad impact | Architecture refactoring, core system migration |

### 2.2 Change Level Matrix

| Level | Impact | Risk | Approval Chain | Window |
| --- | --- | --- | --- | --- |
| L1 (Low) | Single service/module | Low | Tech Lead | Business hours |
| L2 (Medium) | Multiple services/modules | Medium | Tech Lead + Architect | Pre-release window |
| L3 (High) | Cross-system, business impact | High | CAB review | Change window |
| L4 (Major) | Platform-wide, core system | Critical | CTO/VP + CAB | Special window |

### 2.3 Standard Change List

Pre-authorized standard changes (record required, no individual approval):

- Monitoring alert threshold adjustments
- IP whitelist additions/removals
- Log level adjustments (non-production)
- Non-functional config toggles in config center
- Read-only user authorization

---

## 3. Approval Process

### 3.1 Normal Change Process

```
Request > Impact Assessment > Technical Review > Approval > Schedule > Execute > Verify > Close
```

| Step | Owner | Output | Timeline |
| --- | --- | --- | --- |
| 1. Request | Initiator | Change ticket | --- |
| 2. Impact Assessment | Tech Lead | Impact analysis | 2h |
| 3. Technical Review | Architect (L2+) | Review comments | 4h |
| 4. Approval | Approver (per level) | Decision | 4h |
| 5. Schedule | Tech Lead | Execution schedule | --- |
| 6. Execute | Developer/Ops | Execution log | Per schedule |
| 7. Verify | Initiator + QA | Verification report | 30min post-execution |
| 8. Close | Tech Lead | Ticket closed | After verification |

### 3.2 Emergency Change Process

```
Incident > Emergency Assessment > Emergency Approval (post-execution OK) > Execute > Verify > Post-hoc Ticket
```

- Emergency approvers: Tech Lead + Architect + On-call DBA
- Post-hoc ticket and postmortem required within 24 hours
- If a service has 3+ emergency changes in a month, root cause analysis required

### 3.3 Major Change Process

- Submit change plan 1 week in advance
- CAB meeting required for review
- Full-link load testing and canary required
- Detailed rollback plan and emergency response required
- Notify all affected stakeholders in advance
- At least 2 on-call personnel during execution

---

## 4. Change Window

### 4.1 Definition

A change window is a fixed time period during which high-risk changes may be executed, requiring key stakeholders to be online.

### 4.2 Schedule

| Item | Description |
| --- | --- |
| Regular window | Every Thursday 22:00 - 02:00 |
| Emergency window | On-demand, CTO approval required |
| Cooldown period | Last 3 days of month + 3 days before holidays (emergency only) |
| Annual freeze | 2 weeks before Spring Festival to 1 week after (P0 fix only) |

### 4.3 Rules

- Changes must be approved 2 hours before the window
- Changes not started within 30 minutes of window opening are auto-postponed
- Unfinished changes at window close: rollback if in reversible state
- No parallel L3 changes during the same window

---

## 5. Change Ticket Template

```markdown
# Change Ticket - [CHANGE-YYYYMMDD-001]

## Basic Info
- Title: [Brief description]
- Related Requirement: [JIRA-ID / BRD-ID]
- Category: [Standard/Normal/Emergency/Major]
- Level: [L1/L2/L3/L4]
- Initiator: [Name]
- Tech Lead: [Name]

## Description
### Scope
[Affected systems, modules, services]

### Content
[Detailed technical description]

### Expected Impact
[Business impact description]

## Solution
### Steps
1. [Step 1]
2. [Step 2]

### Rollback Plan
[Detailed rollback steps]

### Canary Strategy
[Ratio, verification metrics, promote conditions]

## Risk Assessment
| Risk | Probability | Impact | Mitigation |
| --- | --- | --- | --- |
| [Risk 1] | L/M/H | L/M/H | [Action] |

## Approval History
| Reviewer | Decision | Time | Signature |
| --- | --- | --- | --- |
| [Name] | [Approve/Reject] | [Time] | --- |

## Execution Log
| Step | Time | Executor | Result |
| --- | --- | --- | --- |
| [Step 1] | [Time] | [Name] | [Success/Fail] |

## Verification
| Item | Result | Verifier |
| --- | --- | --- |
| [Item 1] | [Pass/Fail] | [Name] |
```

---

## 6. Change Review

### 6.1 Weekly Summary

Weekly change review meeting covering:

- Total changes for the week
- Count by level
- Success rate
- Rollbacks and reasons
- Emergency change count and root causes

### 6.2 Metrics

| Metric | Target | Alert Threshold |
| --- | --- | --- |
| Change success rate | > 99% | < 98% |
| Emergency change ratio | < 10% | > 20% |
| Rollback rate | < 5% | > 10% |
| Change-induced incidents | 0 | 1 |
| Average lead time | < 3 days | > 7 days |

---

## 7. Appendix

### 7.1 Reference Documents
- ITIL 4 Change Management Practices
- *CICD Standard*
- *Release Checklist Standard*
- *Emergency Response Plan & SOP*

### 7.2 CAB Composition

| Role | Member | Responsibility |
| --- | --- | --- |
| Chair | Tech Director | Lead review, final decision |
| Architect | Core architect | Review technical solutions |
| Ops Representative | Ops lead | Review infrastructure impact |
| Security Representative | Security lead | Review security impact |
| Business Representative | Business lead | Assess business impact |
| Change Manager | PM | Process management and records |
