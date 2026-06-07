<template>
  <el-container class="app-container">
    <el-header class="header">
      <div class="header-content">
        <div class="logo">
          <el-icon size="28">
            <Monitor />
          </el-icon>
          <span class="title">AI智能日志异常检测系统</span>
        </div>
        <div class="marquee-box">
          <div class="marquee-content">
            <span v-for="(item, index) in systemLogs" :key="index" class="log-item">
              <el-tag :type="item.type" size="small">{{ item.time }}</el-tag>
              <span class="log-text">{{ item.message }}</span>
            </span>
          </div>
        </div>
        <div class="header-actions">
          <el-upload action="/api/upload" :show-file-list="false" :on-success="handleUploadSuccess"
            :on-error="handleUploadError" accept=".log,.txt">
            <el-button type="success">
              <el-icon>
                <Upload />
              </el-icon>
              上传日志
            </el-button>
          </el-upload>
          <el-button type="warning" @click="exportAnomalies">
            <el-icon>
              <Download />
            </el-icon>
            导出异常
          </el-button>
          <el-input v-model="timeRangeInput" placeholder="输入时间范围 (如: 2h, 30m, 1d, 90s)" style="width: 200px;"
            @keyup.enter="queryByTimeRange">
            <template #prepend>
              <el-icon>
                <Clock />
              </el-icon>
            </template>
          </el-input>
          <el-button type="info" @click="queryByTimeRange">
            查询
          </el-button>
        </div>
      </div>
    </el-header>

    <el-main class="main-content">
      <el-row :gutter="20" class="dashboard-row">
        <el-col :span="8">
          <el-card class="chat-card" shadow="hover">
            <template #header>
              <div class="card-header">
                <el-avatar :size="36" src="https://cube.elemecdn.com/0/88/03b0d39583f48206768a7534e55bcpng.png" />
                <span class="ai-title">AI安全专家</span>
                <el-tag type="success" size="small">在线</el-tag>
                <el-select v-model="modelMode" size="small" style="width: 100px; margin-left: 8px;">
                  <el-option label="混合模式" value="auto" />
                  <el-option label="纯本地" value="ollama" />
                  <el-option label="纯云端" value="cloud" />
                </el-select>
                <el-button type="primary" size="small" @click="newChat" style="margin-left: auto;">
                  <el-icon>
                    <Plus />
                  </el-icon> 新对话
                </el-button>
              </div>
              <!-- 混合模式：展开两个子选择器 -->
              <div v-if="modelMode === 'auto'" class="model-sub-row">
                <span class="sub-label">本地:</span>
                <el-select v-model="autoLocal" size="small" style="width: 140px;">
                  <el-option v-for="m in localModels" :key="'L' + m.name" :label="m.name + (m.is_default ? ' ★' : '')"
                    :value="m.name" />
                </el-select>
                <span class="sub-label" style="margin-left: 12px;">云端:</span>
                <el-select v-model="autoCloud" size="small" style="width: 180px;">
                  <el-option v-for="m in cloudModels" :key="'C' + m.name" :label="m.name + (m.is_default ? ' ★' : '')"
                    :value="m.name" />
                </el-select>
              </div>
              <!-- 纯本地：展开本地模型选择 -->
              <div v-if="modelMode === 'ollama'" class="model-sub-row">
                <span class="sub-label">本地模型:</span>
                <el-select v-model="singleLocal" size="small" style="width: 180px;">
                  <el-option v-for="m in localModels" :key="'SL' + m.name" :label="m.name + (m.is_default ? ' ★' : '')"
                    :value="m.name" />
                </el-select>
              </div>
              <!-- 纯云端：展开云端模型选择 -->
              <div v-if="modelMode === 'cloud'" class="model-sub-row">
                <span class="sub-label">云端模型:</span>
                <el-select v-model="singleCloud" size="small" style="width: 220px;">
                  <el-option v-for="m in cloudModels" :key="'SC' + m.name" :label="m.name + (m.is_default ? ' ★' : '')"
                    :value="m.name" />
                </el-select>
              </div>
            </template>
            <div class="chat-messages" ref="chatContainer">
              <div v-if="isTyping" class="processing-status">
                <el-icon class="is-loading">
                  <Loading />
                </el-icon>
                正在处理中，请稍候...
              </div>
              <div v-for="(msg, index) in chatMessages" :key="index" class="message" :class="msg.role">
                <div class="message-content" v-html="renderMarkdown(msg.content)"></div>
              </div>
              <div v-if="isTyping" class="message assistant">
                <div class="message-content typing">
                  <span class="dot">●</span>
                  <span class="dot">●</span>
                  <span class="dot">●</span>
                </div>
              </div>
            </div>
            <div class="chat-input">
              <div class="input-toolbar">
                <el-button @click="triggerImageUpload" :disabled="isTyping" title="上传图片" class="tool-btn">
                  <el-icon>
                    <Picture />
                  </el-icon>
                </el-button>
              </div>
              <el-input v-model="userInput" placeholder="请描述您的问题，或上传图片分析..." @keyup.enter="sendMessage"
                :disabled="isTyping" />
              <el-button @click="sendMessage" :loading="isTyping" type="primary">
                <el-icon>
                  <Promotion />
                </el-icon>
              </el-button>
              <input type="file" ref="imageInput" accept="image/*" style="display: none;" @change="handleImageUpload" />
            </div>
          </el-card>
        </el-col>

        <el-col :span="16">
          <!-- 统计面板 -->
          <el-row :gutter="12" style="margin-bottom: 16px;">
            <el-col :span="6">
              <el-card class="stat-card" shadow="hover" body-style="padding: 12px 16px;">
                <div class="stat-label">总日志条数</div>
                <div class="stat-value" style="color: #58D9F9;">{{ (analyzeData.total_logs || 0).toLocaleString() }}
                </div>
              </el-card>
            </el-col>
            <el-col :span="6">
              <el-card class="stat-card" shadow="hover" body-style="padding: 12px 16px;">
                <div class="stat-label">去重 Block 数</div>
                <div class="stat-value" style="color: #4ECDC4;">{{ (analyzeData.total_blocks || 0).toLocaleString() }}
                </div>
              </el-card>
            </el-col>
            <el-col :span="6">
              <el-card class="stat-card" shadow="hover" body-style="padding: 12px 16px;">
                <div class="stat-label">异常 Block 数</div>
                <div class="stat-value" style="color: #FF6B6B;">{{ (analyzeData.anomaly_blocks || 0).toLocaleString() }}
                </div>
              </el-card>
            </el-col>
            <el-col :span="6">
              <el-card class="stat-card" shadow="hover" body-style="padding: 12px 16px;">
                <div class="stat-label">系统健康度</div>
                <div class="stat-value" style="color: #96CEB4;">{{ ((1 - analyzeData.anomaly_ratio) * 100).toFixed(1)
                }}%
                </div>
              </el-card>
            </el-col>
          </el-row>
          <el-row :gutter="20">
            <el-col :span="8">
              <el-card class="chart-card" shadow="hover">
                <template #header>
                  <div class="card-header">
                    <el-icon>
                      <DataAnalysis />
                    </el-icon>
                    <span>系统健康度</span>
                  </div>
                </template>
                <div class="chart-container" ref="gaugeChartRef"></div>
              </el-card>
            </el-col>
            <el-col :span="16">
              <el-card class="chart-card" shadow="hover">
                <template #header>
                  <div class="card-header">
                    <el-icon>
                      <PieChart />
                    </el-icon>
                    <span>异常类型分布</span>
                    <div style="margin-left: auto;">
                      <el-radio-group v-model="chartType" size="small">
                        <el-radio-button label="pie">饼图</el-radio-button>
                        <el-radio-button label="bar">柱状图</el-radio-button>
                        <el-radio-button label="line">折线图</el-radio-button>
                      </el-radio-group>
                    </div>
                  </div>
                </template>
                <div class="chart-container" ref="pieChartRef"></div>
              </el-card>
            </el-col>
          </el-row>

          <el-row :gutter="20" style="margin-top: 20px;">
            <el-col :span="24">
              <el-card class="table-card" shadow="hover">
                <template #header>
                  <div class="card-header">
                    <el-icon>
                      <Warning />
                    </el-icon>
                    <span>Top 10 异常Block</span>
                    <span style="margin-left: auto; font-size: 12px; color: rgba(255,255,255,0.4);">{{ isOnline ?
                      '实时刷新中' : '等待启动' }}</span>
                  </div>
                </template>
                <el-table :data="topAnomalies" stripe style="width: 100%">
                  <el-table-column prop="block_id" label="Block ID" width="200" />
                  <el-table-column label="E事件分布" min-width="400">
                    <template #default="{ row }">
                      <div style="display: flex; flex-wrap: wrap; gap: 4px; align-items: center;">
                        <!-- 主导事件：大标签，突出显示 -->
                        <el-tag v-if="row.events && row.events.length > 0" type="danger" effect="dark" size="default"
                          style="font-size: 13px; font-weight: bold;">
                          {{ row.events[0].event_id }}: {{ row.events[0].count }} - {{ row.events[0].meaning }}
                        </el-tag>
                        <!-- 其余事件：小标签紧凑显示 -->
                        <el-tag v-for="(evt, idx) in (row.events || []).slice(1)" :key="idx" size="small"
                          :type="evt.count > 2 ? 'danger' : 'warning'">
                          {{ evt.event_id }}:{{ evt.count }}
                        </el-tag>
                      </div>
                    </template>
                  </el-table-column>
                </el-table>
              </el-card>
            </el-col>
          </el-row>
        </el-col>
      </el-row>
    </el-main>
  </el-container>
