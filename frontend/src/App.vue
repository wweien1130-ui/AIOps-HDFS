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
              </div>
            </template>
            <div class="chat-messages" ref="chatContainer">
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
                  <el-table-column prop="probability" label="异常概率" width="120">
                    <template #default="{ row }">
                      <el-progress
                        :percentage="(row.probability * 100).toFixed(1)"
                        :color="getProgressColor(row.probability)"
                        :status="row.probability > 0.8 ? 'exception' : ''"
                      />
                    </template>
                  </el-table-column>
                  <el-table-column label="关联事件" min-width="300">
                    <template #default="{ row }">
                      <el-tag
                        v-for="(event, idx) in row.events.slice(0, 3)"
                        :key="idx"
                        size="small"
                        type="danger"
                        style="margin-right: 5px;"
                      >
                        {{ event.event_id }} ({{ event.count }})
                      </el-tag>
                      <el-tag v-if="row.events.length > 3" size="small">
                        +{{ row.events.length - 3 }}
                      </el-tag>
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
import { ref, onMounted, computed, nextTick, onBeforeUnmount } from 'vue'
import { marked } from 'marked'
import * as echarts from 'echarts'

const API_BASE = '/api'

const loading = ref(false)
const isRealtime = ref(false)
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

function renderMarkdown(text) {
  if (!text) return ''
  marked.setOptions({
    breaks: true,
    gfm: true
  })
  return marked.parse(text)
}

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

let realtimeTimer = null

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
      left: 'left',
      textStyle: {
        color: '#fff'
      }
    },
    series: [
      {
        name: '异常类型',
        type: 'pie',
        radius: ['40%', '70%'],
        avoidLabelOverlap: false,
        itemStyle: {
          borderRadius: 10,
          borderColor: '#1a1a2e',
          borderWidth: 2
        },
        label: {
          show: false,
          position: 'center'
        },
        emphasis: {
          label: {
            show: true,
            fontSize: 16,
            fontWeight: 'bold',
            color: '#fff'
          }
        },
        labelLine: {
          show: false
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

function getProgressColor(probability) {
  if (probability > 0.8) return '#FF6B6B'
  if (probability > 0.5) return '#FFB347'
  return '#4ECDC4'
}

async function fetchAnalyzeData() {
  try {
    const response = await fetch(`${API_BASE}/analyze`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ threshold: 0.3 })
    })
    const data = await response.json()
    analyzeData.value = data

    systemLogs.value.unshift({
      time: new Date().toLocaleTimeString(),
      message: `检测完成：发现 ${data.anomaly_count} 个异常块`,
      type: data.anomaly_count > 0 ? 'warning' : 'success'
    })
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

async function refreshData() {
  loading.value = true
  await fetchAnalyzeData()
  updateCharts()
  loading.value = false
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
    fetchAnalyzeData()
    realtimeTimer = setInterval(() => {
      fetchAnalyzeData()
    }, 3000)
  } else {
    if (realtimeTimer) {
      clearInterval(realtimeTimer)
      realtimeTimer = null
    }
  }
}

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

  if (pieChart) {
    pieChart.setOption({
      tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
      series: [{
        name: '异常类型',
        type: 'pie',
        radius: ['40%', '70%'],
        itemStyle: { borderRadius: 10, borderColor: '#1a1a2e', borderWidth: 2 },
        label: { show: false },
        data: pieData,
        color: ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7', '#DDA0DD', '#98D8C8', '#F7DC6F']
      }]
    })
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
  --el-table-row-hover-bg-color: rgba(255, 255, 255, 0.05);
  --el-table-border-color: rgba(255, 255, 255, 0.1);
  --el-table-text-color: #fff;
  --el-table-header-text-color: #58D9F9;
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