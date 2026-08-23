#!/bin/bash
# 监控脚本

# 颜色定义
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}=== 研究Agent平台监控 ===${NC}"
echo ""

# 检查服务状态
echo -e "${YELLOW}服务状态:${NC}"
docker-compose ps
echo ""

# 检查健康状态
echo -e "${YELLOW}健康检查:${NC}"
HEALTH=$(curl -s http://localhost:8000/health 2>/dev/null)
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ API服务正常${NC}"
    echo "  $HEALTH"
else
    echo -e "${RED}✗ API服务异常${NC}"
fi
echo ""

# 检查资源使用
echo -e "${YELLOW}资源使用:${NC}"
docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}" 2>/dev/null || echo "无法获取资源信息"
echo ""

# 检查日志错误
echo -e "${YELLOW}最近错误:${NC}"
if [ -f logs/error.log ]; then
    tail -n 5 logs/error.log 2>/dev/null || echo "无错误日志"
else
    echo "无错误日志文件"
fi
echo ""

# 检查磁盘空间
echo -e "${YELLOW}磁盘空间:${NC}"
df -h . 2>/dev/null || echo "无法获取磁盘信息"
echo ""

# 检查数据库连接
echo -e "${YELLOW}数据库状态:${NC}"
docker-compose exec -T db pg_isready -U postgres 2>/dev/null && echo -e "${GREEN}✓ PostgreSQL正常${NC}" || echo -e "${RED}✗ PostgreSQL异常${NC}"

# 检查Redis
echo -e "${YELLOW}Redis状态:${NC}"
docker-compose exec -T redis redis-cli ping 2>/dev/null && echo -e "${GREEN}✓ Redis正常${NC}" || echo -e "${RED}✗ Redis异常${NC}"

echo ""
echo -e "${GREEN}监控完成${NC}"