</template>

<script setup>
import { ref, onMounted, computed, nextTick, onBeforeUnmount, watch } from 'vue'
import { marked } from 'marked'
import * as echarts from 'echarts'
import { ElMessage } from 'element-plus'
import { Plus, Clock } from '@element-plus/icons-vue'

const API_BASE = '/api'

const loading = ref(false)
const timeRangeInput = ref('1h')  // 时间范围输入框默认值
const isTyping = ref(false)
const userInput = ref('')
const chatMessages = ref([
  { role: 'assistant', content: '您好！我是AI安全专家，请问有什么可以帮您？' }
])
const chatContainer = ref(null)
const imageInput = ref(null)
const modelMode = ref('auto')      // 'auto' | 'ollama' | 'cloud'
const localModels = ref([])
const cloudModels = ref([])
const autoLocal = ref('')          // 混合模式 - 本地模型
const autoCloud = ref('')          // 混合模式 - 云端模型
const singleLocal = ref('')        // 纯本地 - 选中的模型
const singleCloud = ref('')        // 纯云端 - 选中的模型

// 计算最终发送给后端的 model 值
const resolvedModel = computed(() => {
  if (modelMode.value === 'auto') {
    return `auto|${autoLocal.value}|${autoCloud.value}`
  } else if (modelMode.value === 'ollama') {
    return singleLocal.value
  } else {
    return singleCloud.value
  }
})
const gaugeChartRef = ref(null)
const pieChartRef = ref(null)
let gaugeChart = null
let pieChart = null

