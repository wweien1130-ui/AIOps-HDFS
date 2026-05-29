# Retry 与 Fallback 机制调试全记录

## 架构概览

```
START → Supervisor(LLM) → Router → 子Agent → Validator → END
                                          ↓
                                    ErrorHandler
                                    ├─ retry<3 → Command(goto="target_agent")
                                    └─ retry≥3 → Command(goto="fallback")
```

---

## 问题一：retry 只触发一次就 fallback

### 现象
删除 CSV 文件后触发错误，控制台只打印了一次 `[ErrorHandler] 第 1 次重试`，随即就
`Router → fallback`，预期的 3 次 retry 和最终 fallback 都没有完整执行。

### 根因
retry 回环路径为 `ErrorHandler → Supervisor → Router → Agent`。
Supervisor 节点每次执行都会返回 `{"next_agent_override": ""}`，**清空了 ErrorHandler
精心设置的纠错路由指令**。代理又调用了 LLM 重分类意图，分类型一个非法值
（`intent="data_agent"`），Router 将其映射到 fallback。整个回环链条太长，依赖
LLM 的不确定性太大。

### 解决方案
用 LangGraph 的 `Command(goto=...)` 替代条件边回环。ErrorHandler 直接跳转到目标
Agent，**完全绕过 Supervisor**，不再依赖 LLM。

```python
# _handle_error 现在返回 Command 对象
if retry >= 3:
    return Command(goto="fallback", update={"retry_count": retry})
return Command(goto="data_agent", update={"retry_count": retry, "error_type": ""})
```

同时移除 `_decide_retry` 条件边，改为 `builder.add_edge("error_handler", "fallback")`
作为兜底。

---

## 问题二：Validator 漏掉错误 → ErrorHandler 不触发

### 现象
DataAgent 执行工具失败后，Validator 未检测到错误，流程直接 END，retry 和 fallback
完全没有触发。

### 根因
1. **错误消息字面不匹配**：`train_mlp_model` 返回 `"训练失败：找不到矩阵文件"`，
   但 Validator 只匹配 `"矩阵文件不存在"`。两字之差，直接漏过。
2. **只看最后一条消息**：LLM 经常把原始错误信息包在中间的 tool 消息里，最后一条
   AI 消息已经用自己的话"翻译"过了，原始错误关键词丢失。

### 解决方案
1. **补全错误模式**：新增 `"找不到矩阵文件"`、`"找不到模型文件"`、`"训练失败"`、
   `"模型缺失"` 等匹配项
2. **扩大扫描范围**：从只看最后 1 条消息改为扫描最后 10 条消息

```python
# 修复后的 ERROR_PATTERNS
ERROR_PATTERNS = [
    ("找不到矩阵文件",    "data_not_ready"),
    ("矩阵文件不存在",    "data_not_ready"),
    ("找不到模型文件",    "model_not_ready"),
    ("模型文件不存在",    "model_not_ready"),
    ("训练失败",          "model_not_ready"),
    ("模型缺失",          "model_not_ready"),
    ("文件缺失",          "data_not_ready"),
    ("组件不全",          "data_not_ready"),
    ("Connection refused", "connection_failed"),
    ("连接失败",          "connection_failed"),
    ("timeout",           "timeout"),
    ("超时",              "timeout"),
    ("FileNotFoundError", "file_missing"),
]

# 从后往前扫最近 10 条消息
for msg in reversed(messages[-10:]):
    ...
```

---

## 问题三：LLM 自主重试 vs ErrorHandler 重试冲突

### 现象
DataAgent 内部的 ReAct LLM 会在工具失败后自主重试（"我再试一次"、"换个参数试试"），
导致和 ErrorHandler 的重试叠加（3×3=9 次）。且 LLM 的重试是盲目重试同一调用，没有
智能路由。

### 根因
子 Agent 使用 `create_agent` 构建，内部的 ReAct 循环允许 LLM 自行决定是否重新
调用工具。LLM 天然有"再试一次"的倾向。

### 解决方案
在 Diagnosis 和 Data 的 prompt 中**禁止 LLM 自主重试**，将重试权完全交给
ErrorHandler。

```markdown
## 禁止重试！

- **工具调用失败后禁止重复调用！** 失败就失败了，直接报告错误信息
- 不要尝试"我再试一次"、"换个参数试试"
- 错误会由上层 ErrorHandler 自动处理（重试+降级），不需要你重试
- 每个工具只调用一次，失败后立即报告结果
```

| | LLM 自主重试 | ErrorHandler 重试 |
|---|---|---|
| 触发者 | LLM "自觉" | Python 代码 |
| 策略 | 盲目重试同一调用 | 根据错误类型路由到正确 Agent |
| 可预测性 | 不可控 | 确定性 |
| 耗时 | ~3s/次（LLM 推理） | ~0s（直接跳转） |
| 状态 | **已禁止** | **统一管理** |

---

## 关键改动文件

| 文件 | 改动 |
|------|------|
| `agent/react_agent.py` | Validator 补全错误模式+扩大扫描范围；ErrorHandler 改用 Command(goto=...)；导入 langgraph.types.Command |
| `prompts/data_prompt.txt` | 新增「禁止重试！」规则 |
| `prompts/diagnosis_prompt.txt` | 新增「禁止重试！」规则 |

---

## 当前完整流程

```
用户: "训练模型"
  ↓
Supervisor (LLM) → intent=data
  ↓
Router → data_agent
  ↓
DataAgent (LLM, 禁止重试):
  调 preprocess_hdfs_logs → ✅
  调 train_mlp_model → ❌ "找不到矩阵文件"
  立即报告错误（不再自旋重试）
  ↓
Validator (扫描最后10条消息):
  匹配 "找不到矩阵文件" → error_type=data_not_ready
  ↓
ErrorHandler:
  retry=1 → Command(goto="data_agent")
  retry=2 → Command(goto="data_agent")
  retry=3 → Command(goto="fallback")
  ↓
Fallback → "抱歉，我暂时无法完成这个请求..."
```
