# Release Checklist Standard

> Reference: Tencent Release Standards, Alibaba Cloud Release Process, Google SRE Change Management

## 1. Overview

### 1.1 Purpose
Standardize pre-release checklists to ensure all preparations are in place, risks are controlled, and rollback plans are complete, reducing the probability of production incidents caused by releases.

### 1.2 Scope
Applies to all production environment releases within the Technology Development Department, including feature releases, hotfixes, configuration changes, and data migrations.

---

## 2. Release Types & Process

### 2.1 Release Types

| Type | Definition | Approval Chain | Window |
| --- | --- | --- | --- |
| Regular | Feature iteration, bug fixes | Tech Lead + QA | Weekly fixed window |
| Emergency | P0/P1 defect fix | Tech Lead + Architect | Emergency window (24h) |
| Configuration | Config center change | Config admin | Business hours |
| Data | Data correction, migration | DBA + Tech Lead | Change window |

### 2.2 Release Flow Overview

```
Code Freeze > Test Report > Release Approval > Environment Prep > DB Change > App Deploy > Canary > Full Release > Observation
```

---

## 3. Pre-Release Checklist

### 3.1 Code Review

- [ ] Code reviewed and approved
- [ ] All unit tests passed (coverage meets standard)
- [ ] Static analysis: no P0/P1 issues (SonarQube / CodeQL)
- [ ] Security scan: no high-risk vulnerabilities (SAST / DAST)
- [ ] Dependency check: no known vulnerabilities (SCA / Dependabot)
- [ ] Code merged to target branch (release / master)
- [ ] Git tag created (format: v{major}.{minor}.{patch})

### 3.2 Test Verification

- [ ] Functional test report signed off
- [ ] Integration tests passed
- [ ] Regression tests passed (core cases 100%)
- [ ] Performance test passed (or assessed as non-impacting)
- [ ] UAT accepted (business confirmation)
- [ ] Compatibility tests passed (browser/API version/DB version)

### 3.3 Environment Preparation

- [ ] Staging environment verified
- [ ] Production configuration reviewed (config diff)
- [ ] Database change scripts approved and pre-verified
- [ ] External service versions confirmed (third-party APIs/middleware)
- [ ] SSL certificate valid
- [ ] CDN cache refresh plan confirmed
- [ ] DNS changes completed

### 3.4 Rollback Plan

- [ ] Rollback plan documented
- [ ] Application rollback steps verified (rollback script to previous version)
- [ ] Database rollback script prepared and verified
- [ ] Rollback trigger conditions defined
- [ ] Estimated rollback time assessed (RTO)
- [ ] Post-rollback data validity verified

### 3.5 Canary Strategy

- [ ] Canary release plan finalized
- [ ] Canary ratio and timing confirmed
- [ ] Canary verification metrics defined (error rate, RT, business metrics)
- [ ] Canary rollback conditions defined
- [ ] Monitoring configured during canary

### 3.6 Notification & On-Call

- [ ] Release notification sent
- [ ] Affected system owners notified
- [ ] On-call personnel confirmed (online during release)
- [ ] Customer support/operations team informed of potential impact
- [ ] Business stakeholders aware of release window

---

## 4. Canary Release Standards

### 4.1 Canary Strategy Template

```markdown
## Canary Release Plan - [Project] v[Version]

### Canary Scope
- Ratio: [ ]% (recommend starting at 1%)
- Target: by [channel / region / user ID hash]
- Duration: [ ] hours/days

### Verification Metrics
- Error rate: P0 API error rate < 0.1%
- P99 RT: < 1.2x baseline
- Business metrics: no degradation in policy/payment success rates
- System resources: CPU < 70%, memory < 80%

### Promote Conditions
1. No P0/P1 alerts after [ ] hours of canary
2. Core business metrics normal
3. Performance metrics within threshold

### Rollback Conditions
1. Error rate exceeds [ ]%
2. P0 API unavailable
3. Key business metrics significantly degraded (e.g., 10%)
4. Financial loss detected
```

### 4.2 Canary to Full Rollout

| Step | Action | Verification | Duration |
| --- | --- | --- | --- |
| 1 | Canary 1% | Metrics normal | 30 min |
| 2 | Canary 5% | Metrics normal | 30 min |
| 3 | Canary 20% | Metrics normal | 1 hour |
| 4 | Canary 50% | Metrics normal | 1 hour |
| 5 | Full 100% | Metrics normal | 30 min observe |

---

## 5. During-Release Checklist

### 5.1 Database Changes

- [ ] Backup affected tables
- [ ] Pre-verify rollback script on a replica
- [ ] Execute DDL in order (least dependencies first)
- [ ] Verify after each step (SHOW TABLES, DESC)
- [ ] Pre-count DML data changes

### 5.2 Application Deployment

- [ ] Drain old version traffic
- [ ] Deploy new version (rolling update / blue-green)
- [ ] Health check passes after startup (/health)
- [ ] Restore traffic for observation
- [ ] Confirm metrics on monitoring dashboard

### 5.3 Release Confirmation

- [ ] Release system status: OK
- [ ] Core API smoke test passed
- [ ] No abnormal alerts
- [ ] No ERROR level logs
- [ ] Business confirms functionality

---

## 6. Post-Release Checklist

### 6.1 Observation Period (30 min - 24 hours)

- [ ] Monitor dashboard continuously
- [ ] Compare business metrics (pre vs post release)
- [ ] No abnormal error log growth
- [ ] No abnormal slow queries
- [ ] No capacity issues

### 6.2 Confirmation & Retrospective

- [ ] Release result notification (success/failure/rollback)
- [ ] Update change record
- [ ] Archive release artifacts (package/image tag)
- [ ] Initiate postmortem if issues occurred

---

## 7. Appendix

### 7.1 Reference Documents
- *Release & Change Management Standard*
- *Database Change Management Standard*
- *Emergency Response Plan & SOP*
- Environment configuration checklists

### 7.2 Rollback Plan Template

```markdown
# Rollback Plan - [Project] v[Version]

## Trigger Conditions
1. [Condition 1]
2. [Condition 2]

## Application Rollback
1. Rollback to previous version image: [Image Tag]
2. Deploy command: [Command]
3. Verification: [Health check command]

## Database Rollback
1. Rollback script: [SQL file path]
2. Execution method: [DBA / automation tool]
3. Verification: [Verification SQL]

## Data Compensation
- If data was written, compensation plan: [Description]

## Post-Rollback
- Notify stakeholders
- Document rollback reason
- Improvement plan
```
