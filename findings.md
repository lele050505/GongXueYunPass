# 关键技术决策与技术结论

## 工学云周报/月报接口规范
1. **获取岗位信息**:
   - 接口: `POST /practice/job/v4/infoByStu`
   - 参数: `{"planId": plan_id}`
   - 提取: `data.jobId` 或 `data.id`。提交报告时必须包含 `jobId`，否则报 500 参数有误。
2. **已提交报告查询**:
   - 接口: `POST /practice/paper/v2/listByStu`
   - 参数: `{"planId": plan_id, "reportType": "week", "page": 1, "pageSize": 100}`
   - 响应格式可能为直接 `list` 或分页字典 `{"list": [...]}` / `{"rows": [...]}`，需做自适应解析。
3. **开放周次查询**:
   - 接口: `POST /practice/paper/v3/getWeeks1`
   - 参数: `{"planId": plan_id}`
   - 提取开放的周次范围与周起始时间。
4. **报告保存提交**:
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
