# wangjinliang12345 A2A 集成贡献总结

> 本文档总结 jinliang wang (`jlsmile.wang@samsung.com`) 在 Hermes-Agent 仓库中关于 **A2A (Agent-to-Agent) 协议集成** 与 **WebSocket 实时通信** 的设计修改。

---

## 1. 贡献概况

| 项目 | 详情 |
|------|------|
| **作者** | jinliang wang <jlsmile.wang@samsung.com> |
| **GitHub** | wangjinliang12345 |
| **Commits 数量** | ~20 个（含 merge commit 与早期测试提交） |
| **核心主题** | A2A 协议集成、WebSocket 实时通信、智能家居 Skill 示例 |
| **时间跨度** | 2026-04-29 ~ 2026-04-30 |

---

## 2. 设计修改相关目录

### 2.1 核心架构层（直接影响 Hermes Agent 运行时）

| 文件/目录 | 修改内容 | 设计意义 |
|-----------|----------|----------|
| `tools/a2a_proxy.py` | 新增 A2A 代理工具，支持通过 A2A 协议调用远程 Agent | **核心设计文件**，被修改 5 次，是 Agent 调用外部 A2A 服务的能力入口 |
| `toolsets.py` | 注册 `_HERMES_CORE_TOOLS` 中新增 A2A 工具集 | 将 A2A 能力纳入 Hermes 工具发现与调度体系 |
| `hermes_cli/config.py` | 新增 A2A/WebSocket 相关配置项 | CLI 配置层扩展，支持用户通过 `config.yaml` 配置 A2A 连接参数 |
| `hermes_cli/tools_config.py` | 工具配置扩展 | CLI 工具菜单与配置逻辑联动 |
| `websocket_client.py` | 新增 WebSocket 客户端封装 | 与 A2A 服务端建立长连接，支持消息收发 |
| `skills/smart-home/fridge-control/SKILL.md` | 新增智能家居（冰箱控制）Skill | 提供 A2A 工具调用的业务层示例/用例 |
| `tests/tools/test_registry.py` | 工具注册表测试补充 | 确保 A2A 工具在自动发现机制中被正确注册 |

### 2.2 Vendored SDK 层（`a2a-python-1.0.2/`）

该目录为**完整引入的 Google A2A Python SDK（v1.0.2）**，属于大型 vendored dependency：

| 子目录 | 设计作用 |
|--------|----------|
| `src/a2a/client/` | A2A 客户端核心，含 **WebSocket 传输层** (`transports/websocket.py`)、gRPC、REST、JSON-RPC 等多协议支持 |
| `src/a2a/client/websocket_server.py` | WebSocket 服务端逻辑（被后续 commit 追加日志） |
| `src/a2a/server/` | A2A 服务端参考实现（任务管理、事件队列、请求处理、路由分发） |
| `src/a2a/compat/v0_3/` | v0.3 → v1.0 兼容层，保证协议版本平滑迁移 |
| `src/a2a/types/` | Protobuf 生成的类型定义（`a2a_pb2.py`） |
| `tests/` | SDK 自带的大量单元/集成/E2E 测试 |

> `48753897` 这个 commit 一次性新增约 **300 个文件、7.4 万行**，基本就是整个 `a2a-python-1.0.2/` 目录的引入。

### 2.3 工程/配置与文档层

| 文件 | 说明 |
|------|------|
| `pyproject.toml` | 新增 A2A SDK 的依赖声明 |
| `.env.example` | 新增 A2A/WebSocket 环境变量示例 |
| `changes.md` | 记录 A2A 集成与 WebSocket 支持的变更日志 |
| `a2a-python-1.0.2/websocket.md` | WebSocket 使用说明文档 |

---

## 3. Commit 演进时间线

### PR #1 — `d764e3bc` Support A2A Tool and add skill to call the tool
- **创建** `tools/a2a_proxy.py` 与 `skills/smart-home/fridge-control/SKILL.md`
- **打通** Skill → A2A Tool → 远程 Agent 的调用链路
- **关联文件**：`changes.md`, `hermes_cli/tools_config.py`, `toolsets.py`

### PR #2 — `48753897` support WebSocket for A2A Client
- **引入** 完整 `a2a-python-1.0.2/` SDK
- **新增** `demo_websocket_client.py` 与 WebSocket 传输层
- **设计意义**：通信架构从同步 HTTP 扩展到异步长连接

### PR #3 — `642e8c86` Support a2a tools call websocket to send message and get message
- **集成** WebSocket 消息收发能力到 `tools/a2a_proxy.py`
- **新增** 顶层 `websocket_client.py` 作为辅助客户端
- **关联文件**：`.env.example`, `hermes_cli/config.py`, `pyproject.toml`

### PR #4 — `e718be4f` Add logs for tool result and websocket message
- **补全** 可观测性：在 `a2a_proxy.py` 与 `websocket_server.py` 中增加日志

### PR #5 — `ee26432a` update skill
- **更新** `skills/smart-home/fridge-control/SKILL.md` 内容细节

### PR #6 — `0d83aa7c` / `2e26f0f8` 修复与日志级别微调
- **修复** 工具日志打印问题
- **降级** `not supported` 日志为 `info` 级别

---

## 4. 架构影响分析

### 4.1 新增依赖关系

```
Hermes Agent
    ├── tools/a2a_proxy.py          (A2A 工具入口)
    │       └── websocket_client.py  (WebSocket 辅助客户端)
    │       └── a2a-python-1.0.2/    (Vendored A2A SDK)
    │               └── src/a2a/client/transports/websocket.py
    ├── toolsets.py                  (工具集注册)
    ├── hermes_cli/config.py         (配置扩展)
    └── skills/smart-home/           (业务用例示例)
```

### 4.2 设计要点

1. **协议中立性**：通过 vendored SDK 同时支持 gRPC、REST、JSON-RPC、WebSocket 四种传输协议
2. **实时通信**：WebSocket 长连接的引入使 Hermes Agent 能够接收异步事件/推送通知
3. **工具自动发现**：`tools/a2a_proxy.py` 通过 `tools/registry.py` 自动注册，无需手动维护工具列表
4. **配置一致性**：A2A 配置复用 Hermes 现有的 `config.yaml` + `.env` 双层配置体系

---

## 5. 关键文件速查

| 场景 | 查看文件 |
|------|----------|
| 了解 A2A 工具如何被 Agent 调用 | `tools/a2a_proxy.py` |
| 查看 WebSocket 客户端实现 | `websocket_client.py` |
| 了解 A2A 工具注册位置 | `toolsets.py` |
| 了解配置项定义 | `hermes_cli/config.py` |
| 查看 Skill 用例 | `skills/smart-home/fridge-control/SKILL.md` |
| 了解 A2A SDK 客户端 API | `a2a-python-1.0.2/src/a2a/client/` |
| 查看 WebSocket 传输实现 | `a2a-python-1.0.2/src/a2a/client/transports/websocket.py` |
| 查看变更历史记录 | `changes.md` |

---

*文档生成时间：2026-05-06*
*基于分支：`summary-wangjinliang-a2a-contrib`*
