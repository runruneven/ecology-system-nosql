# src/analytics/species_analysis.py
"""物种分布分析模块"""

from ..db_manager import db_manager
from ..utils.serializers import serialize_doc


class SpeciesAnalysis:
    """物种数据分析类"""
    
    def __init__(self):
        self.db = db_manager.mongo
        self.species_col = db_manager.mongo['species']
        self.observations_col = db_manager.mongo['observations']
    
    def get_distribution_stats(self):
        """
        统计各省份/地区的物种数量
        
        使用 MongoDB 聚合查询统计分布信息
        假设 distribution 字段包含地区信息（如：中国东北、吉林省等）
        
        Returns:
            分布统计列表，格式：[{"province": "吉林省", "count": 15}, ...]
        """
        # 使用聚合管道统计
        # 首先需要从 distribution 或 habitat 字段中提取省份信息
        # 这里假设 distribution 字段可能包含省份名称
        
        pipeline = [
            # 筛选有分布信息的物种
            {"$match": {
                "$or": [
                    {"distribution": {"$exists": True, "$ne": ""}},
                    {"habitat": {"$exists": True, "$ne": ""}}
                ]
            }},
            # 展开可能包含多个地区的文档（如果 distribution 是数组）
            # 这里假设 distribution 是字符串，需要手动提取
            {"$project": {
                "name": 1,
                "distribution": 1,
                "habitat": 1,
                # 尝试从分布信息中提取省份
                "province_keywords": {
                    "$split": [
                        {
                            "$concat": [
                                {"$ifNull": ["$distribution", ""]},
                                " ",
                                {"$ifNull": ["$habitat", ""]}
                            ]
                        },
                        " "
                    ]
                }
            }},
            # 展开数组，每个关键词成为一行
            {"$unwind": "$province_keywords"},
            # 匹配省份关键词（简化版，实际可能需要更复杂的匹配逻辑）
            {"$match": {
                "province_keywords": {
                    "$regex": "省|市|自治区|自治区|特别行政区|东北|华北|华东|华南|华中|西南|西北",
                    "$options": "i"
                }
            }},
            # 按省份分组统计
            {"$group": {
                "_id": "$province_keywords",
                "count": {"$sum": 1},
                "species": {"$addToSet": "$name"}
            }},
            # 排序
            {"$sort": {"count": -1}},
            # 格式化输出
            {"$project": {
                "province": "$_id",
                "count": 1,
                "species_count": {"$size": "$species"},
                "_id": 0
            }}
        ]
        
        try:
            result = list(self.species_col.aggregate(pipeline))
            return result
        except Exception as e:
            print(f"统计分布信息时出错: {e}")
            # 如果上面的聚合失败，返回简化版本（基于观测记录的省份统计）
            return self._get_distribution_from_observations()
    
    def _get_distribution_from_observations(self):
        """
        从观测记录中提取分布统计（备用方法）
        
        Returns:
            分布统计列表
        """
        pipeline = [
            # 筛选有位置信息的观测记录
            {"$match": {
                "observation.location.province": {"$exists": True, "$ne": ""}
            }},
            # 按省份分组，统计不同物种数量
            {"$group": {
                "_id": "$observation.location.province",
                "unique_species": {"$addToSet": "$species_id"}
            }},
            # 计算物种数量
            {"$project": {
                "province": "$_id",
                "count": {"$size": "$unique_species"},
                "_id": 0
            }},
            # 排序
            {"$sort": {"count": -1}}
        ]
        
        try:
            result = list(self.observations_col.aggregate(pipeline))
            return result
        except Exception as e:
            print(f"从观测记录统计分布时出错: {e}")
            return []
    
    def get_category_distribution(self):
        """
        统计各类别物种的数量和占比
        
        返回饼图所需的数据格式
        
        Returns:
            分类分布数据，格式：
            {
                "labels": ["哺乳动物", "鸟类", ...],
                "data": [15, 20, ...],
                "percentages": [30.0, 40.0, ...],
                "total": 50
            }
        """
        pipeline = [
            # 筛选有分类信息的物种
            {"$match": {"category": {"$exists": True, "$ne": ""}}},
            # 按分类分组统计
            {"$group": {
                "_id": "$category",
                "count": {"$sum": 1}
            }},
            # 排序（按数量降序）
            {"$sort": {"count": -1}}
        ]
        
        result = list(self.species_col.aggregate(pipeline))
        
        # 计算总数
        total = sum(item['count'] for item in result)
        
        # 格式化数据
        labels = [item['_id'] for item in result]
        data = [item['count'] for item in result]
        percentages = [round((item['count'] / total * 100), 2) if total > 0 else 0 
                      for item in result]
        
        return {
            "labels": labels,
            "data": data,
            "percentages": percentages,
            "total": total,
            "details": [
                {
                    "category": item['_id'],
                    "count": item['count'],
                    "percentage": round((item['count'] / total * 100), 2) if total > 0 else 0
                }
                for item in result
            ]
        }
    
    def get_protection_level_stats(self):
        """
        统计各保护等级的物种数量
        
        Returns:
            保护等级统计列表，格式：
            [{"level": "濒危", "count": 10}, {"level": "易危", "count": 5}, ...]
        """
        pipeline = [
            # 筛选有保护状态信息的物种
            {"$match": {
                "$or": [
                    {"conservation_status": {"$exists": True, "$ne": ""}},
                    {"protection_level": {"$exists": True, "$ne": ""}}
                ]
            }},
            # 使用 $ifNull 统一字段名
            {"$project": {
                "protection_level": {
                    "$ifNull": ["$conservation_status", "$protection_level"]
                },
                "name": 1
            }},
            # 按保护等级分组统计
            {"$group": {
                "_id": "$protection_level",
                "count": {"$sum": 1},
                "species": {"$addToSet": "$name"}
            }},
            # 排序
            {"$sort": {"count": -1}},
            # 格式化输出
            {"$project": {
                "level": "$_id",
                "count": 1,
                "species_count": {"$size": "$species"},
                "_id": 0
            }}
        ]
        
        try:
            result = list(self.species_col.aggregate(pipeline))
            
            # 如果没有保护状态数据，返回默认信息
            if not result:
                # 统计无保护状态信息的物种数量
                total = self.species_col.count_documents({})
                protected_count = self.species_col.count_documents({
                    "$or": [
                        {"conservation_status": {"$exists": True, "$ne": ""}},
                        {"protection_level": {"$exists": True, "$ne": ""}}
                    ]
                })
                return [
                    {"level": "已记录保护状态", "count": protected_count},
                    {"level": "未记录保护状态", "count": total - protected_count}
                ]
            
            return result
        except Exception as e:
            print(f"统计保护等级时出错: {e}")
            return []
    
    def get_diet_distribution(self):
        """
        统计各食性类型的物种数量和占比
        
        Returns:
            食性分布数据
        """
        pipeline = [
            # 筛选有食性信息的物种
            {"$match": {"diet": {"$exists": True, "$ne": ""}}},
            # 按食性分组统计
            {"$group": {
                "_id": "$diet",
                "count": {"$sum": 1}
            }},
            # 排序
            {"$sort": {"count": -1}}
        ]
        
        result = list(self.species_col.aggregate(pipeline))
        total = sum(item['count'] for item in result)
        
        return {
            "labels": [item['_id'] for item in result],
            "data": [item['count'] for item in result],
            "percentages": [
                round((item['count'] / total * 100), 2) if total > 0 else 0
                for item in result
            ],
            "total": total,
            "details": [
                {
                    "diet": item['_id'],
                    "count": item['count'],
                    "percentage": round((item['count'] / total * 100), 2) if total > 0 else 0
                }
                for item in result
            ]
        }
    
    def get_habitat_distribution(self):
        """
        统计各栖息地类型的物种数量
        
        Returns:
            栖息地分布数据
        """
        pipeline = [
            # 筛选有栖息地信息的物种
            {"$match": {"habitat": {"$exists": True, "$ne": ""}}},
            # 按栖息地分组统计
            {"$group": {
                "_id": "$habitat",
                "count": {"$sum": 1}
            }},
            # 排序
            {"$sort": {"count": -1}},
            # 限制返回数量
            {"$limit": 20}
        ]
        
        result = list(self.species_col.aggregate(pipeline))
        
        return [
            {
                "habitat": item['_id'],
                "count": item['count']
            }
            for item in result
        ]



