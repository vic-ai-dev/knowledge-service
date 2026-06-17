# Test Strategy & Case Standard

> Reference: Google Testing Certification, Alibaba Testing Standards, ThoughtWorks Test Pyramid, ISTQB Standards

## 1. Overview

### 1.1 Purpose
Standardize test strategy, case design, and execution processes for insurance core systems, ensuring sufficient test coverage and measurable quality, with special focus on accounting testing and actuarial interface verification.

### 1.2 Scope
This standard applies to functional testing, integration testing, accounting testing, and actuarial interface verification for all products/projects within the Technology Development Department.

---

## 2. Test Pyramid & Strategy

### 2.1 Test Layer Strategy

| Layer | Proportion | Speed | Responsibility | Tools |
| --- | --- | --- | --- | --- |
| Unit Test (UT) | 60% | Milliseconds | Verify function/method logic | JUnit / pytest / Go test |
| Integration Test (IT) | 25% | Seconds | Verify module interaction, DB operations, API calls | Testcontainers / Mockito |
| End-to-End Test (E2E) | 10% | Minutes | Verify complete business workflows | Selenium / Cypress |
| Manual Exploratory | 5% | N/A | Edge cases, complex business logic | Manual |

### 2.2 Test Quadrants

| Quadrant | Test Types | Insurance Focus |
| --- | --- | --- |
| Q1: Tech-facing/Support | Unit tests, component tests | Premium calculation, underwriting engine, reinsurance algorithms |
| Q2: Business-facing/Support | Functional tests, E2E, UAT | Policy issuance, claims, renewal payment, policy servicing |
| Q3: Business-facing/Critique | Exploratory tests, scenario tests | Exception flows, edge cases, regulatory scenarios |
| Q4: Tech-facing/Critique | Performance tests, security tests | Peak season load testing, data security compliance |

---

## 3. Test Case Design Standards

### 3.1 Case Template

```markdown
# TC-[Module]-[ID]: [Title]

## Basic Info
- Related Requirement: [BRD/TRD ID]
- Test Type: [Functional/Accounting/Actuarial/Integration/Performance]
- Priority: [P0/P1/P2/P3]
- Automatable: [Yes/No]

## Prerequisites
1. [Condition 1]

## Steps
1. [Step 1]
2. [Step 2]

## Expected Results
1. [Result 1]
2. [Result 2]

## Test Data
| Field | Value | Description |
| --- | --- | --- |
| [Field] | [Value] | [Description] |

## Cleanup
[Data cleanup after test]
```

### 3.2 Case Design Principles

1. **Equivalence Partitioning** — Cover positive, negative, and boundary values for each business rule
2. **Boundary Value Analysis** — Numeric fields like premium calculation, rate ranges, deductibles
3. **Decision Table** — Multi-condition combinations in underwriting rules (health + occupation + sum assured)
4. **State Transition** — Policy lifecycle (apply > issue > active > claim > terminate)
5. **Exception Scenarios** — Timeout, retry, idempotency, concurrency, data inconsistency
6. **Data-Driven** — Use parameterized data covering multiple products, channels, customer types

---

## 4. Accounting Test Standards

### 4.1 Accounting Test Scope

Accounting testing is the most critical part of insurance core system testing, covering:

| Accounting Type | Test Points |
| --- | --- |
| Premium Collection | Initial premium, renewal premium, loading/reduction, free-look cancellation |
| Claims Payment | Claim payout, maturity benefit, survival benefit, dividend payment |
| Commission Settlement | First-year commission, renewal commission, team management bonus |
| Reinsurance Settlement | Treaty reinsurance ceded, facultative reinsurance, reinsurance recovery |
| Reserves | Unearned premium reserve, outstanding claims reserve |
| Tax Treatment | VAT on premiums, stamp duty, withholding tax |

### 4.2 Verification Methods

**Method 1: T-Account Verification**

```
                [T-Account - Premium Collection]

  Debit (Premium Receivable)    Credit (Premium Income)
 +---------------------------+  +---------------------------+
 | 1000.00                   |  | 1000.00                   |
 +---------------------------+  +---------------------------+
```

**Method 2: Accounting Entry Verification**

