# MCP Agent (PDF summary + Weather)

快速启动：

1. 安装依赖：

```bash
pip install -r requirements.txt
```

2. 运行服务器：

```bash
uvicorn mcp_server:app --reload --port 8000
```

3. 请求示例：

POST http://127.0.0.1:8000/mcp/decide

Body:

```json
{ "prompt": "帮我总结本地文件 readings/lecture1.pdf 的前5页", "context": { "path": "readings/lecture1.pdf" } }
```

天气示例（无 OpenAI key 时使用 fallback）：

```json
{ "prompt": "获取伦敦现在的天气", "context": { "location": "London" } }
```

说明：若设置 `OPENAI_API_KEY`，orchestrator 会使用 OpenAI 的 function-calling，将函数 schema 传给模型。
