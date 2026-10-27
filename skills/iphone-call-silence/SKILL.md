---
name: iphone-call-silence
description: 使用 AirliftSilence-ReBuild 在 macOS 上备份、静音、重新应用或恢复 iPhone 系统通话录音开始和结束提示音。适用于提示音重启后恢复、要求使用 AirliftSilence 或沿用已验证方法；不用于语音备忘录或录音降噪。
---

# iPhone 通话录音提示音

先定位本仓库，阅读根目录 `AGENTS.md` 与 `docs/AGENT-WORKFLOW.zh-CN.md`。技能本身不包含手机备份或配对记录。

## 定位与安装

本技能在仓库内的路径为 `skills/iphone-call-silence`。推荐将此目录符号链接到 Agent 的技能目录，保持仓库和脚本一起更新。复制安装后，也需保留完整仓库：从当前工作目录向上查找 `tools/call_silence.py`，或使用用户提供的仓库路径 / `AIRLIFT_REPO`。不要硬编码作者的电脑路径。

若只有复制安装的技能而没有工程，源码仓库是 `https://github.com/KeyOfTheQuestion/AirliftSilence-ReBuild`。在任务工作目录克隆它，保留已有同名目录，再按根目录文档准备环境；不要把工程克隆进设备备份目录。

初次使用时创建 Python 3.12 虚拟环境并安装根目录 `requirements.txt`。使用仓库的 `.venv/bin/python` 运行以下命令；在正常工作环境已准备好的情况下无需重新安装依赖。

## 任务入口

所有命令均在仓库根目录运行：

```sh
.venv/bin/python tools/call_silence.py doctor
```

- 首次操作：依次执行 `canary` → `backup` → `generate` → `silence`。
- 提示音再次出现：先 `check-files`，再 `doctor` → `silence`；保留原始备份。
- 恢复提示音：`doctor` → `restore`。
- 检查当前静音文件：`verify`，但**这会临时移出文件并写回，不是只读检测**。

`doctor` 只检查连接和环境，不修改音频；`check-files` 和 `generate` 只处理本地文件。`canary` 会在设备临时目录写入一个随机测试文件；`backup`、`silence`、`verify`、`restore` 都会改变设备文件位置或内容，须处于用户要求执行的范围内。仅研究可行性或完善仓库时，不运行这些设备写入命令。

## 必须保留的边界

- Agent 工作流当前只接受实测组合 iPhone 14 Pro（iPhone15,2）/ iOS 18.7.2（22H124）。其他组合先调查，不能删除校验或把上游兼容范围当作本仓库实测结果。
- 每个 `.airlift-local` 目录绑定一部手机的 UDID、机型、系统版本和构建号。不要复用其他设备原件，不上传此目录；多个设备使用各自的 `--state-dir`。
- 原件不覆盖，静音件从本机原件生成。使用封装 CLI，不能改用低层 `airlift.py replace` 绕过落盘和完整性保护。
- 任一阶段失败、哈希不符、设备不符或发现 airlift 残留，立即停止连续重试，保留本地 `recovery/` 和设备 Media 中的副本，按工作流文档调查。
- 两个文件均输出 `verified`、命令成功退出，才能报告文件校验成功；仍需用户实际通话确认听感。未实测重启就不要声称重启有效。

不要代拨电话、主动重启、关闭系统更新或创建自动监控。长时间录音的周期性提醒不在两文件处理范围内；系统可能重新生成提示音，不能承诺永久关闭。

已知证据：2026-10-26 在上述组合完成文件校验，用户实际通话确认提示音消失；此次仓库整理的回归测试不连接手机。详见 `docs/VALIDATION.md`。
