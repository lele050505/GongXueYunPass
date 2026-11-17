# 🎓 GongXueYunPass - 工学云全自动打卡与周月报提交系统

[![GitHub Actions](https://img.shields.io/badge/GitHub%20Actions-Automated-green.svg)](https://github.com/lele050505/GongXueYunPass/actions)
[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-orange.svg)](LICENSE)
[![Release](https://img.shields.io/badge/release-v1.0.0-brightgreen.svg)](https://github.com/lele050505/GongXueYunPass/releases)

> 🚀 **全面适配工学云（蘑菇钉）最新 v6.0 API**，支持上下班打卡智能识别、自动补交周报与月报、304 安全风控智能感知、多渠道消息通知，支持 **GitHub Actions 云端全自动** 与 **Windows 本地静默定时任务**。

---

## 🌟 核心功能特性

- **⚡ 完整支持最新官方接口**：适配工学云/蘑菇钉 `v6.0` 协议，采用 OpenCV 智能算法识别滑动拼图验证码与 AES 加密鉴权。
- **⏰ 智能上下班识别与手动调度**：
  - 自动识别上下班时间段（默认以 17:00 为界），也可在 GitHub Actions 界面下拉选择 `START`（上班）或 `END`（下班）按需手动触发。
- **📝 周报 & 月报全自动提交**：打卡同时自动检测并提交未交的实习周报与月报，省心无忧。
- **🛡️ 304 安全风控与支付宝核验直通**：
  - 针对异地/海外 IP 触发的 304 安全风控，系统能自动生成并捕获支付宝实名核验链接与单号，方便手机一键扫码核验。
- **🌐 灵活的网络环境适配**：
  - 支持直接连接（直连 9000 端口）；
  - 支持配置国内高匿代理（`PROXY_URL` 或 `PROXY_API_URL`）避开异地拦截。
- **💻 双模自动化部署方案**：
  - **云端模式**：直接通过 GitHub Actions 工作流定时触发，0 设备依赖；
  - **本地模式**：支持 Windows 系统计划任务后台静默运行，使用本地真实网络打卡，永无异地风控。
- **📢 多通道消息推送**：支持 Gmail/QQ/163 邮箱通知、Server酱、PushPlus 等主流通知渠道。

---

## 🚀 快速上手部署

### 方案一：GitHub Actions 云端全自动（推荐）

无需自备服务器，直接利用 GitHub Actions 定时执行：

#### 1. Fork 本仓库并开启 Actions
- 点击右上角 **Fork** 将本仓库复制到你的账号下；
- 进入 Fork 后的仓库，点击顶部导航栏的 **Actions**，点击绿色按钮开启工作流功能。

#### 2. 配置 Repository Secrets
进入仓库的 **Settings** -> **Secrets and variables** -> **Actions**，点击 **New repository secret** 添加以下配置：

| Secret 键名 | 是否必填 | 说明 | 示例 |
| :--- | :--- | :--- | :--- |
| `PHONE` | **必填** | 工学云登录手机号 | `17887874506` |
| `PASSWORD` | **必填** | 工学云登录密码 | `Jule0523` |
| `PROVINCE` | **必填** | 打卡所在省份 | `陕西省` |
| `CITY` | **必填** | 打卡所在城市 | `咸阳市` |
| `AREA` | **必填** | 打卡所在区/县 | `兴平市` |
| `ADDRESS` | **必填** | 打卡详细地址描述 | `兴平市永东包装有限公司` |
| `LONGITUDE` | **必填** | 经度（精确到后6位） | `108.432481` |
| `LATITUDE` | **必填** | 纬度（精确到后6位） | `34.270681` |
| `DESCRIPTION`| 选填 | 打卡备注/签到描述 | `日常实习上班` |
| `OUT_REGISTER_NO` | 选填 | 支付宝人脸核验通过单号（若遇304时填入） | `179463...-sign` |
| `PROXY_URL` | 选填 | 国内 HTTP 代理（用于绕过海外机房风控） | `http://user:pwd@ip:port` |
| `SMTP_PASSWORD` | 选填 | 邮箱授权码（配置后打卡结果邮件直达） | `your_smtp_app_password` |

#### 3. 手动触发与定时测试
1. 进入仓库的 **Actions** 标签页；
2. 在左侧选择 **`GongXueYun Auto CheckIn & Report`**；
3. 点击右侧 **`Run workflow`**，选择打卡类型（`START` 或 `END`），点击绿色按钮立即运行；
4. 运行完成后可在查看运行日志和回执信息。
5. 默认定时时间：工作日每天早上 08:30（上班）与下午 18:00（下班）自动执行。

---

### 方案二：本地 Windows 全自动静默打卡（100% 同城原生 IP）

如果你希望使用本地电脑打卡，直接走本地宽带原生 IP，完全免去异地人脸拦截：

#### 1. 克隆代码并安装依赖
```bash
git clone https://github.com/lele050505/GongXueYunPass.git
cd GongXueYunPass
pip install -r requirements.txt
```

#### 2. 填写本地配置 `user.json`
复制 `user.json.example` 为 `user.json` 并填入个人信息：
```json
[
  {
    "remark": "我的打卡",
    "phone": "17887874506",
    "password": "你的密码",
    "province": "陕西省",
    "city": "咸阳市",
    "area": "兴平市",
    "address": "兴平市永东包装有限公司",
    "longitude": "108.432481",
    "latitude": "34.270681",
    "randomLocation": true,
    "enable": true,
    "desc": "实习打卡"
  }
]
```

#### 3. 一键运行与定时计划
- **手动运行**：直接执行 `python gongxueyun_auto.py --mode auto`。
- **定时任务**：可通过 Windows 任务计划程序添加 `run_task.ps1`，设定每天固定时间后台静默执行，错失开机后自动补打。

---

## ❓ 常见问题与排错指南 (FAQ)

### Q1: 运行日志提示 `304 平台监测到您的账户存在风险操作`？
- **原因**：工学云服务端对海外 IP（如 GitHub Actions 所在的微软 Azure 美国机房）或机房代理设有风控，会拦截打卡并要求支付宝实名核验。
- **解决**：
  1. 日志中会自动输出支付宝核验直跳链接与单号，复制链接或扫描生成的二维码在手机支付宝中刷脸核验；
  2. 核验通过后，将核验单号填入 GitHub Secrets 的 `OUT_REGISTER_NO`；
  3. 或者直接在 Secrets 配置国内住宅/高匿代理 `PROXY_URL`。

### Q2: 报错 `Failed to establish a new connection: [Errno 101] Network is unreachable: api.moguding.net:9000`？
- **原因**：工学云使用的是非标 **9000 端口**。部分免费代理服务器会拦截非 80/443 的高位端口连接。请确保所使用的网络或代理开放了 9000 端口通信。

### Q3: 为什么同一天的单号第二次使用提示 `验证已过期`？
- **原因**：工学云服务端的支付宝安全验证单号为**一次性核销令牌**，当成功完成一次打卡后该单号即被核销失效。下一次打卡若再次触发风控需获取新单号。

---

## 📄 免责声明

1. 本项目仅供学习、研究 Python 爬虫、自动化测试及 GitHub Actions 流程编排使用。
2. 请遵守所在高校与实习单位的相关考勤管理制度，合理合规使用，因违规使用造成的任何后果由使用者本人承担。
3. 本项目严禁用于商业牟利及非法用途。

---

## 🤝 致谢与贡献

- 感谢开源社区对工学云/蘑菇钉 API 协议逆向与加解密算法研究的先驱贡献者。
- 欢迎提交 Issue 与 Pull Request 共同改进！
