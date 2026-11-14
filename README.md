# GongXueYunPass - 工学云/蘑菇丁全自动打卡与报告系统

[![GitHub Actions](https://img.shields.io/badge/GitHub%20Actions-Automated-brightgreen?logo=github-actions)](https://github.com/lele050505/GongXueYunPass/actions)
[![Python](https://img.shields.io/badge/Python-3.9%20%7C%203.10%20%7C%203.11-blue?logo=python)](https://www.python.org/)
[![API Version](https://img.shields.io/badge/API-v6.0-orange)](https://api.moguding.net:9000)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

> 工学云（蘑菇丁）全自动定时打卡、周报月报自动化系统。基于官方最新 **v6.0 API** 深度重构，零成本免服务器部署，支持微信消息合并推送、安全单号管理、代理轮换与多用户多线程并发。

---

## ✨ 核心特性

- 🚀 **官方 v6.0 API 适配**：完整支持工学云最新 v6.0 协议规范，重构滑动验证码识别与 AES-PKCS5 加密签名机制。
- ☁️ **零成本云端自动化**：基于 GitHub Actions 定时执行，无需购买或维护任何服务器，每天准时自动打卡。
- 🛡️ **安全验证单号管理**：支持安全验证单号（`OUT_REGISTER_NO`）自动携带与凭证流转，轻松绕过平台异常安全核验。
- 🌐 **动态/静态代理支持**：支持 `PROXY_URL` 与 `PROXY_API_URL` 环境变量，可选接入优质代理池规避海外 IP 访问限制。
- 👥 **多用户多线程并发**：支持配置单个或任意多个账号，采用多线程并发打卡，高效稳定。
- 📬 **智能消息推送**：深度集成 PushPlus（微信通知）与邮件通知，支持多用户结果合并推送，避免刷屏骚扰。
- 🎯 **灵活打卡控制**：支持环境变量及手动工作流参数精确选择打卡类型（`START` 上班打卡 / `END` 下班打卡）。
- 📍 **高精度定位与微调**：支持经纬度精确设置，并内置坐标随机微小浮动（`randomLocation`）算法，打卡更真实自然。
- 🛑 **防重复打卡保护**：打卡前智能查询当日状态，避免多次打卡造成记录混乱。
- 💻 **双模式运行兼容**：既支持 GitHub Actions 环境变量自动化，又支持本地直接读取 `user.json` 配置进行调试运行。

---

## 🚀 快速上手 (GitHub Actions 推荐)

### 第一步：Fork 本仓库
点击本仓库右上角的 **Fork** 按钮，将项目复制到您自己的 GitHub 账号下。

### 第二步：配置 Secrets 环境变量
进入您 Fork 后的仓库页面：
1. 依次点击顶部导航栏的 **Settings** -> **Secrets and variables** -> **Actions**。
2. 点击绿色的 **New repository secret** 按钮添加以下变量：

| Secret 键名 | 是否必填 | 说明 | 示例值 |
| :--- | :--- | :--- | :--- |
| `USER` | 必选 (或填分散变量) | 完整打卡配置 JSON 数组（推荐） | 见下方配置示例 |
| `PHONE` | 可选 | 手机号（与 PASSWORD 配合代替 USER） | `13800138000` |
| `PASSWORD` | 可选 | 登录密码 | `your_password` |
| `OUT_REGISTER_NO` | 可选 | 安全核验单号（若账号触发安全风控时配置） | `179463...-sign` |
| `PROXY_URL` | 可选 | 静态代理地址 | `http://user:pwd@ip:port` |
| `PROXY_API_URL` | 可选 | 动态代理提取 API | `https://api.proxy.com/get` |

#### `USER` 配置 JSON 格式示例：
```json
[
  {
    "remark": "我的打卡",
    "phone": "13800138000",
    "password": "your_password",
    "province": "广东省",
    "city": "广州市",
    "area": "天河区",
    "address": "广东省 广州市 天河区 某某路 100 号",
    "longitude": "113.324520",
    "latitude": "23.102290",
    "randomLocation": true,
    "enable": true,
    "desc": "日常实习打卡",
    "pushKey": "your_pushplus_token"
  }
]
```

### 第三步：开启 Actions 定时任务
1. 点击仓库顶部的 **Actions** 标签栏。
2. 如页面出现绿色确认按钮（`I understand my workflows, go ahead and enable them`），请点击以启用工作流。
3. 在左侧选择 **GongXueYun Auto CheckIn & Report**，点击右侧的 **Run workflow** -> 选择打卡类型（START / END） -> 点击绿色 **Run workflow** 即可立即执行一次测试！

---

## 💻 本地运行指南

如果您希望在个人电脑或自己的 VPS 服务器上运行：

```bash
# 1. 克隆仓库
git clone https://github.com/lele050505/GongXueYunPass.git
cd GongXueYunPass

# 2. 安装 Python 依赖
pip install -r requirements.txt

# 3. 复制并编辑配置文件
cp user.json.example user.json
# 编辑 user.json 填入您的打卡参数

# 4. 运行打卡脚本
python gongxueyun_auto.py
```

---

## ⏰ 定时调度与打卡时间说明

GitHub Actions 工作流预设了每日两次自动执行（工作流使用 UTC 时间，北京时间需加 8 小时）：
- **上午上班打卡**：北京时间 08:30 左右执行
- **下午下班打卡**：北京时间 17:30 左右执行

> 💡 如需调整时间，可直接编辑 `.github/workflows/clock.yml` 中的 `schedule -> cron` 表达式。

---

## ⚠️ 免责声明

1. 本项目仅供学习交流 Python 网络编程、自动化测试与 GitHub Actions 使用，严禁用于任何商业牟利或非法用途。
2. 使用本项目所造成的一切后果及损失均由使用者自行承担，开发者概不负责。
3. 请自觉遵守国家法律法规及工学云平台使用规范。

---

## 📄 开源许可证

本项目基于 [MIT License](LICENSE) 开源协议分发。
