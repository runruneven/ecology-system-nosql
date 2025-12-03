# src/models/observation.py
"""观测记录系统相关的数据库操作"""

from datetime import datetime
from bson import ObjectId
from ..db_manager import db_manager
from ..utils.serializers import serialize_doc


class ObservationModel:
    """观测记录数据模型"""
    
    def __init__(self):
        self.mongo_col = db_manager.mongo['observations']
        self.redis = db_manager.redis
        self.species_col = db_manager.mongo['species']
    
    def add_observation(self, species_id, observer_name, observer_type, 
                       observation_date, location, count=1, behavior=None, 
                       photo_url=None, notes=None):
        """
        添加观测记录
        
        Args:
            species_id: 物种ID
            observer_name: 观测者姓名
            observer_type: 观测者类型（科研人员/公众）
            observation_date: 观测日期（字符串，如 "2024-11-26"）
            location: 地理位置 {"province": "吉林省", "city": "长春市", "coordinates": {...}}
            count: 观测到的数量（默认1）
            behavior: 观测到的行为（如：觅食、迁徙、繁殖）
            photo_url: 照片URL（可选）
            notes: 备注信息
        
        Returns:
            str: 观测记录ID
        """
        # 1. 获取物种信息（用于冗余存储，方便查询）
        species = self.species_col.find_one({'_id': ObjectId(species_id)})
        species_name = species['name'] if species else '未知物种'
        
        # 2. 构建观测记录文档
        obs_doc = {
            "species_id": species_id,
            "species_name": species_name,  # 冗余字段，避免每次都要关联查询
            
            # 观测者信息
            "observer": {
                "name": observer_name,
                "type": observer_type  # "科研人员" 或 "公众"
            },
            
            # 观测数据
            "observation": {
                "date": observation_date,
                "location": location,
                "count": count,
                "behavior": behavior or "",
                "photo_url": photo_url or "",
                "notes": notes or ""
            },
            
            # 验证状态
            "verified": False,  # 是否已验证
            "verifier": None,   # 验证者姓名
            "verified_at": None,  # 验证时间
            
            # 时间戳
            "created_at": datetime.now(),
            "updated_at": datetime.now()
        }
        
        # 3. MongoDB 存储（永久保存）
        result = self.mongo_col.insert_one(obs_doc)
        obs_id = str(result.inserted_id)
        
        # 4. Redis Stream 实时推送 ⭐ 核心功能
        try:
            stream_data = {
                "obs_id": obs_id,
                "species_id": species_id,
                "species_name": species_name,
                "observer_type": observer_type,
                "location_province": location.get('province', ''),
                "count": str(count),
                "timestamp": datetime.now().isoformat()
            }
            
            # xadd 是 Redis Stream 的添加命令
            # 'observations:stream' 是 Stream 的名字
            self.redis.xadd('observations:stream', stream_data)
            print(f"✅ 观测记录已推送到实时数据流")
            
        except Exception as e:
            print(f"⚠️ Redis Stream 推送失败: {e}")
            # 即使 Stream 失败，MongoDB 数据已保存，不影响主流程
        
        print(f"✅ 观测记录 '{species_name}' 添加成功")
        return obs_id
    
    def get_observation(self, obs_id):
        """
        获取单个观测记录详情
        
        Args:
            obs_id: 观测记录ID
        
        Returns:
            dict: 观测记录信息
        """
        obs = self.mongo_col.find_one({'_id': ObjectId(obs_id)})
        
        if obs:
            return serialize_doc(obs)
        return None
    
    def list_observations(self, species_id=None, province=None, 
                         verified=None, observer_type=None,
                         start_date=None, end_date=None, 
                         limit=50):
        """
        列出观测记录（支持多维度筛选）
        
        Args:
            species_id: 按物种筛选
            province: 按省份筛选
            verified: 按验证状态筛选（True/False/None）
            observer_type: 按观测者类型筛选
            start_date: 开始日期（字符串）
            end_date: 结束日期（字符串）
            limit: 返回数量限制
        
        Returns:
            list: 观测记录列表
        """
        query = {}
        
        # 构建查询条件
        if species_id:
            query['species_id'] = species_id
        
        if province:
            query['observation.location.province'] = {"$regex": province, "$options": "i"}
        
        if verified is not None:
            query['verified'] = verified
        
        if observer_type:
            query['observer.type'] = observer_type
        
        if start_date or end_date:
            date_query = {}
            if start_date:
                date_query['$gte'] = start_date
            if end_date:
                date_query['$lte'] = end_date
            query['observation.date'] = date_query
        
        # 按时间倒序排列（最新的在前）
        observations = list(
            self.mongo_col.find(query)
            .sort('created_at', -1)
            .limit(limit)
        )
        
        return [serialize_doc(o) for o in observations]
    
    def verify_observation(self, obs_id, verifier_name):
        """
        验证观测记录（专家审核）
        
        Args:
            obs_id: 观测记录ID
            verifier_name: 验证者姓名
        
        Returns:
            bool: 验证是否成功
        """
        result = self.mongo_col.update_one(
            {'_id': ObjectId(obs_id)},
            {
                '$set': {
                    'verified': True,
                    'verifier': verifier_name,
                    'verified_at': datetime.now(),
                    'updated_at': datetime.now()
                }
            }
        )
        
        if result.modified_count > 0:
            print(f"✅ 观测记录 {obs_id} 已验证")
            return True
        return False
    
    def update_observation(self, obs_id, update_data):
        """
        更新观测记录
        
        Args:
            obs_id: 观测记录ID
            update_data: 要更新的数据
        
        Returns:
            bool: 更新是否成功
        """
        update_data['updated_at'] = datetime.now()
        
        result = self.mongo_col.update_one(
            {'_id': ObjectId(obs_id)},
            {'$set': update_data}
        )
        
        return result.matched_count > 0
    
    def delete_observation(self, obs_id):
        """
        删除观测记录
        
        Args:
            obs_id: 观测记录ID
        
        Returns:
            bool: 删除是否成功
        """
        result = self.mongo_col.delete_one({'_id': ObjectId(obs_id)})
        
        if result.deleted_count > 0:
            print(f"✅ 观测记录 {obs_id} 删除成功")
            return True
        return False
    
    def count_observations(self):
        """
        统计观测记录总数
        
        Returns:
            int: 观测记录数量
        """
        return self.mongo_col.count_documents({})
    
    def get_recent_stream_data(self, count=10):
        """
        获取 Redis Stream 中的最近数据
        
        Args:
            count: 获取数量
        
        Returns:
            list: 最近的观测数据流
        """
        try:
            # xrevrange 获取最新的 N 条数据
            # '+' 表示最新，'-' 表示最旧
            # count 指定数量
            stream_data = self.redis.xrevrange(
                'observations:stream', 
                '+', 
                '-', 
                count=count
            )
            
            # 转换为可读格式
            result = []
            for entry_id, data in stream_data:
                result.append({
                    'stream_id': entry_id.decode() if isinstance(entry_id, bytes) else entry_id,
                    'data': {k.decode() if isinstance(k, bytes) else k: 
                            v.decode() if isinstance(v, bytes) else v 
                            for k, v in data.items()}
                })
            
            return result
            
        except Exception as e:
            print(f"⚠️ 获取 Stream 数据失败: {e}")
            return []
    
    def get_statistics(self):
        """
        获取观测记录统计信息
        
        Returns:
            dict: 统计数据
        """
        pipeline = [
            {
                '$group': {
                    '_id': {
                        'species_name': '$species_name',
                        'verified': '$verified'
                    },
                    'count': {'$sum': 1}
                }
            }
        ]
        
        result = list(self.mongo_col.aggregate(pipeline))
        
        # 统计总数
        total = self.mongo_col.count_documents({})
        verified = self.mongo_col.count_documents({'verified': True})
        unverified = self.mongo_col.count_documents({'verified': False})
        
        return {
            'total': total,
            'verified': verified,
            'unverified': unverified,
            'by_species': result
        }