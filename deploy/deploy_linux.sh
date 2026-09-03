#!/usr/bin/env bash
# =============================================================
# 墨题 (English Practice Machine) — Linux 一键部署脚本
# 适用: Ubuntu 20.04+ / Debian 11+ / CentOS 7+ (云服务器 / 机构服务器)
# 用途: 给培训机构/机构买家做服务端私有化部署
#
# 用法:
#   bash deploy_linux.sh                # 交互式(询问域名/端口)
#   AUTH_ENABLED=1 ADMIN_USER=admin \
#     DOMAIN=exam.example.com PORT=8765 \
#     bash deploy_linux.sh              # 非交互(环境变量驱动)
#
# 关于 EPM_AUTH: 墨题默认单用户模式(本地跑)。给机构/多用户部署时
#   务必设 AUTH_ENABLED=1 开启用户隔离 + 设 ADMIN_USER 指定管理员。
# =============================================================
set -euo pipefail

# ---------- 统一日志 ----------
log() { echo -e "\033[1;32m[deploy]\033[0m $*"; }
err() { echo -e "\033[1;31m[deploy-error]\033[0m $*" >&2; }

# ---------- 参数(环境变量可覆盖) ----------
PROJECT_DIR="${PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
VENV_DIR="${VENV_DIR:-$PROJECT_DIR/.venv}"
APP_NAME="${APP_NAME:-epm}"
APP_PORT="${PORT:-8765}"
DOMAIN="${DOMAIN:-}"
AUTH_ENABLED="${AUTH_ENABLED:-0}"          # 1=多用户模式
ADMIN_USER="${ADMIN_USER:-admin}"          # 多用户模式下的管理员用户名
DATA_DIR="${EPM_DATA_DIR:-$PROJECT_DIR/backend/data}"
CERT_MODE="${CERT_MODE:-http}"             # http | https(需DOMAIN)

# ---------- 0. 检查 root ----------
if [ "$(id -u)" -ne 0 ] && [ -n "${WANT_ROOT:-}" ]; then
    err "请用 root 或 sudo 运行（需要装包/写 systemd）"
    exit 1
fi
SUDO=""
[ "$(id -u)" -ne 0 ] && SUDO="sudo"

# ---------- 1. 系统依赖 ----------
log "安装系统依赖 (python3, node, nginx)..."
if command -v apt-get >/dev/null 2>&1; then
    $SUDO apt-get update -qq
    $SUDO apt-get install -y -qq python3 python3-venv python3-pip nginx \
        nodejs npm curl >/dev/null
elif command -v yum >/dev/null 2>&1; then
    $SUDO yum install -y python3 python3-pip nginx nodejs npm curl >/dev/null
else
    err "未识别的包管理器，请手动安装 python3/nodejs/nginx"
fi

# ---------- 2. Python 依赖 ----------
log "创建 venv 并安装后端依赖..."
cd "$PROJECT_DIR"
[ -d "$VENV_DIR" ] || python3 -m venv "$VENV_DIR"
"$VENV_DIR/bin/pip" install --quiet --upgrade pip
"$VENV_DIR/bin/pip" install --quiet -r requirements.txt
# 生产建议: 装 gunicorn(纯uvicorn在单worker下够用, 高并发用gunicorn)
"$VENV_DIR/bin/pip" install --quiet "gunicorn==23.0.0"

# ---------- 3. 前端构建 ----------
log "构建前端 (需要 node >= 18)..."
if [ -d "$PROJECT_DIR/frontend" ]; then
    ( cd "$PROJECT_DIR/frontend" && \
        ( command -v corepack >/dev/null 2>&1 && corepack enable || true ) && \
        npm install --silent && npm run build )
else
    log "未找到 frontend/ 目录，跳过前端构建（使用已打包的 dist）"
fi

# ---------- 4. 数据目录 + 环境 ----------
log "准备数据目录: $DATA_DIR"
mkdir -p "$DATA_DIR/uploads" "$DATA_DIR/question_banks"
chown -R "$(id -un)" "$DATA_DIR" 2>/dev/null || true

