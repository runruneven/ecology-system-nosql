# src/models/habitat.py
"""栖息地相关的数据库操作"""

import json
from ..db_manager import db_manager
from ..utils.serializers import serialize_doc
from ..config import CACHE_EXPIRY


class HabitatModel:
    """栖息地数据模型"""
    
    def __init__(self):
        self.db = db_manager.mongo
        self.mongo_col = db_manager.mongo['habitats']
        self.redis = db_manager.redis
    
    def add_habitat(self, name, location, environment, protection_level, area, species_list, **extra_fields):
        """
        添加栖息地
        
        Args:
            name: 栖息地名称
            location: 位置信息（字典，包含 province 和 coordinates）
            environment: 环境信息（字典，包含 climate 和 vegetation）
            protection_level: 保护级别
            area: 面积
            species_list: 物种列表
            **extra_fields: 额外字段
        
        Returns:
            栖息地ID
        """
        # 1. 构建文档
        habitat_doc = {
            "name": name,
            "location": location,
            "environment": environment,
            "protection_level": protection_level,
            "area": area,
            "species_list": species_list if isinstance(species_list, list) else [],
            **extra_fields
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
        """
        获取栖息地详情（先查缓存）
        
        Args:
            habitat_id: 栖息地ID
        
        Returns:
            栖息地数据字典，如果不存在则返回 None
        """
        # 1. 先查 Redis 缓存
        cache_key = f'habitat:{habitat_id}'
        cached = self.redis.get(cache_key)
        
        if cached:
            print("🔥 从缓存获取栖息地")
            return json.loads(cached)
        
        # 2. 缓存未命中，查 MongoDB
        from bson import ObjectId
        habitat = self.mongo_col.find_one({'_id': ObjectId(habitat_id)})
        
        if habitat:
            # 更新缓存
            cache_data = serialize_doc(habitat)
            self.redis.setex(cache_key, CACHE_EXPIRY, json.dumps(cache_data))
            return cache_data
        
        return None
    
    def list_habitats(self, limit=50, protection_level=None):
        """
        列出栖息地
        
        Args:
            limit: 返回数量限制
            protection_level: 按保护级别筛选（可选）
        
        Returns:
            栖息地列表
        """
        query = {}
        if protection_level:
            query['protection_level'] = protection_level
        
        habitats = list(self.mongo_col.find(query).limit(limit))
        return [serialize_doc(h) for h in habitats]
    
    def update_habitat(self, habitat_id, update_data):
        """
        更新栖息地信息
        
        Args:
            habitat_id: 栖息地ID
            update_data: 要更新的数据字典
        
        Returns:
            更新是否成功（布尔值）
        """
        from bson import ObjectId
        
        # 1. MongoDB 更新
        # 移除 _id 字段（如果存在），因为 MongoDB 不允许更新 _id
        update_data = {k: v for k, v in update_data.items() if k != '_id'}
        
        result = self.mongo_col.update_one(
            {'_id': ObjectId(habitat_id)},
            {'$set': update_data}
        )
        
        if result.matched_count == 0:
            return False
        
        # 2. 更新或删除 Redis 缓存
        cache_key = f'habitat:{habitat_id}'
        # 重新查询更新后的数据并更新缓存
        updated_habitat = self.mongo_col.find_one({'_id': ObjectId(habitat_id)})
        if updated_habitat:
            cache_data = serialize_doc(updated_habitat)
            self.redis.setex(cache_key, CACHE_EXPIRY, json.dumps(cache_data))
        else:
            # 如果查询失败，删除缓存
            self.redis.delete(cache_key)
        
        return True
    
    def delete_habitat(self, habitat_id):
        """
        删除栖息地
        
        Args:
            habitat_id: 栖息地ID
        
        Returns:
            删除是否成功（布尔值）
        """
        from bson import ObjectId
        
        # 1. MongoDB 删除
        result = self.mongo_col.delete_one({'_id': ObjectId(habitat_id)})
        if result.deleted_count == 0:
            return False
        
        # 2. Redis 删除缓存
        self.redis.delete(f'habitat:{habitat_id}')
        
        return True
    
    def count_habitats(self):
        """
        统计栖息地总数
        
        Returns:
            栖息地数量
        """
        return self.mongo_col.count_documents({})
    
    def get_protection_level_stats(self):
        """
        按保护级别统计
        
        Returns:
            保护级别统计字典
        """
        pipeline = [
            {"$group": {"_id": "$protection_level", "count": {"$sum": 1}}}
        ]
        result = list(self.db.habitats.aggregate(pipeline))
        return {item['_id']: item['count'] for item in result}

