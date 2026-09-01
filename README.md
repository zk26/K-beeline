# K-Beeline 自动化助手

面向最终用户的 Windows 桌面软件：批量自动登录 beeline-ai.com 账号，完成「校友集结号」**发帖**或账号**激活**，并将结果自动写回 Excel 账号表。

## 特性

- **图形界面**：开箱即用，无需安装 Python 或任何依赖
- **浏览器驱动自动更新**：启动时自动检测本机 Edge 版本，自动下载匹配的 msedgedriver（彻底解决 Edge 升级后脚本失效的问题）
- **双模式**：发帖模式 / 激活模式（登录→重置密码→进入芯泉子）
- **一号一IP**：代理池自动分配，历史 IP 持久化记录，避免重复
- **虚拟定位**：全国城市随机定位 + CDP 底层覆盖 + WebRTC 封死
- **拟人化操作**：随机等待、逐字输入、随机图片裁切
- **结果回写**：处理状态、密码、IP、归属地自动写回 Excel 备注列

## 最终用户

直接运行安装程序 `KBeelineSetup.exe`，安装后桌面双击「K-Beeline 自动化助手」即可。
详见 [docs/使用说明.md](docs/使用说明.md)。

## 开发者

### 环境准备

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/
```

### 运行（开发模式）

```powershell
.\.venv\Scripts\python run.py
# 或
.\.venv\Scripts\python -m app
```

### 打包

```powershell
# 1. 构建 exe（产出 dist\KBeeline\）
powershell -File scripts\build_exe.ps1

# 2. 构建安装程序（需要 Inno Setup 6，产出 Output\KBeelineSetup.exe）
& "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" scripts\installer.iss
```

详见 [docs/打包部署.md](docs/打包部署.md)。

## 项目结构

```
K-beeline/
├── app/                    # 应用源码
│   ├── main.py             # 入口（QApplication 初始化）
│   ├── core/               # 核心业务层（无 UI 依赖，可独立测试）
│   │   ├── config.py       #   配置模型 + JSON 持久化
│   │   ├── constants.py    #   状态码 / 文案 / 全国城市坐标库
│   │   ├── models.py       #   数据模型（记录/结果/统计/上下文）
│   │   ├── content.py      #   帖子内容生成 + 图片随机裁切
│   │   ├── excel_service.py#   账号表读写 / 锁定检测 / 备注构建
│   │   ├── proxy_service.py#   代理池（获取/测试/一号一IP）
│   │   ├── location_service.py # 虚拟定位 + IP/坐标归属地
│   │   ├── browser.py      #   Edge 驱动构建（反检测/CDP/WebRTC封死）
│   │   ├── auth.py         #   登录 / 密码重置 / 强制改密
│   │   ├── posting.py      #   导航 / 发帖 / 真人输入 / 结果检测
│   │   └── runner.py       #   批量处理引擎（双模式、可停止）
│   ├── services/
│   │   ├── driver_manager.py # ★ EdgeDriver 自动检测/下载/缓存
│   │   └── logging_service.py# 文件 + UI 双通道日志
│   ├── ui/                 # PySide6 界面层
│   │   ├── main_window.py  #   主窗口
│   │   ├── settings_dialog.py # 高级设置
│   │   └── worker.py       #   后台线程（驱动检测/批量任务）
│   └── utils/
│       ├── paths.py        #   路径解析（开发/打包双模式）
│       └── humanize.py     #   拟人化等待
├── assets/                 # 只读资源（打进安装包）
│   ├── img/                #   内置图片库（35张）
│   ├── templates/          #   账号表模板
│   ├── drivers/            #   兜底 EdgeDriver
│   └── icons/              #   应用图标
├── scripts/                # 构建脚本（PyInstaller / Inno Setup）
├── tests/                  # 测试
├── docs/                   # 文档
└── run.py                  # 启动入口
```

## 运行时数据位置

用户机器上的可写数据统一放在 `%LOCALAPPDATA%\KBeeline\`：

| 内容 | 路径 |
|---|---|
| 配置文件 | `config.json` |
| 驱动缓存 | `drivers\{大版本}\msedgedriver.exe` |
| 已用IP记录 | `used_ips.txt` |
| 运行日志 | `logs\kbeeline_YYYYMMDD.log` |
| 临时上传 | `temp_upload\` |
