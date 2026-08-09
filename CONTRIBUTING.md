# 贡献指南

感谢你考虑为**英语刷题机**做出贡献！无论是修 Bug、加功能、改文档还是提建议，都非常欢迎。

## 如何开始

1. Fork 本仓库并克隆到本地
2. 创建功能分支：`git checkout -b fix/xxx` 或 `feature/xxx`
3. 提交前阅读 [README.md](README.md) 了解项目结构与数据格式
4. 按 [PR 模板](.github/PULL_REQUEST_TEMPLATE.md) 提交 Pull Request

## 开发环境

```bash
# 前端（Vue 3 + Vite）
cd frontend && npm install && npm run dev

# 后端（FastAPI + SQLite）
cd backend && python -m uvicorn app.main:app --host 127.0.0.1 --port 8765

# 构建
cd frontend && npm run build
```

## 代码规范

- **前端**：TypeScript 严格模式；组件遵循现有样式（styles.css 集中管理）
- **后端**：Python 3.10+；路由按模块拆分（app/routers/）；SQL 参数化查询
- **提交信息**：`fix: xxx` / `feat: xxx` / `docs: xxx` / `refactor: xxx`
- **不要**：改动无关文件、大规模重命名、引入未使用的依赖

## 题库与数据

- 题库格式见 [docs/question-bank-format.md](docs/question-bank-format.md)
- 词汇/题目数据入库时保持 category 标签与前端一致（高中/四级/六级/考研）
- 发布流程：`python scripts/release_all.py <版本号>`

## 测试

- 前端：`npm run build` 必须通过
- 后端：启动后 `curl http://127.0.0.1:8765/api/health` 返回 200
- 发布前回归：核心刷题/错题本/单词本/题库导入全流程

## 问题

遇到问题请先看 [FAQ](README.md#常见问题faq)，仍无法解决再开 [Issue](https://github.com/mo9652962-ai/epm-releases/issues)。
