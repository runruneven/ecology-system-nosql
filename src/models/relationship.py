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
    
    def get_relationship(self, relationship_id):
        """
        获取单个生态关系详情
        
        Args:
            relationship_id: 关系ID
        
        Returns:
            关系数据字典，如果不存在则返回 None
        """
        from bson import ObjectId
        
        relationship = self.mongo_col.find_one({'_id': ObjectId(relationship_id)})
        
        if relationship:
            return serialize_doc(relationship)
        
        return None
    
    def update_relationship(self, relationship_id, update_data):
        """
        更新生态关系信息
        
        Args:
            relationship_id: 关系ID
            update_data: 要更新的数据字典
        
        Returns:
            更新是否成功（布尔值）
        """
        from bson import ObjectId
        
        # 1. 先从 MongoDB 获取原始关系信息
        original_relationship = self.mongo_col.find_one({'_id': ObjectId(relationship_id)})
        
        if not original_relationship:
            return False
        
        # 2. 移除 _id 字段（如果存在），因为 MongoDB 不允许更新 _id
        update_data = {k: v for k, v in update_data.items() if k != '_id'}
        
        # 3. MongoDB 更新
        result = self.mongo_col.update_one(
            {'_id': ObjectId(relationship_id)},
            {'$set': update_data}
        )
        
        if result.matched_count == 0:
            return False
        
        # 4. 如果更新了关系类型或物种ID，需要更新 Neo4j
        old_type = original_relationship.get('type', 'PREYS_ON')
        old_species1_id = original_relationship.get('species1_id')
        old_species2_id = original_relationship.get('species2_id')
        
        new_type = update_data.get('type', old_type)
        new_species1_id = update_data.get('species1_id', old_species1_id)
        new_species2_id = update_data.get('species2_id', old_species2_id)
        
        # 如果关系类型或物种ID发生变化，需要更新 Neo4j
        if (new_type != old_type or 
            new_species1_id != old_species1_id or 
            new_species2_id != old_species2_id):
            
            with self.neo4j.session() as session:
                # 删除旧的关系边
                delete_query = f"""
                MATCH (a:Species {{id: $id1}})-[r:{old_type}]->(b:Species {{id: $id2}})
                DELETE r
                """
                session.run(delete_query, id1=old_species1_id, id2=old_species2_id)
                
                # 创建新的关系边
                create_query = f"""
                MATCH (a:Species {{id: $id1}})
                MATCH (b:Species {{id: $id2}})
                MERGE (a)-[r:{new_type}]->(b)
                RETURN r
                """
                session.run(create_query, id1=new_species1_id, id2=new_species2_id)
        
        # 5. 如果只是更新了其他属性（如 description），更新 Neo4j 边的属性
        elif update_data:
            # 提取需要更新到 Neo4j 的属性（排除 species_id 和 type）
            neo4j_properties = {
                k: v for k, v in update_data.items() 
                if k not in ['species1_id', 'species2_id', 'type']
            }
            
            if neo4j_properties:
                with self.neo4j.session() as session:
                    # 构建 SET 子句
                    set_clauses = ', '.join([f"r.{k} = ${k}" for k in neo4j_properties.keys()])
                    update_query = f"""
                    MATCH (a:Species {{id: $id1}})-[r:{old_type}]->(b:Species {{id: $id2}})
                    SET {set_clauses}
                    RETURN r
                    """
                    params = {'id1': old_species1_id, 'id2': old_species2_id, **neo4j_properties}
                    session.run(update_query, **params)
        
        return True
    
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