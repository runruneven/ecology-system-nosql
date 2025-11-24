# src/utils/serializers.py
"""JSON序列化工具"""

from bson import ObjectId


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