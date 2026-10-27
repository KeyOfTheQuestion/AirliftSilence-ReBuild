[English](README.md) · **简体中文**

# AirliftSilence-ReBuild

静音 iPhone 系统通话录音开始/结束提示音：保留上游 Windows GUI，新增可复用的 **macOS Agent 技能与操作流程**。

本 fork 整理了 2026-10-26 的真实操作：iPhone 14 Pro / iOS 18.7.2，用户实际通话确认提示音已经消失。新增设备绑定、原件落盘保护、按设备生成静音、读回校验，以及提示音恢复后的再次应用入口。**尚未验证重启后的持久性**；本次仓库整理未重新操作手机。详见[验证记录](docs/VALIDATION.md)。

## 给 Agent 使用

让 Agent 克隆仓库，读取 [AGENTS.md](AGENTS.md) 和 [iphone-call-silence 技能](skills/iphone-call-silence/SKILL.md)，例如：

> 使用这个仓库里的 iphone-call-silence 技能检查我的 iPhone；符合已验证环境时，先备份，再取消通话录音提示音。

安装到 Codex 的技能目录，并与仓库保持链接：

```sh
python3 tools/install_skill.py
```

安装器不会覆盖已有同名技能。其他 Agent 可通过 `--target /你的Agent/skills/iphone-call-silence` 指定位置。如果安装工具只复制技能目录，仍需保留完整仓库，并向 Agent 提供仓库路径或设置 `AIRLIFT_REPO`。

## macOS 快速开始

封装工作流目前只接受实测组合 **iPhone15,2 / iOS 18.7.2 / 22H124**。这是本工作流的验证边界，不代表上游漏洞的完整兼容范围。

需要 Python 3.12、macOS 自带 Apple 框架与音频工具，以及 USB 连接、已解锁且信任此电脑的 iPhone。无需在手机安装 App、签名或配置 VPN。

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python tools/call_silence.py doctor
```

手机当前仍有原始提示音时，逐步执行；上一步成功后再继续：

```sh
.venv/bin/python -u tools/call_silence.py canary
.venv/bin/python -u tools/call_silence.py backup
.venv/bin/python -u tools/call_silence.py generate
.venv/bin/python -u tools/call_silence.py silence
```

**`backup` 和 `verify` 会把文件移出后写回，并非只读操作。** `doctor` 不修改提示音；`generate` 与 `check-files` 只处理本机文件。设备操作完成前保持手机连接。

已经使用旧版 `local_audio.py` 静音过的手机，请迁移原先保存的原件，不要把当前静音文件重新当作原件备份。详见[完整流程与迁移说明](docs/AGENT-WORKFLOW.zh-CN.md)。

### 重启后提示音又出现

保留本机状态目录，连接并解锁同一部手机，然后双击 `再次取消录音提示音.command`，或执行：

```sh
.venv/bin/python tools/call_silence.py check-files
.venv/bin/python tools/call_silence.py doctor
.venv/bin/python -u tools/call_silence.py silence
```

两个文件均输出 `verified` 且进程成功退出，才表示文件校验通过；之后仍需实际通话试录确认。恢复原提示音使用 `restore` 或双击 `恢复录音提示音.command`。

默认私有状态目录 `.airlift-local/` 包含原件、哈希、设备身份、配对缓存和回收快照，已加入 Git 忽略。**保留并私下备份，不能上传。** 更换手机或系统构建号不符时会停止；多设备须分别使用自己的 `--state-dir`。

## 原版 Windows GUI

Windows 安装 64 位 iTunes / Apple Mobile Device Support 后，仍可运行原 GUI：

```sh
python -m pip install -r requirements.txt
python airlift_gui.py
```

本 fork 未重新验证 Windows。上游作者报告在 iOS 27.0.1（24A446）上测试通过；上游 exe 请到[原项目 Releases](https://github.com/YiHoooong/AirliftSilence/releases) 获取，它不是此 fork 新构建的二进制。

根目录 `silent/` 是上游示例资源。Agent 工作流不使用这些示例，而是从本机原件生成静音件。低层 `airlift.py` CLI 用于研究，不具备封装流程的设备绑定与本地备份完整性检查。

## 范围与失败处理

封装只操作两份提示音：

- `/var/mobile/Library/CallServices/Greetings/default/StartDisclosureWithTone.m4a`
- `/var/mobile/Library/CallServices/Greetings/default/StopDisclosure.caf`

长录音的周期提醒声可能保留。系统可能重新生成提示音，因此不承诺永久关闭。任一步报错，停止连续重试，保留本机回收副本和设备 Media 残留，按[失败处理说明](docs/AGENT-WORKFLOW.zh-CN.md#恢复与失败处理)调查。工具基于真实的沙盒逃逸，操作中断可能导致文件移位或不完整。

这些语音原本会告知通话双方正在录音，使用者应取得所需同意。工具不会代拨电话，也不会永久改变系统录音规则。

## 开发验证

```sh
python3.12 -m unittest discover -s tests -v
```

离线保护测试和 macOS AAC/Opus 合成音频测试均不连接手机。CI 在 Linux、macOS 上运行；无法使用 Core Audio 时跳过音频编码测试。

## 致谢

- [airlift](https://github.com/0xjohnnydev/airlift)，Johnny Franks：AirTraffic / ATAirlock 研究与原始 macOS PoC。
- [airlift-windows](https://github.com/DahanGuy/airlift-windows)，Guy Dahan：Windows ctypes 移植。
- [AirliftSilence](https://github.com/YiHoooong/AirliftSilence)，YiHoooong：提示音替换 GUI 与 Grappa 会话修复。
- [ios-calltone-silence](https://github.com/jiutinglifeng/ios-calltone-silence)，jiutinglifeng：macOS 框架加载和设备探测修复；纳入的提交为 `67582b82ec6d16d596085bc1cd142ec59350ea10`。
- [AirCard-iOS](https://github.com/Mak5er/AirCard-iOS)：Grappa 令牌与协议工作。
- [bl_sbx](https://github.com/h2zi/bl_sbx)：提示音替换先行工作。

MIT，见 [LICENSE](LICENSE)。
