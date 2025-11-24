# src/app.py
"""Flask Web 应用"""

from functools import wraps
from flask import Flask, render_template, request, jsonify
from .models.species import SpeciesModel
from .models.relationship import RelationshipModel
from .models.habitat import HabitatModel
from .models.user import UserModel
from .analytics.network_analysis import NetworkAnalysis
from .analytics.species_analysis import SpeciesAnalysis

from .db_manager import db_manager

app = Flask(__name__, 
            template_folder='../templates',  # 往上一级找templates
            static_folder='../static')       # 往上一级找static

# 初始化模型
species_model = SpeciesModel()
relationship_model = RelationshipModel()
habitat_model = HabitatModel()
user_model = UserModel()
network_analysis = NetworkAnalysis()
species_analysis = SpeciesAnalysis()

# 认证装饰器
def require_auth(action='view'):
    """
    认证装饰器，检查用户是否有权限执行操作
    
    Args:
        action: 需要的操作权限（view, add, edit, delete, verify）
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # 从请求头获取会话令牌
            session_token = request.headers.get('X-Session-Token') or request.args.get('token')
            
            if not session_token:
                return jsonify({
                    'success': False,
                    'message': '需要登录',
                    'code': 'AUTH_REQUIRED'
                }), 401
            
            # 获取用户信息
            user_data = user_model.get_user_from_session(session_token)
            if not user_data:
                return jsonify({
                    'success': False,
                    'message': '会话无效或已过期',
                    'code': 'INVALID_SESSION'
                }), 401
            
            # 检查权限
            role = user_data.get('role', 'public')
            if not user_model.check_permission_by_role(role, action):
                return jsonify({
                    'success': False,
                    'message': f'没有权限执行操作: {action}',
                    'code': 'PERMISSION_DENIED'
                }), 403
            
            # 将用户信息添加到请求上下文
            request.current_user = user_data
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# 页面路由
@app.route('/species')
def species_page():
    """物种管理页面"""
    return render_template('species.html')

@app.route('/relationships')
def relationships_page():
    """生态关系页面"""
    return render_template('relationship.html')

@app.route('/food-chain')
def food_chain_page():
    """食物链查询页面"""
    return render_template('food-chain.html')

@app.route('/habitats')
def habitats_page():
    """栖息地管理页面"""
    return render_template('habitat.html')

@app.route('/statistics')
def statistics_page():
    """数据统计页面"""
    return render_template('statistics.html')

@app.route('/api/statistics')
def api_statistics():
    """统计数据API"""
    stats = {
        'species_count': species_model.count_species(),
        'relationship_count': relationship_model.count_relationships(),
        'habitat_count': habitat_model.count_habitats(),
        'observation_count': 0,  # TODO: 实现观测记录统计
        'categories': species_model.get_category_stats()
    }
    return jsonify(stats)

# API路由
@app.route('/')
def index():
    """首页"""
    return render_template('index.html')


@app.route('/api/species', methods=['GET', 'POST'])
def api_species():
    """物种API"""
    if request.method == 'POST':
        data = request.json
        species_id = species_model.add_species(
            name=data['name'],
            category=data['category'],
            diet=data.get('diet', ''),
            habitat=data.get('habitat', '')
        )
        return jsonify({'success': True, 'id': species_id})
    
    else:
        category = request.args.get('category')
        species_list = species_model.list_species(category=category)
        return jsonify(species_list)


@app.route('/api/species/<species_id>')
def api_species_detail(species_id):
    """物种详情"""
    species = species_model.get_species(species_id)
    if species:
        return jsonify(species)
    return jsonify({'error': 'Not found'}), 404


@app.route('/api/relationships', methods=['GET'])
def api_list_relationships():
    """获取关系列表"""
    rel_type = request.args.get('type')
    relationships = relationship_model.list_relationships(rel_type=rel_type)
    return jsonify(relationships)


@app.route('/api/relationship', methods=['POST'])
def api_create_relationship():
    """创建生态关系"""
    data = request.json
    rel_id = relationship_model.create_relationship(
        species1_id=data['species1_id'],
        species2_id=data['species2_id'],
        rel_type=data.get('type', 'PREYS_ON')
    )
    return jsonify({'success': True, 'id': rel_id})


@app.route('/api/relationship/<relationship_id>', methods=['DELETE'])
def api_delete_relationship(relationship_id):
    """删除生态关系"""
    try:
        result = relationship_model.delete_relationship(relationship_id)
        if result:
            return jsonify({
                'success': True,
                'message': '关系删除成功'
            })
        else:
            return jsonify({
                'success': False,
                'message': '关系不存在'
            }), 404
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route('/api/food-chain')
def api_food_chain():
    """查询食物链"""
    start_id = request.args.get('start')
    end_id = request.args.get('end')
    
    chain = relationship_model.query_food_chain(start_id, end_id)
    if chain:
        return jsonify({'chain': chain})
    return jsonify({'error': 'No path found'}), 404


@app.route('/api/species/<species_id>', methods=['DELETE'])
def delete_species(species_id):
    """删除物种"""
    try:
        result = species_model.delete_species(species_id)
        if result:
            return jsonify({
                'success': True,
                'message': '物种删除成功'
            })
        else:
            return jsonify({
                'success': False,
                'message': '物种不存在'
            }), 404
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


# 搜索相关 API 路由
@app.route('/api/search', methods=['GET'])
def api_search():
    """全文搜索物种"""
    keyword = request.args.get('q', '')
    
    if not keyword:
        return jsonify({'error': '搜索关键词不能为空'}), 400
    
    try:
        results = species_model.search_species(keyword)
        return jsonify({
            'success': True,
            'count': len(results),
            'results': results
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route('/api/search/category', methods=['GET'])
def api_search_by_category():
    """按分类搜索物种"""
    category = request.args.get('category', '')
    
    if not category:
        return jsonify({'error': '分类名称不能为空'}), 400
    
    try:
        results = species_model.search_by_category(category)
        return jsonify({
            'success': True,
            'count': len(results),
            'results': results
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route('/api/search/distribution', methods=['GET'])
def api_search_by_distribution():
    """按地理分布搜索物种"""
    region = request.args.get('region', '')
    
    if not region:
        return jsonify({'error': '地区名称不能为空'}), 400
    
    try:
        results = species_model.search_by_distribution(region)
        return jsonify({
            'success': True,
            'count': len(results),
            'results': results
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


# 栖息地相关 API 路由
@app.route('/api/habitats', methods=['GET', 'POST'])
def api_habitats():
    """栖息地API"""
    if request.method == 'POST':
        # 创建栖息地
        try:
            data = request.json
            habitat_id = habitat_model.add_habitat(
                name=data['name'],
                location=data.get('location', {}),
                environment=data.get('environment', {}),
                protection_level=data.get('protection_level', ''),
                area=data.get('area', ''),
                species_list=data.get('species_list', [])
            )
            return jsonify({'success': True, 'id': habitat_id})
        except Exception as e:
            return jsonify({
                'success': False,
                'message': str(e)
            }), 400
    else:
        # 获取栖息地列表
        protection_level = request.args.get('protection_level')
        habitats = habitat_model.list_habitats(protection_level=protection_level)
        return jsonify(habitats)


@app.route('/api/habitat/<habitat_id>', methods=['GET', 'PUT', 'DELETE'])
def api_habitat_detail(habitat_id):
    """栖息地详情、更新、删除API"""
    if request.method == 'GET':
        # 获取单个栖息地详情
        habitat = habitat_model.get_habitat(habitat_id)
        if habitat:
            return jsonify(habitat)
        return jsonify({'error': 'Not found'}), 404
    
    elif request.method == 'PUT':
        # 更新栖息地
        try:
            data = request.json
            result = habitat_model.update_habitat(habitat_id, data)
            if result:
                return jsonify({
                    'success': True,
                    'message': '栖息地更新成功'
                })
            else:
                return jsonify({
                    'success': False,
                    'message': '栖息地不存在'
                }), 404
        except Exception as e:
            return jsonify({
                'success': False,
                'message': str(e)
            }), 500
    
    elif request.method == 'DELETE':
        # 删除栖息地
        try:
            result = habitat_model.delete_habitat(habitat_id)
            if result:
                return jsonify({
                    'success': True,
                    'message': '栖息地删除成功'
                })
            else:
                return jsonify({
                    'success': False,
                    'message': '栖息地不存在'
                }), 404
        except Exception as e:
            return jsonify({
                'success': False,
                'message': str(e)
            }), 500


# 用户认证相关 API 路由
@app.route('/api/register', methods=['POST'])
def api_register():
    """用户注册"""
    try:
        data = request.json
        username = data.get('username', '')
        password = data.get('password', '')
        role = data.get('role', 'public')
        
        if not username or not password:
            return jsonify({
                'success': False,
                'message': '用户名和密码不能为空'
            }), 400
        
        # 注册用户
        user_id = user_model.register_user(
            username=username,
            password=password,
            role=role,
            email=data.get('email', ''),
            name=data.get('name', '')
        )
        
        return jsonify({
            'success': True,
            'message': '注册成功',
            'user_id': user_id
        })
    except ValueError as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 400
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route('/api/login', methods=['POST'])
def api_login():
    """用户登录"""
    try:
        data = request.json
        username = data.get('username', '')
        password = data.get('password', '')
        
        if not username or not password:
            return jsonify({
                'success': False,
                'message': '用户名和密码不能为空'
            }), 400
        
        # 登录
        result = user_model.login(username, password)
        
        if result:
            return jsonify({
                'success': True,
                'message': '登录成功',
                'session_token': result['session_token'],
                'user': result['user']
            })
        else:
            return jsonify({
                'success': False,
                'message': '用户名或密码错误'
            }), 401
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route('/api/logout', methods=['POST'])
def api_logout():
    """用户登出"""
    try:
        data = request.json
        session_token = data.get('session_token') or request.headers.get('X-Session-Token')
        
        if not session_token:
            return jsonify({
                'success': False,
                'message': '会话令牌不能为空'
            }), 400
        
        # 登出
        result = user_model.logout(session_token)
        
        if result:
            return jsonify({
                'success': True,
                'message': '登出成功'
            })
        else:
            return jsonify({
                'success': False,
                'message': '登出失败'
            }), 400
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route('/api/user/me', methods=['GET'])
def api_user_me():
    """获取当前用户信息"""
    session_token = request.headers.get('X-Session-Token') or request.args.get('token')
    
    if not session_token:
        return jsonify({
            'success': False,
            'message': '需要登录'
        }), 401
    
    user_data = user_model.get_user_from_session(session_token)
    if user_data:
        user_info = user_model.get_user(user_data['user_id'])
        if user_info:
            return jsonify({
                'success': True,
                'user': user_info
            })
    
    return jsonify({
        'success': False,
        'message': '会话无效或已过期'
    }), 401


# 网络分析相关 API 路由
@app.route('/api/network/stats', methods=['GET'])
def api_network_stats():
    """获取网络统计信息"""
    try:
        stats = network_analysis.get_network_stats()
        return jsonify({
            'success': True,
            'stats': stats
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route('/api/network/key-species', methods=['GET'])
def api_key_species():
    """获取关键物种"""
    try:
        top_n = int(request.args.get('top_n', 10))
        algorithm = request.args.get('algorithm', 'degree')
        
        key_species = network_analysis.find_key_species(top_n=top_n, algorithm=algorithm)
        return jsonify({
            'success': True,
            'count': len(key_species),
            'key_species': key_species
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route('/api/network/food-chain-lengths', methods=['GET'])
def api_food_chain_lengths():
    """获取食物链长度分布"""
    try:
        lengths = network_analysis.get_food_chain_lengths()
        return jsonify({
            'success': True,
            'data': lengths
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route('/api/network/export', methods=['GET'])
def api_network_export():
    """导出网络数据用于可视化"""
    try:
        limit_nodes = int(request.args.get('limit_nodes', 100))
        
        network_data = network_analysis.export_network_for_visualization(limit_nodes=limit_nodes)
        return jsonify({
            'success': True,
            'network': network_data
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route('/api/network/species/<species_id>/relationships', methods=['GET'])
def api_species_relationships(species_id):
    """获取某个物种的所有关系"""
    try:
        relationships = network_analysis.get_species_relationships(species_id)
        if relationships:
            return jsonify({
                'success': True,
                'relationships': relationships
            })
        else:
            return jsonify({
                'success': False,
                'message': '物种不存在'
            }), 404
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


# 数据分析相关 API 路由
@app.route('/api/analytics/category-distribution', methods=['GET'])
def api_category_distribution():
    """获取物种分类分布数据"""
    try:
        data = species_analysis.get_category_distribution()
        return jsonify({
            'success': True,
            'data': data
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route('/api/analytics/distribution-stats', methods=['GET'])
def api_distribution_stats():
    """获取地理分布统计数据"""
    try:
        data = species_analysis.get_distribution_stats()
        return jsonify({
            'success': True,
            'data': data
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route('/api/analytics/relationship-types', methods=['GET'])
def api_relationship_types():
    """获取生态关系类型占比数据"""
    try:
        # 从 MongoDB 获取关系类型统计
        pipeline = [
            {"$group": {"_id": "$type", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}
        ]
        result = list(db_manager.mongo['relationships'].aggregate(pipeline))
        
        total = sum(item['count'] for item in result)
        
        data = {
            'labels': [item['_id'] for item in result],
            'data': [item['count'] for item in result],
            'percentages': [
                round((item['count'] / total * 100), 2) if total > 0 else 0
                for item in result
            ],
            'total': total,
            'details': [
                {
                    'type': item['_id'],
                    'count': item['count'],
                    'percentage': round((item['count'] / total * 100), 2) if total > 0 else 0
                }
                for item in result
            ]
        }
        
        return jsonify({
            'success': True,
            'data': data
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route('/api/analytics/network-graph', methods=['GET'])
def api_network_graph():
    """获取生态网络图数据（用于 D3.js 可视化）"""
    try:
        limit_nodes = int(request.args.get('limit_nodes', 50))
        
        network_data = network_analysis.export_network_for_visualization(limit_nodes=limit_nodes)
        return jsonify({
            'success': True,
            'data': network_data
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

if __name__ == '__main__':
    app.run(debug=True, port=5001)