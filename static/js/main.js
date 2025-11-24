// main.js
// 通用前端工具函数

// ============================================
// 全局变量
// ============================================
const API_BASE_URL = '/api';
let loadingOverlay = null;
let toastContainer = null;

// 页面加载时初始化
document.addEventListener('DOMContentLoaded', function() {
    initToastContainer();
    console.log('页面加载完成');
});

// ============================================
// API 请求封装
// ============================================

/**
 * 统一的 API 请求函数
 * @param {string} url - 请求 URL
 * @param {object} options - 请求选项（method, body, headers 等）
 * @returns {Promise} - 返回响应数据
 */
async function apiRequest(url, options = {}) {
    // 添加基础 URL
    if (!url.startsWith('http')) {
        url = API_BASE_URL + url;
    }
    
    // 获取会话令牌
    const sessionToken = getSessionToken();
    
    // 设置默认 headers
    const defaultHeaders = {
        'Content-Type': 'application/json',
    };
    
    if (sessionToken) {
        defaultHeaders['X-Session-Token'] = sessionToken;
    }
    
    // 合并 headers
    const headers = {
        ...defaultHeaders,
        ...(options.headers || {})
    };
    
    // 设置默认选项
    const defaultOptions = {
        method: 'GET',
        headers: headers,
        ...options
    };
    
    // 如果 body 是对象，转换为 JSON
    if (defaultOptions.body && typeof defaultOptions.body === 'object') {
        defaultOptions.body = JSON.stringify(defaultOptions.body);
    }
    
    try {
        // 显示加载动画（可选）
        if (options.showLoading !== false) {
            showLoading();
        }
        
        const response = await fetch(url, defaultOptions);
        const data = await response.json();
        
        // 隐藏加载动画
        if (options.showLoading !== false) {
            hideLoading();
        }
        
        // 处理错误响应
        if (!response.ok) {
            throw new Error(data.message || `HTTP ${response.status}: ${response.statusText}`);
        }
        
        return data;
    } catch (error) {
        // 隐藏加载动画
        if (options.showLoading !== false) {
            hideLoading();
        }
        
        console.error('API 请求失败:', error);
        
        // 显示错误提示
        if (options.showError !== false) {
            showError(error.message || '请求失败，请重试');
        }
        
        throw error;
    }
}

/**
 * GET 请求
 * @param {string} url - 请求 URL
 * @param {object} params - 查询参数
 * @param {object} options - 其他选项
 * @returns {Promise}
 */
async function apiGet(url, params = {}, options = {}) {
    // 构建查询字符串
    const queryString = new URLSearchParams(params).toString();
    if (queryString) {
        url += (url.includes('?') ? '&' : '?') + queryString;
    }
    
    return apiRequest(url, {
        method: 'GET',
        ...options
    });
}

/**
 * POST 请求
 * @param {string} url - 请求 URL
 * @param {object} data - 请求体数据
 * @param {object} options - 其他选项
 * @returns {Promise}
 */
async function apiPost(url, data = {}, options = {}) {
    return apiRequest(url, {
        method: 'POST',
        body: data,
        ...options
    });
}

/**
 * PUT 请求
 * @param {string} url - 请求 URL
 * @param {object} data - 请求体数据
 * @param {object} options - 其他选项
 * @returns {Promise}
 */
async function apiPut(url, data = {}, options = {}) {
    return apiRequest(url, {
        method: 'PUT',
        body: data,
        ...options
    });
}

/**
 * DELETE 请求
 * @param {string} url - 请求 URL
 * @param {object} options - 其他选项
 * @returns {Promise}
 */
async function apiDelete(url, options = {}) {
    return apiRequest(url, {
        method: 'DELETE',
        ...options
    });
}

// ============================================
// 会话管理
// ============================================

/**
 * 获取会话令牌
 * @returns {string|null} - 会话令牌
 */
function getSessionToken() {
    // 从 localStorage 获取
    return localStorage.getItem('session_token') || sessionStorage.getItem('session_token');
}

