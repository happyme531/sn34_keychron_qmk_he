# 狼途 BOOM68 有线版

目标：`langtu/boom68/wired`，SN34F280，USB `0C45:80B5`。
依据原厂 BOOM68-USB V1.10 固件逆向适配。2026-11-03 已在实机刷入，验证 USB 枚举、68 个改键位置、67 个霍尔 ADC 读回、RGB 设置读写及升级时的完整设置保留。后续补足选组稳定时间、支持不同幅度轴的逐键校准，并接入旋钮双向改键；用户已确认校准和旋钮问题解决。验证记录见 [boom68-validation.json](../../../../docs/sn34/boom68-validation.json)。

```sh
qmk compile -kb langtu/boom68/wired -km default
uv run tests/sn34/run.py --keyboard langtu/boom68/wired
uv run util/sn34/export.py .build/langtu_boom68_wired_default.elf --keyboard langtu/boom68/wired
uv run util/sn34/package.py .build/langtu_boom68_wired_default.elf --keyboard langtu/boom68/wired
```

依赖配置见 [SN34 构建说明](../../../../docs/sn34/build.md)。编译直接使用本目录中的 C/JSON，无额外生成步骤。导出的 VIA/Launcher 布局含旋钮按压；它是普通数字按键，不提供磁轴行程设置。

上位机层名使用“主层、Fn、苹果主层、苹果 Fn”：Launcher 会按英文 Win/Mac 名称筛选系统层，中文标签可让四层同时可选。标签在 `board/configurator.json` 中定义；层数在 `keyboard.json` 的 `dynamic_keymap.layer_count` 中定义，具体键位在 `keymaps/default/keymap.c` 中定义，系统/Fn 层编号在 `config.h` 中定义。

## 刷写

已经运行本项目固件时，可在 Windows 使用以下命令，自动备份并验证设置保留：

```powershell
uv run util/sn34/flash.py .build/langtu_boom68_wired_default.elf --keyboard langtu/boom68/wired --flasher .build/standalone-flash/windows/sonixflasher.exe
```

首次从原厂 V1.10 切换有区别：原厂跳入 ISP 后保留 `0C45:80B5` 的接口 3，并不重新枚举为 `7210`。原厂设置也不能转换为 QMK 格式。下面是在本机验证过的首次安装步骤，仅连接一把匹配键盘：

```powershell
uv run util/sn34/flash.py .build/langtu_boom68_wired_default.elf --keyboard langtu/boom68/wired --reset-settings --prepare-only --output-dir .build/boom68-first
uv run --with hidapi python -c 'import hid; ds=[d for d in hid.enumerate(0x0c45,0x80b5) if d["usage_page"]==0xff67 and d["usage"]==0x61]; assert len(ds)==1; h=hid.device(); h.open_path(ds[0]["path"]); h.send_feature_report(bytes.fromhex("00aa55a55aff0033cc")+bytes(56)); h.close()'
& .build/standalone-flash/windows/sonixflasher.exe -v 0c45/80b5 --interface 3 -i
& .build/standalone-flash/windows/sonixflasher.exe -v 0c45/80b5 --interface 3 -o 0 -f .build/boom68-first/application.bin
uv run util/sn34/device.py --keyboard langtu/boom68/wired status
```

`-i` 应识别为 SN34F28X；刷写器也会在擦除前核对芯片。必须使用完整 `application.bin`（516096 字节，含 footer），不能直接刷较短的编译 BIN。保留官方 V1.10 恢复包；以上步骤不构成原厂设置备份。进入 QMK 后的后续升级已验证会重新枚举为 `0C45:7210`，可使用正常自动流程。刷写器版本要求见 [SN34 刷写说明](../../../../docs/sn34/flashing.md)。

## 扫描与接线

67 个霍尔按键共用 ADC0 的 15 路有效按键信号（P2.1～P2.15），通过五组低有效选通逐组扫描。固件能确认使能脚的操作，无法单凭它判断 PCB 上究竟切换传感器供电还是输出使能。

| 原厂组号 / 本实现 phase | 拉低的 GPIO |
| --- | --- |
| 1 / 0 | P0.13、P0.14 |
| 2 / 1 | P0.12 |
| 3 / 2 | P3.0 |
| 4 / 3 | P3.1 |
| 5 / 4 | P0.11 |

切换时先将 P0.11～P0.15、P3.0～P3.1 全部拉高，再选下一组，并等待 8 微秒后启动 ADC。P0.15 在正常扫描中保持高电平。ADC 引脚始终保持输入，不执行 Battle68 的输入放电，也不使用其 P1.12 采样门控。

原厂在选择下一组与启动 ADC 之间处理上一组的数据；快速扫描移植不能省略这段稳定时间。实机对比中，加入等待后，Esc / 减号 / Delete 的按压 ADC 变化量分别从约 506 / 356 / 482 提升到 973 / 938 / 842。时间由 `BOOM68_BANK_SETTLE_US` 定义；调整后应重新完整校准。

