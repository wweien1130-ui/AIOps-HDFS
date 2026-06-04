/**
 * 微信 ClawBot 示例代码
 * 基于 @tencent-weixin/openclaw-weixin-cli 插件
 *
 * 功能：通过微信查询 HDFS 系统监控数据
 */

const axios = require('axios');

// 后端 API 配置
const API_CONFIG = {
  baseURL: 'http://localhost:8000/api',
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json'
  }
};

// 创建 API 客户端
const apiClient = axios.create(API_CONFIG);

/**
 * 指令映射表
 */
const commandMap = {
  // 健康度查询
  '健康度': { tool: 'get_system_health', params: {} },
  '查询健康度': { tool: 'get_system_health', params: {} },
  '系统状态': { tool: 'get_system_health', params: {} },
  'health': { tool: 'get_system_health', params: {} },

  // 时间范围查询
  '过去2小时': { tool: 'get_recent_anomalies', params: { hours: 2 } },
  '查询过去2小时': { tool: 'get_recent_anomalies', params: { hours: 2 } },
  '过去30分钟': { tool: 'get_recent_anomalies', params: { minutes: 30 } },
  '查询过去30分钟': { tool: 'get_recent_anomalies', params: { minutes: 30 } },
  '过去1小时': { tool: 'get_recent_anomalies', params: { hours: 1 } },

  // Top N 查询
  'Top 10': { tool: 'get_top_anomalies', params: { limit: 10 } },
  '异常列表': { tool: 'get_top_anomalies', params: { limit: 10 } },
  'top10': { tool: 'get_top_anomalies', params: { limit: 10 } },

  // 分布查询
  '异常分布': { tool: 'get_event_distribution', params: {} },
  '分布': { tool: 'get_event_distribution', params: {} },

  // 导出数据
  '导出数据': { tool: 'export_anomalies', params: {} },
  '导出': { tool: 'export_anomalies', params: {} },

  // 帮助
  '帮助': { tool: null, action: 'show_help' },
  'help': { tool: null, action: 'show_help' },
  '?': { tool: null, action: 'show_help' }
};

/**
 * 解析用户输入的自然语言
 * @param {string} message - 用户消息
 * @returns {Object} 解析结果
 */
function parseUserInput(message) {
  const text = message.trim().toLowerCase();

  // 1. 检查简单指令匹配
  for (const [keyword, command] of Object.entries(commandMap)) {
    if (text.includes(keyword.toLowerCase())) {
      return command;
    }
  }

  // 2. 解析时间范围（如 "查询过去2小时"）
  const timeMatch = text.match(/过去(\d+)(小时|分钟|秒|天)/);
  if (timeMatch) {
    const value = parseInt(timeMatch[1]);
    const unit = timeMatch[2];

    let params = {};
    if (unit === '小时') params.hours = value;
    else if (unit === '分钟') params.minutes = value;
    else if (unit === '秒') params.seconds = value;
    else if (unit === '天') params.days = value;

    return {
      tool: 'get_recent_anomalies',
      params: params
    };
  }

  // 3. 解析 Top N（如 "查询Top 5异常"）
  const topMatch = text.match(/(top|前)(\d+)/i);
  if (topMatch) {
    const limit = parseInt(topMatch[2]);
    return {
      tool: 'get_top_anomalies',
      params: { limit: limit }
    };
  }

  // 默认返回帮助
  return { tool: null, action: 'show_help' };
}

/**
 * 调用后端 API 获取系统健康度
 * @returns {Promise<Object>}
 */
async function getSystemHealth() {
  try {
    const response = await apiClient.get('/realtime/total');
    return response.data;
  } catch (error) {
    console.error('获取系统健康度失败:', error.message);
    throw error;
  }
}

/**
 * 查询最近异常数据
 * @param {Object} params - 查询参数
 * @returns {Promise<Object>}
 */
async function getRecentAnomalies(params = {}) {
  try {
    const queryParams = new URLSearchParams(params).toString();
    const response = await apiClient.get(`/anomalies/query?${queryParams}`);
    return response.data;
  } catch (error) {
    console.error('查询异常数据失败:', error.message);
    throw error;
  }
}

/**
 * 获取 Top N 异常
 * @param {Object} params - 查询参数
 * @returns {Promise<Object>}
 */
async function getTopAnomalies(params = {}) {
  try {
    const queryParams = new URLSearchParams(params).toString();
    const response = await apiClient.get(`/anomalies/query?${queryParams}`);
    return response.data;
  } catch (error) {
    console.error('获取Top异常失败:', error.message);
    throw error;
  }
}

/**
 * 获取异常类型分布
 * @param {Object} params - 查询参数
 * @returns {Promise<Object>}
 */
async function getEventDistribution(params = {}) {
  try {
    const queryParams = new URLSearchParams(params).toString();
    const response = await apiClient.get(`/anomalies/query?${queryParams}`);
    return response.data;
  } catch (error) {
    console.error('获取异常分布失败:', error.message);
    throw error;
  }
}

/**
 * 导出异常数据
 * @returns {Promise<Object>}
 */
async function exportAnomalies() {
  try {
    const response = await apiClient.get('/export');
    return response.data;
  } catch (error) {
    console.error('导出数据失败:', error.message);
    throw error;
  }
}