```
Transaction: Collect initial premium 1000
Debit: Bank Deposit                   1000.00
Credit: Premium Income - Initial      1000.00

Transaction: Pay commission 200
Debit: Commission Expense              200.00
Credit: Bank Deposit                    200.00
```

**Method 3: Balance Verification**

```
Opening Balance + Current Income - Current Expense = Closing Balance
      0         +     1000      -      200        =      800
```

### 4.3 Accounting Test Checklist

- [ ] Single transaction accounting entries are correct
- [ ] Concurrent transaction accounting summaries are correct
- [ ] Multi-currency exchange rate is correct
- [ ] Reversal/red-ink entries are correct
- [ ] Cross-day, cross-month, cross-year accounting carry-forwards are correct
- [ ] Reconciliation with financial system matches

---

## 5. Actuarial Interface Verification

### 5.1 Verification Scope

| Actuarial Interface | Verification Content |
| --- | --- |
| Rate calculation | Age/gender/sum assured/payment term > premium output |
| Cash value | Cash value per policy year, post-reduction cash value |
| Reserve assessment | Reserve amounts under different valuation standards |
| Profit testing | Embedded value, new business value |
| Reinsurance allocation | Retention, ceded amount, reinsurance premium |

### 5.2 Verification Method

```markdown
## Test Case: Rate Calculation API

### Input
- Product Code: PROD-001 (Whole Life)
- Age: 35
- Gender: M
- Sum Assured: 1,000,000
- Payment Term: 20 years
- Payment Frequency: Annual

### Expected Output
- Annual Premium: 12,350.00 (matching actuarial pricing model)
- Monthly Premium: 1,050.00

### Validation Rules
- Difference from actuarial model: < 0.01
- Monthly x 12 > Annual (monthly has surcharge)
- Premium scales linearly with sum assured
```

### 5.3 Acceptance Criteria

- Rate calculation deviation from actuarial model: less than 0.01
- Cash value table: 100% field match with actuarial model
- Reserve deviation under different standards: within acceptable range
- Actuarial API response time: within SLA (P99 < 2s)

---

## 6. Test Execution & Reporting

### 6.1 Test Phases

| Phase | Executor | Entry Criteria | Exit Criteria |
| --- | --- | --- | --- |
| Unit Test | Developer | Code complete | UT coverage > 80% |
| Integration Test | Developer + QA | UT passed | Core interface tests passed |
| System Test | QA | IT passed | All test pass rate > 95% |
| UAT | Business | System test passed | Key business scenarios verified |
| Regression Test | QA | Version change | Core cases 100% passed |

### 6.2 Test Report Template

```markdown
# Test Report: [Project] v[Version]

## Summary
- Period: YYYY-MM-DD ~ YYYY-MM-DD
- Total Cases: [X]
- Passed: [X] | Failed: [X] | Blocked: [X] | Skipped: [X]
- Pass Rate: [X]%

## Defect Statistics
- Total Defects: [X]
  - P0: [X] | P1: [X] | P2: [X] | P3: [X]
- Fixed: [X] | Pending: [X]
- Remaining Defect Impact: [Description]

## Test Coverage
- Functional Coverage: [X]%
- Code Coverage: [X]%
- Interface Coverage: [X]%

## Key Findings
1. [Key Finding 1]
2. [Key Finding 2]

## Release Recommendation
[Recommendation: Pass / Conditional Pass / Fail]
```

---

## 7. Appendix

### 7.1 Reference Documents
- ISTQB Foundation Certification
- *Requirements Specification Standard*
- *Performance Testing Standard*
- *Release Checklist Standard*

### 7.2 Recommended Tools

| Purpose | Recommended Tool | Alternative |
| --- | --- | --- |
| Unit Testing | JUnit / pytest / go test | TestNG |
| Mocking | Mockito / MockK / unittest.mock | WireMock |
| DB Testing | Testcontainers / H2 | DbUnit |
| API Testing | RestAssured / Postman / Bruno | JMeter |
| E2E Testing | Selenium / Cypress | Playwright |
| Accounting Testing | In-house verification framework | Excel validation |
| Coverage | JaCoCo / coverage.py / gocov | --- |
| Test Management | Xray / TestRail | Allure |
