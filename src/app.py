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
from .models.observation import ObservationModel
from .models.search import SearchModel

from .db_manager import db_manager
from .utils.serializers import serialize_doc

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
observation_model = ObservationModel()
search_model = SearchModel()

# API 调用计数器中间件（已在后面重新定义，这里先注释）
# @app.before_request
# def track_api_calls():
#     """记录 API 调用次数"""
#     try:
#         db_manager.redis.incr('api_call_count')
#     except:
#         pass

# 辅助函数：检查权限
def check_auth(action='view'):
    """检查用户权限，返回 (is_authorized, user_data, error_response_tuple)"""
    session_token = request.headers.get('X-Session-Token') or request.args.get('token')
    if not session_token:
        return False, None, (jsonify({'success': False, 'message': '需要登录'}), 401)
    
    user_data = user_model.get_user_from_session(session_token)
    if not user_data:
        return False, None, (jsonify({'success': False, 'message': '会话无效或已过期'}), 401)
    
    role = user_data.get('role', 'public')
    if role == 'public' and action != 'view':
        return False, None, (jsonify({'success': False, 'message': f'public 角色只能执行查看操作'}), 403)
    
    if not user_model.check_permission_by_role(role, action):
        return False, None, (jsonify({'success': False, 'message': f'没有权限执行操作: {action}'}), 403)
    
    request.current_user = user_data
    return True, user_data, None

# 辅助函数：记录操作日志
def log_user_action(action, target_type, target_id, **extra):
    """记录用户操作日志"""
    try:
        if hasattr(request, 'current_user') and request.current_user:
            user_id = request.current_user.get('user_id')
            if user_id:
                user_model.log_action(
                    user_id=user_id,
                    action=action,
                    target_type=target_type,
                    target_id=target_id,
                    ip_address=request.remote_addr,
                    user_agent=request.headers.get('User-Agent', ''),
                    **extra
                )
    except Exception as e:
        print(f"⚠️ 记录操作日志失败: {e}")

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
            
            # 如果用户是 public 角色，只能执行 view 操作
            if role == 'public' and action != 'view':
                return jsonify({
                    'success': False,
                    'message': f'public 角色只能执行查看操作，无法执行: {action}',
                    'code': 'PERMISSION_DENIED'
                }), 403
            
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


#  备份恢复机制
@app.route('/api/backup/trigger', methods=['POST'])
@require_auth('admin')  # 只有管理员可以
def trigger_backup():
    from .utils.backup import backup_mongodb, backup_neo4j
    mongo_path = backup_mongodb()
    neo4j_path = backup_neo4j()
    return jsonify({
        'success': True,
        'mongodb_backup': mongo_path,
        'neo4j_backup': neo4j_path
    })

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
    return render_template('habitats.html')

@app.route('/statistics')
def statistics_page():
    """数据统计页面"""
    return render_template('statistics.html')

@app.route('/api/statistics')
def api_statistics():
    """统计数据API - 包含 MongoDB 和 Neo4j 统计"""
    try:
        # MongoDB 统计
        species_count = species_model.count_species()
        habitat_count = habitat_model.count_habitats()
        observation_count = observation_model.count_observations()
        categories = species_model.get_category_stats()
        
        # Neo4j 统计
        try:
            with db_manager.neo4j.session() as session:
                # 查询节点总数
                node_result = session.run("MATCH (s:Species) RETURN count(s) as count")
                node_record = node_result.single()
                neo4j_node_count = node_record['count'] if node_record else 0
                
                # 查询关系总数
                rel_result = session.run("MATCH ()-[r]->() RETURN count(r) as count")
                rel_record = rel_result.single()
                neo4j_relationship_count = rel_record['count'] if rel_record else 0
        except Exception as e:
            print(f"⚠️ Neo4j 查询失败: {e}")
            neo4j_node_count = 0
            neo4j_relationship_count = 0
        
        # MongoDB 关系统计（从 MongoDB 集合）
        mongo_relationship_count = relationship_model.count_relationships()
        
        stats = {
            'species_count': species_count,
            'habitat_count': habitat_count,
            'observation_count': observation_count,
            'relationship_count': mongo_relationship_count,
            'neo4j_node_count': neo4j_node_count,
            'neo4j_relationship_count': neo4j_relationship_count,
            'categories': categories
        }
        
        return jsonify(stats)
    except Exception as e:
        return jsonify({
            'error': str(e)
        }), 500

