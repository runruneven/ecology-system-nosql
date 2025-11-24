# redis_demo.py
import redis
import json

# 连接到本地Redis
r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

print("Redis连接成功！")

# 存储字符串
r.set('user:1:name', '张三')
name = r.get('user:1:name')
print(name)  # 输出: 张三

# 存储带过期时间的数据（3600秒 = 1小时）
r.setex('session:abc123', 3600, 'user_id:1')

# 存储对象（转成JSON）
tiger_info = {
    "name": "东北虎",
    "category": "哺乳动物",
    "weight": "200kg"
}
r.set('species:tiger', json.dumps(tiger_info))

# 读取对象
data = r.get('species:tiger')
tiger = json.loads(data)
print(tiger['name'])

import time

def get_species_info(species_id):
    """
    先查Redis缓存，如果没有再查MongoDB
    """
    # 尝试从缓存获取
    cache_key = f'species:{species_id}'
    cached_data = r.get(cache_key)
    
    if cached_data:
        print("从缓存读取！")
        return json.loads(cached_data)
    
    # 缓存未命中，查询MongoDB
    print("从MongoDB读取...")
    from pymongo import MongoClient
    client = MongoClient('localhost', 27017)
    db = client['ecology_db']
    
    species = db.species.find_one({"_id": species_id})
    
    if species:
        # 存入缓存（1小时过期）
        species['_id'] = str(species['_id'])  # ObjectId转字符串
        r.setex(cache_key, 3600, json.dumps(species))
    
    return species

# 测试
species = get_species_info("some_id")

# 每次访问物种时增加计数
def record_visit(species_name):
    r.zincrby('popular_species', 1, species_name)

# 获取热门物种 TOP 10
def get_popular_species(top_n=10):
    return r.zrevrange('popular_species', 0, top_n-1, withscores=True)

# 使用
record_visit("东北虎")
record_visit("东北虎")
record_visit("梅花鹿")

popular = get_popular_species(5)
print("热门物种:", popular)
# 输出: [('东北虎', 2.0), ('梅花鹿', 1.0)]