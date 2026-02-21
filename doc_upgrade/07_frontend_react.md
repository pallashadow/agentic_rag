# 前端迁移到 React — TODO List

## 1. 初始化 React 项目

- [ ] 用 Vite 新建 React+TS 项目（如 `npm create vite@latest frontend -- --template react-ts`），或保留现有 `frontend/` 目录并在其中 `npm init -y` 后安装依赖
- [ ] 安装依赖：`vite`、`react`、`react-dom`、`@vitejs/plugin-react`，以及 `@types/react`、`@types/react-dom`
- [ ] 配置 `vite.config.ts`：若部署到 GitHub Pages 子路径，设置 `base: '/chatbot_milesguo/'`（或当前 repo 名）

## 2. 路由与页面结构

- [ ] 安装 `react-router-dom`
- [ ] 配置路由：`/` → RAG 页，`/agentic` → Agentic 页（对应原 `rag.html` / `agentic.html`）
- [ ] 抽公共布局：Header（GitHub 链接、Switch To Agentic RAG 等）

## 3. 组件与状态迁移

- [ ] **公共组件**：SettingsCard（Cloud URL、title_k、chunk_k、query_expand_k、chunk_index、索引说明、Save/Reset、文档链接）
- [ ] **RAG 页**：RAG 设置 + 聊天区（消息列表、输入框、发送/取消、错误提示）+ Sources 展示
- [ ] **Agentic 页**：Agentic 专用设置（如 max_iter）+ 聊天区 + Agentic 的 Sources/步骤展示
- [ ] 把 `common.ts`、`types.ts`、`shared/page_helpers.ts` 迁入 React 项目，改为不依赖 DOM 的纯函数/工具
- [ ] 设置状态：用 `useState` 或 context，继续用现有 `loadSettingsFromStorage` / `saveSettingsToStorage` 的 key 与结构
- [ ] 消息列表状态：`useState`（或 reducer），流式时更新对应消息内容

## 4. 流式与 SSE

- [ ] 保持用 `EventSource` 或 `fetch` 流式读 body，在回调里更新“当前助手消息”的 state
- [ ] 打字机效果：在 `useEffect` 里对当前消息 ref 调用现有 `typewriterEffect`，或改为 state 驱动逐字显示

## 5. 样式与静态资源

- [ ] 将现有 `styles.css` 拷入 React 项目并 import（如 `src/styles.css` 或按组件拆）
- [ ] 确保 README_INDEX 等静态资源在 build 中可用（复制到 `public/` 或通过 Vite `publicDir`）

## 6. CI / 部署

- [ ] 在「Deploy to GitHub Pages」workflow 中：`cd frontend && npm ci && npm run build`
- [ ] Upload artifact 的 `path` 改为 `frontend/dist`（或配置的 `outDir`）
- [ ] 移除旧的 `tsc -p frontend/tsconfig.json` 步骤；BUILD_INFO 改为在 Vite 的 `index.html` 或插件中注入（可选）
- [ ] 保留或调整「Sync chunk index guide」步骤，使构建产物包含 `README_INDEX.md`

## 7. 过渡与收尾

- [ ] 若需零风险过渡：可先建 `frontend-react/`，CI 部署到子路径或另一分支，验证后再替换 `frontend/` 并改回主路径
- [ ] 替换完成后删除旧 HTML/TS 入口（或归档），更新文档与 README
