// charts.js
// 图表渲染脚本

let categoryChart = null;
let distributionChart = null;
let relationshipChart = null;
let networkGraph = null;

// 加载物种分类分布饼图
async function loadCategoryChart() {
    try {
        const response = await fetch('/api/analytics/category-distribution');
        const result = await response.json();
        
        if (result.success && result.data) {
            const data = result.data;
            
            const ctx = document.getElementById('categoryChart').getContext('2d');
            
            // 销毁旧图表（如果存在）
            if (categoryChart) {
                categoryChart.destroy();
            }
            
            categoryChart = new Chart(ctx, {
                type: 'pie',
                data: {
                    labels: data.labels || [],
                    datasets: [{
                        data: data.data || [],
                        backgroundColor: [
                            '#FF6384',
                            '#36A2EB',
                            '#FFCE56',
                            '#4BC0C0',
                            '#9966FF',
                            '#FF9F40',
                            '#FF6384',
                            '#C9CBCF'
                        ]
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: true,
                    plugins: {
                        legend: {
                            position: 'right',
                        },
                        title: {
                            display: true,
                            text: `总物种数: ${data.total || 0}`
                        },
                        tooltip: {
                            callbacks: {
                                label: function(context) {
                                    const label = context.label || '';
                                    const value = context.parsed || 0;
                                    const percentage = data.percentages[context.dataIndex] || 0;
                                    return `${label}: ${value} (${percentage}%)`;
                                }
                            }
                        }
                    }
                }
            });
        }
    } catch (error) {
        console.error('加载分类分布图表失败:', error);
    }
}

// 加载地理分布柱状图
async function loadDistributionChart() {
    try {
        const response = await fetch('/api/analytics/distribution-stats');
        const result = await response.json();
        
        if (result.success && result.data) {
            const data = result.data;
            
            // 准备数据
            const labels = [];
            const counts = [];
            
            // 只显示前 15 个省份
            const topData = data.slice(0, 15);
            
            topData.forEach(item => {
                labels.push(item.province || item.region || '未知地区');
                counts.push(item.count || item.species_count || 0);
            });
            
            const ctx = document.getElementById('distributionChart').getContext('2d');
            
            // 销毁旧图表（如果存在）
            if (distributionChart) {
                distributionChart.destroy();
            }
            
            distributionChart = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: labels,
                    datasets: [{
                        label: '物种数量',
                        data: counts,
                        backgroundColor: '#36A2EB',
                        borderColor: '#1E88E5',
                        borderWidth: 1
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: true,
                    plugins: {
                        legend: {
                            display: false
                        },
                        title: {
                            display: true,
                            text: '各地区物种分布统计'
                        }
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            ticks: {
                                stepSize: 1
                            }
                        },
                        x: {
                            ticks: {
                                maxRotation: 45,
                                minRotation: 45
                            }
                        }
                    }
                }
            });
        }
    } catch (error) {
        console.error('加载地理分布图表失败:', error);
    }
}

