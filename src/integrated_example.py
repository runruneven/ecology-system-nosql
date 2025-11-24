# integrated_example.py
from pymongo import MongoClient
from neo4j import GraphDatabase
import redis
import json
from bson import ObjectId  # 👈 1. 添加这个导入

# 连接三个数据库
mongo_client = MongoClient('localhost', 27017)
db = mongo_client['ecology_db']
species_col = db['species']

neo4j_driver = GraphDatabase.driver("bolt://localhost:7687", 
                                     auth=("neo4j", "12345678"))

r = redis.Redis(host='localhost', port=6379, decode_responses=True)

# 👇 2. 添加这个序列化函数
def serialize_doc(doc):
    """将 MongoDB 文档转换为可 JSON 序列化的格式"""
    if isinstance(doc, dict):
        return {k: serialize_doc(v) for k, v in doc.items()}
    elif isinstance(doc, list):
        return [serialize_doc(item) for item in doc]
    elif isinstance(doc, ObjectId):
        return str(doc)
    else:
        return doc

def add_species_full(name, category, diet, habitat):
    """
    在MongoDB和Neo4j中同时添加物种
    """
    # 1. MongoDB存储详细信息
    species_doc = {
        "name": name,
        "category": category,
        "diet": diet,
        "habitat": habitat
    }
    result = species_col.insert_one(species_doc)
    species_id = str(result.inserted_id)
    
    # 2. Neo4j创建节点
    with neo4j_driver.session() as session:
        session.run(
            "CREATE (s:Species {name: $name, category: $category})",
            name=name, category=category
        )
    
    # 3. Redis缓存（可选）
    # 👇 3. 修改这里 - 使用序列化函数
    cache_data = serialize_doc(species_doc)
    cache_data['_id'] = species_id  # 添加字符串形式的ID
    r.setex(f'species:{species_id}', 3600, json.dumps(cache_data))
    
    print(f"✅ 物种 '{name}' 添加成功！")
    return species_id

def create_relationship(predator_name, prey_name, rel_type="PREYS_ON"):
    """
    创建生态关系
    """
    with neo4j_driver.session() as session:
        session.run("""
            MATCH (a:Species {name: $pred})
            MATCH (b:Species {name: $prey})
            MERGE (a)-[r:%s]->(b)
            RETURN r
        """ % rel_type, pred=predator_name, prey=prey_name)
    
    print(f"✅ 关系创建: {predator_name} -> {prey_name}")

def query_food_chain(start_species, end_species):
    """
    查询食物链
    """
    with neo4j_driver.session() as session:
        result = session.run("""
            MATCH path = shortestPath(
                (start:Species {name: $start})-[:PREYS_ON*]->(end:Species {name: $end})
            )
            RETURN [node in nodes(path) | node.name] as chain
        """, start=start_species, end=end_species)
        
        record = result.single()
        if record:
            return record["chain"]
    return None

# 使用示例
if __name__ == "__main__":
    # 添加物种
    add_species_full("东北虎", "哺乳动物", "肉食", "温带森林")
    add_species_full("梅花鹿", "哺乳动物", "草食", "森林草原")
    add_species_full("野兔", "哺乳动物", "草食", "草原")
    add_species_full("草", "植物", "自养", "草原")
    
    # 建立关系
    create_relationship("东北虎", "梅花鹿")
    create_relationship("梅花鹿", "草")
    create_relationship("野兔", "草")
    
    # 查询食物链
    chain = query_food_chain("东北虎", "草")
    if chain:
        print(f"\n🔗 食物链: {' → '.join(chain)}")