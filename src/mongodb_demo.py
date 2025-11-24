# mongodb_demo.py
from pymongo import MongoClient

# 连接到本地MongoDB
client = MongoClient('localhost', 27017)

# 选择数据库（如果不存在会自动创建）
db = client['ecology_db']

# 选择集合（相当于关系数据库的"表"）
species_collection = db['species']

print("MongoDB连接成功！")

#------------------------------------------#
# 插入一条数据
tiger = {
    "name": "东北虎",
    "scientific_name": "Panthera tigris altaica",
    "category": "哺乳动物",
    "conservation_status": "濒危",
    "diet": "肉食",
    "habitat": "温带森林"
}

result = species_collection.insert_one(tiger)
print(f"插入成功！ID: {result.inserted_id}")

# 插入多条数据
animals = [
    {"name": "梅花鹿", "category": "哺乳动物", "diet": "草食"},
    {"name": "野猪", "category": "哺乳动物", "diet": "杂食"},
    {"name": "金雕", "category": "鸟类", "diet": "肉食"}
]

result = species_collection.insert_many(animals)
print(f"插入了 {len(result.inserted_ids)} 条数据")

#------------------------------------------#

# 查询所有数据
print("\n=== 所有物种 ===")
for species in species_collection.find():
    print(species)

# 条件查询（相当于 WHERE）
print("\n=== 肉食动物 ===")
for species in species_collection.find({"diet": "肉食"}):
    print(species['name'])

# 查询一条数据
tiger = species_collection.find_one({"name": "东北虎"})
print(f"\n找到: {tiger['name']}")

# 复杂查询
print("\n=== 濒危的哺乳动物 ===")
result = species_collection.find({
    "category": "哺乳动物",
    "conservation_status": "濒危"
})
for item in result:
    print(item['name'])

#------------------------------------------#
# 更新一条数据
species_collection.update_one(
    {"name": "东北虎"},  # 查找条件
    {"$set": {"weight": "200kg"}}  # 更新内容
)
print("更新成功！")

# 更新多条数据
species_collection.update_many(
    {"diet": "肉食"},
    {"$set": {"danger_level": "高"}}
)

#------------------------------------------#

# 删除一条
species_collection.delete_one({"name": "野猪"})

# 删除多条
species_collection.delete_many({"category": "鸟类"})

# 清空整个集合
# species_collection.delete_many({})  # 慎用！