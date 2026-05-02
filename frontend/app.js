// AI 逃跑计划 - 反主流交互设计
// 弹簧动力学：stiffness: 400, damping: 25

const API_BASE_URL = window.location.origin;

// DOM 元素
const destinationGrid = document.getElementById('destinationGrid');
const destinationCards = destinationGrid?.querySelectorAll('.destination-card') || [];
const hiddenDestinationInput = document.getElementById('destination');
const generateBtn = document.getElementById('generateBtn');
const routesSection = document.getElementById('routesSection');
const routesContainer = document.getElementById('routesContainer');
const routeModal = document.getElementById('routeModal');
const modalBody = document.getElementById('modalBody');
const modalClose = document.getElementById('modalClose');
const dayBtns = document.querySelectorAll('.day-btn-raw');
const tagBtns = document.querySelectorAll('.tag-raw');

// 支持的目的地列表
const SUPPORTED_DESTINATIONS = ['桂林'];

// 状态
let selectedDestination = '';
let selectedDays = 3;
let selectedTags = [];

// ========================================
// 弹簧动画配置 (模拟 Framer Motion)
// ========================================
const springConfig = {
    stiffness: 400,
    damping: 25
};

function springAnimate(element, properties, options = {}) {
    // 简化的弹簧动画实现
    element.style.transition = `all ${options.duration || 0.4}s cubic-bezier(0.34, 1.56, 0.64, 1)`;
    Object.assign(element.style, properties);
}

// ========================================
// 天数选择器交互
// ========================================
dayBtns.forEach(btn => {
    btn.addEventListener('click', () => {
        // 弹簧反馈
        springAnimate(btn, { transform: 'scale(0.95)' });

        setTimeout(() => {
            dayBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            selectedDays = parseInt(btn.dataset.days);

            // 恢复弹簧
            springAnimate(btn, { transform: 'scale(1)' });
        }, 100);
    });

    // 悬停效果
    btn.addEventListener('mouseenter', function() {
        if (!this.classList.contains('active')) {
            springAnimate(this, { transform: 'translateY(-3px)' });
        }
    });

    btn.addEventListener('mouseleave', function() {
        if (!this.classList.contains('active')) {
            springAnimate(this, { transform: 'translateY(0)' });
        }
    });
});

// ========================================
// 标签云交互
// ========================================
tagBtns.forEach(btn => {
    btn.addEventListener('click', function() {
        // 弹簧点击反馈
        springAnimate(this, { transform: 'scale(0.92) rotate(-5deg)' });

        setTimeout(() => {
            this.classList.toggle('selected');
            const tag = this.dataset.tag;

            if (selectedTags.includes(tag)) {
                selectedTags = selectedTags.filter(t => t !== tag);
            } else {
                selectedTags.push(tag);
            }

            // 恢复弹簧
            const selectedClass = this.classList.contains('selected');
            springAnimate(this, {
                transform: selectedClass
                    ? 'translate(-2px, -2px) rotate(-3deg)'
                    : 'translateY(0) rotate(0)'
            });
        }, 80);
    });

    // 悬停效果
    btn.addEventListener('mouseenter', function() {
        if (!this.classList.contains('selected')) {
            springAnimate(this, { transform: 'translateY(-2px) rotate(-2deg)' });
        }
    });

    btn.addEventListener('mouseleave', function() {
        if (!this.classList.contains('selected')) {
            springAnimate(this, { transform: 'translateY(0) rotate(0)' });
        }
    });
});

// ========================================
// 目的地选择器交互
// ========================================
destinationCards.forEach(card => {
    card.addEventListener('click', () => {
        const destination = card.dataset.destination;
        const isSupported = SUPPORTED_DESTINATIONS.includes(destination);

        // 弹簧反馈
        springAnimate(card, { transform: 'scale(0.95)' });

        setTimeout(() => {
            if (isSupported) {
                // 取消其他选中
                destinationCards.forEach(c => c.classList.remove('selected'));
                // 选中当前
                card.classList.add('selected');
                // 更新状态
                selectedDestination = destination;
                hiddenDestinationInput.value = destination;

                springAnimate(card, { transform: 'scale(1)' });
            } else {
                // 不支持的目的地
                showToast(`暂不支持该地点的定制规划`);
                // 恢复
                springAnimate(card, { transform: 'translateX(5px)' });
                setTimeout(() => {
                    springAnimate(card, { transform: 'translateX(0)' });
                }, 100);
            }
        }, 80);
    });
});

