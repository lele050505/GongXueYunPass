# 关键技术决策与技术结论

## 工学云周报/月报接口规范
1. **统一安全签名防拦截**:
   - `infoByStu`、`listByStu`、`getWeeks1` 与 `save` 接口必须在 Headers 中携带 `"sign": create_sign(str(userId) + "student")` 以及 `user-agent`。
   - 若缺失 `sign` 头，工学云 WAF 会直接返回 `{"code":403,"msg":"非法请求，禁止访问:<IP>"}`，导致职位与历史报告信息均被阻断获取。
2. **获取岗位信息**:
   - 接口: `POST /practice/job/v4/infoByStu`
   - 参数: `{"planId": plan_id}`
   - 提取: `data.jobId` 或 `data.id`。提交报告时必须包含 `jobId`，否则报 500 参数有误。
3. **已提交报告查询**:
   - 接口: `POST /practice/paper/v2/listByStu`
   - 参数: `{"planId": plan_id, "reportType": "week", "page": 1, "pageSize": 100}`
   - 响应格式自适应兼容直接 `list` 与分页字典（`list` / `rows` / `records` 等）。
4. **开放周次查询**:
   - 接口: `POST /practice/paper/v3/getWeeks1`
   - 参数: `{"planId": plan_id}`
   - 提取开放的周次范围与周起始时间。
5. **报告保存提交**:
   - 接口: `POST /practice/paper/v5/save`
   - 关键字段:
     - `planId`: 实习计划ID
     - `jobId`: 岗位ID
     - `reportType`: `"week"` 或 `"month"`
     - `title`: 报告标题
     - `content`: 报告正文（不少于200字）
     - `attachments`: `[]`（空数组，不可为字符串 `""`）
     - `formFieldDtoList`: `[]`（空数组）
     - 周报必须含 `weeks`（如 `"第1周"` 或 `1`）
     - 月报必须含 `yearmonth`（如 `"2026-11"`）
