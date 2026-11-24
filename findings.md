# 关键技术决策与技术结论

## 历史周报/月报补齐与参数规范
1. **统一安全签名防拦截**:
   - `infoByStu`、`getWeeks1` 必须在 Headers 中携带 `"sign": create_sign(str(userId) + "student")` 以及 `user-agent`。
2. **蘑菇丁/工学云报告 API 逆向核心突破**:
   - **时间戳加密强校验**: 所有报告接口（`listByStu`、`v5/save` 等）的请求体中必须携带毫秒时间戳的密文 `t`。加密算法为 AES-128-ECB PKCS7，密匙为 `23DbtQHR2UMbH6mJ`，输出为 16 进制 hex 字符串。若缺失或明文，后端抛出 `500 参数有误`。
   - **官方请求头签名规则**:
     - 提交报告: `create_sign(str(userId), reportType, planId, title)`（严格对应 body 里的 title）
     - 备选签名: `create_sign(str(userId), reportType, planId, "报告")`
     - 查询历史报告: `create_sign(str(userId), "student", reportType)`
   - **双保存通道**: 优先走 `v5/save`，备用走 `v2/save`，自适应覆盖多套高校后台模板。
3. **用户实际历史锚点与补交清单**:
   - 周报已填报至第 14 周（`2026-10-19` 至 `2026-10-25`）；
   - 待补齐周次列表（时间正序）：
     - 第 15 周：`2026-10-26` ~ `2026-11-01`
     - 第 16 周：`2026-11-02` ~ `2026-11-08`
     - 第 17 周：`2026-11-09` ~ `2026-11-15`
     - 第 18 周：`2026-11-16` ~ `2026-11-22`
     - 第 19 周：`2026-11-23` ~ `2026-11-29`（当前活跃周）
   - 月报已填报至 9 月，待补齐：10 月份月报（`2026-10`）与 11 月份月报（`2026-11`）。
4. **关键参数与字数**:
   - 正文字数充实至 350~500 字（周报）和 550~700 字（月报），满足高校后台严格字数校验；
   - 携带 `jobId`、`studentId`、`startTime` 与 `endTime`，支持高校标准三段式（content, summary, plan）。

## 周报问卷调查接口与结构调研（2026-11-24）
1. **问卷模板拉取接口**:
   - `POST /practice/paper/v2/info`，参数 `{"formType": formType, "t": aes_encrypt(ms)}`（`7`=日报、`8`=周报、`9`=月报），Header 携带标准学生签名。
   - 实测结果：
     - 周报（`formType=8`）：学校（陕西职业技术学院）启用了「问卷式周报系统默认模板」，共 **7 道单选题**（工作强度、工作内容熟悉度、企业导师指导、工作环境评价、情绪状态、同事相处、自我评价）。
     - 每题 `optionEntity[0].opt` 均为 `"a"`（最积极/正常评价），系统预警项 `warningSetValue` 均设在 `"d"`，全选第一个选项零预警风险。
     - 月报（`formType=9`）和日报（`formType=7`）的 `formFieldDtoList` 均为空数组 `[]`，无问卷。
2. **已提交报告问卷状态对比**:
   - 用户手填第 14 周（`reportId=2455186846f4308ef0c2ae0549e37f8c`）：`fieldEntityList` 含 7 题，值全部为 `"a"`。
   - 刚自动补交的第 15~19 周（5 篇，均处于 `state=0` 待批阅状态）：`fieldEntityList` 均为 `null`（缺失问卷）。
   - 月报 10 月、11 月均已入库且无需问卷。
3. **保存接口与字段要求**:
   - 最新保存接口为 `POST /practice/paper/v6/save`（签名同 `v5/save`：`create_sign(userId, reportType, planId, title)`），需同时提交 `formFieldDtoList` 与 `fieldEntityList`。
4. **现存代码隐患**:
   - `modules/report_manager.py` 当前写死了从 `2026-10-26` / 第 15 周开始提交，未基于 `listByStu` 做已提交周次/月份的动态去重，若不优化则在下次日常打卡时会重复提交已入库的周报和月报。