# 写入 systemd 需要的环境文件(密钥不含硬编码, 由部署者填)
ENV_FILE="$PROJECT_DIR/deploy/.env.production"
cat > "$ENV_FILE" <<EOF
EPM_DATA_DIR=$DATA_DIR
EPM_FRONTEND_DIST=$PROJECT_DIR/frontend/dist
EPM_AUTH=$AUTH_ENABLED
EPM_ADMIN_USERNAME=$ADMIN_USER
# ===== 请勿在 .env.production 提交仓库 =====
# 若用多用户+AUTH, 建议额外通过环境注入强密码哈希配置。
EOF
chmod 600 "$ENV_FILE"
log "环境文件已写入: $ENV_FILE (含 DATA_DIR/AUTH/ADMIN 配置)"

# ---------- 5. systemd 服务 ----------
log "写入 systemd 服务..."
UNIT="/etc/systemd/system/$APP_NAME.service"
$SUDO tee "$UNIT" > /dev/null <<EOF
[Unit]
Description=MoTi English Practice Machine (backend)
After=network.target

[Service]
Type=simple
User=$(id -un)
WorkingDirectory=$PROJECT_DIR/backend
EnvironmentFile=$ENV_FILE
ExecStart=$VENV_DIR/bin/gunicorn app.main:app \\
    --bind 0.0.0.0:$APP_PORT \\
    --workers 2 \\
    --timeout 120
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF
$SUDO systemctl daemon-reload
$SUDO systemctl enable "$APP_NAME" >/dev/null 2>&1 || true
$SUDO systemctl restart "$APP_NAME"
log "后端服务已启动: systemctl status $APP_NAME"

# ---------- 6. Nginx 反代 ----------
if [ -n "$DOMAIN" ]; then
    log "配置 Nginx 反代 (如仅本机IP访问可跳过, 直接 http://IP:$APP_PORT)"
    CONF="/etc/nginx/sites-available/$APP_NAME"
    LISTEN="80"
    SERVER_NAME="server_name $DOMAIN;"
    $SUDO tee "$CONF" > /dev/null <<EOF
server {
    listen $LISTEN;
    $SERVER_NAME
    client_max_body_size 50m;

    # 前端静态文件
    root $PROJECT_DIR/frontend/dist;
    index index.html;

    # 前端 SPA fallback
    location / {
        try_files \$uri \$uri/ /index.html;
    }

    # 后端 API
    location /api/ {
        proxy_pass http://127.0.0.1:$APP_PORT;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    # 上传文件(听力/图片/音频)
    location /uploads/ {
        alias $DATA_DIR/uploads/;
    }
}
EOF
    if [ -d /etc/nginx/sites-enabled ]; then
        $SUDO ln -sf "$CONF" /etc/nginx/sites-enabled/"$APP_NAME"
        rm -f /etc/nginx/sites-enabled/default
    fi
    $SUDO nginx -t >/dev/null 2>&1 && $SUDO systemctl reload nginx
    log "Nginx 已配置: http://$DOMAIN/  (API: /api/)"
else
    log "未指定 DOMAIN，跳过 Nginx (可通过 http://<服务器IP>:$APP_PORT 访问)"
    log "提示: 生产环境建议配 Nginx 反代 + HTTPS，避免直接暴露 uvicorn/gunicorn"
fi

# ---------- 7. 完成 ----------
log "=============================================="
log "  墨题部署完成!"
log "  后端:  http://<IP>:$APP_PORT"
[ -n "$DOMAIN" ] && log "  前端:  http://$DOMAIN"
log "  数据:  $DATA_DIR"
log "  多用户: $([ "$AUTH_ENABLED" = "1" ] && echo '已开启 (EPM_AUTH=1)' || echo '未开启 (默认单用户, 机构请设 AUTH_ENABLED=1)')"
log "  管理员: $ADMIN_USER (AUTH=1 时有效)"
log "  管理命令: sudo systemctl restart $APP_NAME"
log "  日志:   sudo journalctl -u $APP_NAME -f"
log "😉 部署完成。机构使用请务必: AUTH_ENABLED=1 bash deploy_linux.sh"
log "=============================================="