// E1-E29 事件含义映射
const EVENT_MEANINGS = {
  E1: '重复添加Block', E2: '校验成功', E3: '提供Block服务',
  E4: '服务异常', E5: '接收Block中', E6: '接收Block完成',
  E7: '写Block异常', E8: '数据包响应中断', E9: '接收Block成功',
  E10: '数据包响应异常', E11: '数据包响应终止', E12: '写镜像异常',
  E13: '接收空数据包', E14: '接收Block异常', E15: '偏移变更',
  E16: '传输完成', E17: '传输失败', E18: '开始传输',
  E19: '重新打开Block', E20: '删除Block异常', E21: '删除Block文件',
  E22: '分配Block', E23: '标记无效', E24: '移除复制',
  E25: '请求复制', E26: 'Block映射更新', E27: '重复添加存储Block',
  E28: 'Block不在文件中', E29: '复制超时'
}

const analyzeData = ref({
  total_logs: 0,
  total_blocks: 0,
  anomaly_blocks: 0,
  anomaly_count: 0,
  anomaly_ratio: 0,
  top_anomalies: []
})

const topAnomalies = computed(() => analyzeData.value.top_anomalies || [])

const systemLogs = ref([
  { time: '10:23:45', message: '系统运行正常', type: 'success' },
  { time: '10:23:42', message: 'MLP模型加载成功', type: 'success' },
  { time: '10:23:40', message: '检测到17个新异常', type: 'warning' },
  { time: '10:23:38', message: 'API服务连接正常', type: 'success' }
])

function analyzeEmotion(text) {
  const urgentKeywords = ['紧急', '救命', '崩溃了', '坏了', '故障', '不行', '挂了', '死机', '蓝屏', '报错']
  const anxiousPatterns = [/！{2,}/, /？{2,}/, /\?{2,}/, /操/, /靠/, /草/, /日/, /靠/, /tmd/i, /fuck/i]
  const exclamationCount = (text.match(/！/g) || []).length
  const questionCount = (text.match(/[？?]/g) || []).length

  let emotion = 'normal'
  let priorityMessage = ''

  if (urgentKeywords.some(kw => text.toLowerCase().includes(kw.toLowerCase()))) {
    emotion = 'urgent'
    priorityMessage = '检测到您非常焦虑，请放心，我已经优先为您锁定了故障点，正在分析中...'
  } else if (anxiousPatterns.some(p => p.test(text)) || exclamationCount >= 2 || questionCount >= 3) {
    emotion = 'anxious'
    priorityMessage = '检测到您很着急，我理解您的心情，请稍等，我马上为您排查问题...'
  }

  return { emotion, priorityMessage }
}

function renderMarkdown(text) {
  if (!text) return ''
  marked.setOptions({
    breaks: true,
    gfm: true
  })
  return marked.parse(text)
}

function newChat() {
  chatMessages.value = [
    { role: 'assistant', content: '您好！我是AI安全专家，请问有什么可以帮您？' }
  ]
  userInput.value = ''
}

let realtimeTimer = null
let statusTimer = null
let isFetching = false
const isOnline = ref(false)

function startDataRefresh() {
  if (realtimeTimer) return
  realtimeTimer = setInterval(async () => {
    if (isFetching) return
    isFetching = true
    try {
      await fetchAnalyzeData()
      updateCharts()
    } catch (e) {
      console.error('自动刷新失败:', e)
    } finally {
      isFetching = false
    }
  }, 5000)
}

function stopDataRefresh() {
  if (realtimeTimer) {
    clearInterval(realtimeTimer)
    realtimeTimer = null
  }
}

async function checkServiceStatus() {
  try {
    const res = await fetch(`${API_BASE}/realtime/status`)
    const data = await res.json()
    if (data.online && !isOnline.value) {
      isOnline.value = true
      startDataRefresh()
    } else if (!data.online && isOnline.value) {
      isOnline.value = false
      stopDataRefresh()
    }
  } catch (e) {
    // 静默失败
  }
}

const gaugeOption = computed(() => ({
  series: [
    {
      type: 'gauge',
      startAngle: 180,
      endAngle: 0,
      min: 0,
      max: 100,
      splitNumber: 10,
      radius: '70%',
      center: ['50%', '60%'],
      itemStyle: {
        color: '#58D9F9'
      },
      progress: {
        show: true,
        width: 20
      },
      pointer: {
        show: false
      },
      axisLine: {
        lineStyle: {
          width: 20
        }
      },
      axisTick: {
        show: false
      },
      splitLine: {
        show: false
      },
      axisLabel: {
        show: false
      },
      detail: {
        valueAnimation: true,
        fontSize: 28,
        offsetCenter: [0, '45%'],
        formatter: '{value}%',
        color: '#58D9F9'
      },
      data: [
        {
          value: ((1 - analyzeData.value.anomaly_ratio) * 100).toFixed(1)
        }
      ]
    }
  ]
}))

// 当前选中的图表类型
const chartType = ref('pie')

