# src/models/user.py
"""用户管理相关的数据库操作"""

import json
import secrets
import hashlib
from datetime import datetime
from ..db_manager import db_manager
from ..utils.serializers import serialize_doc


class UserModel:
    """用户数据模型"""
    
    # 权限定义
    PERMISSIONS = {
        'admin': ['view', 'add', 'edit', 'delete', 'verify'],  # 所有权限
        'researcher': ['view', 'add', 'edit', 'verify'],  # 查看、添加、修改、验证
        'conservationist': ['view', 'add'],  # 查看、添加
        'public': ['view']  # 仅查看
    }
    
    def __init__(self):
        self.db = db_manager.mongo
        self.mongo_col = db_manager.mongo['users']
        self.redis = db_manager.redis
    
    def _hash_password(self, password):
        """
        哈希密码（使用 SHA256，实际生产环境建议使用 bcrypt）
        
        Args:
            password: 明文密码
        
        Returns:
            哈希后的密码
        """
        # 生产环境建议使用 bcrypt，这里使用 SHA256 作为简化版本
        return hashlib.sha256(password.encode('utf-8')).hexdigest()
    
    def _verify_password(self, password, hashed):
        """
        验证密码
        
        Args:
            password: 明文密码
            hashed: 哈希后的密码
        
        Returns:
            是否匹配
        """
        return self._hash_password(password) == hashed
    
    def _generate_session_token(self):
        """生成随机会话令牌"""
        return secrets.token_urlsafe(32)
    
    def register_user(self, username, password, role='public', **extra_fields):
        """
        注册用户
        
        Args:
            username: 用户名
            password: 密码（明文）
            role: 角色（admin, researcher, conservationist, public）
            **extra_fields: 额外字段（如 email, name 等）
        
        Returns:
            用户ID，如果注册失败返回 None
        """
        # 检查用户名是否已存在
        existing_user = self.mongo_col.find_one({'username': username})
        if existing_user:
            raise ValueError('用户名已存在')
        
        # 验证角色
        if role not in self.PERMISSIONS:
            raise ValueError(f'无效的角色: {role}')
        
        # 构建用户文档
        user_doc = {
            "username": username,
            "password_hash": self._hash_password(password),  # 存储哈希后的密码
            "role": role,
            "created_at": datetime.now(),
            "last_login": None,
            "active": True,
            **extra_fields
        }
        
        # 插入 MongoDB
        result = self.mongo_col.insert_one(user_doc)
        user_id = str(result.inserted_id)
        
        return user_id
    
    def login(self, username, password):
        """
        用户登录
        
        Args:
            username: 用户名
            password: 密码（明文）
        
        Returns:
            会话令牌和用户信息，如果登录失败返回 None
        """
        # 查找用户
        user = self.mongo_col.find_one({
            'username': username,
            'active': True
        })
        
        if not user:
            return None
        
        # 验证密码
        if not self._verify_password(password, user['password_hash']):
            return None
        
        # 生成会话令牌
        session_token = self._generate_session_token()
        
        # 存储会话到 Redis（1小时过期）
        user_data = {
            'user_id': str(user['_id']),
            'username': user['username'],
            'role': user['role']
        }
        self.redis.setex(
            f'session:{session_token}',
            3600,  # 1小时
            json.dumps(user_data)
        )
        
        # 更新最后登录时间
        self.mongo_col.update_one(
            {'_id': user['_id']},
            {'$set': {'last_login': datetime.now()}}
        )
        
        return {
            'session_token': session_token,
            'user': serialize_doc(user)
        }
    
    def logout(self, session_token):
        """
        用户登出
        
        Args:
            session_token: 会话令牌
        
        Returns:
            是否成功
        """
        # 从 Redis 删除会话
        deleted = self.redis.delete(f'session:{session_token}')
        return deleted > 0
    
    def get_user_from_session(self, session_token):
        """
        从会话令牌获取用户信息
        
        Args:
            session_token: 会话令牌
        
        Returns:
            用户信息字典，如果会话无效返回 None
        """
        session_key = f'session:{session_token}'
        user_data_str = self.redis.get(session_key)
        
        if not user_data_str:
            return None
        
        try:
            user_data = json.loads(user_data_str)
            # 刷新会话过期时间
            self.redis.expire(session_key, 3600)
            return user_data
        except:
            return None
    
    def check_permission(self, user_id, action):
        """
        检查用户是否有权限执行某操作
        
        Args:
            user_id: 用户ID
            action: 操作名称（view, add, edit, delete, verify）
        
        Returns:
            是否有权限
        """
        # 从 MongoDB 获取用户信息
        from bson import ObjectId
        user = self.mongo_col.find_one({'_id': ObjectId(user_id)})
        
        if not user or not user.get('active'):
            return False
        
        role = user.get('role', 'public')
        allowed_actions = self.PERMISSIONS.get(role, [])
        
        return action in allowed_actions
    
    def check_permission_by_role(self, role, action):
        """
        检查角色是否有权限执行某操作（不需要查询数据库）
        
        Args:
            role: 角色名称
            action: 操作名称
        
        Returns:
            是否有权限
        """
        allowed_actions = self.PERMISSIONS.get(role, [])
        return action in allowed_actions
    
    def get_user(self, user_id):
        """
        获取用户信息
        
        Args:
            user_id: 用户ID
        
        Returns:
            用户信息（不包含密码哈希）
        """
        from bson import ObjectId
        user = self.mongo_col.find_one({'_id': ObjectId(user_id)})
        
        if user:
            user_data = serialize_doc(user)
            # 移除敏感信息
            user_data.pop('password_hash', None)
            return user_data
        
        return None
    
    def update_user_role(self, user_id, new_role):
        """
        更新用户角色（管理员功能）
        
        Args:
            user_id: 用户ID
            new_role: 新角色
        
        Returns:
            是否成功
        """
        if new_role not in self.PERMISSIONS:
            raise ValueError(f'无效的角色: {new_role}')
        
        from bson import ObjectId
        result = self.mongo_col.update_one(
            {'_id': ObjectId(user_id)},
            {'$set': {'role': new_role}}
        )
        
        return result.matched_count > 0
    
    def log_action(self, user_id, action, target_type, target_id, **extra):
        """
        记录操作日志
        
        Args:
            user_id: 用户ID
            action: 操作类型（add, edit, delete, view）
            target_type: 目标类型（species, habitat, relationship, observation）
            target_id: 目标ID
            **extra: 额外信息
        """
        logs_col = self.db['logs']
        
        log_doc = {
            'user_id': user_id,
            'action': action,
            'target_type': target_type,
            'target_id': target_id,
            'timestamp': datetime.now(),
            **extra
        }
        
        logs_col.insert_one(log_doc)

