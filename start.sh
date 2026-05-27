#!/bin/bash
# AI Memory Hub 一键启动脚本

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"
FRONTEND_DIR="$SCRIPT_DIR/frontend"

RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

cleanup() {
    echo ""
    echo -e "${RED}正在关闭服务...${NC}"
    kill $BACKEND_PID 2>/dev/null
    kill $FRONTEND_PID 2>/dev/null
    echo -e "${GREEN}已关闭${NC}"
    exit 0
}

trap cleanup SIGINT SIGTERM

# ── 启动后端 ──
echo -e "${BLUE}[1/2] 启动后端 (FastAPI)...${NC}"
cd "$BACKEND_DIR"

# 检查依赖
if ! python3 -c "import fastapi" 2>/dev/null; then
    echo "安装后端依赖..."
    pip install -r requirements.txt -q
fi

python3 main.py &
BACKEND_PID=$!
sleep 2

if ! kill -0 $BACKEND_PID 2>/dev/null; then
    echo -e "${RED}后端启动失败${NC}"
    exit 1
fi
echo -e "${GREEN}  后端已启动: http://127.0.0.1:8712${NC}"

# ── 启动前端 ──
echo -e "${BLUE}[2/2] 启动前端 (Vite + React)...${NC}"
cd "$FRONTEND_DIR"

# 检查 node_modules
if [ ! -d "node_modules" ]; then
    echo "安装前端依赖..."
    npm install -q
fi

npx vite --host 0.0.0.0 &
FRONTEND_PID=$!
sleep 2

if ! kill -0 $FRONTEND_PID 2>/dev/null; then
    echo -e "${RED}前端启动失败${NC}"
    kill $BACKEND_PID 2>/dev/null
    exit 1
fi
echo -e "${GREEN}  前端已启动: http://localhost:5173${NC}"

# ── 就绪 ──
echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  AI Memory Hub 已就绪${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "  前端:     ${BLUE}http://localhost:5173${NC}"
echo -e "  后端:     ${BLUE}http://127.0.0.1:8712${NC}"
echo -e "  上下文:   ${BLUE}http://localhost:5173/context${NC}"
echo -e "  图谱:     ${BLUE}http://localhost:5173/graph${NC}"
echo ""
echo -e "  按 ${RED}Ctrl+C${NC} 关闭所有服务"
echo ""

wait
