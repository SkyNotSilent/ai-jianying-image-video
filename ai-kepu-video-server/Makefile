.PHONY: test test-latest test-all help

# 默认目标
help:
	@echo "剪映兼容性测试工具"
	@echo ""
	@echo "可用命令:"
	@echo "  make test-latest    测试最新生成的项目（最常用）"
	@echo "  make test-all       批量测试所有项目"
	@echo "  make test PROJECT=项目名  测试指定项目"
	@echo ""
	@echo "示例:"
	@echo "  make test-latest"
	@echo "  make test PROJECT=行行出状元"
	@echo "  make test-all"

# 测试最新项目
test-latest:
	@./tests/quick_test.sh

# 测试指定项目
test:
ifdef PROJECT
	@./tests/quick_test.sh $(PROJECT)
else
	@echo "❌ 请指定项目名称: make test PROJECT=项目名"
	@exit 1
endif

# 批量测试所有项目
test-all:
	@source venv/bin/activate && python tests/batch_test_all_drafts.py
