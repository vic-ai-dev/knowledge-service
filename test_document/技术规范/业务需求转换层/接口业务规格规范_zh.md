# 接口业务规格规范

> 参考：阿里巴巴 API 设计规范、腾讯微服务接口规范、Google API Design Guide

## 1. 概述

### 1.1 目的
定义保险公司各系统间（核心系统、渠道平台、资金平台、数据中台等）接口的设计规范，确保接口的可理解性、一致性、健壮性和可维护性。

### 1.2 适用范围
本规范适用于技术开发部所有系统间的同步/异步接口设计，包括 RESTful API、gRPC、消息队列等交互方式。

---

## 2. 接口设计原则

### 2.1 通用原则
1. **契约优先** — 先定义接口文档，再实现代码
2. **兼容性优先** — 接口默认向前兼容，不兼容变更必须走变更流程
3. **幂等性** — 写操作接口（特别是涉及账务的）必须支持幂等
4. **无状态** — 服务端不依赖客户端会话状态
5. **单一职责** — 一个接口只做一件事

### 2.2 协议选择

| 场景 | 推荐协议 | 理由 |
|------|---------|------|
| 前端 → 后端查询 | RESTful / GraphQL | 浏览器友好，缓存方便 |
| 系统间同步调用 | RESTful / gRPC | 结构化、类型安全 |
| 异步通知/事件驱动 | 消息队列（RocketMQ/Kafka） | 解耦、削峰填谷 |
| 文件批量传输 | SFTP / S3 | 大文件、断点续传 |
| 实时数据订阅 | CDC（Debezium/Canal） | 低延迟、事务一致 |

---

## 3. RESTful API 规范

### 3.1 URL 命名规范

```
/{domain}/{context}/{version}/{resource}[/{resource_id}][?query_params]
```

**示例：**

```
/v1/underwriting/{proposal_no}/decision
/v1/claims/{claim_no}/documents
/v2/policy/{policy_no}/endorsements
```

**命名规则：**

- 全部使用小写字母
- 单词间使用连字符 `-`
- 不使用下划线 `_`
- 不使用文件扩展名（`.json`、`.xml`）
- 路径中数字使用路径变量，不要拼在路径里

### 3.2 HTTP 方法使用

| 方法 | 用途 | 幂等 | 安全 |
|------|------|------|------|
| GET | 查询资源 | ✓ | ✓ |
| POST | 创建资源/触发操作 | ✗ | ✗ |
| PUT | 全量更新资源 | ✓ | ✗ |
| PATCH | 部分更新资源 | ✗ | ✗ |
| DELETE | 删除资源 | ✓ | ✗ |

### 3.3 请求 & 响应规范

**请求头规范：**

```
Content-Type: application/json
Accept: application/json
X-Request-ID: <UUID>           // 全链路追踪 ID
X-Channel: <channel_code>      // 渠道标识
X-User-ID: <user_identifier>   // 操作人标识
Idempotency-Key: <UUID>        // 幂等键（写操作必传）
```

**统一响应结构：**

```json
{
  "code": 200,
  "message": "success",
  "data": { },
  "requestId": "a1b2c3d4-...",
  "timestamp": 1718000000000
}
```

**分页响应：**

```json
{
  "code": 200,
  "data": {
    "items": [],
    "pagination": {
      "page": 1,
      "pageSize": 20,
      "totalItems": 156,
      "totalPages": 8
    }
  }
}
```

### 3.4 错误码规范

| 错误码范围 | 含义 |
|-----------|------|
| 200 | 成功 |
| 400 - 4xx | 客户端错误 |
| 500 - 5xx | 服务端错误 |

**业务错误码结构：** `{HTTP状态码}{三位业务码}`

示例：

- `400001` — 参数校验失败
- `400002` — 保单状态不允许操作
- `400003` — 请求已被处理（幂等拒绝）
- `500001` — 核心系统服务不可用

### 3.5 接口版本管理

