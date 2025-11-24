# src/analytics/network_analysis.py
"""生态关系网络分析模块"""

from ..db_manager import db_manager


class NetworkAnalysis:
    """生态网络分析类"""
    
    def __init__(self):
        self.neo4j = db_manager.neo4j
        self.mongo_col = db_manager.mongo['relationships']
    
    def get_network_stats(self):
        """
        获取网络统计信息
        
        Returns:
            网络统计信息字典，包含：
            - total_nodes: 总节点数（物种数量）
            - total_edges: 总边数（关系数量）
            - density: 网络密度（实际边数 / 最大可能边数）
        """
        with self.neo4j.session() as session:
            # 获取节点数
            node_result = session.run("MATCH (s:Species) RETURN count(s) as count")
            node_record = node_result.single()
            total_nodes = node_record['count'] if node_record else 0
            
            # 获取边数
            edge_result = session.run("MATCH ()-[r]->() RETURN count(r) as count")
            edge_record = edge_result.single()
            total_edges = edge_record['count'] if edge_record else 0
            
            # 计算网络密度
            # 密度 = 实际边数 / (节点数 * (节点数 - 1))
            # 对于有向图：最大可能边数 = n * (n - 1)
            max_possible_edges = total_nodes * (total_nodes - 1) if total_nodes > 1 else 0
            density = total_edges / max_possible_edges if max_possible_edges > 0 else 0
            
            # 获取平均度数（每个节点的平均连接数）
            # 平均度数 = 2 * 边数 / 节点数（对于无向图）
            # 对于有向图：平均出度 = 边数 / 节点数
            avg_degree = total_edges / total_nodes if total_nodes > 0 else 0
            
            return {
                "total_nodes": total_nodes,
                "total_edges": total_edges,
                "density": round(density, 4),
                "avg_degree": round(avg_degree, 2),
                "max_possible_edges": max_possible_edges
            }
    
    def find_key_species(self, top_n=10, algorithm='degree'):
        """
        找出生态网络中的关键物种
        
        Args:
            top_n: 返回前 N 个关键物种
            algorithm: 使用的算法（'degree' 或 'pagerank'）
        
        Returns:
            关键物种列表，格式：
            [{"species_id": "...", "name": "...", "score": 10.5, "rank": 1}, ...]
        """
        with self.neo4j.session() as session:
            if algorithm == 'degree':
                # 使用度中心性（度中心性）
                # 计算每个节点的度数（连接的边数）
                query = """
                MATCH (s:Species)
                OPTIONAL MATCH (s)-[r1]->()
                OPTIONAL MATCH ()-[r2]->(s)
                WITH s, 
                     size((s)-[]->()) as out_degree,
                     size([]-[]->(s)) as in_degree,
                     size((s)-[]-()) as total_degree
                RETURN s.id as species_id, 
                       s.name as name,
                       total_degree as degree,
                       out_degree,
                       in_degree
                ORDER BY total_degree DESC
                LIMIT $top_n
                """
                result = session.run(query, top_n=top_n)
                
                key_species = []
                rank = 1
                for record in result:
                    key_species.append({
                        "species_id": record['species_id'],
                        "name": record['name'],
                        "score": record['degree'],
                        "out_degree": record['out_degree'],
                        "in_degree": record['in_degree'],
                        "rank": rank,
                        "algorithm": "degree_centrality"
                    })
                    rank += 1
                
                return key_species
            
            elif algorithm == 'pagerank':
                # 使用 PageRank 算法（需要 Neo4j GDS 库支持）
                # 如果 GDS 库不可用，回退到度中心性
                try:
                    # 尝试使用 GDS PageRank
                    query = """
                    CALL gds.pageRank.stream('myGraph')
                    YIELD nodeId, score
                    RETURN gds.util.asNode(nodeId).name as name,
                           gds.util.asNode(nodeId).id as species_id,
                           score
                    ORDER BY score DESC
                    LIMIT $top_n
                    """
                    result = session.run(query, top_n=top_n)
                    
                    key_species = []
                    rank = 1
                    for record in result:
                        key_species.append({
                            "species_id": record['species_id'],
                            "name": record['name'],
                            "score": round(record['score'], 4),
                            "rank": rank,
                            "algorithm": "pagerank"
                        })
                        rank += 1
                    
                    return key_species
                except Exception as e:
                    print(f"PageRank 算法不可用，使用度中心性: {e}")
                    return self.find_key_species(top_n=top_n, algorithm='degree')
            else:
                raise ValueError(f"不支持的算法: {algorithm}")
    
    def get_food_chain_lengths(self):
        """
        统计所有食物链的长度分布
        
        Returns:
            食物链长度统计，格式：
            {
                "length_distribution": {1: 10, 2: 5, 3: 2, ...},
                "max_length": 5,
                "min_length": 1,
                "avg_length": 2.3
            }
        """
        with self.neo4j.session() as session:
            # 查找所有可能的最短路径（食物链）
            # 这里使用 PREYS_ON 关系类型
            query = """
            MATCH path = (start:Species)-[:PREYS_ON*1..10]->(end:Species)
            WHERE NOT ()-[:PREYS_ON]->(start)  // 起始节点（没有捕食者）
            AND NOT (end)-[:PREYS_ON]->()  // 终止节点（没有猎物）
            RETURN length(path) as chain_length
            """
            
            result = session.run(query)
            
            chain_lengths = []
            for record in result:
                length = record['chain_length']
                if length and length > 0:
                    chain_lengths.append(length)
            
            # 统计长度分布
            length_distribution = {}
            for length in chain_lengths:
                length_distribution[length] = length_distribution.get(length, 0) + 1
            
            # 计算统计信息
            if chain_lengths:
                max_length = max(chain_lengths)
                min_length = min(chain_lengths)
                avg_length = sum(chain_lengths) / len(chain_lengths)
            else:
                max_length = 0
                min_length = 0
                avg_length = 0
            
            return {
                "length_distribution": length_distribution,
                "max_length": max_length,
                "min_length": min_length,
                "avg_length": round(avg_length, 2),
                "total_chains": len(chain_lengths)
            }
    
    def export_network_for_visualization(self, limit_nodes=100):
        """
        导出节点和边的数据，用于前端可视化（如 D3.js）
        
        Args:
            limit_nodes: 限制导出的节点数量（避免数据过大）
        
        Returns:
            网络数据字典，格式：
            {
                "nodes": [{"id": "...", "name": "...", "category": "..."}, ...],
                "links": [{"source": "...", "target": "...", "type": "..."}, ...]
            }
        """
        with self.neo4j.session() as session:
            # 获取节点数据
            nodes_query = """
            MATCH (s:Species)
            RETURN s.id as id, s.name as name, s.category as category
            LIMIT $limit
            """
            nodes_result = session.run(nodes_query, limit=limit_nodes)
            
            nodes = []
            node_ids = set()  # 用于跟踪已包含的节点
            for record in nodes_result:
                node_data = {
                    "id": record['id'],
                    "name": record['name'],
                    "category": record.get('category', '未知')
                }
                nodes.append(node_data)
                node_ids.add(record['id'])
            
            # 获取边数据（只包含已导出的节点之间的关系）
            links_query = """
            MATCH (a:Species)-[r]->(b:Species)
            WHERE a.id IN $node_ids AND b.id IN $node_ids
            RETURN a.id as source, b.id as target, type(r) as type
            LIMIT 500
            """
            links_result = session.run(links_query, node_ids=list(node_ids))
            
            links = []
            for record in links_result:
                link_data = {
                    "source": record['source'],
                    "target": record['target'],
                    "type": record.get('type', 'UNKNOWN')
                }
                links.append(link_data)
            
            return {
                "nodes": nodes,
                "links": links,
                "node_count": len(nodes),
                "link_count": len(links)
            }
    
    def get_species_relationships(self, species_id):
        """
        获取某个物种的所有关系（用于详细信息展示）
        
        Args:
            species_id: 物种ID
        
        Returns:
            物种关系信息，包含捕食者、猎物等
        """
        with self.neo4j.session() as session:
            query = """
            MATCH (s:Species {id: $species_id})
            OPTIONAL MATCH (s)-[r1:PREYS_ON]->(prey:Species)
            OPTIONAL MATCH (predator:Species)-[r2:PREYS_ON]->(s)
            RETURN s.id as species_id,
                   s.name as species_name,
                   collect(DISTINCT {id: prey.id, name: prey.name}) as prey_list,
                   collect(DISTINCT {id: predator.id, name: predator.name}) as predator_list
            """
            result = session.run(query, species_id=species_id)
            record = result.single()
            
            if record:
                return {
                    "species_id": record['species_id'],
                    "species_name": record['species_name'],
                    "prey_list": [p for p in record['prey_list'] if p.get('id')],  # 过滤 None
                    "predator_list": [p for p in record['predator_list'] if p.get('id')],  # 过滤 None
                    "prey_count": len([p for p in record['prey_list'] if p.get('id')]),
                    "predator_count": len([p for p in record['predator_list'] if p.get('id')])
                }
            
            return None



