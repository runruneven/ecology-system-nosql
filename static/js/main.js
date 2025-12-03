// 页面加载完成后执行
document.addEventListener('DOMContentLoaded', function() {
    console.log('页面加载完成');
    loadStatistics();
});

// 加载统计数据
function loadStatistics() {
    fetch('/api/statistics')
        .then(response => response.json())
        .then(data => {
            console.log('统计数据:', data);
            // 可以在这里更新页面上的统计数字
        })
        .catch(error => console.error('加载统计失败:', error));
}