@app.route('/observations')
def observations_page():
    """观测记录页面"""
    return render_template('observations.html')

@app.route('/api/observations/unverified', methods=['GET'])
def api_unverified_observations():
    """获取待验证列表"""
    observations = observation_model.get_unverified_observations()
    return jsonify(observations)



@app.route('/search')
def search_page():
    """搜索页面"""
    return render_template('search.html')

@app.route('/login')
def login_page():
    """登录页面"""
    return render_template('login.html')

@app.route('/logout')
def logout_page():
    """登出页面（重定向到首页）"""
    return render_template('index.html')

@app.route('/monitor')
def monitor_page():
    """系统监控页面"""
    return render_template('monitor.html')

# API路由
@app.route('/')
def index():
    """首页"""
    return render_template('index.html')


@app.route('/api/species', methods=['GET', 'POST'])
def api_species():
    """物种API"""
    if request.method == 'POST':
        # 检查权限
        is_auth, user_data, error = check_auth('add')
        if not is_auth:
            return error[0], error[1]
        
        data = request.json
        species_id = species_model.add_species(
            name=data['name'],
            category=data['category'],
            diet=data.get('diet', ''),
            habitat=data.get('habitat', '')
        )
        # 记录操作日志
        log_user_action('add', 'species', species_id, details=data)
        return jsonify({'success': True, 'id': species_id})
    
    else:
        category = request.args.get('category')
        species_list = species_model.list_species(category=category)
        return jsonify(species_list)


@app.route('/api/species/<species_id>', methods=['GET', 'PUT', 'DELETE'])
def api_species_detail(species_id):     
    """物种详情、更新、删除API"""
    if request.method == 'GET':
        species = species_model.get_species(species_id)
        if species:
            return jsonify(species)
        return jsonify({'error': 'Not found'}), 404
    elif request.method == 'PUT':
        # 检查权限
        is_auth, user_data, error = check_auth('edit')
        if not is_auth:
            return error[0], error[1]
        
        data = request.json
        result = species_model.update_species(species_id, data)
        if result:
            log_user_action('edit', 'species', species_id, details=data)
            return jsonify({'success': True, 'message': '物种更新成功'})
        else:
            return jsonify({'success': False, 'message': '物种不存在'}), 404
    elif request.method == 'DELETE':
        # 检查权限
        is_auth, user_data, error = check_auth('delete')
        if not is_auth:
            return error[0], error[1]
        
        result = species_model.delete_species(species_id)
        if result:
            log_user_action('delete', 'species', species_id)
            return jsonify({'success': True, 'message': '物种删除成功'})
        else:
            return jsonify({'success': False, 'message': '物种不存在'}), 404
    
    return jsonify({'error': 'Invalid request method'}), 405


@app.route('/api/relationships', methods=['GET'])
def api_list_relationships():
    """获取关系列表"""
    rel_type = request.args.get('type')
    relationships = relationship_model.list_relationships(rel_type=rel_type)
    return jsonify(relationships)


@app.route('/api/relationship', methods=['POST'])
def api_create_relationship():
    """创建生态关系"""
    # 检查权限
    is_auth, user_data, error = check_auth('add')
    if not is_auth:
        return error[0], error[1]
    
    data = request.json
    rel_id = relationship_model.create_relationship(
        species1_id=data['species1_id'],
        species2_id=data['species2_id'],
        rel_type=data.get('type', 'PREYS_ON')
    )
    log_user_action('add', 'relationship', rel_id, details=data)
    return jsonify({'success': True, 'id': rel_id})


