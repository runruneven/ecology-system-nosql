# neo4j_demo.py
from neo4j import GraphDatabase

class Neo4jConnection:
    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
    
    def close(self):
        self.driver.close()
    
    def run_query(self, query, parameters=None):
        with self.driver.session() as session:
            result = session.run(query, parameters)
            return [record for record in result]

# 连接（改成你的密码）
conn = Neo4jConnection("bolt://localhost:7687", "neo4j", "your_password")
print("Neo4j连接成功！")


# 创建物种节点
query = """
CREATE (s:Species {
    name: $name,
    category: $category
})
"""

conn.run_query(query, {
    "name": "东北虎",
    "category": "哺乳动物"
})

# 批量创建
species_list = ["东北虎", "梅花鹿", "野猪", "金雕", "野兔"]
for species_name in species_list:
    query = "CREATE (s:Species {name: $name})"
    conn.run_query(query, {"name": species_name})

print("节点创建成功！")


# 创建捕食关系：老虎 -> 梅花鹿
query = """
MATCH (predator:Species {name: $predator_name})
MATCH (prey:Species {name: $prey_name})
CREATE (predator)-[:PREYS_ON {strength: $strength}]->(prey)
"""

conn.run_query(query, {
    "predator_name": "东北虎",
    "prey_name": "梅花鹿",
    "strength": 0.9
})

# 批量创建食物链
food_chain = [
    ("东北虎", "梅花鹿"),
    ("东北虎", "野猪"),
    ("金雕", "野兔"),
    ("野猪", "植物")
]

for predator, prey in food_chain:
    query = """
    MATCH (a:Species {name: $pred})
    MATCH (b:Species {name: $prey})
    MERGE (a)-[:PREYS_ON]->(b)
    """
    conn.run_query(query, {"pred": predator, "prey": prey})

print("关系创建成功！")


# 查询某物种的猎物
def get_prey(species_name):
    query = """
    MATCH (predator:Species {name: $name})-[:PREYS_ON]->(prey)
    RETURN prey.name as prey_name
    """
    result = conn.run_query(query, {"name": species_name})
    return [record["prey_name"] for record in result]

prey_list = get_prey("东北虎")
print(f"东北虎的猎物: {prey_list}")

# 查询某物种的天敌
def get_predators(species_name):
    query = """
    MATCH (predator)-[:PREYS_ON]->(prey:Species {name: $name})
    RETURN predator.name as predator_name
    """
    result = conn.run_query(query, {"name": species_name})
    return [record["predator_name"] for record in result]

# 查询食物链路径（最短路径）
def find_food_chain(start, end):
    query = """
    MATCH path = shortestPath(
        (start:Species {name: $start})-[:PREYS_ON*]->(end:Species {name: $end})
    )
    RETURN [node in nodes(path) | node.name] as chain
    """
    result = conn.run_query(query, {"start": start, "end": end})
    if result:
        return result[0]["chain"]
    return None

chain = find_food_chain("东北虎", "植物")
print(f"食物链: {' -> '.join(chain)}")

# 查询生态网络（N跳关系）
def get_ecosystem(species_name, depth=2):
    query = """
    MATCH (s:Species {name: $name})-[:PREYS_ON*1..%d]-(related)
    RETURN DISTINCT related.name as species
    """ % depth
    result = conn.run_query(query, {"name": species_name})
    return [record["species"] for record in result]