// 加载生态关系类型占比图
async function loadRelationshipChart() {
    try {
        const response = await fetch('/api/analytics/relationship-types');
        const result = await response.json();
        
        if (result.success && result.data) {
            const data = result.data;
            
            // 关系类型中文映射
            const typeMapping = {
                'PREYS_ON': '捕食关系',
                'COMPETES_WITH': '竞争关系',
                'SYMBIOSIS': '共生关系',
                'PARASITISM': '寄生关系'
            };
            
            const labels = (data.labels || []).map(label => typeMapping[label] || label);
            
            const ctx = document.getElementById('relationshipChart').getContext('2d');
            
            // 销毁旧图表（如果存在）
            if (relationshipChart) {
                relationshipChart.destroy();
            }
            
            relationshipChart = new Chart(ctx, {
                type: 'doughnut',
                data: {
                    labels: labels,
                    datasets: [{
                        data: data.data || [],
                        backgroundColor: [
                            '#FF6384',
                            '#36A2EB',
                            '#FFCE56',
                            '#4BC0C0',
                            '#9966FF'
                        ]
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: true,
                    plugins: {
                        legend: {
                            position: 'right',
                        },
                        title: {
                            display: true,
                            text: `总关系数: ${data.total || 0}`
                        },
                        tooltip: {
                            callbacks: {
                                label: function(context) {
                                    const label = context.label || '';
                                    const value = context.parsed || 0;
                                    const percentage = data.percentages[context.dataIndex] || 0;
                                    return `${label}: ${value} (${percentage}%)`;
                                }
                            }
                        }
                    }
                }
            });
        }
    } catch (error) {
        console.error('加载关系类型图表失败:', error);
    }
}

// 加载生态网络可视化
async function loadNetworkGraph() {
    try {
        const limitNodes = document.getElementById('nodeLimit')?.value || 50;
        const response = await fetch(`/api/analytics/network-graph?limit_nodes=${limitNodes}`);
        const result = await response.json();
        
        if (result.success && result.data) {
            const networkData = result.data;
            renderNetworkGraph(networkData);
        }
    } catch (error) {
        console.error('加载网络图失败:', error);
        document.getElementById('networkContainer').innerHTML = 
            '<p class="error">加载网络图失败，请检查数据连接</p>';
    }
}

// 使用 D3.js 渲染生态网络图
function renderNetworkGraph(data) {
    const container = document.getElementById('networkContainer');
    container.innerHTML = ''; // 清空容器
    
    if (!data.nodes || data.nodes.length === 0) {
        container.innerHTML = '<p class="no-data">暂无网络数据</p>';
        return;
    }
    
    const width = container.clientWidth || 800;
    const height = 600;
    
    // 创建 SVG
    const svg = d3.select('#networkContainer')
        .append('svg')
        .attr('width', width)
        .attr('height', height);
    
    // 创建缩放和平移行为
    const zoom = d3.zoom()
        .scaleExtent([0.1, 4])
        .on('zoom', (event) => {
            g.attr('transform', event.transform);
        });
    
    svg.call(zoom);
    
    // 创建主容器组
    const g = svg.append('g');
    
    // 添加箭头标记（定义）
    svg.append('defs').append('marker')
        .attr('id', 'arrowhead')
        .attr('viewBox', '0 -5 10 10')
        .attr('refX', 25)
        .attr('refY', 0)
        .attr('markerWidth', 6)
        .attr('markerHeight', 6)
        .attr('orient', 'auto')
        .append('path')
        .attr('d', 'M0,-5L10,0L0,5')
        .attr('fill', '#999');
    
    // 绘制连接线
    const link = g.append('g')
        .selectAll('line')
        .data(data.links)
        .enter()
        .append('line')
        .attr('stroke', '#999')
        .attr('stroke-opacity', 0.6)
        .attr('stroke-width', 2)
        .attr('marker-end', 'url(#arrowhead)');
    
    // 绘制节点
    const node = g.append('g')
        .selectAll('circle')
        .data(data.nodes)
        .enter()
        .append('circle')
        .attr('r', 10)
        .attr('fill', '#36A2EB')
        .attr('stroke', '#fff')
        .attr('stroke-width', 2);
    
    // 添加鼠标悬停提示
    node.append('title')
        .text(d => `${d.name}\n类别: ${d.category || '未知'}`);
    
    // 添加节点标签
    const labels = g.append('g')
        .selectAll('text')
        .data(data.nodes)
        .enter()
        .append('text')
        .text(d => d.name)
        .attr('font-size', '12px')
        .attr('dx', 15)
        .attr('dy', 5)
        .attr('fill', '#333');
    
    // 创建模拟力
    const simulation = d3.forceSimulation(data.nodes)
        .force('link', d3.forceLink(data.links).id(d => d.id).distance(100))
        .force('charge', d3.forceManyBody().strength(-300))
        .force('center', d3.forceCenter(width / 2, height / 2))
        .force('collision', d3.forceCollide().radius(30));
    
    // 拖拽行为
    function drag(simulation) {
        function dragstarted(event, d) {
            if (!event.active) simulation.alphaTarget(0.3).restart();
            d.fx = d.x;
            d.fy = d.y;
        }
        
        function dragged(event, d) {
            d.fx = event.x;
            d.fy = event.y;
        }
        
        function dragended(event, d) {
            if (!event.active) simulation.alphaTarget(0);
            d.fx = null;
            d.fy = null;
        }
        
        return d3.drag()
            .on('start', dragstarted)
            .on('drag', dragged)
            .on('end', dragended);
    }
    
    // 应用拖拽行为到节点
    node.call(drag(simulation));
    
    // 更新节点和边的位置
    simulation.on('tick', () => {
        link
            .attr('x1', d => d.source.x)
            .attr('y1', d => d.source.y)
            .attr('x2', d => d.target.x)
            .attr('y2', d => d.target.y);
        
        node
            .attr('cx', d => d.x)
            .attr('cy', d => d.y);
        
        labels
            .attr('x', d => d.x)
            .attr('y', d => d.y);
    });
    
    // 存储图引用以便后续操作
    networkGraph = { svg, simulation, node, link, labels };
}

