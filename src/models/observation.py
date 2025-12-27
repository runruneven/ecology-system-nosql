# src/models/observation.py
"""观测记录相关的数据库操作"""

import json
from datetime import datetime, timedelta
from bson import ObjectId
from ..db_manager import db_manager
from ..utils.serializers import serialize_doc


class ObservationModel:
    """观测记录数据模型"""
    
    def __init__(self):
        self.mongo_col = db_manager.mongo['observations']
        self.redis = db_manager.redis
    
    def add_observation(self, species_id, observer, location, count, behavior="", **extra):
        """添加观测记录"""
        # 1. 构建文档
        observation_doc = {
            "species_id": species_id,
            "observer": observer,
            "location": location,
            "count": count,
            "behavior": behavior,
            "timestamp": datetime.now(),
            "verified": False,
            **extra
        }
        
        # 2. MongoDB 插入
        result = self.mongo_col.insert_one(observation_doc)
        observation_id = str(result.inserted_id)
        
        # 3. 可选：使用 redis.xadd 添加到 'observations_stream'
        try:
            stream_data = {
                "observation_id": observation_id,
                "species_id": species_id,
                "timestamp": datetime.now().isoformat()
            }
            self.redis.xadd('observations_stream', stream_data)
        except Exception as e:
            print(f"⚠️ Redis Stream 推送失败: {e}")
        
        return observation_id
    
    def get_observation(self, observation_id):
        """获取观测记录详情"""
        observation = self.mongo_col.find_one({'_id': ObjectId(observation_id)})
        
        if observation:
            return serialize_doc(observation)
        return None
    
    def list_observations(self, species_id=None, limit=50):
        """列出观测记录"""
        query = {}
        if species_id:
            query = {'species_id': species_id}
        
        observations = list(
            self.mongo_col.find(query)
            .sort('timestamp', -1)
            .limit(limit)
        )
        return [serialize_doc(o) for o in observations]
    
    def verify_observation(self, observation_id, expert_id):
        """验证观测记录"""
        self.mongo_col.update_one(
            {'_id': ObjectId(observation_id)},
            {
                '$set': {
                    'verified': True,
                    'verified_by': expert_id,
                    'verified_at': datetime.now()
                }
            }
        )
    
    def get_recent_observations(self, species_id, days=30):
        """获取最近的观测记录"""
        time_threshold = datetime.now() - timedelta(days=days)
        
        query = {
            'species_id': species_id,
            'timestamp': {'$gte': time_threshold}
        }
        
        observations = list(
            self.mongo_col.find(query)
            .sort('timestamp', -1)
        )
        return [serialize_doc(o) for o in observations]
    
    def get_observation_stats(self, species_id):
        """获取观测记录统计"""
        pipeline = [
            {'$match': {'species_id': species_id}},
            {
                '$group': {
                    '_id': None,
                    'total_observations': {'$sum': 1},
                    'total_count': {'$sum': '$count'},
                    'verified_count': {
                        '$sum': {
                            '$cond': [{'$eq': ['$verified', True]}, 1, 0]
                        }
                    }
                }
            }
        ]
        
        result = list(self.mongo_col.aggregate(pipeline))
        if result:
            return result[0]
        return {
            'total_observations': 0,
            'total_count': 0,
            'verified_count': 0
        }
    
    def count_observations(self):
        """统计观测记录总数"""
        return self.mongo_col.count_documents({})

    def get_unverified_observations(self, limit=50):
        """获取待验证的观测记录"""
        return list(self.mongo_col.find({'verified': False}).limit(limit))

    def bulk_verify(self, observation_ids, expert_id):
        """批量验证"""
        self.mongo_col.update_many(
            {'_id': {'$in': [ObjectId(id) for id in observation_ids]}},
            {'$set': {'verified': True, 'verified_by': expert_id}}
        )