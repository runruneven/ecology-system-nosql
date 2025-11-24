# src/models/observation.py
"""观测记录相关的数据库操作"""

import json
import time
from datetime import datetime
from ..db_manager import db_manager
from ..utils.serializers import serialize_doc
from ..config import CACHE_EXPIRY


class ObservationModel:
    """观测记录数据模型"""
    
    # Redis Stream 键名
    STREAM_KEY = 'observations:stream'
    
    def __init__(self):
        self.db = db_manager.mongo
        self.mongo_col = db_manager.mongo['observations']
        self.redis = db_manager.redis
    
    def add_observation(self, species_id, observer_info, observation_data, **extra_fields):
        """
        添加观测记录
        
        Args:
            species_id: 物种ID
            observer_info: 观测者信息（字典，包含 name 和 type）
            observation_data: 观测数据（字典，包含 date, location, count, behavior 等）
            **extra_fields: 额外字段
        
        Returns:
            观测记录ID
        """
        from bson import ObjectId
        
        # 1. 获取物种名称（用于显示）
        species = self.db.species.find_one({'_id': ObjectId(species_id)})
        species_name = species.get('name', '未知物种') if species else '未知物种'
        
        # 2. 构建观测记录文档
        obs_doc = {
            "species_id": ObjectId(species_id) if isinstance(species_id, str) else species_id,
            "species_name": species_name,
            "observer": observer_info,
            "observation": observation_data,
            "verified": False,
            "verified_by": None,
            "verified_at": None,
            "created_at": datetime.now(),
            **extra_fields
        }
        
        # 3. MongoDB 插入完整记录
        result = self.mongo_col.insert_one(obs_doc)
        obs_id = str(result.inserted_id)
        
        # 4. Redis Stream 添加实时数据流
        stream_data = {
            'obs_id': obs_id,
            'species_id': species_id,
            'species_name': species_name,
            'observer_name': observer_info.get('name', ''),
            'observer_type': observer_info.get('type', ''),
            'date': observation_data.get('date', ''),
            'location_province': observation_data.get('location', {}).get('province', ''),
            'count': str(observation_data.get('count', 0)),
            'behavior': observation_data.get('behavior', ''),
            'verified': 'false',
            'timestamp': str(int(time.time() * 1000))  # 毫秒时间戳
        }
        
        # 添加到 Redis Stream（自动生成ID）
        self.redis.xadd(self.STREAM_KEY, stream_data)
        
        return obs_id
    
    def list_observations(self, filters=None, limit=50):
        """
        列出观测记录（支持多维度筛选）
        
        Args:
            filters: 筛选条件字典，支持：
                - species_id: 按物种ID筛选
                - species_name: 按物种名称筛选
                - observer_type: 按观测者类型筛选
                - date_from: 开始日期（字符串，格式：YYYY-MM-DD）
                - date_to: 结束日期（字符串，格式：YYYY-MM-DD）
                - location_province: 按省份筛选
                - verified: 是否已验证（布尔值）
            limit: 返回数量限制
        
        Returns:
            观测记录列表
        """
        from bson import ObjectId
        
        # 构建查询条件
        query = {}
        
        if filters:
            # 按物种ID筛选
            if 'species_id' in filters:
                query['species_id'] = ObjectId(filters['species_id'])
            
            # 按物种名称筛选
            if 'species_name' in filters:
                query['species_name'] = {'$regex': filters['species_name'], '$options': 'i'}
            
            # 按观测者类型筛选
            if 'observer_type' in filters:
                query['observer.type'] = filters['observer_type']
            
            # 按日期范围筛选（observation.date 是字符串格式 "YYYY-MM-DD"）
            if 'date_from' in filters or 'date_to' in filters:
                date_query = {}
                if 'date_from' in filters:
                    date_query['$gte'] = filters['date_from']  # 字符串比较，格式：YYYY-MM-DD
                if 'date_to' in filters:
                    date_query['$lte'] = filters['date_to']  # 字符串比较
                if date_query:
                    query['observation.date'] = date_query
            
            # 按省份筛选
            if 'location_province' in filters:
                query['observation.location.province'] = filters['location_province']
            
            # 按验证状态筛选
            if 'verified' in filters:
                query['verified'] = filters['verified']
        
        # 查询并排序（最新的在前）
        observations = list(
            self.mongo_col.find(query)
            .sort('created_at', -1)
            .limit(limit)
        )
        
        return [serialize_doc(obs) for obs in observations]
    
    def verify_observation(self, obs_id, verifier_name):
        """
        标记观测记录为已验证
        
        Args:
            obs_id: 观测记录ID
            verifier_name: 验证者姓名
        
        Returns:
            更新是否成功（布尔值）
        """
        from bson import ObjectId
        from datetime import datetime
        
        # 1. 更新 MongoDB 记录
        result = self.mongo_col.update_one(
            {'_id': ObjectId(obs_id)},
            {
                '$set': {
                    'verified': True,
                    'verified_by': verifier_name,
                    'verified_at': datetime.now()
                }
            }
        )
        
        if result.matched_count == 0:
            return False
        
        # 2. 更新 Redis Stream 中对应的消息（通过添加新消息标记验证状态）
        # 注意：Redis Stream 中的消息是不可变的，我们只能添加新的验证消息
        verification_data = {
            'obs_id': obs_id,
            'action': 'verified',
            'verifier_name': verifier_name,
            'verified_at': datetime.now().isoformat(),
            'timestamp': str(int(time.time() * 1000))
        }
        self.redis.xadd('observations:verifications', verification_data)
        
        return True
    
    def get_recent_observations_stream(self, count=10, start_id=None):
        """
        使用 Redis Stream 获取最近的观测数据流
        
        Args:
            count: 返回的消息数量
            start_id: 起始消息ID（可选，用于分页）
        
        Returns:
            观测数据流列表
        """
        messages = []
        
        try:
            if start_id:
                # 从指定ID开始读取
                stream_messages = self.redis.xread(
                    {self.STREAM_KEY: start_id},
                    count=count,
                    block=0  # 非阻塞模式
                )
            else:
                # 读取最新的消息
                stream_messages = self.redis.xread(
                    {self.STREAM_KEY: '$'},  # '$' 表示只读取新消息
                    count=count,
                    block=0
                )
            
            # 如果没有新消息，尝试读取最新的几条
            if not stream_messages:
                # 使用 XREVRANGE 获取最新的消息
                latest_messages = self.redis.xrevrange(self.STREAM_KEY, count=count)
                
                for msg_id, data in latest_messages:
                    messages.append({
                        'id': msg_id.decode() if isinstance(msg_id, bytes) else msg_id,
                        'data': {k.decode() if isinstance(k, bytes) else k: 
                                v.decode() if isinstance(v, bytes) else v 
                                for k, v in data.items()}
                    })
            else:
                # 解析流消息
                for stream_name, msgs in stream_messages:
                    for msg_id, data in msgs:
                        messages.append({
                            'id': msg_id.decode() if isinstance(msg_id, bytes) else msg_id,
                            'data': {k.decode() if isinstance(k, bytes) else k: 
                                    v.decode() if isinstance(v, bytes) else v 
                                    for k, v in data.items()}
                        })
        
        except Exception as e:
            print(f"读取 Redis Stream 时出错: {e}")
            # 如果 Stream 不存在或出错，返回空列表
        
        return messages
    
    def get_observation(self, obs_id):
        """
        获取单个观测记录详情
        
        Args:
            obs_id: 观测记录ID
        
        Returns:
            观测记录数据字典，如果不存在则返回 None
        """
        from bson import ObjectId
        
        observation = self.mongo_col.find_one({'_id': ObjectId(obs_id)})
        
        if observation:
            return serialize_doc(observation)
        
        return None
    
    def count_observations(self, filters=None):
        """
        统计观测记录总数
        
        Args:
            filters: 筛选条件（与 list_observations 相同）
        
        Returns:
            观测记录数量
        """
        from bson import ObjectId
        
        query = {}
        
        if filters:
            # 复用 list_observations 的查询逻辑
            if 'species_id' in filters:
                query['species_id'] = ObjectId(filters['species_id'])
            if 'species_name' in filters:
                query['species_name'] = {'$regex': filters['species_name'], '$options': 'i'}
            if 'observer_type' in filters:
                query['observer.type'] = filters['observer_type']
            if 'location_province' in filters:
                query['observation.location.province'] = filters['location_province']
            if 'verified' in filters:
                query['verified'] = filters['verified']
        
        return self.mongo_col.count_documents(query)