// 饼图配置（自动显示数据标签）- 使用全局事件分布
const pieOption = computed(() => {
  const eventDist = analyzeData.value.event_distribution || {}

  const pieData = Object.entries(eventDist)
    .map(([name, value]) => ({ name, value }))
    .sort((a, b) => b.value - a.value)
    .slice(0, 10)

  return {
    tooltip: {
      trigger: 'item',
      formatter: '{b}: {c} ({d}%)'
    },
    legend: {
      orient: 'vertical',
      right: 10,
      top: 'center',
      textStyle: {
        color: '#fff',
        fontSize: 10
      },
      itemWidth: 12,
      itemHeight: 8,
      itemGap: 5
    },
    series: [
      {
        name: '异常类型',
        type: 'pie',
        radius: ['35%', '65%'],
        center: ['45%', '50%'],
        avoidLabelOverlap: true,
        itemStyle: {
          borderRadius: 8,
          borderColor: '#1a1a2e',
          borderWidth: 2
        },
        label: {
          show: true,
          position: 'outside',
          formatter: '{b}\n{d}%',
          fontSize: 10,
          color: '#fff',
          lineHeight: 14
        },
        emphasis: {
          label: {
            show: true,
            fontSize: 12,
            fontWeight: 'bold',
            color: '#fff'
          },
          itemStyle: {
            shadowBlur: 10,
            shadowOffsetX: 0,
            shadowColor: 'rgba(0, 0, 0, 0.5)'
          }
        },
        labelLine: {
          show: true,
          length: 8,
          length2: 8,
          smooth: 0.2
        },
        data: pieData,
        color: [
          '#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4',
          '#FFEAA7', '#DDA0DD', '#98D8C8', '#F7DC6F'
        ]
      }
    ]
  }
})

// 柱状图配置 - 使用全局事件分布
const barOption = computed(() => {
  const eventDist = analyzeData.value.event_distribution || {}

  const barData = Object.entries(eventDist)
    .map(([name, value]) => ({ name, value }))
    .sort((a, b) => b.value - a.value)
    .slice(0, 10)

  return {
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'shadow'
      },
      formatter: '{b}: {c} 次'
    },
    grid: {
      left: '8%',
      right: '5%',
      bottom: '15%',
      top: '10%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: barData.map(item => item.name),
      axisLabel: {
        color: '#fff',
        fontSize: 9,
        rotate: 45,
        interval: 0
      },
      axisLine: {
        lineStyle: {
          color: '#58D9F9'
        }
      }
    },
    yAxis: {
      type: 'value',
      axisLabel: {
        color: '#fff',
        fontSize: 10
      },
      axisLine: {
        lineStyle: {
          color: '#58D9F9'
        }
      },
      splitLine: {
        lineStyle: {
          color: 'rgba(255,255,255,0.1)'
        }
      }
    },
    series: [
      {
        name: '异常次数',
        type: 'bar',
        data: barData.map(item => item.value),
        itemStyle: {
          borderRadius: [4, 4, 0, 0],
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: '#4ECDC4' },
            { offset: 1, color: '#45B7D1' }
          ])
        },
        label: {
          show: true,
          position: 'top',
          color: '#fff',
          fontSize: 9
        }
      }
    ]
  }
})

// 折线图配置 - 使用全局事件分布
const lineOption = computed(() => {
  const eventDist = analyzeData.value.event_distribution || {}

  const lineData = Object.entries(eventDist)
    .map(([name, value]) => ({ name, value }))
    .sort((a, b) => b.value - a.value)
    .slice(0, 10)

  return {
    tooltip: {
      trigger: 'axis',
      formatter: '{b}: {c} 次'
    },
    grid: {
      left: '8%',
      right: '5%',
      bottom: '15%',
      top: '10%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: lineData.map(item => item.name),
      axisLabel: {
        color: '#fff',
        fontSize: 9,
        rotate: 45,
        interval: 0
      },
      axisLine: {
        lineStyle: {
          color: '#58D9F9'
        }
      }
    },
    yAxis: {
      type: 'value',
      axisLabel: {
        color: '#fff',
        fontSize: 10
      },
      axisLine: {
        lineStyle: {
          color: '#58D9F9'
        }
      },
      splitLine: {
        lineStyle: {
          color: 'rgba(255,255,255,0.1)'
        }
      }
    },
    series: [
      {
        name: '异常次数',
        type: 'line',
        data: lineData.map(item => item.value),
        smooth: true,
        itemStyle: {
          color: '#FF6B6B'
        },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(255,107,107,0.5)' },
            { offset: 1, color: 'rgba(255,107,107,0.1)' }
          ])
        },
        label: {
          show: true,
          position: 'top',
          color: '#fff',
          fontSize: 9
        }
      }
    ]
  }
})

// 根据当前选中的图表类型返回对应的配置
const currentChartOption = computed(() => {
  switch (chartType.value) {
    case 'bar':
      return barOption.value
    case 'line':
      return lineOption.value
    default:
      return pieOption.value
  }
})

async function fetchAnalyzeData() {
  try {
    const response = await fetch(`${API_BASE}/realtime/anomalies?limit=10`)
    const result = await response.json()

    const totalLogs = result.total_logs || 0
    const totalBlocks = result.total_blocks || 0
    const totalAnomalies = result.total_anomalies || 0
    const anomalyRatio = totalBlocks > 0 ? totalAnomalies / totalBlocks : 0
    const eventDist = result.event_distribution || {}

    const topAnomalies = (result.anomalies || []).map(a => {
      const events = Object.entries(a)
        .filter(([k]) => k.startsWith('E'))
        .map(([k, v]) => ({ event_id: k, count: parseInt(v) || 0, meaning: EVENT_MEANINGS[k] || k }))
        .filter(e => e.count > 0)
        .sort((a, b) => b.count - a.count)
      return { block_id: a.block_id, events }
    })

    analyzeData.value = {
      total_logs: totalLogs,
      total_blocks: totalBlocks,
      anomaly_blocks: totalAnomalies,
      anomaly_count: totalAnomalies,
      anomaly_ratio: anomalyRatio,
      top_anomalies: topAnomalies,
      event_distribution: eventDist
    }

    if (systemLogs.value.length > 10) systemLogs.value.pop()
  } catch (error) {
    console.error('获取分析数据失败:', error)
  }
}

