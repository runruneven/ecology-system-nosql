# src/db_manager.py
"""统一的数据库连接管理器"""

from pymongo import MongoClient
from neo4j import GraphDatabase
import redis
from .config import MONGO_CONFIG, NEO4J_CONFIG, REDIS_CONFIG


class DatabaseManager:
    """单例模式的数据库管理器"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        # 连接 MongoDB
        self.mongo_client = MongoClient(
            MONGO_CONFIG['host'], 
            MONGO_CONFIG['port']
        )
        self.db = self.mongo_client[MONGO_CONFIG['database']]
        
        # 连接 Neo4j
        self.neo4j_driver = GraphDatabase.driver(
            NEO4J_CONFIG['uri'],
            auth=(NEO4J_CONFIG['user'], NEO4J_CONFIG['password'])
        )
        
        # 连接 Redis
        self.redis_client = redis.Redis(**REDIS_CONFIG)
        
        self._initialized = True
        print("✅ 数据库连接已建立")
    
    def close_all(self):
        """关闭所有数据库连接"""
        self.mongo_client.close()
        self.neo4j_driver.close()
        self.redis_client.close()
        print("✅ 所有数据库连接已关闭")
    
    # 便捷访问方法
    @property
    def mongo(self):
        return self.db
    
    @property
    def neo4j(self):
        return self.neo4j_driver
    
    @property
    def redis(self):
        return self.redis_client


# 创建全局实例
db_manager = DatabaseManager()