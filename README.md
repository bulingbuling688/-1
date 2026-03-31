# 知识引擎（建议名：News Pipeline Collector）

> 说明：仓库当前目录名为“知识引擎”。如果你希望对外更正式一些，可使用建议名 `News Pipeline Collector` 作为开源项目名。

## 项目简介

这个项目是一个本地运行的新闻采集与分发管道：从多个信息源抓取内容，做基础清洗与去重，再批量推送到 n8n Webhook，方便你接到后续自动化流程（如入库、AI 摘要、推送到飞书多维表格等）。

它解决的核心问题是：把“分散在不同来源的信息”变成“可持续、可追踪、可重试”的统一输入流，避免手工复制粘贴和重复处理。

相比普通的一次性脚本，这个项目的特点是有状态（SQLite 去重 + outbox）、有失败重试机制、支持分阶段运行（只采集/只投递），更适合长期稳定跑数据流。

## 主要功能

### 核心功能

- 多源新闻采集：支持 Hacker News、RSS、Raingou 等来源，统一输出为同一数据结构，便于后续处理。
- 本地去重与状态持久化：使用 SQLite 记录 `seen_items` 和 `outbox`，避免重复入队和重复发送。
- 批量投递到 Webhook：按批次把数据推送到 n8n，便于接入自动化工作流。
- 失败重试与退避：投递失败后自动重试，并支持指数退避，降低临时网络问题带来的丢单风险。
- 正文增强（可选）：可抓取网页 HTML 并提取正文文本，补充 `content_full/content_snippet`，提升后续 AI 处理效果。

### 辅助功能

- 分模式运行：支持 `--collect-only`、`--deliver-only`、`--retry-failed`，便于排障和运维。
- 配置化开关：通过 `config.json` 控制源启停、超时、批大小、重试次数等参数。
- 预留插件接口：翻译、实体提取、聚类、个性化模块已预留（当前为 no-op，便于后续扩展）。

## 适用场景

- 个人或小团队搭建“信息雷达”：定时抓取技术新闻、行业资讯，再分发到飞书/数据库/消息系统。
- 需要把外部资讯接入 n8n 自动化链路的开发者或运营同学。
- 想低成本实现“可持续采集 + 去重 + 重试投递”的数据入口，而不是维护复杂爬虫平台的场景。

## 项目特点

- 本地可落地：依赖简单（Python + SQLite），单机即可跑通。
- 工程化基础完整：有采集、处理、存储、投递的清晰模块边界。
- 可靠性优先：通过 outbox 状态机和重试机制，避免一次失败导致数据中断。
- 接入友好：统一 JSON payload，对接 n8n Webhook 成本低。
- 可演进：已预留插件扩展点，后续可逐步接入翻译、实体识别、聚类等能力。

## 快速开始

### 1. 安装依赖

```bash
python -m pip install -r requirements.txt
```

### 2. 配置

```bash
copy config.example.json config.json
```

编辑 `config.json`，重点修改：

- `webhook_url`：你的 n8n Webhook 地址
- `sources[*].enabled`：启用/禁用对应采集源
- `delivery`：批量发送和重试参数（按实际情况调整）

### 3. 运行

```bash
python collector.py --config config.json
```

常用运行模式：

```bash
# 只采集并入队，不发送
python collector.py --config config.json --collect-only

# 只发送 outbox 中待发送数据
python collector.py --config config.json --deliver-only

# 先把 failed 重新入队，再执行发送
python collector.py --config config.json --retry-failed --deliver-only
```

## 使用示例

### 示例：推送到 n8n 的 payload 结构

```json
{
  "items": [
    {
      "source_id": "hn:123",
      "source_name": "hackernews",
      "title": "Example Title",
      "url": "https://example.com/article",
      "domain": "example.com",
      "author": "author_name",
      "published_at": "2026-03-29T11:50:52+00:00",
      "content_snippet": "摘要或正文片段",
      "score": 10,
      "raw": {},
      "fetched_at": "2026-03-29T11:50:52+00:00"
    }
  ]
}
```

> 此处建议后续补充一张 n8n 工作流截图或最小工作流 JSON，帮助新用户 1 分钟理解端到端接入方式。

## 项目结构

```text
.
├─ collector.py                       # 程序入口
├─ config.example.json                # 配置模板
├─ news_pipeline/
│  ├─ orchestrator.py                 # 主流程编排
│  ├─ source_registry.py              # 采集源注册与调度
│  ├─ collectors/
│  │  ├─ hn.py                        # Hacker News 采集器
│  │  ├─ rss.py                       # RSS 采集器
│  │  └─ raingou.py                   # Raingou 采集器
│  ├─ processors/
│  │  └─ content_enricher.py          # 正文抓取与文本提取
│  ├─ storage/
│  │  └─ state_store.py               # SQLite 状态管理（去重/outbox）
│  ├─ delivery/
│  │  └─ webhook.py                   # Webhook 批量发送与重试
│  └─ plugins/                        # 扩展点（当前预留）
└─ run_collector.ps1                  # Windows 一键运行脚本
```

## Roadmap

- 完善插件能力：逐步实现翻译、实体提取、主题聚类、个性化排序。
- 增加观测性：补充更细粒度日志、失败告警和运行指标。
- 增加测试与示例：补充关键模块单元测试和最小 n8n 工作流示例。

> Roadmap 可根据实际项目节奏补充和调整。
