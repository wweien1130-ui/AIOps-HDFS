<template>
  <el-container class="app-container">
    <el-header class="header">
      <div class="header-content">
        <div class="logo">
          <el-icon size="28"><Monitor /></el-icon>
          <span class="title">AI智能日志异常检测系统</span>
        </div>
        <div class="marquee-box">
          <div class="marquee-content" :class="{ 'marquee-paused': !isRealtime }">
            <span v-for="(item, index) in systemLogs" :key="index" class="log-item">
              <el-tag :type="item.type" size="small">{{ item.time }}</el-tag>
              <span class="log-text">{{ item.message }}</span>
            </span>
          </div>
        </div>
        <div class="header-actions">
          <el-upload
            action="/api/upload"
            :show-file-list="false"
            :on-success="handleUploadSuccess"
            :on-error="handleUploadError"
            accept=".log,.txt"
          >
            <el-button type="success">
              <el-icon><Upload /></el-icon>
              上传日志
            </el-button>
          </el-upload>
          <el-button type="warning" @click="exportAnomalies">
            <el-icon><Download /></el-icon>
            导出异常
          </el-button>
          <el-switch
            v-model="isRealtime"
            active-text="模拟实时"
            inactive-text="停止"
            @change="handleRealtimeChange"
          />
          <el-button type="primary" @click="refreshData" :loading="loading">
            <el-icon><Refresh /></el-icon>
            刷新数据
          </el-button>
          <el-input
            v-model="timeRangeInput"
            placeholder="输入时间范围 (如: 2h, 30m, 1d, 90s)"
            style="width: 200px;"
            @keyup.enter="queryByTimeRange"
          >
            <template #prepend>
              <el-icon><Clock /></el-icon>
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
                <el-button type="primary" size="small" @click="newChat" style="margin-left: auto;">
                  <el-icon><Plus /></el-icon> 新对话
                </el-button>
              </div>
            </template>
            <div class="chat-messages" ref="chatContainer">
              <div v-if="isTyping" class="processing-status">
                <el-icon class="is-loading"><Loading /></el-icon>
                正在处理中，请稍候...
              </div>
              <div
                v-for="(msg, index) in chatMessages"
                :key="index"
                class="message"
                :class="msg.role"
              >
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
                  <el-icon><Picture /></el-icon>
                </el-button>
                <el-button @click="toggleVoiceInput" :disabled="isTyping" :class="{ 'voice-active': isRecording }" title="语音输入" class="tool-btn">
                  <el-icon><Microphone /></el-icon>
                </el-button>
                <el-button @click="speakLastResponse" :disabled="!lastResponse" title="语音播报" class="tool-btn">
                  <el-icon><Headset /></el-icon>
                </el-button>
              </div>
              <el-input
                v-model="userInput"
                placeholder="请描述您的问题，或上传图片分析..."
                @keyup.enter="sendMessage"
                :disabled="isTyping"
              />
              <el-button @click="sendMessage" :loading="isTyping" type="primary">
                <el-icon><Promotion /></el-icon>
              </el-button>
              <input
                type="file"
                ref="imageInput"
                accept="image/*"
                style="display: none;"
                @change="handleImageUpload"
              />
            </div>
          </el-card>
        </el-col>

        <el-col :span="16">
          <el-row :gutter="20">
            <el-col :span="12">
              <el-card class="chart-card" shadow="hover">
                <template #header>
                  <div class="card-header">
                    <el-icon><DataAnalysis /></el-icon>
                    <span>系统健康度</span>
                  </div>
                </template>
                <div class="chart-container" ref="gaugeChartRef"></div>
              </el-card>
            </el-col>
            <el-col :span="12">
              <el-card class="chart-card" shadow="hover">
                <template #header>
                  <div class="card-header">
                    <el-icon><PieChart /></el-icon>
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
                    <el-icon><Warning /></el-icon>
                    <span>Top 10 异常Block</span>
                    <el-button type="primary" size="small" style="margin-left: auto;" @click="refreshData">
                      <el-icon><Refresh /></el-icon>
                    </el-button>
                  </div>
                </template>
                <el-table :data="topAnomalies" stripe style="width: 100%">
                  <el-table-column prop="block_id" label="Block ID" width="180" />
                  <el-table-column prop="probability" label="异常概率" width="100">
                    <template #default="{ row }">
                      <el-progress
                        :percentage="(row.probability * 100).toFixed(1)"
                        :color="getProgressColor(row.probability)"
                      />
                    </template>
                  </el-table-column>
                  <el-table-column prop="label" label="标签" width="70" />
                  <el-table-column label="E事件" min-width="300">
                    <template #default="{ row }">
                      <el-tag
                        v-for="(evt, idx) in (row.events || []).filter(e => e.count > 0).slice(0, 6)"
                        :key="idx"
                        size="small"
                        :type="evt.count > 2 ? 'danger' : 'warning'"
                        style="margin-right: 4px; margin-bottom: 2px;"
                      >
                        {{ evt.event_id }}:{{ evt.count }}
                      </el-tag>
                      <span v-if="(row.events || []).filter(e => e.count > 0).length > 6" style="color: #909399; font-size: 12px;">
                        +{{ (row.events || []).filter(e => e.count > 0).length - 6 }}
                      </span>
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
const isRealtime = ref(true)  // 默认开启实时模式（使用ClickHouse数据）
const timeRangeInput = ref('1h')  // 时间范围输入框默认值
const isTyping = ref(false)
const userInput = ref('')
const chatMessages = ref([
  { role: 'assistant', content: '您好！我是AI安全专家，请问有什么可以帮您？' }
])
const chatContainer = ref(null)
const imageInput = ref(null)
const gaugeChartRef = ref(null)
const pieChartRef = ref(null)
let gaugeChart = null
let pieChart = null

