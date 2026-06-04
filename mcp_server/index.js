#!/usr/bin/env node
/**
 * OpenClaw MCP Server - 将后端 API 包装为 MCP 工具
 *
 * 安装:
 *   openclaw mcp set hdfs-monitor '{"command":"node","args":["/home/ubunto/mcp-server-hdfs/index.js"]}'
 *
 * 环境变量:
 *   BACKEND_HOST - Windows 主机 IP（默认 172.21.64.1）
 *   BACKEND_PORT - 后端 API 端口（默认 8000）
 */

const BACKEND_HOST = process.env.BACKEND_HOST || "172.21.64.1";
const BACKEND_PORT = process.env.BACKEND_PORT || "8000";
const BASE_URL = `http://${BACKEND_HOST}:${BACKEND_PORT}/api`;

// ========== MCP 协议（stdio JSON-RPC） ==========
const readline = require("readline");

const rl = readline.createInterface({ input: process.stdin });
let buf = "";
let contentLength = 0;

rl.on("line", (line) => {
  if (line.startsWith("Content-Length: ")) {
    contentLength = parseInt(line.slice(16), 10);
  } else if (line === "" && contentLength > 0) {
    buf = "";
    // 接下来的数据是 JSON body
  } else if (contentLength > 0) {
    buf += line;
    // 检查是否接收完整
    if (Buffer.byteLength(buf, "utf-8") >= contentLength) {
      try {
        const msg = JSON.parse(buf);
        handleMessage(msg);
      } catch (_) {}
      buf = "";
      contentLength = 0;
    }
  }
});

function sendMsg(id, result) {
  const res = JSON.stringify({ jsonrpc: "2.0", id, result });
  process.stdout.write(
    `Content-Length: ${Buffer.byteLength(res, "utf-8")}\r\n\r\n${res}`
  );
}

function sendErr(id, msg) {
  const res = JSON.stringify({
    jsonrpc: "2.0",
    id,
    error: { code: -32603, message: String(msg) },
  });
  process.stdout.write(
    `Content-Length: ${Buffer.byteLength(res, "utf-8")}\r\n\r\n${res}`
  );
}

// ========== 工具定义 ==========
const TOOLS = [
  {
    name: "get_system_health",
    description: "获取 HDFS 系统健康度，查询当前总 Block 数量和系统状态",
    inputSchema: { type: "object", properties: {}, required: [] },
  },
  {
    name: "get_recent_anomalies",
    description: "查询最近指定时间范围内的异常数据",
    inputSchema: {
      type: "object",
      properties: {
        hours: { type: "integer", description: "过去多少小时（默认 1）" },
        minutes: { type: "integer", description: "过去多少分钟" },
        limit: { type: "integer", description: "返回数量限制（默认 10）" },
      },
      required: [],
    },
  },
  {
    name: "get_top_anomalies",
    description: "获取异常分数最高的 Top N Block 及其主要事件",
    inputSchema: {
      type: "object",
      properties: {
        limit: { type: "integer", description: "返回数量（默认 10）" },
        hours: { type: "integer", description: "过去多少小时（默认 1）" },
      },
      required: [],
    },
  },
  {
    name: "get_event_distribution",
    description: "获取异常类型分布，统计各 E 事件的发生次数和占比",
    inputSchema: {
      type: "object",
      properties: {
        hours: { type: "integer", description: "过去多少小时（默认 1）" },
      },
      required: [],
    },
  },
];

// ========== 调用后端 API ==========
async function callAPI(endpoint, params = {}) {
  const url = new URL(`${BASE_URL}${endpoint}`);
  for (const [k, v] of Object.entries(params)) {
    if (v !== null && v !== undefined) url.searchParams.set(k, String(v));
  }
  const res = await fetch(url.toString(), {
    headers: { "Content-Type": "application/json" },
    signal: AbortSignal.timeout(15000),
  });
  if (!res.ok) throw new Error(`API ${res.status}`);
  return res.json();
}

