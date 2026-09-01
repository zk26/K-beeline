# AGENTS.md — K-Beeline 项目指南

## 项目定位

将原 5300 行单文件脚本（`main.py` 发帖 / `main_jihuo.py` 激活）重构为可分发的 Windows 桌面软件。
最终用户无技术背景：双击安装、选择账号表、点开始。任何破坏这一点的改动都是倒退。

## 环境

- Python 3.12，虚拟环境 `.venv\`（激活：`.\.venv\Scripts\Activate.ps1`）
- 安装依赖：`pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/`
  （本机网络访问 pypi.org 极慢，必须用国内镜像；大包如 PySide6 用 curl 断点续传下载 wheel 后本地安装）
- 运行：`.\.venv\Scripts\python run.py`
- 打包：`scripts\build_exe.ps1` → `scripts\installer.iss`（Inno Setup 6）

## 架构铁律

1. **`app/core/` 禁止导入 PySide6**。核心层通过 `PipelineContext` + `RunnerEvents` 回调与 UI 解耦，可在无 GUI 环境独立测试。
2. **禁止模块级全局可变状态**。原脚本的 `CURRENT_PROXY` / `USED_PROXY_IPS` / `IP_METHOD` 已分别迁入 `PipelineContext.current_proxy`、`ProxyPool.used_ips`、`AppConfig`。新增状态一律走这三个载体。
3. **路径一律走 `app/utils/paths.py`**：只读资源 `resource_path()`（兼容 PyInstaller `_MEIPASS`），可写数据 `user_data_path()`（%LOCALAPPDATA%\KBeeline）。禁止硬编码绝对路径（原脚本的 `G:\edgedriver_win64` 教训）。
4. **驱动路径只允许来自 `DriverManager`**；`ctx.driver_path` 为 `None` 是合法值，表示交给 Selenium Manager。

## 业务要点（改动前必读）

- **双模式状态码不同**：发帖模式成功码=2，激活模式成功码=1；映射逻辑在 `runner._process_account` 与 `excel_service.build_remark`，两处必须同步修改。
- **激活模式专属步骤**：登录成功后若 `login_password != reset_password`，必须执行 `auth.force_change_password_in_settings`（账号设置页强制改密），然后回首页再导航。
- **重试策略（与原脚本一致，勿随意改动数值）**：代理验证≤3 次、首页访问≤2 次、登录重试≤1 次、发帖重试≤1 次；发帖遇"网络超时"走"退出→重登录→重导航→重发"且不计重试次数。
- **备注格式**是下游统计依据：发帖 `序号.状态-是否重置[密码]-位置-IP`（内网IP省略），激活 `序号.状态-重置状态[密码]-时间`。
- 选择器（`.login-btn.flex-center`、`.publish-btn`、`.my-editor`、话题弹窗等）与 beeline-ai.com 前端强耦合，网站改版时按 F12 实际结构更新 `auth.py` / `posting.py`。
- **代理 API URL 含付费密钥**（`priority_proxy_api_url`），属于有意随软件分发的资产，但不要提交到公开仓库。

## 测试

- 无 pytest 套件；冒烟测试方式见 `tests/`（直接用 venv python 运行）。
- 改动 `core/` 后至少运行：`tests\smoke_core.py`；改动 UI 后运行 `tests\smoke_gui.py`（离屏模式）。

## 文档同步

修改本文件所述的任何规则、结构、流程后，必须同步更新本文件与 `README.md`。