async function refreshData() {
  loading.value = true
  await fetchAnalyzeData()
  updateCharts()
  loading.value = false
}

function parseTimeRange(input) {
  /**
   * 解析时间范围输入
   * 支持格式: 2h, 30m, 90s, 1d, 1h30m, 2h30m15s 等
   */
  input = input.trim().toLowerCase()

  // 提取数字和单位
  const regex = /(\d+)([smhd])/g
  let totalSeconds = 0
  let match

  while ((match = regex.exec(input)) !== null) {
    const value = parseInt(match[1])
    const unit = match[2]

    switch (unit) {
      case 's':
        totalSeconds += value
        break
      case 'm':
        totalSeconds += value * 60
        break
      case 'h':
        totalSeconds += value * 3600
        break
      case 'd':
        totalSeconds += value * 86400
        break
    }
  }

  // 如果没有匹配到任何单位，假设是小时
  if (totalSeconds === 0) {
    const hours = parseInt(input) || 1
    totalSeconds = hours * 3600
  }

  return totalSeconds
}

async function queryByTimeRange() {
  try {
    const seconds = parseTimeRange(timeRangeInput.value)

    if (seconds <= 0) {
      ElMessage.error('请输入有效的时间范围')
      return
    }

    // 构建查询参数
    let queryParams = `limit=100`

    // 根据时间范围选择合适的单位
    if (seconds < 60) {
      queryParams += `&seconds=${seconds}`
    } else if (seconds < 3600) {
      queryParams += `&minutes=${Math.floor(seconds / 60)}`
    } else if (seconds < 86400) {
      queryParams += `&hours=${Math.floor(seconds / 3600)}`
    } else {
      queryParams += `&days=${Math.floor(seconds / 86400)}`
    }

    // 并行获取总Block数和异常数据
    const [totalResponse, anomaliesResponse] = await Promise.all([
      fetch(`${API_BASE}/realtime/total`),
      fetch(`${API_BASE}/anomalies/query?${queryParams}`)
    ])

    const totalResult = await totalResponse.json()
    const totalLogs = totalResult.total_logs || 0
    const totalBlocks = totalResult.total_blocks || 0
    const anomalyBlocks = totalResult.anomaly_blocks || 0

    const result = await anomaliesResponse.json()

    if (result.anomalies && result.anomalies.length > 0) {
      const eventDist = result.event_distribution || {}
      const topAnomalies = result.anomalies.map(a => {
        const events = Object.entries(a)
          .filter(([k]) => k.startsWith('E'))
          .map(([k, v]) => ({ event_id: k, count: parseInt(v) || 0, meaning: EVENT_MEANINGS[k] || k }))
          .filter(e => e.count > 0)
          .sort((a, b) => b.count - a.count)
        return {
          block_id: a.block_id,
          events: events
        }
      })

      const eventDistribution = eventDist

      // 计算系统健康度
      const totalAnomalies = result.total_anomalies || anomalyBlocks
      const anomalyRatio = totalBlocks > 0 ? totalAnomalies / totalBlocks : 0

      // 限制 Top 10
      const top10 = topAnomalies.slice(0, 10)

      analyzeData.value = {
        total_logs: totalLogs,
        total_blocks: totalBlocks,
        anomaly_blocks: anomalyBlocks,
        anomaly_count: totalAnomalies,
        anomaly_ratio: anomalyRatio,
        top_anomalies: top10,
        event_distribution: eventDistribution
      }

      updateCharts()

      // 格式化时间显示
      const timeDisplay = formatTimeDisplay(seconds)

      ElMessage.success(`查询${timeDisplay}：发现 ${topAnomalies.length} 个异常 (健康度: ${((1 - anomalyRatio) * 100).toFixed(1)}%)`)
      systemLogs.value.unshift({
        time: new Date().toLocaleTimeString(),
        message: `查询${timeDisplay}：总Block ${totalBlocks}，异常 ${topAnomalies.length} 个`,
        type: topAnomalies.length > 0 ? 'warning' : 'info'
      })
    } else {
      analyzeData.value = {
        total_blocks: totalBlocks,
        anomaly_count: 0,
        anomaly_ratio: 0,
        top_anomalies: [],
        event_distribution: {}
      }
      updateCharts()

      const timeDisplay = formatTimeDisplay(seconds)
      ElMessage.info(`${timeDisplay}内没有异常数据`)
      systemLogs.value.unshift({
        time: new Date().toLocaleTimeString(),
        message: `查询${timeDisplay}：总Block ${totalBlocks}，无异常数据`,
        type: 'info'
      })
    }
  } catch (error) {
    console.error('查询异常失败:', error)
    ElMessage.error('查询失败: ' + error.message)
    systemLogs.value.unshift({
      time: new Date().toLocaleTimeString(),
      message: `查询失败: ${error.message}`,
      type: 'danger'
    })
  }
}

function formatTimeDisplay(seconds) {
  /**
   * 格式化时间显示
   */
  if (seconds < 60) {
    return `过去${seconds}秒`
  } else if (seconds < 3600) {
    const minutes = Math.floor(seconds / 60)
    return `过去${minutes}分钟`
  } else if (seconds < 86400) {
    const hours = Math.floor(seconds / 3600)
    return `过去${hours}小时`
  } else {
    const days = Math.floor(seconds / 86400)
    return `过去${days}天`
  }
}