每组保留原厂 17 次转换顺序：
`10,11,9,8,15,14,7,6,5,4,3,2,1,0,13,12,16`。
其中 P2.0 没有按键映射，通道 16 为片内通道。原厂槽位 16～95 在本实现压缩为 0～79；五组完成后才发布一帧。逐键映射见 [keys.inc](board/keys.inc)，扫描操作见 [wiring.h](board/wiring.h)。

逻辑矩阵为 6×16，第 0 行只放 Fn，其余五行对应实体行；旋钮按压为 `(4,13)`。Fn 排在前面，确保同帧按下 Fn 与数字键时先切换层。逻辑坐标与原厂 layout ID 无关。

| 外设 | 接线 / 实现 |
| --- | --- |
| 旋钮 A、B | P3.8、P3.9，输入上拉，完整正交解码 |
| 旋钮按压 | P3.10，低有效，独立 5 ms 消抖，可在 VIA 改键 |
| RGB 数据 | P1.15 / SPI1 MO1，DMA1 channel 0，GRB |
| 外设使能候选 | P1.4，按原厂操作置高，具体控制负载待确认 |
| 按键 RGB | 灯链 0～66，沿用原厂逐键映射 |
| 灯箱 | 同一灯链 67～93，共 27 像素，原厂逻辑像素 i 对应 93−i |

灯箱随 QMK RGB Matrix 灯效和亮度一起工作。其二维坐标暂按键盘上方的一条横线布置，真实灯珠位置及左右方向尚需核对。未复刻原厂独立灯箱模式或音乐动画。P3.10 保持输入，不作为指示灯输出；不额外复用 P1.13 为 SPI 时钟。

## 默认操作

- 旋钮：音量；按压：静音。Fn＋旋钮：整体灯光亮度；Fn＋按压：灯光开关。旋转两方向使用标准 QMK/VIA 编码器映射，四层均可独立改键；Launcher JSON 的旋钮带 `ei: 0`。
- Fn＋1～0、减号、等号：F1～F12。Fn＋Esc：反引号；Fn＋Del：Print Screen。
- Fn＋Backspace：灯光开关；Fn＋Caps：下一灯效。
- Fn＋F/G：亮度减/加；Fn＋H/J：速度减/加；Fn＋左右：色相减/加；Fn＋上下：亮度加/减。
- Fn＋A/S：Windows/macOS 基础层；Fn＋Win：Win 锁。
- Fn＋P＋Z/X/C：切换 HE 配置 1/2/3。组合期间不发送 P 或静音/播放/停止事件。

旋钮暂按每圈正交循环 4 个跳变产生一个事件。原厂 `11→10` 对应音量加，实物顺逆时针及每格跳变数待测；需要时在 `board_config.h` 调整 `BOOM68_ENCODER_REVERSE` / `BOOM68_ENCODER_RESOLUTION`。

## 校准与验证范围

采用本机原厂轴体 1 的响应表（ROM `0x13abc`，330 个增量，名义 3.3 mm），归一化至现有 HE 核心的 0～240 行程单位。界面显示的毫米数沿用核心约定，不能据此认定实测精度或真实行程。默认松开/触底 ADC 值为原厂名义值 `2200/1500`，并非这块 PCB 的逐键实测值；首次实机使用前应完整校准。更换磁铁或轴体后，校准端点也不能自动匹配不同响应曲线。

手动校准的最低幅度独立设为 200 个 ADC 计数，区别于 700 的备用行程估计；触底端点按每个键自己的松开值验证，重启后保留。它允许混用不同幅度的轴，不以同一绝对触底电压筛掉小幅度轴。旋钮按压不参与磁轴校准。

EEPROM 使用本板独立 magic 和 v4 格式，旋钮映射采用 QMK 标准存储布局。首次提交前的试验格式已停用；当前 v4 设置可按正常流程备份、保留和验证。不导入 Battle68 或原厂设置。原厂升级器封装可选，模板必须匹配 `board/updater.json` 中的 SHA256，资源 ID 为 4000/4014。

离线测试覆盖五组选通与稳定等待、ADC 排序/帧发布、全部霍尔按键、混轴小幅度校准及重启恢复、旋钮双向改键、按压消抖、94 像素编码、设置保存，以及 Fn＋P＋Z/X/C 的 Windows/macOS 组合、同时按下、不同释放顺序和媒体事件隔离。尚未测量全键扫描率、完整模拟稳定曲线、灯箱实体排列及冷启动；不承诺原厂宣传的 128 kHz。

逆向来源：原厂 `BOOM68-USB_V1.10.bin`，SHA256
`4d44b59daeef15271826043715ff5126324c4d84bf19c6407de0511398a86f25`。
官方升级器：[BOOM68-USB_V1.10.exe](https://cp.driveall.cn/device_firmware/langtu/20260827/BOOM68-USB_V1.10.exe)。