async function getSystemHealth() {
  const d = await callAPI("/realtime/total");
  const n = d.total_blocks || 0;
  return `📊 系统健康度\n- 总 Block 数量: ${n}\n- 状态: ${n > 0 ? "✅ 正常运行" : "⚠️ 无数据"}`;
}

async function getRecentAnomalies(args) {
  const d = await callAPI("/anomalies/query", {
    hours: args.hours,
    minutes: args.minutes,
    limit: args.limit || 10,
  });
  const list = d.anomalies || [];
  let t = `🔍 异常查询结果: 共 ${d.anomaly_count || 0} 个异常\n`;
  if (list.length) {
    list.slice(0, 10).forEach((a, i) => {
      t += `\n${i + 1}. ${a.block_id}\n   分数: ${(a.anomaly_score || 0).toFixed(4)}`;
      if (a.events?.length) {
        t += `\n   事件: ${a.events.slice(0, 5).map((e) => `${e.event_id}(${e.count})`).join(", ")}`;
      }
    });
  }
  if (d.event_distribution) {
    t += "\n\n📈 事件分布:\n";
    Object.entries(d.event_distribution)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 10)
      .forEach(([k, v]) => { t += `  ${k}: ${v}次\n`; });
  }
  return t;
}

async function getTopAnomalies(args) {
  const d = await callAPI("/anomalies/query", {
    hours: args.hours || 1,
    limit: args.limit || 10,
  });
  const list = d.anomalies || [];
  let t = `🏆 Top ${args.limit || 10} 异常 Block\n`;
  if (!list.length) { t += "\n暂无异常数据"; return t; }
  list.forEach((a, i) => {
    t += `\n${i + 1}. ${a.block_id}\n   异常分数: ${(a.anomaly_score || 0).toFixed(4)}`;
    if (a.events?.length) {
      t += `\n   主要事件: ${a.events.slice(0, 5).map((e) => `${e.event_id}(${e.count})`).join(", ")}`;
    }
  });
  return t;
}

async function getEventDistribution(args) {
  const d = await callAPI("/anomalies/query", { hours: args.hours || 1, limit: 1 });
  const dist = d.event_distribution || {};
  const items = Object.entries(dist).sort((a, b) => b[1] - a[1]);
  let t = `📊 异常类型分布（过去 ${args.hours || 1} 小时）\n`;
  if (!items.length) { t += "\n暂无数据"; return t; }
  const total = items.reduce((s, [, v]) => s + v, 0);
  items.forEach(([k, v]) => {
    t += `\n  ${k}: ${v}次 (${((v / total) * 100).toFixed(1)}%)`;
  });
  t += `\n\n总计: ${total} 次事件`;
  return t;
}

const HANDLERS = {
  get_system_health: (args) => getSystemHealth(args),
  get_recent_anomalies: (args) => getRecentAnomalies(args),
  get_top_anomalies: (args) => getTopAnomalies(args),
  get_event_distribution: (args) => getEventDistribution(args),
};

// ========== 处理 MCP 消息 ==========
async function handleMessage(msg) {
  if (msg.method === "notifications/initialized") return;
  try {
    let result;
    switch (msg.method) {
      case "initialize":
        result = {
          protocolVersion: msg.params?.protocolVersion || "2024-11-05",
          capabilities: { tools: {} },
          serverInfo: { name: "hdfs-monitor", version: "1.0.0" },
        };
        break;
      case "tools/list":
        result = { tools: TOOLS };
        break;
      case "tools/call": {
        const text = await HANDLERS[msg.params.name](msg.params.arguments || {});
        result = { content: [{ type: "text", text }] };
        break;
      }
      default:
        result = {};
    }
    sendMsg(msg.id, result);
  } catch (e) {
    sendErr(msg.id, e.message || "Internal error");
  }
}

// 防止进程退出
process.stdin.resume();