function applyModelSwitch(modelValue) {
  // 解析模型切换值并更新前端选择器状态
  if (modelValue.startsWith('auto|')) {
    const parts = modelValue.split('|')
    if (parts.length === 3) {
      modelMode.value = 'auto'
      autoLocal.value = parts[1]
      autoCloud.value = parts[2]
    }
  } else {
    // 单模型：判断是本地还是云端
    const isLocal = localModels.value.some(m => m.name === modelValue)
    if (isLocal) {
      modelMode.value = 'ollama'
      singleLocal.value = modelValue
    } else {
      modelMode.value = 'cloud'
      singleCloud.value = modelValue
    }
  }
}

async function sendMessage() {
  if (!userInput.value.trim() || isTyping.value) return

  const userMessage = userInput.value.trim()
  chatMessages.value.push({ role: 'user', content: userMessage })
  userInput.value = ''

  await nextTick()
  scrollToBottom()

  isTyping.value = true

  const { emotion, priorityMessage } = analyzeEmotion(userMessage)
  if (priorityMessage) {
    chatMessages.value.push({ role: 'assistant', content: priorityMessage })
    await nextTick()
    scrollToBottom()
    await new Promise(resolve => setTimeout(resolve, 1500))
    chatMessages.value.push({ role: 'assistant', content: '' })
  } else {
    chatMessages.value.push({ role: 'assistant', content: '' })
  }

  try {
    console.log('[ModelSwitch] Sending:', { message: userMessage, model: resolvedModel.value, mode: modelMode.value })
    const response = await fetch(`${API_BASE}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: userMessage, model: resolvedModel.value })
    })

    const reader = response.body.getReader()
    const decoder = new TextDecoder()

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      const text = decoder.decode(value)
      const lines = text.split('\n')

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const data = JSON.parse(line.slice(6))

            // 处理事件类型
            if (data.event === 'done') {
              console.log('流结束')
              break
            }
            if (data.event === 'error') {
              throw new Error(data.error || '未知错误')
            }

            if (data.content) {
              // 检测模型切换指令
              try {
                const inner = JSON.parse(data.content)
                if (inner.event === 'model_switch' && inner.model) {
                  applyModelSwitch(inner.model)
                  continue
                }
              } catch (_) { }

              const lastMsg = chatMessages.value[chatMessages.value.length - 1]
              if (lastMsg && lastMsg.role === 'assistant') {
                lastMsg.content += data.content
              }
              nextTick(() => scrollToBottom())
            }
          } catch (e) { }
        }
      }
    }
  } catch (error) {
    const lastMsg = chatMessages.value[chatMessages.value.length - 1]
    if (lastMsg && lastMsg.role === 'assistant') {
      lastMsg.content = `抱歉，发生了错误：${error.message}`
    } else {
      chatMessages.value.push({
        role: 'assistant',
        content: `抱歉，发生了错误：${error.message}`
      })
    }
  }

  isTyping.value = false
  await nextTick()
  scrollToBottom()
}

function scrollToBottom() {
  if (chatContainer.value) {
    chatContainer.value.scrollTop = chatContainer.value.scrollHeight
  }
}

function triggerImageUpload() {
  imageInput.value.click()
}

async function handleImageUpload(event) {
  const file = event.target.files[0]
  if (!file) return

  chatMessages.value.push({
    role: 'user',
    content: '[图片上传]',
    image: true,
    imageUrl: URL.createObjectURL(file)
  })
  await nextTick()
  scrollToBottom()

  chatMessages.value.push({ role: 'assistant', content: '正在识别图片内容...' })

  const formData = new FormData()
  formData.append('file', file)

  try {
    const response = await fetch(`${API_BASE}/ocr`, {
      method: 'POST',
      body: formData
    })
    const data = await response.json()

    if (data.success && data.text) {
      chatMessages.value.pop()
      chatMessages.value.push({
        role: 'assistant',
        content: `图片识别完成！识别到以下内容：\n\n"${data.text}"\n\n正在分析中...`
      })
      await nextTick()
      scrollToBottom()

      userInput.value = data.text
      await new Promise(resolve => setTimeout(resolve, 1000))
      await sendMessage()
    } else {
      chatMessages.value.pop()
      chatMessages.value.push({
        role: 'assistant',
        content: `图片识别失败：${data.error || '无法识别图片内容'}`
      })
    }
  } catch (error) {
    chatMessages.value.pop()
    chatMessages.value.push({
      role: 'assistant',
      content: `请求失败：${error.message}`
    })
  }

  event.target.value = ''
}

async function handleUploadSuccess(response) {
  ElMessage.success(response.message || '文件上传成功')
  systemLogs.value.unshift({
    time: new Date().toLocaleTimeString(),
    message: `上传成功: ${response.file_path}`,
    type: 'success'
  })
  await refreshData()
}

function handleUploadError(error) {
  ElMessage.error('文件上传失败: ' + (error.message || error))
}

async function exportAnomalies() {
  try {
    const response = await fetch('/api/export')
    if (!response.ok) throw new Error('导出失败')

    const blob = await response.blob()
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `anomalies_${new Date().toISOString().slice(0, 10)}.csv`
    a.click()
    window.URL.revokeObjectURL(url)

    ElMessage.success('导出成功')
    systemLogs.value.unshift({
      time: new Date().toLocaleTimeString(),
      message: '异常数据已导出',
      type: 'success'
    })
  } catch (error) {
    ElMessage.error('导出失败: ' + error.message)
  }
}

// 监听图表类型变化，自动更新图表
watch(chartType, () => {
  if (pieChart) {
    pieChart.setOption(currentChartOption.value, true)
  }
})

onMounted(() => {
  nextTick(() => {
    if (gaugeChartRef.value) {
      gaugeChart = echarts.init(gaugeChartRef.value)
    }
    if (pieChartRef.value) {
      pieChart = echarts.init(pieChartRef.value)
    }
    refreshData()
  })
  fetchModels()

  // 每10秒检测服务状态，运行中则开启5秒数据刷新
  checkServiceStatus()
  statusTimer = setInterval(checkServiceStatus, 30000)
})

onBeforeUnmount(() => {
  stopDataRefresh()
  if (statusTimer) {
    clearInterval(statusTimer)
    realtimeTimer = null
  }
})

async function fetchModels() {
  try {
    const res = await fetch(`${API_BASE}/models`)
    const data = await res.json()
    localModels.value = data.local || []
    cloudModels.value = data.cloud || []
    // 设置默认值
    autoLocal.value = data.defaults?.local || ''
    autoCloud.value = data.defaults?.cloud || ''
    singleLocal.value = data.defaults?.local || ''
    singleCloud.value = data.defaults?.cloud || ''
  } catch (e) {
    console.warn('获取模型列表失败:', e)
  }
}

function updateCharts() {
  const healthPercent = ((1 - analyzeData.value.anomaly_ratio) * 100).toFixed(1)

  if (gaugeChart) {
    gaugeChart.setOption({
      series: [{
        type: 'gauge',
        startAngle: 180,
        endAngle: 0,
        min: 0,
        max: 100,
        radius: '70%',
        center: ['50%', '60%'],
        itemStyle: { color: '#58D9F9' },
        progress: { show: true, width: 20 },
        pointer: { show: false },
        axisLine: { lineStyle: { width: 20 } },
        axisTick: { show: false },
        splitLine: { show: false },
        axisLabel: { show: false },
        detail: {
          valueAnimation: true,
          fontSize: 28,
          offsetCenter: [0, '45%'],
          formatter: '{value}%',
          color: '#58D9F9'
        },
        data: [{ value: healthPercent }]
      }]
    })
  }

  // 更新异常类型分布图表
  if (pieChart) {
    pieChart.setOption(currentChartOption.value, true)
  }
}
</script>

<style scoped>
.app-container {
  height: 100vh;
  background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
}

.header {
  background: rgba(255, 255, 255, 0.05);
  backdrop-filter: blur(10px);
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  display: flex;
  align-items: center;
  padding: 0 20px;
}

.header-content {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 20px;
}

.logo {
  display: flex;
  align-items: center;
  gap: 10px;
  color: #58D9F9;
}

.title {
  font-size: 20px;
  font-weight: bold;
  background: linear-gradient(90deg, #58D9F9, #7B68EE);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.marquee-box {
  flex: 1;
  overflow: hidden;
  background: rgba(0, 0, 0, 0.3);
  border-radius: 20px;
  padding: 8px 15px;
}

.marquee-content {
  display: flex;
  gap: 20px;
  animation: marquee 20s linear infinite;
}

@keyframes marquee {
  0% {
    transform: translateX(0);
  }

  100% {
    transform: translateX(-50%);
  }
}

.log-item {
  display: flex;
  align-items: center;
  gap: 8px;
  white-space: nowrap;
}

.log-text {
  color: rgba(255, 255, 255, 0.8);
  font-size: 13px;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 15px;
}

.main-content {
  padding: 16px 20px;
  height: calc(100vh - 60px);
  overflow-y: auto;
}

.dashboard-row {
  align-items: stretch;
}

.dashboard-row>.el-col:first-child {
  position: sticky;
  top: 16px;
  align-self: flex-start;
  height: calc(100vh - 60px - 32px);
  display: flex;
  overflow: hidden;
}

.chat-card {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.chat-card :deep(.el-card__body) {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 0;
  overflow: hidden;
}

.card-header {
  display: flex;
  align-items: center;
  gap: 10px;
  color: #fff;
  font-size: 16px;
}

.model-sub-row {
  display: flex;
  align-items: center;
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid rgba(255, 255, 255, 0.15);
}

.sub-label {
  color: rgba(255, 255, 255, 0.7);
  font-size: 12px;
  margin-right: 4px;
}

.ai-title {
  font-weight: bold;
  color: #58D9F9;
}

.chat-messages {
  flex: 1 1 0;
  min-height: 0;
  overflow-y: auto;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.message {
  display: flex;
  max-width: 92%;
}

.message.user {
  align-self: flex-end;
}

.message.assistant {
  align-self: flex-start;
}

.message-content {
  padding: 10px 14px;
  border-radius: 10px;
  line-height: 1.7;
  font-size: 13.5px;
  word-break: break-word;
}

.message-content h1,
.message-content h2,
.message-content h3 {
  margin: 10px 0 6px;
  color: #58D9F9;
  font-weight: 600;
}

.message-content h1 {
  font-size: 16px;
}

.message-content h2 {
  font-size: 15px;
}

.message-content h3 {
  font-size: 14px;
}

.message-content p {
  margin: 6px 0;
}

.message-content ul,
.message-content ol {
  margin: 6px 0;
  padding-left: 18px;
}

.message-content li {
  margin: 3px 0;
}

.message-content code {
  background: rgba(0, 0, 0, 0.35);
  padding: 1px 5px;
  border-radius: 3px;
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 12.5px;
  color: #FF6B6B;
}

.message-content pre {
  background: rgba(0, 0, 0, 0.45);
  padding: 10px 12px;
  border-radius: 6px;
  overflow-x: auto;
  margin: 8px 0;
  border: 1px solid rgba(255, 255, 255, 0.08);
}

.message-content pre code {
  background: none;
  padding: 0;
  color: #A8E6CF;
  font-size: 12px;
  line-height: 1.5;
}

.message-content table {
  width: 100%;
  border-collapse: collapse;
  margin: 8px 0;
  font-size: 12.5px;
}

.message-content th,
.message-content td {
  border: 1px solid rgba(255, 255, 255, 0.15);
  padding: 6px 10px;
  text-align: left;
}

.message-content th {
  background: rgba(88, 217, 249, 0.15);
  color: #58D9F9;
  font-weight: 600;
}

.message-content tr:hover {
  background: rgba(255, 255, 255, 0.03);
}

.message-content hr {
  border: none;
  border-top: 1px solid rgba(255, 255, 255, 0.15);
  margin: 12px 0;
}

.message-content strong {
  color: #FFEAA7;
  font-weight: 600;
}

.message-content em {
  color: #81ECEC;
  font-style: italic;
}

.message-content blockquote {
  border-left: 3px solid #58D9F9;
  padding: 4px 12px;
  margin: 8px 0;
  background: rgba(88, 217, 249, 0.05);
  color: rgba(255, 255, 255, 0.8);
}

.message-content a {
  color: #58D9F9;
  text-decoration: none;
}

.message-content a:hover {
  text-decoration: underline;
}

.message.user .message-content {
  background: linear-gradient(135deg, #4ECDC4, #44A08D);
  color: #fff;
}

.message.assistant .message-content {
  background: rgba(255, 255, 255, 0.1);
  color: #fff;
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.typing {
  display: flex;
  gap: 5px;
}

.typing .dot {
  animation: blink 1.4s infinite;
  color: #58D9F9;
}

.typing .dot:nth-child(2) {
  animation-delay: 0.2s;
}

.typing .dot:nth-child(3) {
  animation-delay: 0.4s;
}

@keyframes blink {

  0%,
  60%,
  100% {
    opacity: 0.3;
  }

  30% {
    opacity: 1;
  }
}

.chat-input {
  padding: 15px;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
  display: flex;
  align-items: center;
  gap: 10px;
}

.input-toolbar {
  display: flex;
  gap: 5px;
}

.chat-input .el-input {
  flex: 1;
}

.chat-input :deep(.el-input__wrapper) {
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.2);
  box-shadow: none;
}

.chat-input :deep(.el-input__inner) {
  color: #fff;
}

.tool-btn {
  padding: 4px 8px !important;
}

.chat-input :deep(.el-divider--vertical) {
  height: 24px;
  margin: 0 4px;
  background-color: rgba(255, 255, 255, 0.3);
}


.message-content img {
  max-width: 200px;
  border-radius: 8px;
  margin-top: 8px;
}

.chart-card {
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  color: #fff;
}

.chart-card :deep(.el-card__header) {
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.chart-container {
  height: 250px;
  overflow: hidden;
}

.stat-card {
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  color: #fff;
  text-align: center;
}

.stat-label {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.6);
  margin-bottom: 4px;
}

.stat-value {
  font-size: 22px;
  font-weight: bold;
}

.table-card {
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  color: #fff;
}

.table-card :deep(.el-card__header) {
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.table-card :deep(.el-table) {
  --el-table-bg-color: transparent;
  --el-table-tr-bg-color: transparent;
  --el-table-header-bg-color: rgba(255, 255, 255, 0.05);
  --el-table-row-hover-bg-color: rgba(255, 255, 255, 0.1);
  --el-table-border-color: rgba(255, 255, 255, 0.1);
  --el-table-text-color: #fff;
  --el-table-header-text-color: #58D9F9;
}

/* 修复斑马纹行的背景色 */
.table-card :deep(.el-table__row--striped) {
  background-color: rgba(255, 255, 255, 0.03) !important;
}

.table-card :deep(.el-table__row--striped) td {
  background-color: rgba(255, 255, 255, 0.03) !important;
}

/* 确保所有行都有正确的背景色 */
.table-card :deep(.el-table__row) {
  background-color: transparent;
}

.table-card :deep(.el-table__row) td {
  background-color: transparent;
}

:deep(.el-table__empty-text) {
  color: rgba(255, 255, 255, 0.5);
}

:deep(.el-card) {
  --el-card-bg-color: transparent;
}

:deep(.el-switch__label) {
  color: #fff;
}

/* 全局滚动条样式 */
.main-content::-webkit-scrollbar {
  width: 6px;
}

.main-content::-webkit-scrollbar-track {
  background: rgb(17, 47, 86);
  border-radius: 3px;
}

.main-content::-webkit-scrollbar-thumb {
  background: rgba(88, 217, 249, 0.4);
  border-radius: 3px;
}

.main-content::-webkit-scrollbar-thumb:hover {
  background: rgba(88, 217, 249, 0.6);
}

/* 聊天框内部滚动条样式 */
.chat-messages::-webkit-scrollbar {
  width: 5px;
}

.chat-messages::-webkit-scrollbar-track {
  background: rgb(17, 47, 86);
  border-radius: 3px;
}

.chat-messages::-webkit-scrollbar-thumb {
  background: rgba(88, 217, 249, 0.35);
  border-radius: 3px;
}

.chat-messages::-webkit-scrollbar-thumb:hover {
  background: rgba(88, 217, 249, 0.55);
}

/* Firefox 滚动条 */
.main-content,
.chat-messages {
  scrollbar-width: thin;
  scrollbar-color: rgba(88, 217, 249, 0.4) rgb(17, 47, 86);
}
</style>
