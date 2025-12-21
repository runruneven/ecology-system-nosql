# src/models/habitat.py
"""栖息地相关的数据库操作"""

import json
from bson import ObjectId
from ..db_manager import db_manager
from ..utils.serializers import serialize_doc
from ..config import CACHE_EXPIRY


class HabitatModel:
    """栖息地数据模型"""
    
    def __init__(self):
        self.mongo_col = db_manager.mongo['habitats']
        self.redis = db_manager.redis
    
    def add_habitat(self, name, location, environment, protection_level, **extra):
        """添加栖息地"""
        # 1. 构建文档
        habitat_doc = {
            "name": name,
            "location": location,
            "environment": environment,
            "protection_level": protection_level,
            "species_ids": [],
            **extra
        }
        
        # 2. MongoDB 插入
        result = self.mongo_col.insert_one(habitat_doc)
        habitat_id = str(result.inserted_id)
        
        # 3. Redis 缓存
        cache_data = serialize_doc(habitat_doc)
        cache_data['_id'] = habitat_id
        self.redis.setex(
            f'habitat:{habitat_id}',
            CACHE_EXPIRY,
            json.dumps(cache_data)
        )
        
        return habitat_id
    
    def get_habitat(self, habitat_id):
        """获取栖息地详情（先查缓存）"""
        # 1. 先查 Redis 缓存
        cache_key = f'habitat:{habitat_id}'
        cached = self.redis.get(cache_key)
        
        if cached:
            return json.loads(cached)
        
        # 2. 缓存未命中，查 MongoDB
        habitat = self.mongo_col.find_one({'_id': ObjectId(habitat_id)})
        
        if habitat:
            # 更新缓存
            cache_data = serialize_doc(habitat)
            self.redis.setex(cache_key, CACHE_EXPIRY, json.dumps(cache_data))
            return cache_data
        
        return None
    
    def list_habitats(self, limit=50):
        """列出栖息地"""
        habitats = list(self.mongo_col.find().limit(limit))
        return [serialize_doc(h) for h in habitats]
    
    def link_species(self, habitat_id, species_id):
        """关联物种到栖息地"""
        # 使用 $addToSet 添加 species_id 到 species_ids 数组
        self.mongo_col.update_one(
            {'_id': ObjectId(habitat_id)},
            {'$addToSet': {'species_ids': species_id}}
        )
        # 删除 Redis 缓存
        self.redis.delete(f'habitat:{habitat_id}')
    
    def get_habitat_species(self, habitat_id):
        """获取栖息地关联的物种ID列表"""
        habitat = self.mongo_col.find_one({'_id': ObjectId(habitat_id)})
        if habitat:
            return habitat.get('species_ids', [])
        return []
    
    def delete_habitat(self, habitat_id):
        """删除栖息地"""
        # 1. MongoDB 删除
        self.mongo_col.delete_one({'_id': ObjectId(habitat_id)})
        
        # 2. Redis 删除缓存
        self.redis.delete(f'habitat:{habitat_id}')
        
        return True
    
    def count_habitats(self):
        """统计栖息地总数"""
        return self.mongo_col.count_documents({})