const isRecording = ref(false)
const isSpeaking = ref(false)
let recognition = null
let synthesis = null

const analyzeData = ref({
  total_blocks: 0,
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

const lastResponse = computed(() => {
  const messages = chatMessages.value
  for (let i = messages.length - 1; i >= 0; i--) {
    if (messages[i].role === 'assistant' && messages[i].content) {
      return messages[i].content
    }
  }
  return ''
})

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
let isFetching = false

const gaugeOption = computed(() => ({
  series: [
    {
      type: 'gauge',
      startAngle: 180,
      endAngle: 0,
      min: 0,
      max: 100,
      splitNumber: 10,
      itemStyle: {
        color: '#58D9F9'
      },
      progress: {
        show: true,
        width: 30
      },
      pointer: {
        show: false
      },
      axisLine: {
        lineStyle: {
          width: 30
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
        fontSize: 36,
        offsetCenter: [0, '40%'],
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

// 饼图配置（自动显示数据标签）
const pieOption = computed(() => {
  const eventCounts = {}
  topAnomalies.value.forEach(anomaly => {
    anomaly.events.forEach(event => {
      const eventId = event.event_id
      eventCounts[eventId] = (eventCounts[eventId] || 0) + event.count
    })
  })

  const pieData = Object.entries(eventCounts)
    .map(([name, value]) => ({ name, value }))
    .sort((a, b) => b.value - a.value)
    .slice(0, 8)

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
        center: ['35%', '50%'],
        avoidLabelOverlap: true,
        itemStyle: {
          borderRadius: 8,
          borderColor: '#1a1a2e',
          borderWidth: 2
        },
        label: {
          show: true,
          position: 'outside',
          formatter: '{b}\n{c}',
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

// 柱状图配置
const barOption = computed(() => {
  const eventCounts = {}
  topAnomalies.value.forEach(anomaly => {
    anomaly.events.forEach(event => {
      const eventId = event.event_id
      eventCounts[eventId] = (eventCounts[eventId] || 0) + event.count
    })
  })

  const barData = Object.entries(eventCounts)
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

// 折线图配置
const lineOption = computed(() => {
  const eventCounts = {}
  topAnomalies.value.forEach(anomaly => {
    anomaly.events.forEach(event => {
      const eventId = event.event_id
      eventCounts[eventId] = (eventCounts[eventId] || 0) + event.count
    })
  })

  const lineData = Object.entries(eventCounts)
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

function getProgressColor(probability) {
  if (probability > 0.8) return '#FF6B6B'
  if (probability > 0.5) return '#FFB347'
  return '#4ECDC4'
}

async function fetchAnalyzeData() {
  try {
    // 并行获取总Block数和异常数据
    const [totalResponse, anomaliesResponse] = await Promise.all([
      fetch(`${API_BASE}/realtime/total`),
      fetch(`${API_BASE}/realtime/anomalies?limit=10&hours=1`)
    ])

    const totalResult = await totalResponse.json()
    const totalBlocks = totalResult.total_blocks || 0

    const result = await anomaliesResponse.json()

    if (result.anomalies && result.anomalies.length > 0) {
      const eventDist = result.event_distribution || {}
      const topAnomalies = result.anomalies.map(a => {
        const events = Object.entries(a)
          .filter(([k]) => k.startsWith('E'))
          .map(([k, v]) => ({ event_id: k, count: parseInt(v) || 0 }))
        if (events.length === 0) {
          Object.entries(eventDist).forEach(([k, v]) => {
            if (k.startsWith('E')) events.push({ event_id: k, count: parseInt(v) || 0 })
          })
          events.sort((a, b) => b.count - a.count)
          events.splice(6)
        }
        return {
          block_id: a.block_id,
          probability: parseFloat(a.anomaly_score) || 0,
          events: events.filter(e => e.count > 0)
        }
      })

      const eventDistribution = {}
      topAnomalies.forEach(anomaly => {
        anomaly.events.forEach(evt => {
          eventDistribution[evt.event_id] = (eventDistribution[evt.event_id] || 0) + evt.count
        })
      })

      // 计算系统健康度
      const anomalyRatio = totalBlocks > 0 ? topAnomalies.length / totalBlocks : 0

      analyzeData.value = {
        total_blocks: totalBlocks,
        anomaly_count: topAnomalies.length,
        anomaly_ratio: anomalyRatio,
        top_anomalies: topAnomalies,
        event_distribution: eventDistribution
      }

      systemLogs.value.unshift({
        time: new Date().toLocaleTimeString(),
        message: `检测完成：总Block ${totalBlocks}，异常 ${topAnomalies.length} 个 (健康度: ${((1 - anomalyRatio) * 100).toFixed(1)}%)`,
        type: topAnomalies.length > 0 ? 'warning' : 'success'
      })
    } else {
      analyzeData.value = {
        total_blocks: totalBlocks,
        anomaly_count: 0,
        anomaly_ratio: 0,
        top_anomalies: [],
        event_distribution: {}
      }
      systemLogs.value.unshift({
        time: new Date().toLocaleTimeString(),
        message: `检测完成：总Block ${totalBlocks}，无异常数据`,
        type: 'success'
      })
    }

    if (systemLogs.value.length > 10) {
      systemLogs.value.pop()
    }
  } catch (error) {
    console.error('获取分析数据失败:', error)
    systemLogs.value.unshift({
      time: new Date().toLocaleTimeString(),
      message: `API请求失败: ${error.message}`,
      type: 'danger'
    })
  }
}

async function fetchRealtimeAnomalies() {
  const now = new Date()
  const timeStr = now.toLocaleTimeString()
  console.log(`[${timeStr}] 开始获取实时异常...`)
  try {
    // 获取过去1小时的异常数据
    const response = await fetch(`${API_BASE}/realtime/anomalies?limit=100&hours=1`)
    const result = await response.json()
    console.log(`[${timeStr}] 获取成功，数据来源: ${result.source}`)

    if (result.anomalies && result.anomalies.length > 0) {
      const eventDist = result.event_distribution || {}
      const topAnomalies = result.anomalies.map(a => {
        const events = Object.entries(a)
          .filter(([k]) => k.startsWith('E'))
          .map(([k, v]) => ({ event_id: k, count: parseInt(v) || 0 }))
        if (events.length === 0) {
          Object.entries(eventDist).forEach(([k, v]) => {
            if (k.startsWith('E')) events.push({ event_id: k, count: parseInt(v) || 0 })
          })
          events.sort((a, b) => b.count - a.count)
          events.splice(6)
        }
        return {
          block_id: a.block_id,
          probability: parseFloat(a.anomaly_score) || 0,
          events: events.filter(e => e.count > 0)
        }
      })
      const eventDistribution = {}
      topAnomalies.forEach(anomaly => {
        anomaly.events.forEach(evt => {
          eventDistribution[evt.event_id] = (eventDistribution[evt.event_id] || 0) + evt.count
        })
      })
      // 获取总Block数
      const totalResponse = await fetch(`${API_BASE}/realtime/total`)
      const totalResult = await totalResponse.json()
      const totalBlocks = totalResult.total_blocks || 0

      // 计算系统健康度
      const anomalyRatio = totalBlocks > 0 ? topAnomalies.length / totalBlocks : 0

      analyzeData.value = {
        ...analyzeData.value,
        top_anomalies: topAnomalies,
        anomaly_count: topAnomalies.length,
        total_blocks: totalBlocks,
        anomaly_ratio: anomalyRatio,
        event_distribution: eventDistribution
      }
      systemLogs.value.unshift({
        time: new Date().toLocaleTimeString(),
        message: `实时异常：总Block ${totalBlocks}，异常 ${topAnomalies.length} 个 (健康度: ${((1 - anomalyRatio) * 100).toFixed(1)}%)`,
        type: 'success'
      })
      if (systemLogs.value.length > 10) {
        systemLogs.value.pop()
      }
    } else {
      systemLogs.value.unshift({
        time: new Date().toLocaleTimeString(),
        message: '暂无实时异常数据',
        type: 'info'
      })
    }
  } catch (error) {
    console.error('获取实时异常失败:', error)
    systemLogs.value.unshift({
      time: new Date().toLocaleTimeString(),
      message: `获取实时异常失败: ${error.message}`,
      type: 'danger'
    })
  }
}

async function refreshData() {
  loading.value = true
  await fetchAnalyzeData()
  await fetchRealtimeAnomalies()
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
    const totalBlocks = totalResult.total_blocks || 0

    const result = await anomaliesResponse.json()

    if (result.anomalies && result.anomalies.length > 0) {
      const eventDist = result.event_distribution || {}
      const topAnomalies = result.anomalies.map(a => {
        const events = Object.entries(a)
          .filter(([k]) => k.startsWith('E'))
          .map(([k, v]) => ({ event_id: k, count: parseInt(v) || 0 }))
        if (events.length === 0) {
          Object.entries(eventDist).forEach(([k, v]) => {
            if (k.startsWith('E')) events.push({ event_id: k, count: parseInt(v) || 0 })
          })
          events.sort((a, b) => b.count - a.count)
          events.splice(6)
        }
        return {
          block_id: a.block_id,
          probability: parseFloat(a.anomaly_score) || 0,
          events: events.filter(e => e.count > 0)
        }
      })

      const eventDistribution = {}
      topAnomalies.forEach(anomaly => {
        anomaly.events.forEach(evt => {
          eventDistribution[evt.event_id] = (eventDistribution[evt.event_id] || 0) + evt.count
        })
      })

      // 计算系统健康度
      const anomalyRatio = totalBlocks > 0 ? topAnomalies.length / totalBlocks : 0

      analyzeData.value = {
        total_blocks: totalBlocks,
        anomaly_count: topAnomalies.length,
        anomaly_ratio: anomalyRatio,
        top_anomalies: topAnomalies,
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
    const response = await fetch(`${API_BASE}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: userMessage })
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
              const lastMsg = chatMessages.value[chatMessages.value.length - 1]
              if (lastMsg && lastMsg.role === 'assistant') {
                lastMsg.content += data.content
              }
              nextTick(() => scrollToBottom())
            }
          } catch (e) {}
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

function initSpeechRecognition() {
  if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
    return null
  }

  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
  const recognizer = new SpeechRecognition()
  recognizer.continuous = false
  recognizer.interimResults = true
  recognizer.lang = 'zh-CN'

  return recognizer
}

function toggleVoiceInput() {
  if (isRecording.value) {
    if (recognition) {
      recognition.stop()
    }
    isRecording.value = false
    return
  }

  if (!recognition) {
    recognition = initSpeechRecognition()
    if (!recognition) {
      chatMessages.value.push({
        role: 'assistant',
        content: '抱歉，您的浏览器不支持语音识别功能。请使用Chrome浏览器。'
      })
      return
    }

    recognition.onstart = () => {
      isRecording.value = true
      chatMessages.value.push({
        role: 'assistant',
        content: '🎤 正在聆听，请说话...'
      })
    }

    recognition.onresult = (event) => {
      const transcript = Array.from(event.results)
        .map(result => result[0].transcript)
        .join('')

      const lastMsg = chatMessages.value[chatMessages.value.length - 1]
      if (lastMsg && lastMsg.content.includes('聆听')) {
        lastMsg.content = `🎤 识别中：${transcript}`
      } else {
        chatMessages.value.push({
          role: 'assistant',
          content: `🎤 识别中：${transcript}`
        })
      }
    }

    recognition.onerror = (event) => {
      isRecording.value = false
      chatMessages.value.push({
        role: 'assistant',
        content: `语音识别出错：${event.error}`
      })
    }

    recognition.onend = () => {
      isRecording.value = false
    }
  }

  try {
    recognition.start()
  } catch (e) {
    console.error('语音识别启动失败:', e)
  }
}

function speakLastResponse() {
  if (!lastResponse.value || isSpeaking.value) return

  if (!synthesis) {
    synthesis = window.speechSynthesis
  }

  if (!synthesis) {
    chatMessages.value.push({
      role: 'assistant',
      content: '抱歉，您的浏览器不支持语音播报功能。'
    })
    return
}

  synthesis.cancel()

  const utterance = new SpeechSynthesisUtterance(lastResponse.value)
  utterance.lang = 'zh-CN'
  utterance.rate = 1.0
  utterance.pitch = 1.0

  utterance.onstart = () => {
    isSpeaking.value = true
  }

  utterance.onend = () => {
    isSpeaking.value = false
  }

  utterance.onerror = () => {
    isSpeaking.value = false
  }

  synthesis.speak(utterance)
}

function handleRealtimeChange(val) {
  if (val) {
    realtimeTimer = setInterval(async () => {
      if (isFetching) {
        console.log('上次请求还未完成，跳过本次')
        return
      }
      isFetching = true
      try {
        await fetchRealtimeAnomalies()
        updateCharts()
      } catch (e) {
        console.error('实时刷新失败:', e)
      } finally {
        isFetching = false
      }
    }, 5000)
    ElMessage.success('实时模式已开启，每5秒刷新一次')
  } else {
    if (realtimeTimer) {
      clearInterval(realtimeTimer)
      realtimeTimer = null
    }
    ElMessage.info('实时模式已关闭')
  }
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
    a.download = `anomalies_${new Date().toISOString().slice(0,10)}.csv`
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
})

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
        itemStyle: { color: '#58D9F9' },
        progress: { show: true, width: 30 },
        pointer: { show: false },
        axisLine: { lineStyle: { width: 30 } },
        axisTick: { show: false },
        splitLine: { show: false },
        axisLabel: { show: false },
        detail: {
          valueAnimation: true,
          fontSize: 36,
          offsetCenter: [0, '40%'],
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

.marquee-paused {
  animation-play-state: paused;
}

@keyframes marquee {
  0% { transform: translateX(0); }
  100% { transform: translateX(-50%); }
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
  padding: 20px;
  height: calc(100vh - 60px);
  overflow-y: auto;
}

.dashboard-row {
  height: 100%;
}

.chat-card {
  height: calc(100vh - 140px);
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  display: flex;
  flex-direction: column;
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

.ai-title {
  font-weight: bold;
  color: #58D9F9;
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 15px;
  display: flex;
  flex-direction: column;
  gap: 15px;
}

.message {
  display: flex;
  max-width: 85%;
}

.message.user {
  align-self: flex-end;
}

.message.assistant {
  align-self: flex-start;
}

.message-content {
  padding: 12px 16px;
  border-radius: 12px;
  line-height: 1.6;
  font-size: 14px;
}

.message-content h1,
.message-content h2,
.message-content h3 {
  margin: 12px 0 8px;
  color: #58D9F9;
  font-weight: 600;
}

.message-content h1 { font-size: 18px; }
.message-content h2 { font-size: 16px; }
.message-content h3 { font-size: 15px; }

.message-content p {
  margin: 8px 0;
}

.message-content ul,
.message-content ol {
  margin: 8px 0;
  padding-left: 20px;
}

.message-content li {
  margin: 4px 0;
}

.message-content code {
  background: rgba(0, 0, 0, 0.3);
  padding: 2px 6px;
  border-radius: 4px;
  font-family: 'Consolas', monospace;
  font-size: 13px;
  color: #FF6B6B;
}

.message-content pre {
  background: rgba(0, 0, 0, 0.4);
  padding: 12px;
  border-radius: 8px;
  overflow-x: auto;
  margin: 10px 0;
}

.message-content pre code {
  background: none;
  padding: 0;
  color: #A8E6CF;
}

.message-content table {
  width: 100%;
  border-collapse: collapse;
  margin: 10px 0;
}

.message-content th,
.message-content td {
  border: 1px solid rgba(255, 255, 255, 0.2);
  padding: 8px;
  text-align: left;
}

.message-content th {
  background: rgba(88, 217, 249, 0.2);
  color: #58D9F9;
}

.message-content hr {
  border: none;
  border-top: 1px solid rgba(255, 255, 255, 0.2);
  margin: 16px 0;
}

.message-content strong {
  color: #FFEAA7;
}

.message-content em {
  color: #81ECEC;
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
  0%, 60%, 100% { opacity: 0.3; }
  30% { opacity: 1; }
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

.voice-active {
  background: #ff6b6b !important;
  border-color: #ff6b6b !important;
  color: #fff !important;
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
</style>