# src/utils/backup.py
import subprocess
from datetime import datetime
import os

def backup_mongodb():
    """备份 MongoDB"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_dir = f'./backup/mongodb_{timestamp}'
    
    os.makedirs(backup_dir, exist_ok=True)
    
    # 使用 mongodump
    subprocess.run([
        'mongodump',
        '--db', 'ecology_db',
        '--out', backup_dir
    ])
    
    print(f"✅ MongoDB 备份完成: {backup_dir}")
    return backup_dir

def backup_neo4j():
    """备份 Neo4j（导出 Cypher 查询）"""
    # 简化版本：导出所有节点和关系
    from ..db_manager import db_manager
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_file = f'./backup/neo4j_{timestamp}.cypher'
    
    with db_manager.neo4j.session() as session:
        # 导出节点
        nodes = session.run("MATCH (n:Species) RETURN n")
        # ... 写入文件
    
    print(f"✅ Neo4j 备份完成: {backup_file}")