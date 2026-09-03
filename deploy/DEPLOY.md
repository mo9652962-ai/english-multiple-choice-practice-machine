# 墨题 (English Practice Machine) 部署文档

> 版本: v2.0.0+ · 更新: 2026-09-03 · 适用: 培训机构 / 机构买家 / 云服务器私有化部署

本文档用于将墨题部署到 **Linux 云服务器** 或 **Windows 服务器/本机**，并提供多用户（机构）模式、HTTPS、备份等生产配置。部署脚本位于 `deploy/` 目录。

---

## 一、快速开始（30 秒看这里）

| 场景 | 命令 |
|:---|:---|
| **Linux 服务器部署**（推荐） | `AUTH_ENABLED=1 ADMIN_USER=admin DOMAIN=exam.your.com bash deploy/deploy_linux.sh` |
| Windows 服务器/本机 | 双击 `deploy/deploy_windows.bat` |
| 部署后访问 | `http://<服务器IP>:8765` 或 `http://<域名>` |
| 查看状态/日志 | `systemctl status epm` / `journalctl -u epm -f` |

**⚠️ 机构（多用户）部署必须加 `AUTH_ENABLED=1`**，否则默认单用户模式，用户之间数据不隔离。

---

## 二、环境要求

| 组件 | 版本 | 说明 |
|:---|:---|:---|
| Linux | Ubuntu 20.04+ / Debian 11+ / CentOS 7+ | 推荐 Ubuntu 22.04 LTS |
| Windows | 10 / Server 2016+ | 需安装 Python 3.12 + Node 18+ |
| Python | 3.10–3.12 | 3.12 推荐 |
| Node.js | 18+ | 仅构建前端需要 |
| Nginx | 任意新版本 | Linux 生产反代用（脚本自动装）|
| SQLite | 内置 | 无需额外安装，数据在 `backend/data/question_bank.db` |
| 服务器配置 | 2 核 2G 起 | 100 并发内够用；AI 功能需外接 API |

---

## 三、Linux 一键部署（详细）

### 3.1 上传代码

```bash
# 方式A: 从 Git 拉取（有源码仓库）
git clone <你的仓库地址> /opt/epm && cd /opt/epm

# 方式B: 打包上传
# 本地压缩后 scp 到服务器
scp -r /d/english-multiple-choice-practice-machine user@server:/opt/epm
```

### 3.2 一键部署（交互式）

```bash
cd /opt/epm
bash deploy/deploy_linux.sh
```

脚本自动完成：系统依赖 → Python venv → 后端依赖 → 前端构建 → 数据目录 → systemd 服务 → Nginx 反代。

### 3.3 一键部署（非交互/多用户模式，机构推荐）

```bash
cd /opt/epm
AUTH_ENABLED=1 ADMIN_USER=admin \
DOMAIN=exam.your.com \
PORT=8765 \
bash deploy/deploy_linux.sh
```

| 环境变量 | 默认 | 说明 |
|:---|:---|:---|
| `AUTH_ENABLED` | `0` | `1` = 开启多用户隔离（机构必须）|
| `ADMIN_USER` | `admin` | 管理员用户名（AUTH=1 时第一个注册该用户名的账号成为管理员）|
| `DOMAIN` | 空 | 配置 Nginx 反代域名；留空则直接 IP:端口访问 |
| `PORT` | `8765` | 后端端口 |
| `EPM_DATA_DIR` | `backend/data` | 数据目录（数据库/上传文件）|

### 3.4 部署后验证

```bash
# 服务状态
systemctl status epm
# 日志
journalctl -u epm -f
# API 健康检查
curl http://127.0.0.1:8765/api/version
# 前端访问（有域名时）
curl -I http://exam.your.com
```

---

## 四、Windows 部署（本机/内网）

