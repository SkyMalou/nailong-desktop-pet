# 发布到 GitHub

建议仓库名：`nailong-desktop-pet`，可见性：Public。

本目录是从本机工作目录单独整理的源码仓库。当前本机使用的 EXE、个人设置和原始素材不需要搬到仓库中，也不会因整理而被删除。

## 发布前检查

在本目录运行：

```powershell
git status --short
git ls-files
```

公开文件应只包括源代码、测试、依赖文件、打包配置和文档。个人邮箱、绝对路径、运行配置、日志、开发工具记忆、动画二进制、音频和 EXE 不应出现在提交内容中。当前仓库使用项目内的 noreply 提交邮箱，不修改电脑的全局 Git 设置。

## 创建并推送

在 GitHub 创建名为 `nailong-desktop-pet` 的公开空仓库。不要让 GitHub 另外初始化 README、许可证或 `.gitignore`，因为本地已经包含这些文件。

把下面命令中的 `YOUR_ACCOUNT` 替换为实际账号，然后在本目录执行：

```powershell
git remote add origin https://github.com/YOUR_ACCOUNT/nailong-desktop-pet.git
git push -u origin main
```

GitHub 身份验证应通过 Git Credential Manager、SSH 或已授权的 GitHub CLI 完成，不要把访问令牌写入代码、脚本、README 或远程地址。

建议仓库简介：

```text
Windows 奶龙桌宠：透明窗口、鼠标互动、交替迈步、分裂玩法和高采样渲染。Python + Win32，MIT 开源代码，素材需自行准备。
```

可选 Topics：`desktop-pet`、`windows`、`python`、`win32`、`nailong`。

## EXE 发行

公开仓库中的 GitHub Actions 只运行检查，不自动上传本机文件或创建 Release。需要发行 EXE 时，请先核实包含素材和第三方组件的发行条件，再单独创建 Release；不要把本机 `settings.json`、日志或构建缓存一起上传。

源码仓库保留 `requirements.txt` 和 `requirements-dev.txt`，供开发者从源码运行、测试和重新打包。普通用户下载 EXE 即可使用，无需安装 Python 或这些依赖。

1. 在仓库的 **Releases** 页面选择 **Draft a new release**，填写版本标签（例如首次发布使用 `v1.0.0`）和版本说明。
2. 在附件区域上传已验证可独立运行的 `NailongPet.exe`。当前打包配置会将 Python、运行库和素材一起打包到单个 EXE 中；不需要附带虚拟环境、依赖清单或 `start.bat`。
3. 发布说明中写明：支持 Windows 10/11，下载后双击运行，无需安装 Python 或依赖；若附件为 ZIP，请先完整解压。
4. 发布后在未安装项目依赖的 Windows 环境验证启动、动画、拖动、声音和设置保存，并将 README 中“目前尚未在 GitHub 发布发行包”的说明替换为实际的发行页面链接。

GitHub 自动生成的 **Source code** 压缩包只包含源码，不是可直接运行的 EXE 发行包。引导普通用户下载单独上传的 EXE 附件。
