#!/bin/bash
# 部署脚本

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}=== 研究Agent平台部署脚本 ===${NC}"

# 检查Docker
if ! command -v docker &> /dev/null; then
    echo -e "${RED}错误: 未安装Docker${NC}"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}错误: 未安装Docker Compose${NC}"
    exit 1
fi

# 检查环境变量文件
if [ ! -f .env ]; then
    echo -e "${YELLOW}警告: 未找到.env文件，从模板创建...${NC}"
    cat > .env << EOF
# API配置
OPENAI_API_KEY=your-api-key-here
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4

# 安全配置
SECRET_KEY=$(openssl rand -hex 32)

# 调试模式
DEBUG=false
EOF
    echo -e "${YELLOW}请编辑.env文件配置API密钥${NC}"
fi

# 解析参数
ACTION=${1:-"up"}

case $ACTION in
    "up")
        echo -e "${GREEN}启动服务...${NC}"
        docker-compose up -d
        echo -e "${GREEN}服务已启动${NC}"
        echo -e "访问: http://localhost:8000"
        echo -e "API文档: http://localhost:8000/docs"
        ;;
    "down")
        echo -e "${YELLOW}停止服务...${NC}"
        docker-compose down
        echo -e "${GREEN}服务已停止${NC}"
        ;;
    "restart")
        echo -e "${YELLOW}重启服务...${NC}"
        docker-compose restart
        echo -e "${GREEN}服务已重启${NC}"
        ;;
    "build")
        echo -e "${GREEN}构建镜像...${NC}"
        docker-compose build --no-cache
        echo -e "${GREEN}构建完成${NC}"
        ;;
    "logs")
        docker-compose logs -f
        ;;
    "status")
        docker-compose ps
        ;;
    "update")
        echo -e "${GREEN}更新服务...${NC}"
        git pull
        docker-compose build
        docker-compose up -d
        echo -e "${GREEN}更新完成${NC}"
        ;;
    *)
        echo "用法: $0 {up|down|restart|build|logs|status|update}"
        exit 1
        ;;
esac