1. 安装 [Python 3.12](https://www.python.org/downloads/)（勾选 Add to PATH）和 [Node.js 18+](https://nodejs.org/)
2. 双击 `deploy/deploy_windows.bat`
3. 启动后端：
   ```bat
   cd backend
   ..\.venv\Scripts\uvicorn app.main:app --host 0.0.0.0 --port 8765
   ```
4. 浏览器访问 `http://localhost:8765`

> Windows 生产建议：用 NSSM 把 uvicorn 注册为 Windows 服务（开机自启）。脚本内置提示，不强制。

---

## 五、生产配置（重要）

### 5.1 多用户/机构模式（AUTH=1）

开启后：
- 用户注册/登录，数据按用户隔离（练习、错题、考试、证书、AI 对话）
- 匿名用户（未登录）可做题但不保存进度
- 管理员用户名由 `EPM_ADMIN_USERNAME` 指定，**注册该用户名的人自动成为管理员**
- 管理端接口（题库管理/试卷删除等）受 `require_admin` 保护

```bash
# 修改配置后重启
AUTH_ENABLED=1 ADMIN_USER=admin bash deploy/deploy_linux.sh   # 重跑会更新 systemd 环境文件
sudo systemctl restart epm
```

### 5.2 HTTPS（证书加密）

有域名后建议启用 HTTPS：

```bash
# 用 certbot 自动申请 Let's Encrypt 证书
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d exam.your.com
# certbot 会自动改 Nginx 配置并配 HTTPS + 自动续期
```

### 5.3 数据备份（必须）

数据库在 `backend/data/question_bank.db`，定期备份：

```bash
# 每日凌晨 2 点备份（crontab -e 添加）
0 2 * * * cp /opt/epm/backend/data/question_bank.db /opt/epm/backend/data/backups/question_bank_$(date +\%Y\%m\%d).db
# 保留最近 30 份
0 2 * * * find /opt/epm/backend/data/backups -name "question_bank_*.db" -mtime +30 -delete
```

> 墨题启动时也会自动备份（`backend/data/backups/`），但定期备份仍是第一道防线。

### 5.4 更新升级

```bash
cd /opt/epm
git pull                          # 拉新代码
bash deploy/deploy_linux.sh       # 重跑（依赖/前端/服务自动更新）
sudo systemctl restart epm
```

升级前建议先备份数据库。数据库迁移（新增表/字段）在应用启动时自动执行，无需手工操作。

---

## 六、企业版功能（v9.40+）

本次部署包含三大企业功能，全部通过 API 使用：

### 6.1 动态组卷

| 接口 | 方法 | 说明 |
|:---|:---|:---|
| `/api/papers/generate` | POST | 按题型×数量从题库随机抽题组卷 |
| `/api/papers/generated` | GET | 列出已生成试卷 |

```json
// POST /api/papers/generate
{
  "title": "高三月考卷",
  "profile_id": 2,
  "types": {"single_choice": 15, "multiple_choice": 5},
  "randomize": true,
  "pass_score": 60
}
```

### 6.2 防作弊

| 接口 | 方法 | 说明 |
|:---|:---|:---|
| `/api/exams/{id}/anti-cheat` | POST | 记录切屏/复制/粘贴/失焦等异常事件 |
| `/api/exams/{id}/anti-cheat` | GET | 查询考试异常记录（管理端）|

事件类型：`screen_switch`（切屏）、`suspend`（挂起）、`copy`/`paste`（复制粘贴）、`window_blur`（失焦）、`inactivity`（长时间无操作）。服务端记录 + 返回累计违规次数，前端可据此决定提示或强制交卷。

### 6.3 证书

| 接口 | 方法 | 说明 |
|:---|:---|:---|
| `/api/certificates` | GET | 我的证书列表 |
| `/api/certificates/{cert_no}` | GET | 证书详情 |
| `/api/certificates/verify/{cert_no}` | GET | 证书真伪校验（无需登录，可对外）|

考试交卷时若正确率 ≥ pass_score（默认 60%），自动生成电子证书（编号唯一、可校验真伪、等级优秀/良好/合格）。

---

## 七、常见问题（FAQ）

| 问题 | 解决 |
|:---|:---|
| 访问不了 | 防火墙放行 8765 端口：`sudo ufw allow 8765`；云服务器安全组也要放行 |
| 前端 404 / 白屏 | 确认 `frontend/dist` 已构建；Nginx `try_files $uri /index.html` 已配置 |
| 上传题目/听力失败 | Nginx `client_max_body_size 50m` 已设；确认 `backend/data/uploads` 可写 |
| 忘记管理员密码 | 直接改数据库：`sqlite3 backend/data/question_bank.db "UPDATE users SET password_hash='<新hash>' WHERE username='admin'"`（哈希算法见 `auth.py`，或删用户重新注册）|
| AI 功能报错 | 检查外接 AI API Key 配置；AI 功能依赖第三方 API，网络需可达 |
| 升级后数据丢失 | 先备份再升级；数据库文件路径确认是 `backend/data/question_bank.db`（非打包版路径）|

---

## 八、目录速览

```
deploy/
├── deploy_linux.sh      # Linux 一键部署
├── deploy_windows.bat   # Windows 一键部署
└── .env.production      # 生产环境配置（部署时自动生成）
backend/
├── app/main.py          # FastAPI 入口
├── app/database.py      # SQLite 建表/迁移
├── data/                # 数据库 + 上传文件
└── data/backups/        # 自动备份
frontend/dist/           # 前端构建产物
```
