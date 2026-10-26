.PHONY: help install dev test lint format baseline check-types ci run docker-build docker-run docker-stop clean

help:
	@echo "可用命令:"
	@echo "  make install      - 安装依赖"
	@echo "  make dev          - 安装开发依赖"
	@echo "  make test         - 运行测试"
	@echo "  make test-cov     - 运行测试并生成覆盖率报告"
	@echo "  make lint         - 代码检查（ruff；mypy 请改用 check-types）"
	@echo "  make format       - 代码格式化"
	@echo "  make baseline     - 重新生成 mypy 基线（每合并一批修复后执行）"
	@echo "  make check-types  - mypy 增量校验（改动文件不得上升）"
	@echo "  make ci           - 本地复刻 CI 三条门禁"
	@echo "  make run          - 启动开发服务器"
	@echo "  make docker-build - 构建Docker镜像"
	@echo "  make docker-up    - 启动Docker服务"
	@echo "  make docker-down  - 停止Docker服务"
	@echo "  make docker-logs  - 查看Docker日志"
	@echo "  make clean        - 清理临时文件"

install:
	pip install -r requirements.txt || poetry install

dev:
	pip install -r requirements-dev.txt || poetry install --with dev

test:
	python -m pytest tests/ -v

test-cov:
	python -m pytest tests/ -v --cov=app --cov-report=html --cov-report=term

lint:
	ruff check app tests

format:
	black app tests
	ruff check --fix app tests

# mypy 基线：存量 890 条冻结在 reports/mypy-baseline.txt，只做增量归零。
# 合并任何修复批次后必须重跑 baseline，数字单调不增。
baseline:
	python scripts/gen_mypy_baseline.py

check-types:
	git diff --name-only origin/master...HEAD -- 'app/**/*.py' \
		| python scripts/gen_mypy_baseline.py --check --stdin

ci:
	@echo "=== 1/3 ruff ==="
	@ruff check app
	@echo "=== 2/3 mypy（增量）==="
	@$(MAKE) --silent check-types
	@echo "=== 3/3 pytest ==="
	@python -m pytest -q --no-header

run:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

docker-build:
	docker-compose build

docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

docker-logs:
	docker-compose logs -f

docker-restart:
	docker-compose restart

docker-ps:
	docker-compose ps

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	rm -rf htmlcov/ .coverage 2>/dev/null || true

db-init:
	python -c "from app.core.database import engine, Base; import app.models; Base.metadata.create_all(engine)"

db-migrate:
	alembic revision --autogenerate -m "$(msg)"

db-upgrade:
	alembic upgrade head

db-downgrade:
	alembic downgrade -1
