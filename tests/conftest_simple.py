"""
简化的 pytest 配置 - 用于独立运行批量操作测试

跳过复杂的基础设施依赖，专注测试批量操作逻辑
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
