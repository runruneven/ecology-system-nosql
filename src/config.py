# src/config.py
"""数据库配置"""

# MongoDB配置
MONGO_CONFIG = {
    'host': 'localhost',
    'port': 27017,
    'database': 'ecology_db'
}

# Neo4j配置
NEO4J_CONFIG = {
    'uri': 'bolt://localhost:7687',
    'user': 'neo4j',
    'password': '12345678'
}

# Redis配置
REDIS_CONFIG = {
    'host': 'localhost',
    'port': 6379,
    'decode_responses': True
}

# 缓存过期时间（秒）
CACHE_EXPIRY = 3600