@app.route('/api/relationship/<relationship_id>', methods=['GET', 'PUT', 'DELETE'])
def api_relationship_detail(relationship_id):
    """生态关系详情、更新、删除API"""
    if request.method == 'GET':
        # 获取单个关系详情
        relationship = relationship_model.get_relationship(relationship_id)
        if relationship:
            return jsonify(relationship)
        return jsonify({'error': 'Not found'}), 404
    
    elif request.method == 'PUT':
        # 检查权限
        is_auth, user_data, error = check_auth('edit')
        if not is_auth:
            return error[0], error[1]
        
        # 更新生态关系
        try:
            data = request.json
            result = relationship_model.update_relationship(relationship_id, data)
            if result:
                log_user_action('edit', 'relationship', relationship_id, details=data)
                return jsonify({
                    'success': True,
                    'message': '关系更新成功'
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
    
    elif request.method == 'DELETE':
        # 检查权限
        is_auth, user_data, error = check_auth('delete')
        if not is_auth:
            return error[0], error[1]
        
        # 删除生态关系
        try:
            result = relationship_model.delete_relationship(relationship_id)
            if result:
                log_user_action('delete', 'relationship', relationship_id)
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

@app.route('/api/observations', methods=['GET', 'POST'])
def api_observations():
    """观测记录API"""
    if request.method == 'POST':
        # 检查权限
        is_auth, user_data, error = check_auth('add')
        if not is_auth:
            return error[0], error[1]
        
        data = request.json
        obs_id = observation_model.add_observation(
            species_id=data['species_id'],
            observer=data.get('observer', ''),
            location=data.get('location', ''),
            count=data.get('count', 1),
            behavior=data.get('behavior', '')
        )
        log_user_action('add', 'observation', obs_id, details=data)
        return jsonify({'success': True, 'id': obs_id})
    else:
        species_id = request.args.get('species_id')
        observations = observation_model.list_observations(species_id=species_id)
        return jsonify(observations)


@app.route('/api/observation/<obs_id>', methods=['GET', 'PUT', 'DELETE'])
def api_observation_detail(obs_id):
    """观测记录详情 API - 查询、更新、删除"""
    
    if request.method == 'GET':
        # 查询观测记录详情
        observation = observation_model.get_observation(obs_id)
        if observation:
            return jsonify(observation)
        return jsonify({'error': 'Not found'}), 404
    
    elif request.method == 'PUT':
        # 检查权限
        is_auth, user_data, error = check_auth('edit')
        if not is_auth:
            return error[0], error[1]
        
        # 更新观测记录
        try:
            data = request.json
            
            # 构建更新数据
            update_data = {}
            
            # 允许更新的字段
            if 'observation' in data:
                update_data['observation'] = data['observation']
            
            if 'observer' in data:
                update_data['observer'] = data['observer']
            
            if not update_data:
                return jsonify({
                    'success': False,
                    'message': '没有提供要更新的字段'
                }), 400
            
            result = observation_model.update_observation(obs_id, update_data)
            
            if result:
                log_user_action('edit', 'observation', obs_id, details=update_data)
                return jsonify({
                    'success': True,
                    'message': '观测记录更新成功'
                })
            else:
                return jsonify({
                    'success': False,
                    'message': '观测记录不存在'
                }), 404
                
        except Exception as e:
            return jsonify({
                'success': False,
                'message': str(e)
            }), 500
    
    elif request.method == 'DELETE':
        # 检查权限
        is_auth, user_data, error = check_auth('delete')
        if not is_auth:
            return error[0], error[1]
        
        # 删除观测记录
        try:
            result = observation_model.delete_observation(obs_id)
            if result:
                log_user_action('delete', 'observation', obs_id)
                return jsonify({
                    'success': True,
                    'message': '观测记录删除成功'
                })
            else:
                return jsonify({
                    'success': False,
                    'message': '观测记录不存在'
                }), 404
        except Exception as e:
            return jsonify({
                'success': False,
                'message': str(e)
            }), 500


@app.route('/api/observation/<obs_id>/verify', methods=['POST'])
def api_verify_observation(obs_id):
    """验证观测记录"""
    try:
        data = request.json
        verifier_name = data.get('verifier_name', '管理员')
        
        result = observation_model.verify_observation(obs_id, verifier_name)
        
        if result:
            return jsonify({
                'success': True,
                'message': '观测记录已验证'
            })
        else:
            return jsonify({
                'success': False,
                'message': '验证失败'
            }), 404
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route('/api/observations/stream', methods=['GET'])
def api_observations_stream():
    """获取实时观测数据流"""
    try:
        count = int(request.args.get('count', 10))
        stream_data = observation_model.get_recent_stream_data(count)
        
        return jsonify({
            'success': True,
            'data': stream_data
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route('/api/observations/statistics', methods=['GET'])
def api_observations_statistics():
    """获取观测记录统计数据"""
    try:
        stats = observation_model.get_statistics()
        return jsonify(stats)
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500



@app.route('/api/search', methods=['GET'])
def api_search():
    """全文搜索 - 跨所有集合"""
    keyword = request.args.get('q', '')
    category = request.args.get('category', '')
    
    if not keyword:
        return jsonify({'error': '搜索关键词不能为空'}), 400
    
    try:
        # ⭐⭐⭐ 添加这一行 - 递增今日搜索次数 ⭐⭐⭐
        db_manager.redis.incr('today_searches')
        
        # 使用 SearchModel 进行统一搜索
        results = search_model.search_all(keyword, category=category if category else None)
        
        # 更新热门搜索（使用 Redis ZINCRBY）
        # 这个操作在 search_model.search_all 中的 _save_search_history 已经完成
        
        return jsonify({
            'success': True,
            'results': results,
            'total': results.get('total', 0)
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

# 搜索相关 API 路由
# 获取热门搜索词 API
@app.route('/api/search/popular', methods=['GET'])
def api_popular_searches():
    """
    获取热门搜索词 API
    
    Query Parameters:
        limit: 可选，返回数量（默认10）
    """
    limit = int(request.args.get('limit', 10))
    
    try:
        popular = search_model.get_popular_searches(limit)
        
        return jsonify({
            'success': True,
            'popular_searches': popular
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route('/api/search/recommendations', methods=['GET'])
def api_search_recommendations():
    """
    获取推荐内容 API
    
    Query Parameters:
        keyword: 基于此关键词推荐
        limit: 可选，每类推荐数量（默认5）
    """
    keyword = request.args.get('keyword', '').strip()
    limit = int(request.args.get('limit', 5))
    
    if not keyword:
        return jsonify({
            'success': False,
            'message': '请提供关键词'
        }), 400
    
    try:
        recommendations = search_model.get_recommendations(keyword, limit)
        
        return jsonify({
            'success': True,
            'recommendations': recommendations
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route('/api/search/advanced', methods=['POST'])
def api_advanced_search():
    """
    高级搜索 API
    
    Body (JSON):
    {
        "name": "东北虎",
        "category": "哺乳动物",
        "province": "吉林省",
        "verified": true
    }
    """
    try:
        filters = request.json
        
        if not filters:
            return jsonify({
                'success': False,
                'message': '请提供搜索条件'
            }), 400
        
        results = search_model.advanced_search(filters)
        
        return jsonify({
            'success': True,
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
        # 检查权限
        is_auth, user_data, error = check_auth('add')
        if not is_auth:
            return error[0], error[1]
        
        data = request.json
        habitat_id = habitat_model.add_habitat(
            name=data['name'],
            location=data.get('location', {}),
            environment=data.get('environment', ''),
            protection_level=data.get('protection_level', '')
        )
        log_user_action('add', 'habitat', habitat_id, details=data)
        return jsonify({'success': True, 'id': habitat_id})
    else:
        habitats = habitat_model.list_habitats()
        return jsonify(habitats)


@app.route('/api/habitats/<habitat_id>', methods=['GET', 'DELETE'])
def api_habitat_detail(habitat_id):
    """栖息地详情、删除API"""
    if request.method == 'DELETE':
        # 检查权限
        is_auth, user_data, error = check_auth('delete')
        if not is_auth:
            return error[0], error[1]
        
        result = habitat_model.delete_habitat(habitat_id)
        if result:
            log_user_action('delete', 'habitat', habitat_id)
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'message': '栖息地不存在'}), 404
    else:
        habitat = habitat_model.get_habitat(habitat_id)
        return jsonify(habitat) if habitat else jsonify({'error': 'Not found'}), 404


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
        
        # ⭐⭐⭐ 新增：注册成功后自动登录 ⭐⭐⭐
        login_result = user_model.login(username, password)
        
        if login_result:
            return jsonify({
                'success': True,
                'message': '注册成功',
                'user_id': user_id,
                'session_token': login_result['session_token'],  # 返回会话令牌
                'user': login_result['user']
            })
        else:
            # 注册成功但登录失败（理论上不会发生）
            return jsonify({
                'success': True,
                'message': '注册成功，请登录',
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
    """获取物种分类分布数据 - 使用 MongoDB 聚合管道"""
    try:
        # 使用 MongoDB 聚合管道统计物种分类
        pipeline = [
            {"$match": {"category": {"$exists": True, "$ne": ""}}},
            {"$group": {"_id": "$category", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}
        ]
        
        result = list(db_manager.mongo['species'].aggregate(pipeline))
        
        # 如果数据为空，返回 Mock 数据
        if not result or len(result) == 0:
            data = {
                "labels": ["哺乳动物", "鸟类", "爬行动物", "两栖动物", "鱼类", "植物", "昆虫"],
                "data": [15, 12, 8, 6, 10, 20, 18],
                "percentages": [18.75, 15.0, 10.0, 7.5, 12.5, 25.0, 22.5],
                "total": 89,
                "details": [
                    {"category": "哺乳动物", "count": 15, "percentage": 18.75},
                    {"category": "鸟类", "count": 12, "percentage": 15.0},
                    {"category": "爬行动物", "count": 8, "percentage": 10.0},
                    {"category": "两栖动物", "count": 6, "percentage": 7.5},
                    {"category": "鱼类", "count": 10, "percentage": 12.5},
                    {"category": "植物", "count": 20, "percentage": 25.0},
                    {"category": "昆虫", "count": 18, "percentage": 22.5}
                ]
            }
        else:
            # 计算总数和百分比
            total = sum(item['count'] for item in result)
            labels = [item['_id'] for item in result]
            data_counts = [item['count'] for item in result]
            percentages = [
                round((item['count'] / total * 100), 2) if total > 0 else 0
                for item in result
            ]
            
            data = {
                "labels": labels,
                "data": data_counts,
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
    """获取地理分布统计数据 - 使用 MongoDB 聚合管道"""
    try:
        # 方法1: 从观测记录中统计地理分布
        pipeline = [
            {"$match": {
                "$or": [
                    {"observation.location.province": {"$exists": True, "$ne": ""}},
                    {"location": {"$exists": True, "$ne": ""}}
                ]
            }},
            {"$project": {
                "province": {
                    "$ifNull": [
                        "$observation.location.province",
                        {"$ifNull": ["$location.province", "$location"]}
                    ]
                },
                "species_id": 1
            }},
            {"$match": {"province": {"$ne": None, "$ne": ""}}},
            {"$group": {
                "_id": "$province",
                "unique_species": {"$addToSet": "$species_id"}
            }},
            {"$project": {
                "province": "$_id",
                "count": {"$size": "$unique_species"},
                "species_count": {"$size": "$unique_species"},
                "_id": 0
            }},
            {"$sort": {"count": -1}},
            {"$limit": 20}
        ]
        
        result = list(db_manager.mongo['observations'].aggregate(pipeline))
        
        # 如果观测记录中没有数据，尝试从栖息地统计
        if not result or len(result) == 0:
            habitat_pipeline = [
                {"$match": {"location": {"$exists": True}}},
                {"$project": {
                    "province": {
                        "$ifNull": [
                            "$location.province",
                            {"$ifNull": ["$location.city", "未知地区"]}
                        ]
                    }
                }},
                {"$group": {
                    "_id": "$province",
                    "count": {"$sum": 1}
                }},
                {"$project": {
                    "province": "$_id",
                    "count": 1,
                    "species_count": 1,
                    "_id": 0
                }},
                {"$sort": {"count": -1}}
            ]
            result = list(db_manager.mongo['habitats'].aggregate(habitat_pipeline))
        
        # 如果数据为空，返回 Mock 数据
        if not result or len(result) == 0:
            data = [
                {"province": "吉林省", "count": 25, "species_count": 25},
                {"province": "内蒙古自治区", "count": 18, "species_count": 18},
                {"province": "黑龙江省", "count": 22, "species_count": 22},
                {"province": "辽宁省", "count": 15, "species_count": 15},
                {"province": "四川省", "count": 30, "species_count": 30},
                {"province": "云南省", "count": 28, "species_count": 28},
                {"province": "新疆维吾尔自治区", "count": 20, "species_count": 20},
                {"province": "西藏自治区", "count": 12, "species_count": 12}
            ]
        else:
            data = result
        
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
    """获取生态关系类型占比数据 - 使用 MongoDB 聚合管道"""
    try:
        # 从 MongoDB 获取关系类型统计
        pipeline = [
            {"$match": {"type": {"$exists": True, "$ne": ""}}},
            {"$group": {"_id": "$type", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}
        ]
        result = list(db_manager.mongo['relationships'].aggregate(pipeline))
        
        # 如果数据为空，返回 Mock 数据
        if not result or len(result) == 0:
            data = {
                'labels': ['PREYS_ON', 'COMPETES_WITH', 'SYMBIOSIS', 'PARASITISM'],
                'data': [45, 12, 8, 5],
                'percentages': [64.29, 17.14, 11.43, 7.14],
                'total': 70,
                'details': [
                    {'type': 'PREYS_ON', 'count': 45, 'percentage': 64.29},
                    {'type': 'COMPETES_WITH', 'count': 12, 'percentage': 17.14},
                    {'type': 'SYMBIOSIS', 'count': 8, 'percentage': 11.43},
                    {'type': 'PARASITISM', 'count': 5, 'percentage': 7.14}
                ]
            }
        else:
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
        
        try:
            network_data = network_analysis.export_network_for_visualization(limit_nodes=limit_nodes)
            
            # 如果数据为空，返回 Mock 数据
            if not network_data or not network_data.get('nodes') or len(network_data.get('nodes', [])) == 0:
                # 生成 Mock 网络数据
                mock_nodes = [
                    {"id": "1", "name": "东北虎", "category": "哺乳动物"},
                    {"id": "2", "name": "梅花鹿", "category": "哺乳动物"},
                    {"id": "3", "name": "野兔", "category": "哺乳动物"},
                    {"id": "4", "name": "金雕", "category": "鸟类"},
                    {"id": "5", "name": "草", "category": "植物"}
                ]
                
                mock_links = [
                    {"source": "1", "target": "2", "type": "PREYS_ON"},
                    {"source": "2", "target": "5", "type": "PREYS_ON"},
                    {"source": "4", "target": "3", "type": "PREYS_ON"},
                    {"source": "3", "target": "5", "type": "PREYS_ON"},
                    {"source": "1", "target": "3", "type": "PREYS_ON"}
                ]
                
                network_data = {
                    "nodes": mock_nodes,
                    "links": mock_links,
                    "node_count": len(mock_nodes),
                    "link_count": len(mock_links)
                }
        except Exception as e:
            print(f"⚠️ 获取网络数据失败: {e}")
            # 返回 Mock 数据
            mock_nodes = [
                {"id": "1", "name": "东北虎", "category": "哺乳动物"},
                {"id": "2", "name": "梅花鹿", "category": "哺乳动物"},
                {"id": "3", "name": "野兔", "category": "哺乳动物"},
                {"id": "4", "name": "金雕", "category": "鸟类"},
                {"id": "5", "name": "草", "category": "植物"}
            ]
            
            mock_links = [
                {"source": "1", "target": "2", "type": "PREYS_ON"},
                {"source": "2", "target": "5", "type": "PREYS_ON"},
                {"source": "4", "target": "3", "type": "PREYS_ON"},
                {"source": "3", "target": "5", "type": "PREYS_ON"},
                {"source": "1", "target": "3", "type": "PREYS_ON"}
            ]
            
            network_data = {
                "nodes": mock_nodes,
                "links": mock_links,
                "node_count": len(mock_nodes),
                "link_count": len(mock_links)
            }
        
        return jsonify({
            'success': True,
            'data': network_data
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

# 系统监控相关 API 路由
@app.route('/api/monitor/stats', methods=['GET'])
def api_monitor_stats():
    """获取系统监控统计数据"""
    import time
    from datetime import datetime
    
    try:
        stats = {}
        
        # 1. Redis 实时指标
        try:
            api_call_count = db_manager.redis.get('api_call_count') or 0
            today_searches = db_manager.redis.get('today_searches') or 0
            online_users = len(db_manager.redis.keys('session:*'))
            
            stats['redis'] = {
                'api_call_count': int(api_call_count),
                'today_searches': int(today_searches),
                'online_users': online_users
            }
        except Exception as e:
            stats['redis'] = {'error': str(e)}
        
        # 2. MongoDB 性能数据
        try:
            mongo_stats = {}
            collections = ['species', 'habitats', 'observations', 'relationships', 'users', 'logs']
            for col_name in collections:
                col = db_manager.mongo[col_name]
                count = col.count_documents({})
                mongo_stats[col_name] = {
                    'count': count,
                    'size_mb': 0  # 简化版本，实际可以查询集合统计信息
                }
            stats['mongodb'] = mongo_stats
        except Exception as e:
            stats['mongodb'] = {'error': str(e)}
        
        # 3. 数据库连接延迟检查
        latency = {}
        
        # MongoDB 延迟
        try:
            start = time.time()
            db_manager.mongo['species'].find_one()
            latency['mongodb'] = round((time.time() - start) * 1000, 2)  # 毫秒
        except Exception as e:
            latency['mongodb'] = None
        
        # Neo4j 延迟
        try:
            start = time.time()
            with db_manager.neo4j.session() as session:
                session.run("RETURN 1")
            latency['neo4j'] = round((time.time() - start) * 1000, 2)
        except Exception as e:
            latency['neo4j'] = None
        
        # Redis 延迟
        try:
            start = time.time()
            db_manager.redis.ping()
            latency['redis'] = round((time.time() - start) * 1000, 2)
        except Exception as e:
            latency['redis'] = None
        
        stats['latency'] = latency
        stats['timestamp'] = datetime.now().isoformat()
        
        return jsonify({
            'success': True,
            'data': stats
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route('/api/monitor/quality', methods=['GET'])
def api_monitor_quality():
    """数据质量检查"""
    try:
        quality_report = {
            'integrity': {},
            'consistency': {},
            'alerts': []
        }
        
        # 1. 数据完整性检查
        try:
            # 检查缺少 category 或 habitat 的物种
            missing_category = db_manager.mongo['species'].count_documents({
                '$or': [
                    {'category': {'$exists': False}},
                    {'category': ''}
                ]
            })
            missing_habitat = db_manager.mongo['species'].count_documents({
                '$or': [
                    {'habitat': {'$exists': False}},
                    {'habitat': ''}
                ]
            })
            
            quality_report['integrity'] = {
                'missing_category': missing_category,
                'missing_habitat': missing_habitat,
                'total_species': db_manager.mongo['species'].count_documents({})
            }
        except Exception as e:
            quality_report['integrity'] = {'error': str(e)}
        
        # 2. 一致性检查：Neo4j 节点 vs MongoDB 记录
        try:
            with db_manager.neo4j.session() as session:
                # 获取 Neo4j 中的所有物种节点
                result = session.run("MATCH (s:Species) RETURN s.id as id")
                neo4j_ids = [record['id'] for record in result]
            
            # 检查 MongoDB 中是否存在对应记录
            missing_in_mongo = []
            for neo4j_id in neo4j_ids:
                from bson import ObjectId
                try:
                    exists = db_manager.mongo['species'].find_one({'_id': ObjectId(neo4j_id)})
                    if not exists:
                        missing_in_mongo.append(neo4j_id)
                except:
                    missing_in_mongo.append(neo4j_id)
            
            quality_report['consistency'] = {
                'neo4j_nodes': len(neo4j_ids),
                'missing_in_mongo': len(missing_in_mongo),
                'missing_ids': missing_in_mongo[:10]  # 只返回前10个
            }
        except Exception as e:
            quality_report['consistency'] = {'error': str(e)}
        
        # 3. 获取最近的异常预警
        try:
            alerts = list(db_manager.mongo['alerts'].find().sort('timestamp', -1).limit(10))
            quality_report['alerts'] = [
                {
                    'type': alert.get('type', 'unknown'),
                    'message': alert.get('message', ''),
                    'timestamp': str(alert.get('timestamp', ''))
                }
                for alert in alerts
            ]
        except Exception as e:
            quality_report['alerts'] = []
        
        return jsonify({
            'success': True,
            'data': quality_report
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


# 异常预警辅助函数
def log_alert(alert_type, message, **extra):
    """记录异常预警"""
    try:
        from datetime import datetime
        alert_doc = {
            'type': alert_type,
            'message': message,
            'timestamp': datetime.now(),
            **extra
        }
        db_manager.mongo['alerts'].insert_one(alert_doc)
    except Exception as e:
        print(f"⚠️ 记录异常预警失败: {e}")


# API 调用计数器和慢查询监控
@app.before_request
def track_api_calls_and_slow_queries():
    """记录 API 调用次数和慢查询"""
    import time
    request.start_time = time.time()
    
    # 记录 API 调用次数
    try:
        db_manager.redis.incr('api_call_count')
    except:
        pass


@app.after_request
def log_slow_queries(response):
    """记录慢查询"""
    import time
    try:
        elapsed = (time.time() - request.start_time) * 1000  # 毫秒
        if elapsed > 1000:  # 超过1秒
            log_alert(
                'slow_query',
                f'API 请求耗时过长: {request.path}',
                path=request.path,
                method=request.method,
                elapsed_ms=elapsed
            )
    except:
        pass
    
    return response

# ==================== 用户管理相关 API ====================

@app.route('/api/users', methods=['GET'])
@require_auth('view')  # 只有登录用户可查看
def api_list_users():
    """获取用户列表（仅管理员）"""
    # 检查是否为管理员
    if request.current_user.get('role') != 'admin':
        return jsonify({
            'success': False,
            'message': '只有管理员才能查看用户列表'
        }), 403
    
    try:
        # 从 MongoDB 获取所有用户
        users = list(db_manager.mongo['users'].find())
        
        # 序列化并移除敏感信息
        users_data = []
        for user in users:
            user_data = serialize_doc(user)
            user_data.pop('password_hash', None)  # 移除密码哈希
            users_data.append(user_data)
        
        return jsonify({
            'success': True,
            'users': users_data
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route('/api/user/<user_id>', methods=['GET', 'PUT'])
@require_auth('view')
def api_user_detail(user_id):
    """获取或更新用户详情"""
    if request.method == 'GET':
        try:
            user = user_model.get_user(user_id)
            if user:
                return jsonify({
                    'success': True,
                    'user': user
                })
            else:
                return jsonify({
                    'success': False,
                    'message': '用户不存在'
                }), 404
        except Exception as e:
            return jsonify({
                'success': False,
                'message': str(e)
            }), 500
    
    elif request.method == 'PUT':
        # 只有管理员可以修改用户
        if request.current_user.get('role') != 'admin':
            return jsonify({
                'success': False,
                'message': '只有管理员才能修改用户信息'
            }), 403
        
        try:
            from bson import ObjectId
            data = request.json
            
            # 更新用户信息
            update_data = {}
            if 'role' in data:
                update_data['role'] = data['role']
            if 'active' in data:
                update_data['active'] = data['active']
            
            result = db_manager.mongo['users'].update_one(
                {'_id': ObjectId(user_id)},
                {'$set': update_data}
            )
            
            if result.matched_count > 0:
                log_user_action('edit', 'user', user_id, details=update_data)
                return jsonify({
                    'success': True,
                    'message': '更新成功'
                })
            else:
                return jsonify({
                    'success': False,
                    'message': '用户不存在'
                }), 404
        except Exception as e:
            return jsonify({
                'success': False,
                'message': str(e)
            }), 500


@app.route('/api/user/<user_id>/logs', methods=['GET'])
@require_auth('view')
def api_user_logs(user_id):
    """获取用户操作日志（仅管理员）"""
    if request.current_user.get('role') != 'admin':
        return jsonify({
            'success': False,
            'message': '只有管理员才能查看操作日志'
        }), 403
    
    try:
        # 从 MongoDB 获取该用户的操作日志
        logs = list(
            db_manager.mongo['logs']
            .find({'user_id': user_id})
            .sort('timestamp', -1)
            .limit(100)
        )
        
        logs_data = [serialize_doc(log) for log in logs]
        
        return jsonify({
            'success': True,
            'logs': logs_data
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@app.route('/register')
def register_page():
    """注册页面"""
    return render_template('register.html')

@app.route('/users')
def users_page():
    """用户管理页面（仅管理员）"""
    return render_template('users.html')

if __name__ == '__main__':
    app.run(debug=True, port=5001)

