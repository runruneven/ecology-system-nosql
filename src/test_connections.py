# test_connections.py
from pymongo import MongoClient
from neo4j import GraphDatabase
import redis

# MongoDB
mongo = MongoClient('localhost', 27017)
db = mongo['ecology_db']
print("MongoDB connected!")

# Redis
r = redis.Redis(host='localhost', port=6379, db=0)
r.set('test', 'hello')
print("Redis connected!")

# Neo4j
driver = GraphDatabase.driver("bolt://localhost:7687", 
                               auth=("neo4j", "your_password"))
print("Neo4j connected!")
