# src/models/species.py
"""物种相关的数据库操作"""

import json
from ..db_manager import db_manager
from ..utils.serializers import serialize_doc
from ..config import CACHE_EXPIRY


class SpeciesModel:
    """物种数据模型"""
    
    def __init__(self):
        self.db = db_manager.mongo  
        self.mongo_col = db_manager.mongo['species']
        self.neo4j = db_manager.neo4j
        self.redis = db_manager.redis
    
    def add_species(self, name, category, diet, habitat, **extra_fields):
        """添加物种"""
        # 1. 构建文档
        species_doc = {
            "name": name,
            "category": category,
            "diet": diet,
            "habitat": habitat,
            **extra_fields
        }
        
        # 2. MongoDB 插入
        result = self.mongo_col.insert_one(species_doc)
        species_id = str(result.inserted_id)
        
        # 3. Neo4j 创建节点
        with self.neo4j.session() as session:
            session.run(
                "CREATE (s:Species {id: $id, name: $name, category: $category})",
                id=species_id, name=name, category=category
            )
        
        # 4. Redis 缓存
        cache_data = serialize_doc(species_doc)
        cache_data['_id'] = species_id
        self.redis.setex(
            f'species:{species_id}', 
            CACHE_EXPIRY, 
            json.dumps(cache_data)
        )
        
        return species_id
    
    def get_species(self, species_id):
        """获取物种详情（先查缓存）"""
        # 1. 先查 Redis 缓存
        cache_key = f'species:{species_id}'
        cached = self.redis.get(cache_key)
        
        if cached:
            print("🔥 从缓存获取")
            return json.loads(cached)
        
        # 2. 缓存未命中，查 MongoDB
        from bson import ObjectId
        species = self.mongo_col.find_one({'_id': ObjectId(species_id)})
        
        if species:
            # 更新缓存
            cache_data = serialize_doc(species)
            self.redis.setex(cache_key, CACHE_EXPIRY, json.dumps(cache_data))
            return cache_data
        
        return None
    
    def list_species(self, category=None, limit=50):
        """列出物种"""
        query = {'category': category} if category else {}
        species_list = list(self.mongo_col.find(query).limit(limit))
        return [serialize_doc(s) for s in species_list]
    
    def delete_species(self, species_id):
        """删除物种"""
        from bson import ObjectId
        
        # 1. MongoDB 删除
        result = self.mongo_col.delete_one({'_id': ObjectId(species_id)})
        if result.deleted_count == 0:
            return False
        
        # 2. Neo4j 删除节点（DETACH DELETE 会同时删除该节点的所有关系）
        with self.neo4j.session() as session:
            session.run("MATCH (s:Species {id: $id}) DETACH DELETE s", id=species_id)
        
        # 3. Redis 删除缓存
        self.redis.delete(f'species:{species_id}')
        
        return True
    
    def count_species(self):
        """统计物种总数"""
        return self.mongo_col.count_documents({})

    def get_category_stats(self):
        """按分类统计"""
        pipeline = [
            {"$group": {"_id": "$category", "count": {"$sum": 1}}}
        ]
        result = list(self.db.species.aggregate(pipeline))
        return {item['_id']: item['count'] for item in result}
    
    def _ensure_text_index(self):
        """确保全文索引存在（如果不存在则创建）"""
        try:
            # 检查索引是否已存在
            indexes = self.mongo_col.list_indexes()
            index_names = [idx['name'] for idx in indexes]
            
            if 'name_text_description_text' not in index_names:
                # 创建全文索引
                self.mongo_col.create_index([
                    ("name", "text"),
                    ("description", "text"),
                    ("scientific_name", "text")
                ], name='name_text_description_text')
                print("✅ 全文索引创建成功")
        except Exception as e:
            print(f"创建索引时出错（可能已存在）: {e}")
    
    def search_species(self, keyword, limit=50):
        """
        全文搜索物种
        
        Args:
            keyword: 搜索关键词
            limit: 返回数量限制
        
        Returns:
            匹配的物种列表
        """
        # 确保全文索引存在
        self._ensure_text_index()
        
        # 使用 MongoDB 全文搜索
        query = {"$text": {"$search": keyword}}
        
        # 执行搜索，按相关性排序
        cursor = self.mongo_col.find(
            query,
            {"score": {"$meta": "textScore"}}
        ).sort([("score", {"$meta": "textScore"})]).limit(limit)
        
        species_list = list(cursor)
        return [serialize_doc(s) for s in species_list]
    
    def search_by_category(self, category, limit=50):
        """
        按分类搜索物种
        
        Args:
            category: 分类名称（如：哺乳动物、鸟类等）
            limit: 返回数量限制
        
        Returns:
            匹配的物种列表
        """
        query = {"category": {"$regex": category, "$options": "i"}}  # 不区分大小写
        
        species_list = list(self.mongo_col.find(query).limit(limit))
        return [serialize_doc(s) for s in species_list]
    
    def search_by_distribution(self, region, limit=50):
        """
        按地理分布搜索物种
        
        Args:
            region: 地区名称（如：吉林省、东北等）
            limit: 返回数量限制
        
        Returns:
            匹配的物种列表
        """
        # 支持在 distribution 字段中搜索
        query = {
            "$or": [
                {"distribution": {"$regex": region, "$options": "i"}},
                {"habitat": {"$regex": region, "$options": "i"}}
            ]
        }
        
        species_list = list(self.mongo_col.find(query).limit(limit))
        return [serialize_doc(s) for s in species_list]