/**
 * 设置会话令牌
 * @param {string} token - 会话令牌
 * @param {boolean} remember - 是否记住（使用 localStorage）
 */
function setSessionToken(token, remember = false) {
    if (remember) {
        localStorage.setItem('session_token', token);
    } else {
        sessionStorage.setItem('session_token', token);
    }
}

/**
 * 清除会话令牌
 */
function clearSessionToken() {
    localStorage.removeItem('session_token');
    sessionStorage.removeItem('session_token');
}

// ============================================
// 提示消息
// ============================================

/**
 * 初始化提示容器
 */
function initToastContainer() {
    if (!toastContainer) {
        toastContainer = document.createElement('div');
        toastContainer.className = 'toast-container';
        document.body.appendChild(toastContainer);
    }
}

/**
 * 显示成功提示
 * @param {string} message - 提示消息
 * @param {number} duration - 显示时长（毫秒），默认 3000
 */
function showSuccess(message, duration = 3000) {
    showToast(message, 'success', duration);
}

/**
 * 显示错误提示
 * @param {string} message - 提示消息
 * @param {number} duration - 显示时长（毫秒），默认 4000
 */
function showError(message, duration = 4000) {
    showToast(message, 'error', duration);
}

/**
 * 显示警告提示
 * @param {string} message - 提示消息
 * @param {number} duration - 显示时长（毫秒），默认 3000
 */
function showWarning(message, duration = 3000) {
    showToast(message, 'warning', duration);
}

/**
 * 显示信息提示
 * @param {string} message - 提示消息
 * @param {number} duration - 显示时长（毫秒），默认 3000
 */
function showInfo(message, duration = 3000) {
    showToast(message, 'info', duration);
}

/**
 * 显示提示消息
 * @param {string} message - 提示消息
 * @param {string} type - 提示类型（success, error, warning, info）
 * @param {number} duration - 显示时长（毫秒）
 */
function showToast(message, type = 'info', duration = 3000) {
    initToastContainer();
    
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    
    // 图标
    const icons = {
        success: '✓',
        error: '✕',
        warning: '⚠',
        info: 'ℹ'
    };
    
    toast.innerHTML = `
        <span class="toast-icon">${icons[type] || icons.info}</span>
        <span class="toast-message">${message}</span>
        <span class="toast-close" onclick="this.parentElement.remove()">&times;</span>
    `;
    
    toastContainer.appendChild(toast);
    
    // 自动移除
    if (duration > 0) {
        setTimeout(() => {
            if (toast.parentElement) {
                toast.style.animation = 'slideOutRight 0.3s ease-out';
                setTimeout(() => toast.remove(), 300);
            }
        }, duration);
    }
}

// ============================================
// 加载动画
// ============================================

/**
 * 显示加载动画
 */
function showLoading() {
    if (loadingOverlay) {
        return;
    }
    
    loadingOverlay = document.createElement('div');
    loadingOverlay.className = 'loading-overlay';
    loadingOverlay.innerHTML = '<div class="loading-spinner"></div>';
    document.body.appendChild(loadingOverlay);
}

/**
 * 隐藏加载动画
 */
function hideLoading() {
    if (loadingOverlay) {
        loadingOverlay.remove();
        loadingOverlay = null;
    }
}

// ============================================
// 表单验证
// ============================================

/**
 * 验证表单
 * @param {HTMLElement} formElement - 表单元素
 * @returns {boolean} - 验证是否通过
 */
