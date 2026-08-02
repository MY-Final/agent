# Changelog

本仓库提交历史遵循 Conventional Commits 风格，按版本组织（[Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/) 规范）。

## [Unreleased]

## [v0.1.0] - 2026-08-02

首个正式版本，覆盖从后端基础服务到桌面端打包的完整主流程。

### Added

- 桌面端侧车打包并自动拉起后端（[c22765d](https://github.com/MY-Final/agent/commit/c22765d)）
- 新增 Docker Compose 服务器部署（[6681bbb](https://github.com/MY-Final/agent/commit/6681bbb)）
- Agent 对话支持 Markdown 渲染与思考过程展示（[7dbc173](https://github.com/MY-Final/agent/commit/7dbc173)）
- 支持与 Agent 会话式对话并强化流式容错（[141b00f](https://github.com/MY-Final/agent/commit/141b00f)）
- 实现大模型流式输出与 AI 解析过程详情（[690fd8b](https://github.com/MY-Final/agent/commit/690fd8b)）
- 新增工作台与知识库管理，完善原文修正、报告导出和 AI 成本统计（[7ac4062](https://github.com/MY-Final/agent/commit/7ac4062)）
- 重构标书解析为模板驱动，支持 AI 生成模板与多版本溯源（[2c61592](https://github.com/MY-Final/agent/commit/2c61592)）
- 增加多模型提供商设置与连接测试（[9ce8933](https://github.com/MY-Final/agent/commit/9ce8933)）
- 完成投标分析后端第一阶段基础服务（[0c18339](https://github.com/MY-Final/agent/commit/0c18339)）
- 实现标书解析 Skill 第二阶段能力（[453afbe](https://github.com/MY-Final/agent/commit/453afbe)）
- 增加公司资质知识库与资质匹配能力（[f37ca9a](https://github.com/MY-Final/agent/commit/f37ca9a)）
- 实现 LangGraph 单任务分析 Agent 流程（[7112c4c](https://github.com/MY-Final/agent/commit/7112c4c)）
- 增加投标分析桌面端并完善项目说明（[eaecacc](https://github.com/MY-Final/agent/commit/eaecacc)）

### Changed

- 提示词抽离为独立模板并优化多模型适配（[d3719a7](https://github.com/MY-Final/agent/commit/d3719a7)）
- 完善打包配置、基础设施连接设置与大模型提供商体验（[3a07ff2](https://github.com/MY-Final/agent/commit/3a07ff2)）

### Fixed

- 优化大模型结构化校验报错并容错缺失字段（[4a61720](https://github.com/MY-Final/agent/commit/4a61720)）

### Docs

- 更新 README 至当前功能全貌（[48f034a](https://github.com/MY-Final/agent/commit/48f034a)）
- 补充桌面端 Windows 安装包说明并启用 NSIS/MSI 打包（[d3b7643](https://github.com/MY-Final/agent/commit/d3b7643)）

[v0.1.0]: https://github.com/MY-Final/agent/releases/tag/v0.1.0