// ========================================
// 生成按钮交互
// ========================================
generateBtn.addEventListener('click', handleGenerate);

// ========================================
// 模态框交互
// ========================================
modalClose.addEventListener('click', () => {
    springAnimate(modalClose, { transform: 'rotate(0) scale(1)' });
    routeModal.classList.add('hidden');
});

// 关闭按钮悬停
modalClose.addEventListener('mouseenter', function() {
    springAnimate(this, { transform: 'rotate(90deg) scale(1.1)' });
});

// 背景点击关闭
document.querySelector('.modal-backdrop-raw')?.addEventListener('click', () => {
    routeModal.classList.add('hidden');
});

// ========================================
// 底部导航交互
// ========================================
document.querySelectorAll('.nav-item-raw').forEach(item => {
    item.addEventListener('click', function(e) {
        e.preventDefault();

        // 弹簧反馈
        springAnimate(this, { transform: 'scale(0.9)' });

        setTimeout(() => {
            document.querySelectorAll('.nav-item-raw').forEach(n => n.classList.remove('active'));
            this.classList.add('active');
            springAnimate(this, { transform: 'scale(1.2) translateY(-3px)' });
        }, 100);
    });
});

// ========================================
// 处理生成请求
// ========================================
async function handleGenerate() {
    const destination = selectedDestination;

    if (!destination) {
        showToast('目的地都没选！别怂啊！');
        springAnimate(destinationGrid, {
            transform: 'translateX(-5px)',
        });
        setTimeout(() => {
            springAnimate(destinationGrid, {
                transform: 'translateX(0)',
            });
        }, 200);
        return;
    }

    // 按钮加载状态
    setLoading(true);

    try {
        const response = await fetch(`${API_BASE_URL}/api/generate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                destination,
                days: selectedDays,
                preferences: selectedTags
            })
        });

        if (!response.ok) {
            throw new Error('逃跑计划生成失败！');
        }

        const data = await response.json();

        if (!data.routes || data.routes.length === 0) {
            showToast('没找到路线...AI 也需要冷静下');
        } else {
            displayRoutes(data.routes);
            showToast(`找到 ${data.routes.length} 条逃跑路线！`);
        }

    } catch (error) {
        console.error('生成失败:', error);
        showToast(error.message || '出错了！再试一次！');
    } finally {
        setLoading(false);
    }
}

// ========================================
// 设置加载状态
// ========================================
function setLoading(loading) {
    if (loading) {
        generateBtn.disabled = true;
        generateBtn.innerHTML = `
            <span class="iconify loading" data-icon="ph:spinner"></span>
            <span class="loading">正在规划逃跑路线...</span>
        `;
        // 按下效果
        springAnimate(generateBtn, {
            transform: 'translate(2px, 2px)',
            boxShadow: 'var(--hard-shadow-sm)'
        });
    } else {
        generateBtn.disabled = false;
        generateBtn.innerHTML = `
            <span class="iconify" data-icon="ph:lightning-bold"></span>
            <span>生成逃离计划</span>
            <div class="btn-glitch"></div>
        `;
        // 恢复效果
        springAnimate(generateBtn, {
            transform: 'translate(0, 0)',
            boxShadow: 'var(--hard-shadow)'
        });
    }
}

// ========================================
// 显示路线
// ========================================
function displayRoutes(routes) {
    if (!routes || routes.length === 0) {
        showToast('没找到合适的路线，换个地方？');
        return;
    }

    window.currentRoutes = routes;

    routesContainer.innerHTML = routes.map((route, index) => `
        <div class="route-card-raw" data-index="${index}" onclick="showRouteDetail(${index})">
            <img
                src="https://picsum.photos/seed/${encodeURIComponent(route.product_name || 'travel')}/400/140"
                alt="${route.product_name}"
                class="route-card-image-raw"
                loading="lazy">
            <div class="route-card-content-raw">
                <h3 class="route-card-title-raw">${route.product_name || '神秘路线'}</h3>
                <p class="route-card-route-raw">
                    <span class="iconify" data-icon="lucide:map-pin"></span>
                    ${route.route || '路线保密'}
                </p>
            </div>
        </div>
    `).join('');

    // 显示路线区域 - 弹簧动画
    routesSection.classList.remove('hidden');
    springAnimate(routesSection, { opacity: '1' });

    // 滚动到路线区域
    setTimeout(() => {
        routesSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 100);
}

// ========================================
// 显示路线详情
// ========================================
async function showRouteDetail(index) {
    const routes = window.currentRoutes || [];
    const route = routes[index];
    if (!route) return;

    // 显示加载状态
    modalBody.innerHTML = `
        <div class="loading-container" style="display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 40px;">
            <span class="iconify loading" data-icon="ph:spinner" style="font-size: 48px; color: var(--warning-yellow);"></span>
            <p style="margin-top: 16px; color: var(--concrete-gray); font-weight: 700;">正在生成详细行程...</p>
            <p style="margin-top: 8px; color: var(--concrete-gray); font-size: 12px;">AI 正在为你定制专属路线</p>
        </div>
    `;
    routeModal.classList.remove('hidden');

    try {
        // 调用后端 API 生成路线详情
        const response = await fetch(`${API_BASE_URL}/api/route-detail`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                route: {
                    product_name: route.product_name,
                    route: route.route,
                    days: route.days
                },
                preferences: selectedTags
            })
        });

        if (!response.ok) {
            throw new Error('详情生成失败');
        }

        const detail = await response.json();
        displayRouteDetail(route, detail);

    } catch (error) {
        console.error('生成详情失败:', error);
        showToast('详情生成失败，请稍后重试');
        // 显示基础信息
        displayRouteDetailFallback(route);
    }
}

// 显示路线详情（完整版）
function displayRouteDetail(route, detail) {
    const schedule = detail.schedule || [];
    const accommodation = detail.accommodation || [];
    const foodRecommendations = detail.food_recommendations || [];
    const travelTips = detail.travel_tips || [];

    let html = `
        <h2 class="route-detail-title-raw">${route.product_name || '神秘路线'}</h2>
        <p class="route-detail-route-raw">
            <span class="iconify" data-icon="lucide:map-pin"></span>
            ${route.route || '路线保密'}
        </p>
    `;

    // 概述
    if (detail.overview) {
        html += `
            <div class="detail-section" style="margin-bottom: 20px;">
                <h3 class="detail-section-title">
                    <span class="iconify" data-icon="ph:info"></span>
                    路线概览
                </h3>
                <p class="detail-section-content">${detail.overview}</p>
            </div>
        `;
    }

    // 每日行程
    if (schedule.length > 0) {
        html += `
            <div class="detail-section" style="margin-bottom: 20px;">
                <h3 class="detail-section-title">
                    <span class="iconify" data-icon="ph:calendar"></span>
                    详细行程
                </h3>
        `;

        schedule.forEach(daySchedule => {
            html += `
                <div class="day-card">
                    <div class="day-card-header">
                        <span class="day-badge">Day ${daySchedule.day}</span>
                        <span class="day-theme">${daySchedule.theme || ''}</span>
                    </div>
                    <div class="day-card-items">
            `;

            (daySchedule.items || []).forEach(item => {
                const isMust = item.is_must ? 'must' : '';
                const isWarning = item.is_warning ? 'warning' : '';
                const itemType = item.type || 'general';

                html += `
                    <div class="schedule-item ${itemType} ${isMust} ${isWarning}">
                        <div class="schedule-time">${item.time}</div>
                        <div class="schedule-content">
                            <div class="schedule-activity">
                                ${item.is_must ? '<span class="must-badge">★</span>' : ''}
                                ${item.activity}
                            </div>
                `;

                // 景点类型信息
                if (itemType === 'sightseeing') {
                    html += `
                                <div class="schedule-details">
                                    ${item.transport ? `<p><span class="iconify" data-icon="ph:car"></span> ${item.transport}</p>` : ''}
                                    ${item.ticket_info ? `<p><span class="iconify" data-icon="ph:ticket"></span> ${item.ticket_info}</p>` : ''}
                                    ${item.photo_spot ? `<p><span class="iconify" data-icon="ph:camera"></span> ${item.photo_spot}</p>` : ''}
                                    ${item.tips ? `<p class="tips-text">⚠️ ${item.tips}</p>` : ''}
                                </div>
                    `;
                } else if (itemType === 'food') {
                    html += `
                                <div class="schedule-details">
                                    ${item.address ? `<p><span class="iconify" data-icon="ph:map-pin"></span> ${item.address}</p>` : ''}
                                    ${item.avg_cost ? `<p><span class="iconify" data-icon="ph:currency-cny"></span> ${item.avg_cost}</p>` : ''}
                                    ${item.signature_dish ? `<p><span class="iconify" data-icon="ph:chopsticks"></span> ${item.signature_dish}</p>` : ''}
                                    ${item.opening_hours ? `<p><span class="iconify" data-icon="ph:clock"></span> ${item.opening_hours}</p>` : ''}
                                </div>
                    `;
                } else {
                    html += `
                                <div class="schedule-details">
                                    ${item.description ? `<p>${item.description}</p>` : ''}
                                </div>
                    `;
                }

                html += `
                        </div>
                    </div>
                    `;
                });

                html += `
                    </div>
                </div>
                `;
            });

            html += `
            </div>
            </div>
            `;
    }

    // 住宿推荐
    if (accommodation.length > 0) {
        html += `
            <div class="detail-section" style="margin-bottom: 20px;">
                <h3 class="detail-section-title">
                    <span class="iconify" data-icon="ph:bed"></span>
                    住宿推荐
                </h3>
                <div class="accommodation-list">
        `;

        accommodation.forEach(hotel => {
            html += `
                <div class="accommodation-item">
                    <h4 class="accommodation-name">${hotel.name}</h4>
                    <p class="accommodation-location"><span class="iconify" data-icon="ph:map-pin"></span> ${hotel.location}</p>
                    <p class="accommodation-advantage">${hotel.advantage}</p>
                    ${hotel.price_range ? `<p class="accommodation-price">${hotel.price_range}</p>` : ''}
                    ${hotel.booking_tip ? `<p class="accommodation-tip">💡 ${hotel.booking_tip}</p>` : ''}
                </div>
            `;
        });

        html += `
                </div>
            </div>
            </div>
        `;
    }

    // 美食推荐
    if (foodRecommendations.length > 0) {
        html += `
            <div class="detail-section" style="margin-bottom: 20px;">
                <h3 class="detail-section-title">
                    <span class="iconify" data-icon="ph:utensils"></span>
                    美食推荐
                </h3>
                <div class="food-list">
        `;

        foodRecommendations.forEach(food => {
            html += `
                <div class="food-item">
                    <h4 class="food-name">${food.name}</h4>
                    <p class="food-type">${food.type}</p>
                    ${food.address ? `<p class="food-detail"><span class="iconify" data-icon="ph:map-pin"></span> ${food.address}</p>` : ''}
                    ${food.avg_cost ? `<p class="food-detail"><span class="iconify" data-icon="ph:currency-cny"></span> ${food.avg_cost}</p>` : ''}
                    ${food.signature_dish ? `<p class="food-detail"><span class="iconify" data-icon="ph:chopsticks"></span> ${food.signature_dish}</p>` : ''}
                    ${food.reason ? `<p class="food-reason">💡 ${food.reason}</p>` : ''}
                </div>
            `;
        });

        html += `
                </div>
            </div>
            </div>
        `;
    }

    // 预算估算
    if (detail.estimated_budget) {
        html += `
            <div class="detail-section" style="margin-bottom: 20px;">
                <h3 class="detail-section-title">
                    <span class="iconify" data-icon="ph:wallet"></span>
                    预算估算
                </h3>
                <div class="budget-overview" style="font-size: 18px; font-weight: 900; color: var(--warning-yellow); margin-bottom: 12px;">
                    ${detail.estimated_budget.total || '待补充'}
                </div>
                ${detail.estimated_budget.breakdown ? `
                <div class="budget-breakdown">
                    ${detail.estimated_budget.breakdown.accommodation ? `<div class="budget-item"><span>住宿：</span><span>${detail.estimated_budget.breakdown.accommodation}</span></div>` : ''}
                    ${detail.estimated_budget.breakdown.food ? `<div class="budget-item"><span>餐饮：</span><span>${detail.estimated_budget.breakdown.food}</span></div>` : ''}
                    ${detail.estimated_budget.breakdown.tickets ? `<div class="budget-item"><span>门票：</span><span>${detail.estimated_budget.breakdown.tickets}</span></div>` : ''}
                    ${detail.estimated_budget.breakdown.transport ? `<div class="budget-item"><span>交通：</span><span>${detail.estimated_budget.breakdown.transport}</span></div>` : ''}
                </div>
                ` : ''}
            </div>
        `;
    }

    // 旅行提示
    if (travelTips.length > 0) {
        html += `
            <div class="detail-section" style="margin-bottom: 20px;">
                <h3 class="detail-section-title">
                    <span class="iconify" data-icon="ph:bell"></span>
                    旅行提示
                </h3>
                <ul class="tips-list">
        `;

        travelTips.forEach(tip => {
            html += `<li class="tip-item">⚠️ ${tip}</li>`;
        });

        html += `
                </ul>
            </div>
            </div>
        `;
    }

    // 预订按钮
    html += `
        <button class="route-detail-action-raw" onclick="handleBookRoute('${route.product_name || ''}')">
            预订这个路线
        </button>
    `;

    modalBody.innerHTML = html;

    // 重新加载 Iconify 图标
    if (window.iconify && window.iconify.scanDOM) {
        window.iconify.scanDOM();
    }
}

// 显示路线详情（降级版本，当 LLM 生成失败时）
function displayRouteDetailFallback(route) {
    modalBody.innerHTML = `
        <h2 class="route-detail-title-raw">${route.product_name || '神秘路线'}</h2>
        <p class="route-detail-route-raw">
            <span class="iconify" data-icon="lucide:map-pin"></span>
            ${route.route || '路线保密'}
        </p>
        <div class="detail-section" style="margin-bottom: 20px;">
            <h3 class="detail-section-title">
                <span class="iconify" data-icon="ph:info"></span>
                路线信息
            </h3>
            <p class="detail-section-content">
                抱歉，详细行程暂时无法生成，请稍后重试。<br><br>
                产品名称：${route.product_name || '未知'}<br>
                路线：${route.route || '未知'}<br>
                天数：${route.days || '未知'}天
            </p>
        </div>
        <button class="route-detail-action-raw" onclick="handleBookRoute('${route.product_name || ''}')">
            预订这个路线
        </button>
    `;
}

// ========================================
// 预订处理
// ========================================
function handleBookRoute(routeName) {
    showToast(`"${routeName}" - 这个功能在做了！`);
}

// ========================================
// Toast 提示 (工业风格)
// ========================================
function showToast(message) {
    const container = document.getElementById('toast-container');

    const toast = document.createElement('div');
    toast.className = 'toast-raw';
    toast.textContent = message;

    container.appendChild(toast);

    // 3 秒后移除
    setTimeout(() => {
        toast.remove();
    }, 3000);
}

// ========================================
// 页面加载完成
// ========================================
document.addEventListener('DOMContentLoaded', () => {
    console.log('🚀 AI 逃跑计划已启动');

    // 入口动画
    const mainTitle = document.querySelector('.main-title');
    if (mainTitle) {
        mainTitle.style.opacity = '0';
        mainTitle.style.transform = 'translateY(-20px)';
        setTimeout(() => {
            springAnimate(mainTitle, {
                opacity: '1',
                transform: 'translateY(0)'
            });
        }, 200);
    }
});
