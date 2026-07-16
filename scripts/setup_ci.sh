#!/bin/bash
# 云端会话依赖安装：让 pytest 与 SIL 模式开箱即用。
#
# 由 .claude/settings.json 的 SessionStart 钩子调用。
# - 仅在云端会话执行（本地由开发者自管 venv）。
# - 依赖已装则跳过，降低会话启动延迟。

# 仅云端执行；本地跳过
if [ "$CLAUDE_CODE_REMOTE" != "true" ]; then
  exit 0
fi

# 已装则跳过
if python -c "import transitions, pytest_cov" 2>/dev/null; then
  exit 0
fi

# 安装 SIL 精简依赖 + 测试相关（|| true 避免偶发失败阻塞会话启动）
pip install -q -r requirements_sil.txt || true
pip install -q pytest-cov transitions || true

exit 0
