#!/usr/bin/env bash
#
# fix_db_permissions.sh
# 修复 SQLite 数据库文件权限，解决 "attempt to write a readonly database" 错误
#
# 用法:
#   sudo bash fix_db_permissions.sh                    # 默认使用 www-data 用户
#   SERVICE_USER=ubuntu sudo bash fix_db_permissions.sh  # 自定义服务用户
#
# 集成到部署流程:
#   1. 在 systemd 服务 Unit 文件中添加 ExecStartPre:
#      [Service]
#      ExecStartPre=/opt/ai_learning_farm/fix_db_permissions.sh
#      ExecStart=...
#   2. 或在 CI/CD 部署脚本中，在重启服务前执行此脚本
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_USER="${SERVICE_USER:-www-data}"
SERVICE_NAME="knowledgefarm"

echo "============================================"
echo " SQLite 数据库权限修复脚本"
echo " 项目目录: ${SCRIPT_DIR}"
echo " 服务用户: ${SERVICE_USER}"
echo "============================================"
echo ""

# ---- 第1步: 定位数据库文件 ----
echo "[1/5] 定位数据库文件..."

DB_FILE=""
SEARCH_PATHS=(
    "${SCRIPT_DIR}/backend/instance/farm.db"
    "${SCRIPT_DIR}/backend/farm.db"
    "${SCRIPT_DIR}/instance/farm.db"
    "${SCRIPT_DIR}/farm.db"
)

for path in "${SEARCH_PATHS[@]}"; do
    if [ -f "$path" ]; then
        DB_FILE="$path"
        echo "  找到数据库: ${DB_FILE}"
        break
    fi
done

if [ -z "$DB_FILE" ]; then
    echo "  未找到 farm.db，尝试 find 搜索..."
    FOUND=$(find "${SCRIPT_DIR}" -name "*.db" -type f 2>/dev/null | head -5)
    if [ -n "$FOUND" ]; then
        echo "  发现以下 .db 文件:"
        echo "$FOUND" | while read -r f; do echo "    - $f"; done
        DB_FILE=$(echo "$FOUND" | head -1)
        echo "  使用: ${DB_FILE}"
    else
        echo "  [错误] 未找到任何 .db 文件！请确认数据库路径。"
        exit 1
    fi
fi

DB_DIR=$(dirname "$DB_FILE")
echo "  数据库目录: ${DB_DIR}"
echo ""

# ---- 第2步: 修改文件和目录权限 ----
echo "[2/5] 修改权限..."

chmod 666 "$DB_FILE"
echo "  数据库文件权限: $(stat -c '%a' "$DB_FILE" 2>/dev/null || stat -f '%Lp' "$DB_FILE")"

chmod 755 "$DB_DIR"
echo "  数据库目录权限: $(stat -c '%a' "$DB_DIR" 2>/dev/null || stat -f '%Lp' "$DB_DIR")"

# -wal 和 -shm 文件也需要修改
for ext in "-wal" "-shm"; do
    WAL_FILE="${DB_FILE}${ext}"
    if [ -f "$WAL_FILE" ]; then
        chmod 666 "$WAL_FILE"
        echo "  ${ext} 文件权限已修复"
    fi
done
echo ""

# ---- 第3步: 修改文件所有者 ----
echo "[3/5] 检查文件所有者..."

CURRENT_OWNER=$(stat -c '%U' "$DB_FILE" 2>/dev/null || stat -f '%Su' "$DB_FILE")
echo "  当前所有者: ${CURRENT_OWNER}"

if [ "$CURRENT_OWNER" != "$SERVICE_USER" ]; then
    echo "  所有者不是 ${SERVICE_USER}，执行 chown..."
    chown "${SERVICE_USER}:${SERVICE_USER}" "$DB_FILE"
    chown "${SERVICE_USER}:${SERVICE_USER}" "$DB_DIR"

    for ext in "-wal" "-shm"; do
        WAL_FILE="${DB_FILE}${ext}"
        if [ -f "$WAL_FILE" ]; then
            chown "${SERVICE_USER}:${SERVICE_USER}" "$WAL_FILE"
        fi
    done
    echo "  所有者已修改为: ${SERVICE_USER}"
else
    echo "  所有者正确，无需修改"
fi
echo ""

# ---- 第4步: 重启后端服务 ----
echo "[4/5] 重启后端服务..."

if systemctl list-units --type=service | grep -q "$SERVICE_NAME"; then
    systemctl restart "$SERVICE_NAME"
    echo "  服务 ${SERVICE_NAME} 已重启"
    sleep 2
    if systemctl is-active --quiet "$SERVICE_NAME"; then
        echo "  服务状态: 运行中 ✓"
    else
        echo "  [警告] 服务未正常运行，请检查: systemctl status ${SERVICE_NAME}"
    fi
else
    echo "  [提示] 未找到 systemd 服务 ${SERVICE_NAME}，请手动重启后端："
    echo "    cd ${SCRIPT_DIR}/backend && python app.py"
    echo "  或使用 gunicorn:"
    echo "    gunicorn -w 2 -b 0.0.0.0:5000 app:app"
fi
echo ""

# ---- 第5步: 验证数据库可写 ----
echo "[5/5] 验证数据库可写..."

if command -v sqlite3 &>/dev/null; then
    TEST_RESULT=$(sqlite3 "$DB_FILE" "CREATE TABLE IF NOT EXISTS _perm_test(id INTEGER); INSERT INTO _perm_test VALUES(1); SELECT * FROM _perm_test; DROP TABLE _perm_test;" 2>&1)
    if [ $? -eq 0 ]; then
        echo "  数据库读写测试: 通过 ✓"
    else
        echo "  [错误] 数据库读写测试失败: ${TEST_RESULT}"
        echo "  请检查文件权限和所有者是否正确"
        exit 1
    fi
else
    echo "  [提示] sqlite3 命令不可用，跳过验证"
    echo "  安装方法: apt-get install sqlite3"
fi
echo ""

echo "============================================"
echo " 修复完成！"
echo " 数据库: ${DB_FILE}"
echo " 所有者: ${SERVICE_USER}"
echo " 权限: 文件=666 目录=755"
echo "============================================"
