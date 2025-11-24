# src/models/relationship.py
"""生态关系相关的数据库操作"""

from ..db_manager import db_manager
from ..utils.serializers import serialize_doc


class RelationshipModel:
    """生态关系数据模型"""
    
    def __init__(self):
        self.mongo_col = db_manager.mongo['relationships']
        self.neo4j = db_manager.neo4j
    
    def create_relationship(self, species1_id, species2_id, rel_type="PREYS_ON", **properties):
        """创建生态关系"""
        # 1. MongoDB 记录
        rel_doc = {
            "species1_id": species1_id,
            "species2_id": species2_id,
            "type": rel_type,
            **properties
        }
        result = self.mongo_col.insert_one(rel_doc)
        
        # 2. Neo4j 创建关系边
        with self.neo4j.session() as session:
            query = f"""
            MATCH (a:Species {{id: $id1}})
            MATCH (b:Species {{id: $id2}})
            MERGE (a)-[r:{rel_type}]->(b)
            RETURN r
            """
            session.run(query, id1=species1_id, id2=species2_id)
        
        return str(result.inserted_id)
    
    def query_food_chain(self, start_id, end_id):
        """查询食物链"""
        with self.neo4j.session() as session:
            result = session.run("""
                MATCH path = shortestPath(
                    (start:Species {id: $start})-[:PREYS_ON*]->(end:Species {id: $end})
                )
                RETURN [node in nodes(path) | {id: node.id, name: node.name}] as chain
            """, start=start_id, end=end_id)
            
            record = result.single()
            return record["chain"] if record else None
        
        
    def count_relationships(self):
        """统计关系总数"""
        with self.neo4j.session() as session:
            result = session.run("MATCH ()-[r]->() RETURN count(r) as count")
            record = result.single()
            return record['count'] if record else 0
    
    def list_relationships(self, rel_type=None, limit=100):
        """列出生态关系"""
        # 构建查询条件
        query = {}
        if rel_type:
            query['type'] = rel_type
        
        # 从 MongoDB 获取关系列表
        relationships = list(self.mongo_col.find(query).limit(limit))
        
        # 序列化并返回
        return [serialize_doc(rel) for rel in relationships]
    
    def delete_relationship(self, relationship_id):
        """删除生态关系"""
        from bson import ObjectId
        
        # 1. 先从 MongoDB 获取关系信息（用于删除 Neo4j 中的关系）
        relationship = self.mongo_col.find_one({'_id': ObjectId(relationship_id)})
        
        if not relationship:
            return False
        
        # 2. 从 MongoDB 删除关系文档
        result = self.mongo_col.delete_one({'_id': ObjectId(relationship_id)})
        
        if result.deleted_count == 0:
            return False
        
        # 3. 从 Neo4j 删除关系边
        species1_id = relationship.get('species1_id')
        species2_id = relationship.get('species2_id')
        rel_type = relationship.get('type', 'PREYS_ON')
        
        with self.neo4j.session() as session:
            # 删除指定类型的关系
            query = f"""
            MATCH (a:Species {{id: $id1}})-[r:{rel_type}]->(b:Species {{id: $id2}})
            DELETE r
            """
            session.run(query, id1=species1_id, id2=species2_id)
        
        return True