function validateForm(formElement) {
    if (!formElement || formElement.tagName !== 'FORM') {
        console.error('validateForm: 需要一个有效的表单元素');
        return false;
    }
    
    let isValid = true;
    const errors = [];
    
    // 获取所有必填字段
    const requiredFields = formElement.querySelectorAll('[required]');
    
    requiredFields.forEach(field => {
        // 重置错误样式
        field.classList.remove('error');
        const errorMsg = field.parentElement.querySelector('.error-message');
        if (errorMsg) {
            errorMsg.remove();
        }
        
        // 检查是否为空
        if (!field.value.trim()) {
            isValid = false;
            field.classList.add('error');
            const label = field.previousElementSibling?.textContent || field.name;
            errors.push(`${label}不能为空`);
            
            // 显示错误消息
            const errorElement = document.createElement('span');
            errorElement.className = 'error-message';
            errorElement.textContent = `${label}不能为空`;
            errorElement.style.color = 'var(--danger-color)';
            errorElement.style.fontSize = '12px';
            errorElement.style.marginTop = '4px';
            errorElement.style.display = 'block';
            
            if (field.parentElement) {
                field.parentElement.appendChild(errorElement);
            }
        }
        
        // 检查邮箱格式
        if (field.type === 'email' && field.value) {
            const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
            if (!emailRegex.test(field.value)) {
                isValid = false;
                field.classList.add('error');
                errors.push('邮箱格式不正确');
            }
        }
        
        // 检查密码长度
        if (field.type === 'password' && field.value) {
            if (field.value.length < 6) {
                isValid = false;
                field.classList.add('error');
                errors.push('密码长度至少为6位');
            }
        }
    });
    
    // 显示错误提示
    if (!isValid && errors.length > 0) {
        showError(errors[0]);
    }
    
    return isValid;
}

// ============================================
// 模态框管理
// ============================================

/**
 * 打开模态框
 * @param {string} modalId - 模态框 ID
 */
function openModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.style.display = 'block';
        document.body.style.overflow = 'hidden'; // 禁止背景滚动
        
        // 添加动画效果
        const modalContent = modal.querySelector('.modal-content');
        if (modalContent) {
            modalContent.style.animation = 'slideDown 0.3s';
        }
        
        // 点击模态框外部关闭
        modal.onclick = function(event) {
            if (event.target === modal) {
                closeModal(modalId);
            }
        };
    }
}

/**
 * 关闭模态框
 * @param {string} modalId - 模态框 ID
 */
function closeModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.style.display = 'none';
        document.body.style.overflow = ''; // 恢复背景滚动
        
        // 清空表单
        const form = modal.querySelector('form');
        if (form) {
            form.reset();
            // 清除错误样式
            const errorFields = form.querySelectorAll('.error');
            errorFields.forEach(field => field.classList.remove('error'));
            const errorMessages = form.querySelectorAll('.error-message');
            errorMessages.forEach(msg => msg.remove());
        }
    }
}

/**
 * 关闭所有模态框
 */
function closeAllModals() {
    const modals = document.querySelectorAll('.modal');
    modals.forEach(modal => {
        modal.style.display = 'none';
    });
    document.body.style.overflow = '';
}

// ============================================
// 数据格式化
// ============================================

/**
 * 格式化日期
 * @param {string|Date} dateString - 日期字符串或 Date 对象
 * @param {string} format - 格式（'YYYY-MM-DD', 'YYYY-MM-DD HH:mm:ss'）
 * @returns {string} - 格式化后的日期字符串
 */