/**
 * 格式化系统健康度回复
 * @param {Object} data - API 返回数据
 * @returns {string}
 */
function formatHealthReply(data) {
  const totalBlocks = data.total_blocks || 0;
  const anomalyCount = data.anomaly_count || 0;
  const healthPercent = totalBlocks > 0
    ? ((1 - (anomalyCount / totalBlocks)) * 100).toFixed(1)
    : 100;

  let status = '✅ 优秀';
  if (healthPercent < 80) status = '❌ 需关注';
  else if (healthPercent < 95) status = '⚠️ 良好';

  return `📊 系统健康度: ${healthPercent}%
• 总Block数: ${totalBlocks}
• 异常数量: ${anomalyCount}
• 健康状态: ${status}`;
}

/**
 * 格式化异常列表回复
 * @param {Object} data - API 返回数据
 * @returns {string}
 */
function formatAnomaliesReply(data) {
  const anomalies = data.anomalies || [];
  if (anomalies.length === 0) {
    return '暂无异常数据';
  }

  let reply = `📋 Top ${anomalies.length} 异常Block:\n\n`;
  anomalies.forEach((item, index) => {
    const events = item.events || [];
    const eventStr = events.slice(0, 3).map(e => `${e.event_id}:${e.count}`).join(', ');
    reply += `${index + 1}. ${item.block_id}\n`;
    reply += `   异常分数: ${(item.probability * 100).toFixed(1)}%\n`;
    if (eventStr) {
      reply += `   主要事件: ${eventStr}\n`;
    }
    reply += '\n';
  });

  return reply;
}

/**
 * 格式化异常分布回复
 * @param {Object} data - API 返回数据
 * @returns {string}
 */
function formatDistributionReply(data) {
  const eventDist = data.event_distribution || {};
  const events = Object.entries(eventDist)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 8);

  if (events.length === 0) {
    return '暂无异常类型数据';
  }

  let reply = `📊 异常类型分布:\n\n`;
  events.forEach(([eventId, count]) => {
    reply += `${eventId}: ${count} 次\n`;
  });

  return reply;
}

/**
 * 显示帮助信息
 * @returns {string}
 */
function showHelp() {
  return `🤖 HDFS系统监控助手

可用指令:
• 健康度 / 查询健康度 - 查询系统健康状态
• 过去X小时 / 过去X分钟 - 查询指定时间范围异常
• Top N / 异常列表 - 查询Top N异常Block
• 异常分布 - 查询异常类型分布
• 导出数据 - 导出异常数据为CSV
• 帮助 - 显示此帮助信息

示例:
• "查询健康度"
• "过去2小时"
• "Top 10"
• "异常分布"`;
}

/**
 * 处理用户消息
 * @param {string} message - 用户消息
 * @returns {Promise<string>} 回复内容
 */
async function handleMessage(message) {
  try {
    // 解析用户意图
    const command = parseUserInput(message);

    // 处理帮助指令
    if (command.action === 'show_help') {
      return showHelp();
    }

    // 调用对应工具
    let data;
    switch (command.tool) {
      case 'get_system_health':
        data = await getSystemHealth();
        // 需要同时获取异常数量
        const anomaliesData = await getRecentAnomalies({ hours: 1, limit: 10 });
        data.anomaly_count = anomaliesData.anomaly_count || 0;
        return formatHealthReply(data);

      case 'get_recent_anomalies':
        data = await getRecentAnomalies(command.params);
        return formatAnomaliesReply(data);

      case 'get_top_anomalies':
        data = await getTopAnomalies(command.params);
        return formatAnomaliesReply(data);

      case 'get_event_distribution':
        data = await getEventDistribution(command.params);
        return formatDistributionReply(data);

      case 'export_anomalies':
        await exportAnomalies();
        return '异常数据已导出，可下载CSV文件';

      default:
        return showHelp();
    }
  } catch (error) {
    console.error('处理消息失败:', error);
    return '抱歉，暂时无法获取数据，请稍后重试';
  }
}

/**
 * 微信 ClawBot 消息处理入口
 * @param {Object} wechatMessage - 微信消息对象
 * @returns {Promise<string>} 回复内容
 */
async function wechatBotHandler(wechatMessage) {
  const userMessage = wechatMessage.content || '';
  console.log(`收到微信消息: ${userMessage}`);

  const reply = await handleMessage(userMessage);
  console.log(`回复消息: ${reply}`);

  return reply;
}

// 导出函数供 OpenClaw 插件调用
module.exports = {
  wechatBotHandler,
  handleMessage,
  parseUserInput,
  showHelp
};

// 如果直接运行此文件，进行测试
if (require.main === module) {
  async function test() {
    console.log('=== 微信 ClawBot 测试 ===\n');

    const testMessages = [
      '查询健康度',
      '过去2小时',
      'Top 10',
      '异常分布',
      '帮助'
    ];

    for (const msg of testMessages) {
      console.log(`用户: ${msg}`);
      const reply = await handleMessage(msg);
      console.log(`机器人: ${reply}\n`);
    }
  }

  test().catch(console.error);
}
