# 智能差旅与户外活动应急管家

这是一个基于 MCP Agent 架构的场景化智能助手，当前主要聚焦在：

- 天气查询：根据城市/地点查询天气
- 路线与交通查询：根据起点/终点查询通勤时间、拥堵状态和路线信息
- 活动风险评估：结合天气、路线、活动类型、备选场地等信息做应急评估
- 本地文档解析：读取本地 txt / pdf 文件，提取活动行程和场地方案中的位置信息
- 前端展示：通过网页端完成天气查询、路线查询和风险评估的交互

项目当前适用场景为：

- 差旅出行
- 户外活动组织
- 应急方案评估
- 活动场地备选和路线转移预案

## 1. Agent 设计概览

项目采用典型的 skill-based agent 架构：

- orchestrator.py：负责对用户意图进行路由，并调用相应 skill
- skills/：每个功能独立封装成 skill
- schemas.py：定义功能参数与返回结构
- mcp_server.py：FastAPI 后端，对外暴露 API 与静态页面
- frontend/：前端网页界面

当前已注册的主要技能包括：

- get_weather：查询天气
- get_route_status：查询路线状态、拥堵和用时
- assess_trip_risk：综合风险评估
- summarize_pdf：摘要提取（保留通用 PDF 处理能力）

## 2. 主要功能

### 2.1 天气查询

- 支持按城市/地点查询天气
- 通过高德地图 Web服务 API 进行地理编码和天气查询
- 若未配置高德 key，则回退到其他可用方案，保证程序不直接崩掉

### 2.2 路线查询

- 支持起点、终点和出行方式（driving / walking / transit）
- 使用高德 Web服务 API 进行路线规划
- 前端使用高德 JS API 显示地图与实时路况
- 结果包含：状态、耗时、距离、API 来源等

### 2.3 活动风险评估

- 读取本地行程文件和备用场地方案文件
- 提取活动类型、当前活动地点、备用场地
- 结合天气风险和路线状态，输出风险等级、因素和建议动作
- 适用于户外活动、商业路演、摄影采风、团建活动等场景

### 2.4 本地文件读取

- 支持 .txt 和 .pdf 文件
- 自动解析活动方案中的文本
- 提取城市、地点、备用场地等关键信息
- 不依赖远程写死的默认资料，确保“数据来源本地文件”

## 3. 技术架构

### 后端

- FastAPI
- Pydantic schema 校验
- async HTTP 请求
- skill registry + orchestrator

### 前端

- 原生 HTML / JavaScript
- 支持独立面板：天气、路线、风险评估
- 支持文件上传与解析
- 使用高德 JS API 展示地图和交通图层

### 核心上下文与集成方式

当前 Agent 使用以下上下文 / 集成方式：

- prompt context：用户输入的 prompt 与上下文参数
- file context：本地 itinerary / venue plan 文件路径
- extracted location context：从文档中抽取出的地点和城市
- weather context：当前城市或活动地点的天气信息
- route context：起点、终点、交通方式和路况信息
- risk context：活动类型、风险阈值、临时场地转移建议

此外，系统支持：

- OpenAI function-calling（如果配置 OPENAI_API_KEY）
- 本地规则分流（当未配置 OpenAI 时）

## 4. 项目结构

```text
labAgent/
├── mcp_server.py            # FastAPI 服务入口
├── orchestrator.py          # Agent 意图路由
├── schemas.py              # 参数与返回结构定义
├── requirements.txt        # Python 依赖
├── README.md               # 项目说明
├── frontend/
│   ├── index.html          # 网页前端
│   └── app.js              # 前端逻辑
├── skills/
│   ├── __init__.py
│   ├── get_weather.py      # 天气查询 skill
│   ├── get_route_status.py # 路线查询 skill
│   ├── summarize_pdf.py    # PDF 摘要 skill
│   └── travel_emergency_manager.py  # 风险评估 skill
├── tests/
│   └── test_skills.py      # 回归测试
└── .venv/                  # 本地 Python 环境
```

## 5. 启动方式

### 安装依赖

```bash
pip install -r requirements.txt
```

### 启动后端

```bash
python -m uvicorn mcp_server:app --host 127.0.0.1 --port 8011
```

### 打开前端

浏览器访问：

```text
http://127.0.0.1:8011/
```

## 6. 接口说明

### 6.1 主页

```http
GET /
```
返回前端页面。

### 6.2 配置接口

```http
GET /api/config
```
返回当前高德 key 配置状态，用于前端 JS API 初始化。

### 6.3 Agent 决策接口

```http
POST /mcp/decide
```
Body 示例：

```json
{
  "prompt": "评估我的户外活动风险并给出建议",
  "context": {
    "activity_type": "商业路演",
    "current_location": "上海",
    "backup_location": "上海虹桥万怡会议中心",
    "itinerary_path": "tests/sample_itinerary.txt",
    "venue_plan_path": "tests/sample_venue_plan.txt"
  }
}
```

## 7. 高德地图配置说明

项目已按“高德 Web服务 API + JS API”模式设计：

- 后端路线/天气查询：使用高德 Web服务 API
- 前端地图展示：使用高德 Web端 JS API

常用环境变量：

```bash
GAODE_MAP_API_KEY=your_web_service_key
GAODE_JS_API_KEY=your_js_api_key
GAODE_SECURITY_JS_CODE=your_security_js_code
```

如果未配置，系统会走兜底逻辑，但真实地图能力依赖有效高德 Key。

## 8. 使用示例

### 8.1 天气查询

```json
{
  "prompt": "查询上海天气",
  "context": {
    "location": "上海"
  }
}
```

### 8.2 路线查询

```json
{
  "prompt": "分析从北京朝阳公园到北京国贸会议中心的路线",
  "context": {
    "origin": "北京朝阳公园",
    "destination": "北京国贸会议中心",
    "mode": "driving"
  }
}
```

### 8.3 风险评估

```json
{
  "prompt": "评估户外活动应急方案",
  "context": {
    "activity_type": "户外团建",
    "current_location": "上海",
    "backup_location": "上海外滩·黄浦江景观带",
    "itinerary_path": "tests/sample_itinerary.txt",
    "venue_plan_path": "tests/sample_venue_plan.txt"
  }
}
```

## 9. 运行验证

项目已包含针对关键 skill 的回归测试：

```bash
python -m pytest tests/test_skills.py -q
```

测试覆盖：

- 天气查询
- 路线查询
- 风险评估
- 本地文件解析路径

## 10. 当前项目价值

这个项目已经从简单的 MCP Demo 扩展成一个具备真实业务场景的智能助手，重点体现了：

- 多 skill 协同
- 本地数据优先的场景判断
- 天气 + 路线 + 风险统一分析
- 适合户外活动和差旅应急场景

如果你需要继续扩展，下一步可以考虑加入：

- 住宿推荐
- 交通拥堵历史分析
- 应急资源库
- 个人偏好和历史出行数据
- 更强的 LLM / 多轮对话交互

## 11. 备注

当前项目默认强调本地文档优先、地理信息与地图服务结合，以及可视化前端交互。对于真实生产环境，推荐进一步强化：

- 正式高德 key 管理
- 异常处理和服务降级
- 日志与监控
- 权限控制和安全校验