function formatDate(dateString, format = 'YYYY-MM-DD') {
    if (!dateString) return '';
    
    const date = new Date(dateString);
    if (isNaN(date.getTime())) return dateString;
    
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    const hours = String(date.getHours()).padStart(2, '0');
    const minutes = String(date.getMinutes()).padStart(2, '0');
    const seconds = String(date.getSeconds()).padStart(2, '0');
    
    if (format === 'YYYY-MM-DD') {
        return `${year}-${month}-${day}`;
    } else if (format === 'YYYY-MM-DD HH:mm:ss') {
        return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`;
    } else if (format === 'YYYY-MM-DD HH:mm') {
        return `${year}-${month}-${day} ${hours}:${minutes}`;
    }
    
    return `${year}-${month}-${day}`;
}

/**
 * 格式化数字
 * @param {number} number - 数字
 * @param {number} decimals - 小数位数
 * @returns {string} - 格式化后的数字字符串
 */
function formatNumber(number, decimals = 0) {
    if (number === null || number === undefined) return '0';
    
    return Number(number).toLocaleString('zh-CN', {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals
    });
}

/**
 * 格式化百分比
 * @param {number} number - 数字（0-1 或 0-100）
 * @param {number} decimals - 小数位数
 * @returns {string} - 格式化后的百分比字符串
 */
function formatPercent(number, decimals = 2) {
    if (number === null || number === undefined) return '0%';
    
    // 如果数字大于1，假设它是百分比形式（0-100）
    const percent = number > 1 ? number : number * 100;
    
    return `${formatNumber(percent, decimals)}%`;
}

// ============================================
// 工具函数
// ============================================

/**
 * 防抖函数
 * @param {Function} func - 要防抖的函数
 * @param {number} wait - 等待时间（毫秒）
 * @returns {Function} - 防抖后的函数
 */
function debounce(func, wait = 300) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

/**
 * 节流函数
 * @param {Function} func - 要节流的函数
 * @param {number} limit - 时间限制（毫秒）
 * @returns {Function} - 节流后的函数
 */
function throttle(func, limit = 300) {
    let inThrottle;
    return function executedFunction(...args) {
        if (!inThrottle) {
            func.apply(this, args);
            inThrottle = true;
            setTimeout(() => inThrottle = false, limit);
        }
    };
}

/**
 * 确认对话框
 * @param {string} message - 确认消息
 * @param {string} title - 标题
 * @returns {Promise<boolean>} - 用户是否确认
 */
function confirmDialog(message, title = '确认') {
    return new Promise((resolve) => {
        const confirmed = confirm(`${title}\n${message}`);
        resolve(confirmed);
    });
}

/**
 * 深拷贝对象
 * @param {object} obj - 要拷贝的对象
 * @returns {object} - 拷贝后的对象
 */
function deepClone(obj) {
    return JSON.parse(JSON.stringify(obj));
}

/**
 * 获取 URL 参数
 * @param {string} name - 参数名
 * @returns {string|null} - 参数值
 */
function getUrlParam(name) {
    const urlParams = new URLSearchParams(window.location.search);
    return urlParams.get(name);
}

/**
 * 设置 URL 参数
 * @param {string} name - 参数名
 * @param {string} value - 参数值
 */
function setUrlParam(name, value) {
    const url = new URL(window.location);
    url.searchParams.set(name, value);
    window.history.pushState({}, '', url);
}

// ============================================
// 导出到全局作用域（供其他脚本使用）
// ============================================
window.apiRequest = apiRequest;
window.apiGet = apiGet;
window.apiPost = apiPost;
window.apiPut = apiPut;
window.apiDelete = apiDelete;
window.showSuccess = showSuccess;
window.showError = showError;
window.showWarning = showWarning;
window.showInfo = showInfo;
window.showLoading = showLoading;
window.hideLoading = hideLoading;
window.validateForm = validateForm;
window.openModal = openModal;
window.closeModal = closeModal;
window.closeAllModals = closeAllModals;
window.formatDate = formatDate;
window.formatNumber = formatNumber;
window.formatPercent = formatPercent;
window.getSessionToken = getSessionToken;
window.setSessionToken = setSessionToken;
window.clearSessionToken = clearSessionToken;
window.debounce = debounce;
window.throttle = throttle;
window.confirmDialog = confirmDialog;

// 页面加载时的统计加载（保留原有功能）
function loadStatistics() {
    apiGet('/statistics', {}, { showLoading: false })
        .then(data => {
            console.log('统计数据:', data);
            // 可以在这里更新页面上的统计数字
        })
        .catch(error => {
            console.error('加载统计失败:', error);
        });
}

// 如果页面有统计功能，自动加载
if (document.getElementById('statistics-container')) {
    loadStatistics();
}
