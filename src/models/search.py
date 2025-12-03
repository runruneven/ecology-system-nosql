# src/models/search.py
"""统一搜索系统"""

from ..db_manager import db_manager
from ..utils.serializers import serialize_doc
import json


class SearchModel:
    """搜索数据模型"""
    
    def __init__(self):
        self.mongo = db_manager.mongo
        self.redis = db_manager.redis
        
        # 各个集合
        self.species_col = self.mongo['species']
        self.habitats_col = self.mongo['habitats']
        self.observations_col = self.mongo['observations']
        self.relationships_col = self.mongo['relationships']
    
    def search_all(self, keyword, category=None, limit=50):
        """
        全文搜索 - 跨所有集合搜索
        
        Args:
            keyword: 搜索关键词
            category: 可选，按类别筛选（物种/栖息地/观测记录）
            limit: 返回结果数量限制
        
        Returns:
            dict: 搜索结果 {species: [], habitats: [], observations: []}
        """
        if not keyword:
            return {
                'species': [],
                'habitats': [],
                'observations': [],
                'total': 0
            }
        
        results = {}
        
        # 1. 搜索物种
        if not category or category == '物种':
            results['species'] = self._search_species(keyword, limit)
        else:
            results['species'] = []
        
        # 2. 搜索栖息地
        if not category or category == '栖息地':
            results['habitats'] = self._search_habitats(keyword, limit)
        else:
            results['habitats'] = []
        
        # 3. 搜索观测记录
        if not category or category == '观测记录':
            results['observations'] = self._search_observations(keyword, limit)
        else:
            results['observations'] = []
        
        # 4. 计算总结果数
        results['total'] = (
            len(results['species']) + 
            len(results['habitats']) + 
            len(results['observations'])
        )
        
        # 5. 记录搜索历史（存到 Redis）
        self._save_search_history(keyword)
        
        return results
    
    def _search_species(self, keyword, limit):
        """
        搜索物种
        
        搜索字段：name, scientific_name, category, habitat, description
        """
        query = {
            '$or': [
                {'name': {'$regex': keyword, '$options': 'i'}},  # 不区分大小写
                {'scientific_name': {'$regex': keyword, '$options': 'i'}},
                {'category': {'$regex': keyword, '$options': 'i'}},
                {'habitat': {'$regex': keyword, '$options': 'i'}},
                {'description': {'$regex': keyword, '$options': 'i'}},
                {'morphology': {'$regex': keyword, '$options': 'i'}},
            ]
        }
        
        species_list = list(self.species_col.find(query).limit(limit))
        
        # 添加结果类型标记
        for s in species_list:
            s['result_type'] = '物种'
            s['result_score'] = self._calculate_species_score(s, keyword)
        
        return [serialize_doc(s) for s in species_list]
    
    def _search_habitats(self, keyword, limit):
        """
        搜索栖息地
        
        搜索字段：name, location.province, description
        """
        query = {
            '$or': [
                {'name': {'$regex': keyword, '$options': 'i'}},
                {'location.province': {'$regex': keyword, '$options': 'i'}},
                {'location.city': {'$regex': keyword, '$options': 'i'}},
                {'description': {'$regex': keyword, '$options': 'i'}},
                {'environment.climate': {'$regex': keyword, '$options': 'i'}},
            ]
        }
        
        habitats_list = list(self.habitats_col.find(query).limit(limit))
        
        # 添加结果类型标记
        for h in habitats_list:
            h['result_type'] = '栖息地'
            h['result_score'] = self._calculate_habitat_score(h, keyword)
        
        return [serialize_doc(h) for h in habitats_list]
    
    def _search_observations(self, keyword, limit):
        """
        搜索观测记录
        
        搜索字段：species_name, observer.name, observation.location.province
        """
        query = {
            '$or': [
                {'species_name': {'$regex': keyword, '$options': 'i'}},
                {'observer.name': {'$regex': keyword, '$options': 'i'}},
                {'observation.location.province': {'$regex': keyword, '$options': 'i'}},
                {'observation.behavior': {'$regex': keyword, '$options': 'i'}},
                {'observation.notes': {'$regex': keyword, '$options': 'i'}},
            ]
        }
        
        obs_list = list(self.observations_col.find(query).limit(limit))
        
        # 添加结果类型标记
        for o in obs_list:
            o['result_type'] = '观测记录'
            o['result_score'] = self._calculate_observation_score(o, keyword)
        
        return [serialize_doc(o) for o in obs_list]
    
    def _calculate_species_score(self, species, keyword):
        """
        计算物种搜索结果的相关度评分
        
        评分规则：
        - 名称完全匹配: +100
        - 名称包含: +50
        - 学名匹配: +30
        - 其他字段匹配: +10
        """
        score = 0
        keyword_lower = keyword.lower()
        
        # 名称匹配
        if species.get('name', '').lower() == keyword_lower:
            score += 100
        elif keyword_lower in species.get('name', '').lower():
            score += 50
        
        # 学名匹配
        if keyword_lower in species.get('scientific_name', '').lower():
            score += 30
        
        # 类别匹配
        if keyword_lower in species.get('category', '').lower():
            score += 20
        
        # 其他字段
        if keyword_lower in species.get('habitat', '').lower():
            score += 10
        if keyword_lower in species.get('description', '').lower():
            score += 10
        
        return score
    
    def _calculate_habitat_score(self, habitat, keyword):
        """计算栖息地搜索结果的相关度评分"""
        score = 0
        keyword_lower = keyword.lower()
        
        if habitat.get('name', '').lower() == keyword_lower:
            score += 100
        elif keyword_lower in habitat.get('name', '').lower():
            score += 50
        
        location = habitat.get('location', {})
        if keyword_lower in location.get('province', '').lower():
            score += 30
        if keyword_lower in location.get('city', '').lower():
            score += 20
        
        return score
    
    def _calculate_observation_score(self, observation, keyword):
        """计算观测记录搜索结果的相关度评分"""
        score = 0
        keyword_lower = keyword.lower()
        
        if keyword_lower in observation.get('species_name', '').lower():
            score += 50
        
        obs_data = observation.get('observation', {})
        location = obs_data.get('location', {})
        
        if keyword_lower in location.get('province', '').lower():
            score += 30
        
        # 已验证的记录权重更高
        if observation.get('verified'):
            score += 20
        
        return score
    
    def _save_search_history(self, keyword):
        """
        保存搜索历史到 Redis
        
        使用 Redis 的有序集合（sorted set）记录搜索次数
        """
        try:
            # zincrby: 增加分数（搜索次数）
            self.redis.zincrby('search:popular', 1, keyword)
            
            # 限制热门搜索词数量（只保留前100个）
            self.redis.zremrangebyrank('search:popular', 0, -101)
            
        except Exception as e:
            print(f"⚠️ 保存搜索历史失败: {e}")
    
    def get_popular_searches(self, limit=10):
        """
        获取热门搜索词
        
        Returns:
            list: [(keyword, count), ...]
        """
        try:
            # zrevrange: 按分数倒序获取
            # withscores=True: 同时返回分数
            popular = self.redis.zrevrange(
                'search:popular', 
                0, 
                limit - 1, 
                withscores=True
            )
            
            # 转换为可读格式
            result = []
            for item, score in popular:
                keyword = item.decode() if isinstance(item, bytes) else item
                result.append({
                    'keyword': keyword,
                    'count': int(score)
                })
            
            return result
            
        except Exception as e:
            print(f"⚠️ 获取热门搜索失败: {e}")
            return []
    
    def get_recommendations(self, keyword, limit=5):
        """
        简单推荐系统
        
        基于搜索关键词推荐相关内容
        
        推荐逻辑：
        1. 如果搜索物种，推荐相关栖息地
        2. 如果搜索栖息地，推荐该地的物种
        3. 推荐热门搜索词
        """
        recommendations = {
            'related_species': [],
            'related_habitats': [],
            'popular_searches': []
        }
        
        # 1. 查找搜索词对应的物种
        species = self.species_col.find_one(
            {'name': {'$regex': keyword, '$options': 'i'}}
        )
        
        if species:
            # 推荐相同类别的物种
            similar_species = list(
                self.species_col.find({
                    'category': species.get('category'),
                    '_id': {'$ne': species['_id']}  # 排除自己
                }).limit(limit)
            )
            recommendations['related_species'] = [
                serialize_doc(s) for s in similar_species
            ]
            
            # 推荐相关栖息地
            habitat_keyword = species.get('habitat', '')
            if habitat_keyword:
                related_habitats = list(
                    self.habitats_col.find({
                        'name': {'$regex': habitat_keyword, '$options': 'i'}
                    }).limit(limit)
                )
                recommendations['related_habitats'] = [
                    serialize_doc(h) for h in related_habitats
                ]
        
        # 2. 推荐热门搜索词
        recommendations['popular_searches'] = self.get_popular_searches(limit)
        
        return recommendations
    
    def advanced_search(self, filters):
        """
        高级搜索 - 支持多条件组合
        
        Args:
            filters: {
                'name': '东北虎',
                'category': '哺乳动物',
                'province': '吉林省',
                'verified': True
            }
        
        Returns:
            dict: 搜索结果
        """
        results = {
            'species': [],
            'habitats': [],
            'observations': []
        }
        
        # 物种高级搜索
        if 'name' in filters or 'category' in filters:
            species_query = {}
            
            if filters.get('name'):
                species_query['name'] = {
                    '$regex': filters['name'], 
                    '$options': 'i'
                }
            
            if filters.get('category'):
                species_query['category'] = filters['category']
            
            if species_query:
                species_list = list(self.species_col.find(species_query).limit(50))
                results['species'] = [serialize_doc(s) for s in species_list]
        
        # 栖息地高级搜索
        if 'province' in filters:
            habitats_query = {
                'location.province': {
                    '$regex': filters['province'],
                    '$options': 'i'
                }
            }
            habitats_list = list(self.habitats_col.find(habitats_query).limit(50))
            results['habitats'] = [serialize_doc(h) for h in habitats_list]
        
        # 观测记录高级搜索
        if 'verified' in filters or 'province' in filters:
            obs_query = {}
            
            if 'verified' in filters:
                obs_query['verified'] = filters['verified']
            
            if filters.get('province'):
                obs_query['observation.location.province'] = {
                    '$regex': filters['province'],
                    '$options': 'i'
                }
            
            if obs_query:
                obs_list = list(self.observations_col.find(obs_query).limit(50))
                results['observations'] = [serialize_doc(o) for o in obs_list]
        
        results['total'] = (
            len(results['species']) + 
            len(results['habitats']) + 
            len(results['observations'])
        )
        
        return results