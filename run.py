"""
项目启动脚本 - 集成数据库监控与自动初始化
"""
import sys
import hashlib
from datetime import datetime
from src.app import app
from src.db_manager import db_manager

def initialize_system():
    """系统初始化：检查连接并创建初始管理员"""
    print("="*50)
    print("🌿 动植物物种生态关系系统 - 启动中...")
    print("="*50)

    # 1. 数据库连通性监控 (对应需求10：系统监控)
    print("🔍 正在检查 NoSQL 数据库状态...")
    try:
        # 检查 MongoDB
        db_manager.mongo.command('ping')
        print("✅ MongoDB 连接正常")
        
        # 检查 Redis
        db_manager.redis.ping()
        print("✅ Redis 连接正常")
        
        # 检查 Neo4j
        with db_manager.neo4j.session() as session:
            session.run("RETURN 1")
        print("✅ Neo4j 连接正常")
    except Exception as e:
        print(f"❌ 数据库连接失败: {str(e)}")
        print("\n提示: 请确保 MongoDB, Redis, Neo4j 服务已全部启动！")
        return False

    # 2. 自动初始化管理员账号 (对应需求9：权限管理)
    print("🔐 正在检查系统账号...")
    users_col = db_manager.mongo['users']
    admin_exists = users_col.find_one({"role": "admin"})
    
    if not admin_exists:
        print("⚠️ 检测到无管理员账号，正在创建默认账号...")
        # 默认密码: admin123
        password_hash = hashlib.sha256("admin123".encode('utf-8')).hexdigest()
        admin_doc = {
            "username": "admin",
            "password_hash": password_hash,
            "role": "admin",
            "name": "系统管理员",
            "active": True,
            "created_at": datetime.now()
        }
        users_col.insert_one(admin_doc)
        print("✅ 默认管理员账号已创建: admin / admin123")
    else:
        print(f"✅ 管理员账号已就绪: {admin_exists['username']}")

    print("="*50)
    return True

if __name__ == '__main__':
    # 先执行初始化检查
    if initialize_system():
        print("🚀 Web 系统已上线: http://127.0.0.1:5002")
        # 启动 Flask 应用
        app.run(debug=True, host='0.0.0.0', port=5002)
    else:
        sys.exit(1)