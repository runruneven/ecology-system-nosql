# run.py
"""项目启动脚本"""

import subprocess
import time
import sys
from src.app import app


def check_databases():
    """检查数据库是否运行"""
    print("🔍 检查数据库状态...")
    
    # 这里可以添加数据库连接检查
    # 简化起见，直接启动应用
    
    return True


if __name__ == '__main__':
    if check_databases():
        print("🚀 启动 Web 应用...")
        app.run(debug=True, host='0.0.0.0', port=5002)
    else:
        print("❌ 数据库未启动，请先启动 MongoDB, Neo4j, Redis")
        sys.exit(1)