- 版本标识放在 URL 路径中：`/v1/...`、`/v2/...`
- 向下兼容的变更（新增字段、新增可选参数）不需要升级版本
- 不兼容变更必须升级大版本
- 旧版本至少维护 6 个月，提前 3 个月通知调用方

---

## 4. gRPC 规范

### 4.1 .proto 文件规范

```protobuf
syntax = "proto3";

package insurance.underwriting.v1;

service UnderwritingService {
  rpc Evaluate(UnderwritingRequest) returns (UnderwritingResponse);
  rpc QueryDecision(QueryRequest) returns (DecisionResult);
}

message UnderwritingRequest {
  string proposal_no = 1;
  string product_code = 2;
}
```

### 4.2 约定

- 包名格式：`{company}.{domain}.{service}.v{version}`
- 字段编号从 1 开始，预留 1-15 给高频字段
- 使用 `google.protobuf` 提供的 Well-Known Types
- 枚举值首字母大写，使用 `ENUM_NAME_UNSPECIFIED = 0`

---

## 5. 消息队列规范

### 5.1 消息结构

```json
{
  "messageId": "UUID",
  "producer": "underwriting-service",
  "timestamp": 1718000000000,
  "type": "POLICY_ISSUED",
  "version": "1.0",
  "traceId": "UUID",
  "payload": { }
}
```

### 5.2 Topic 命名

```
{domain}.{event_type}.{version}

示例：
underwriting.proposal.submitted.v1
policy.policy.issued.v1
claims.claim.settled.v1
```

### 5.3 消息可靠性

- Producer：发送确认机制（ACK），重试 3 次，超过进死信队列
- Consumer：消费成功后手动 ACK，失败后重试（最多 16 次），超过进死信队列
- 关键消息（账务相关）必须开启事务消息

---

## 6. 接口文档要求

### 6.1 必含内容

1. **接口概述** — 接口用途、涉及系统、业务触发场景
2. **请求说明** — HTTP 方法、URL、Headers、请求体示例
3. **响应说明** — 正常响应、异常响应、错误码列表
4. **字段定义表** — 字段名、类型、长度、必填、说明、枚举值

### 6.2 文档工具

- OpenAPI 3.0 (Swagger) 用于 RESTful API
- Protobuf 文件用于 gRPC
- AsyncAPI 用于事件驱动接口
- 所有接口文档统一托管至接口管理平台

### 6.3 字段定义表模板

| 字段名 | 类型 | 长度 | 必填 | 说明 | 枚举值/示例 |
|-------|------|------|------|------|------------|
| policy_no | String | 20 | Y | 保单号 | P2024000001 |
| premium | Decimal | 18,2 | Y | 保费金额 | 1000.00 |
| status | String | 10 | Y | 保单状态 | ACTIVE/LAPSE/SURRENDER |

---

## 7. 接口评审

### 7.1 评审要点

- [ ] URL 命名符合规范
- [ ] 请求/响应格式统一
- [ ] 错误码覆盖所有异常场景
- [ ] 幂等方案已设计
- [ ] 安全防控（鉴权、防篡改、防重放）
- [ ] 限流方案已定义
- [ ] 接口文档使用工具管理而非 Word
- [ ] 字段变更的兼容性已评估

### 7.2 安全要求

- 所有接口必须通过 OAuth2.0 / JWT 鉴权
- 敏感数据（身份证、手机号、银行卡）传输必须加密
- 核心接口必须开启签名验证
- 防重放：nonce + timestamp 机制
- 限流：按接口 × 渠道 × 调用方进行令牌桶限流

---

## 8. 附录

### 8.1 参考文档
- Google API Design Guide
- OpenAPI 3.0 Specification
- gRPC Best Practices
- 《核心系统数据模型设计规范》

### 8.2 模板
- API 接口文档模板：[内链]
- OpenAPI 示例文件：[内链]
- gRPC proto 文件示例：[内链]
