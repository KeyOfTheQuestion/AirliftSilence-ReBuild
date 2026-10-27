# Agent 操作流程（macOS）

## 适用范围与前置条件

本工作流来自一次真实验证：iPhone 14 Pro（iPhone15,2），iOS 18.7.2（22H124），Apple Silicon Mac / macOS 15.0.1。用户于 2026-10-26 实际通话确认开始/结束语音消失。没有验证重启后的持久性，也没有验证本封装在其他机型或构建号上的表现。

代码只接受上述设备组合。Windows 原 GUI 的上游验证范围是另一份证据；不能据此扩大本工作流的兼容声明。其他版本应先开展兼容性调查，而不是删除检查后直接写手机。

需要 Python 3.12、macOS 自带的 `AirTrafficHost.framework`、`afinfo`、`afconvert`，以及 USB 连接、已解锁并信任此电脑的 iPhone。无需给手机安装 App、签名 IPA 或配置 VPN。若同步提示缺少 Books 客户端，可检查 Apple Books 是否已安装并打开过；不能将所有同步错误都归因于它。

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

如系统没有 Python 3.12，可使用已安装的 `uv`：`uv venv --python 3.12 .venv`，再安装依赖。不要为了修复提示音关闭系统安全设置或更新。

## 各命令实际做什么

| 命令 | 手机操作 | 本地结果 |
|---|---|---|
| `doctor` | 建立已信任连接，检查型号/构建号、Media 残留、Apple 框架；不修改提示音 | 可能创建配对缓存 |
| `canary` | 临时写入并移回随机测试文件；不以提示音为目标 | 记录设备身份、可用性及 Books 快照 |
| `backup` | **移出原提示音、读取、写回原位** | 持久保存原件和哈希，不覆盖已有原件 |
| `generate` | 无 | 按本机原件生成并解码验证静音件 |
| `check-files` | 无 | 校验两份原件与静音件的完整性 |
| `silence` | 替换两份提示音，读回并写回验证 | 保存回收副本、快照和校验输出 |
| `verify` | **移出提示音、读回、写回原位** | 与本机静音件比较；并非只读检测 |
| `restore` | 用本机原件替换并读回验证 | 保留最初原件和回收副本 |
| `import-legacy` | 无 | 导入旧工作流的原件/静音件和哈希，不复制配对记录 |

`read` 不是无风险读取：AirTraffic 逃逸通过移动文件工作。手机在任何设备文件操作期间都应保持连接；不得把备份或验证描述为不触碰设备。

## 首次使用（手机当前仍有原始提示音）

```sh
.venv/bin/python -u tools/call_silence.py doctor
.venv/bin/python -u tools/call_silence.py canary
.venv/bin/python -u tools/call_silence.py backup
.venv/bin/python -u tools/call_silence.py generate
.venv/bin/python -u tools/call_silence.py check-files
.venv/bin/python -u tools/call_silence.py silence
```

每步成功后再继续。原件已经被其他工具替换时，不要重新初始化备份：应先找到当时保存的原件。静音生成器会拒绝看起来已经静音的备份，避免把它当作原音，但此检查不能证明任何非零音频一定是正确原件。

默认状态目录是仓库内 `.airlift-local/`，绑定 UDID、机型、iOS 版本和构建号。首次接了多台设备时，用 `--device <目标设备UDID>` 明确选择；后续自动选择已绑定的设备。多设备须分别使用 `--state-dir <各自目录>`，所有后续命令都带同一个参数。

## 重启后或过一段时间提示音恢复

先接上同一部手机并解锁，然后双击根目录 `再次取消录音提示音.command`。它会先检查本机文件、连接条件和残留，再替换并校验；日志保存在 `.airlift-local/logs/`。只想检查本机文件时：

```sh
bash 再次取消录音提示音.command --check-files
```

Agent 也可直接执行 `check-files` → `doctor` → `silence`。不重新运行首次备份，不覆盖原件。成功标准是两个文件都输出 `verified`，且进程退出码为 0；之后请用户实际通话试录。不要主动替用户拨电话或重启。

## 迁移此前本机版备份

此前 `local_audio.py` 工作流把 `original/`、`silent/` 和 `manifest.json` 存在 `local-device/`。保留旧工程，核实 UDID 来自当时的本机设备记录，再离线导入一个空状态目录：

```sh
.venv/bin/python tools/call_silence.py import-legacy \
  --source /你的旧工程/local-device \
  --device 该备份对应手机的UDID
.venv/bin/python tools/call_silence.py check-files
```

导入会校验全部文件后复制，拒绝覆盖已有状态；后续连接仍要核对设备身份与系统构建号。UDID 参数是使用者对备份归属的确认，工具无法离线证明它属于哪部手机。不要把 UDID 或命令中的真实值贴到公开 issue。配对缓存、设备日志和 Books 快照不迁移、不上传。

## 恢复与失败处理

正常恢复：连接原手机，运行 `restore` 或双击 `恢复录音提示音.command`。恢复只依赖本机原件；不要用仓库根目录 `silent/` 中的上游示例替换自己的备份，也不要从他人设备拿原件。

任一失败先停止连续重试，保留整个 `.airlift-local/`。`recovery/airlift-recovered-*` 和 `airlift-replaced-*` 文件在设备临时副本被清理前已写入本机；`books-*.json` 保存每次操作前的同步索引字节。失败时 Media 中也可能留有唯一原件，**不要删除残留来让检查通过**。

调查时：核对失败阶段、记录哪个目标文件被移动、检查本机 `recovery/` 和设备 Media 副本、校验其字节与已知原件。若需读取 Media，可参考上游 AFC 工具；先复制到本机，不上传整份设备目录。只有明确目标状态及恢复路径后再执行针对性恢复。此仓库没有自动救援命令，也没有保证所有中断都可自动恢复。

原件/静音件缺失或哈希不符时，先从自己的已知备份恢复本地文件。设备或系统构建号不符时，保留旧配置并重新评估兼容性，不修改 manifest 伪装原设备。系统语言或音频资源更新也可能使原件过时，需要进一步确认；“同一构建号”不是所有音频资源不变的证明。

## 私有数据与范围

`.airlift-local/` 已被 Git 忽略，包括原件、设备身份、配对缓存、Books 快照和日志。提交前仍需检查暂存文件；自定义 `--state-dir` 在其他目录时，必须自行保持私有。

本工具只处理两份开始/结束语音。周期性提醒可能仍然存在，系统可能重新生成提示音；不保证永久关闭。录音提示原本会告知通话双方，使用者应取得所需同意。
