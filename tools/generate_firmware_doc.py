"""Generate firmware implementation notes separately from board connectivity."""
from collections import Counter
import json
import re
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def main():
    mapping=json.loads((ROOT/"analysis/board_map_v118.json").read_text(encoding="utf-8"))["keys"]
    profile=json.loads((ROOT/"analysis/hall_board_profile.json").read_text())["keys"]
    manifest=json.loads((ROOT/"build/native_app/manifest.json").read_text())
    names=Counter(k["name"] for k in mapping)
    assert len(mapping)==67 and len({k["raw_slot"] for k in mapping})==67
    grid=[["--"]*16 for _ in range(6)]
    channel_for={};phase_for={}
    clusters=((10,11,12,13),(1,2,3,4),(5,6,7,14))
    phase_lines=[]
    for phase in range(8):
        entries=[]
        for cluster,channels in enumerate(clusters):
            for lane in range(4):
                upper=phase>>2
                slot=cluster*32+upper*16+(lane>>1)*8+(phase&3)*2+(lane&1)
                channel=channels[lane^upper]
                assert slot not in channel_for
                channel_for[slot]=channel;phase_for[slot]=phase
                entries.append(f"{slot:02d}:CH{channel:02d}")
        phase_lines.append(f"  phase {phase}  P0.1/P0.0/P2.9={phase:03b}  "+"  ".join(entries))
    assert set(channel_for)==set(range(96))
    key_lines=[]
    for key in sorted(mapping,key=lambda k:k["raw_slot"]):
        slot=key["raw_slot"];row,col=divmod(slot,16)
        assert slot==(key["electrical"]&7)*16+(key["electrical"]>>3)
        label=key["name"]+(f"@{key['layout_index']}" if names[key["name"]]>1 else "")
        grid[row][col]=label
        channel=channel_for[slot]
        key_lines.append(f"  {label:<13} {key['layout_index']:>3}  {key['electrical']:>3}  {slot:>3}  {row},{col:<2}  {phase_for[slot]}  CH{channel:<2} P2.{channel:<2}  {key['hid_usage']}")
    matrix="  col "+" ".join(f"{i:>9}" for i in range(16))+"\n"
    matrix+="\n".join(f"  row{r}"+" ".join(f"{name:>9}" for name in row) for r,row in enumerate(grid))
    text=f"""BAT68 硬件与固件接口说明
更新日期：2026-10-30

本说明针对本机 HFD8KCG200 主控、原厂 v1.18 布局的 BAT68。
当前完整独立固件已通过实际断电启动、打字/Fn、持久改键和官方 OTA 测试。
应用区已经完整替换；保留的是原厂 8 KiB Bootloader。
三个单色指示灯与 WS2812 仍未适配，不能把 GPIO/AFIO 已初始化理解为灯已可用。

证据分级：
  [实测] 已在这块键盘上运行、读回或由用户实际按键确认。
  [固件] 从原厂 v1.18/已备份 Boot 的指令、寄存器及官方 AFIO 定义确认。
  [待确认] 尚未做板上通断测量、逐灯点亮或示波器确认。
管脚编号 Pn.m 指 MCU 端口，不是封装脚号，也不是焊盘在 PCB 上的排列顺序。

1. 主控与外设

主控丝印：HFD8KCG200。[用户观察]
软件目标：SONiX SN34F280 系列 Cortex-M4F 寄存器体系；官方 SDK v2.1.4 已能
实际驱动 Flash、RCC、GPIO、ADC、USB 和看门狗。[实测]
这不等于已根据丝印确认了具体 SN34F28x 尾号。
板上另有 6 颗 HFD24MH001；内部电路、单颗通道数与六颗芯片到 ADC 引脚的
逐根对应未取得原理图/通断证据，扫描实现不依赖这些内部假设。[待确认]
SWD 焊盘完整，另有未焊的串口座。CH347T 手按接触的 SWD 尝试未取得稳定读数。

时钟配置：EHS 按 12 MHz，PLL NS=64、FS=/4，目标 HCLK=192 MHz；
AHB=/1，APB0/APB1 各 /2。独立程序的 HCLK 报告与 DWT 实际计时已验证。[实测]
SysTick 不作为系统时基；HAL_GetTick 使用 DWT 周期计数器，并处理计数回绕。
主循环喂独立看门狗，装载值 640000，目标约 20 秒。

2. IO 分配

  IO/信号             用途                               证据/适配状态
  P2.9                扫描相位 bit0                      [实测] 已适配
  P0.0                扫描相位 bit1                      [实测] 已适配
  P0.1                扫描相位 bit2                      [实测] 已适配
  P1.12               磁轴前端采样门控                   [实测] 已适配
  P2.1..P2.7          ADC0 CH1..CH7                      [实测] 已适配
  P2.10..P2.14        ADC0 CH10..CH14                    [实测] 已适配
  P3.12/P3.13         XIN/XOUT 晶振复用                  [固件/SDK] 已适配
  USB_DP/USB_DM       USB HS PHY 专用信号                [实测] 已适配；封装脚号未核对
  P3.5                SWDIO，SDK 复用功能 0              [SDK] 板上焊盘到引脚未逐根测量
  P3.6                SWCLK，SDK 复用功能 0              [SDK] 板上焊盘到引脚未逐根测量
  P1.3                原 Boot 强制 ISP 检测输入          [固件] 拉低路径未在 PCB 上实测
  P1.6                CapsLock 单色指示灯控制            [固件] 未适配
  P1.10               Win Lock 单色指示灯控制            [固件] 未适配
  P1.11               Mac 模式单色指示灯控制             [固件] 未适配
  P1.15 / SPI1_MO1    WS2812 数据脚候选                  [固件/SDK] 未适配、待走线/波形确认
  P1.13 / SPI1_SCK1   原 RGB 发送路径同时配置的 SPI 时钟 [固件/SDK] 未适配
  P1.4                原 RGB 初始化后置高的控制脚        [固件] 疑似灯链使能/供电，待确认
  未焊串口座          ROM UART 下载或调试的候选连接      [待确认] TX/RX 端口与电平未追踪

ADC 引脚的 AFIO 功能值为 12。P2.0、P2.8、P2.9 等可有 ADC 复用能力，
但本板当前扫描不把它们当作模拟采样输入；尤其 P2.9 已用于相位选择。
P1.12 高/低电平的确切电路名称尚未知；代码只复现已验证的门控时序，
不要把它未经测量地当作可随意关闭的整板电源使能。

三个指示灯的物理左右顺序、颜色和丝印对应尚未逐灯确认。
原厂 FUN_0000d0e4 在 CapsLock/HID bit1 为 1 时写 P1.6 BSET，反之 BCLR；
P1.10 跟随原厂 Win Lock 状态，P1.11 跟随会交换 Win/Alt 等键码的 Mac 模式状态。
当前 USB 已收取主机的键盘 LED 报告到 native_keyboard_leds，但未写入这三个 GPIO。

WS2812 线索：原厂 FUN_0000f528 配置 SPI1，P1_AFIO2=0x10040，
即 P1.13=SCK1、P1.15=MO1。FUN_00001040 配置 DMA，目标为 SPI1 数据寄存器
0x4002B018。单线 WS2812 DIN 最有力的候选是 P1.15，但还没有板上连通性/波形实测。
原厂 RGB 缓冲区按 90 个位置组织；90 是固件容量，不是已确认的实物灯珠数。
颜色字节顺序、灯链物理顺序、实际灯数、脉冲编码与亮度上限仍待验证。

3. GPIO 与相关寄存器

  GPIO0  0x40037000    GPIO1 0x40038000
  GPIO2  0x40039000    GPIO3 0x4003A000
  SCU    0x4001F000    ALWAYSON/AFIO 0x4001B000
  ADC0   0x40027000    USB HS 0x40057000
  SPI1   0x4002B000    DMA 0x40054000
  Flash FIFO 0x00600000，Flash 控制寄存器 0x00601000

GPIO 通用偏移：DATAOUT=0x00、DATAIN=0x04、DIR=0x08、
BSET=0x10、BCLR=0x14、PULLEN=0x18、PUTYPE=0x1C。
扫描代码通过 BSET/BCLR 改相位，不应对 DATAOUT 做会覆盖其他管脚的整口赋值。

初始 GPIO 配置来自原厂运行快照，并已用于独立程序冷启动：
             DATAOUT     DIR        PULLEN     PUTYPE
  GPIO0      0x000002    0x004003   0x1FFFFB   0x1FFFFF
  GPIO1      0x000010    0x00DED0   0x1FFFDF   0x1FFFFF
  GPIO2      0x000200    0x1F8301   0x1F8301   0x1FFFFF
  GPIO3      0x000100    0x000100   0x1FFDFF   0x1FFFFF
这些是初始化值；扫描会持续改变 mux、门控、GPIO2 的 DIR 和对应 AFIO。
GPIO 时钟需由 SDK RCC 显式打开。晶振 P3.12/P3.13 的 AFIO 由 RCC 驱动管理。

4. 磁轴扫描方式与时序

这是模拟量 mux 扫描，不是普通开关键盘的行列拉高/读取矩阵。
相位 0..7 通过 P2.9/P0.0/P0.1 选择；每相位收集 12 路有效 ADC 值，
8 相位形成 96 个 raw 槽位。目前已建立 67 个按键映射，包含 Fn。

ADC0：单次序列扫描，15 次转换；pre_clock=5，power_en_time=32，hold_time=2；
参考为 VDD/GND，XTEST=8，并执行官方 HAL 的 ADC 偏移校准。
转换序列：11,10,13,12,2,1,4,3,6,5,14,7,13,12,11。
末尾重复 13/12/11，当前保留该序列；重复转换的电路目的没有独立定量验证。

每次 ADC0_IRQHandler：
  1. 检查整段序列完成 RIS，清相应状态。
  2. 暂时清 GPIO2 模拟 AFIO；将掩码 0x7CFE 对应输入改为 GPIO 输出并拉低。
  3. P1.12 置高，恢复 GPIO2 模拟 AFIO。
  4. 读取 ADC 通道数据，按当前相位写入 96 槽 raw 数组。
  5. 解除 GPIO2 对 0x7CFE 管脚的输出驱动。
  6. phase=(phase+1)&7；回到 0 时增加完整帧计数。
  7. 更新三个 mux 引脚，P1.12 拉低，启动下一次序列转换。

恢复用 AFIO 常量：P2_AFIO0=0x18C63180、P2_AFIO1=0x18C0018C、P2_AFIO2=0x318C。
关键中断配置：整段扫描完成 IE=1；通道 EOCIE=0。
HAL_ADC_Start_IT 默认也打开逐通道 EOC；本驱动随后明确屏蔽它。
否则会反复进入只清整段状态的 ISR，主循环近乎停滞；该问题已在实机重现并修正。

NVIC IRQ18 是 ADC0，对应 Cortex 向量索引 34；USB 为 IRQ77/向量93，
SCU 为 IRQ3/向量19。不要把 Ghidra 的 Vector_34 当成 NVIC IRQ34。
USB 优先级为 1，ADC 为 2。已测约 5.9 k 个完整矩阵帧/秒，
这不是 USB 回报率或端到端延迟的测量结果。

5. 八相位 ADC 到 raw 槽的完整对应

每项为 raw_slot:ADC_channel。相位位序明确为 P0.1、P0.0、P2.9：
{chr(10).join(phase_lines)}

对应的通用算法见 firmware/board/bat68_scan.c：
  upper = phase >> 2，pair = (phase & 3) * 2
  三组 ADC 通道分别为 [10,11,12,13]、[1,2,3,4]、[5,6,7,14]
  base = cluster * 32 + upper * 16
  raw[base + (lane >> 1)*8 + pair + (lane & 1)] = adc[channels[lane XOR upper]]
后四相位的相邻通道交换是映射的一部分，不可简单按通道号顺排。
64 组随机输入下，独立 ISR 的 raw 写入与 GPIO mux 输出均已对照原厂 Thumb 代码通过。

6. QMK 逻辑矩阵与按键表

原厂 electrical 编号 e 的换算：
  row=e&7，col=e>>3，raw_slot=row*16+col；只接受 row<6、col<16。
逆换算：e=col*8+row。
这里的 row/col 是逻辑地址，不是键盘上的物理行列。
QMK 配置是 6x16。raw row0 当前没有映射按键；其余位置也有空槽。
-- 表示没有已识别按键。重复键名后面的 @数字是 layout_index，可用于命令行改键。

{matrix}

完整表：最后两列是采样 ADC 对应端口与普通层 HID Usage。
  键名          layout  e   raw  r,c  phase ADC   port   HID
{chr(10).join(key_lines)}

Fn 的 raw_slot=90、e=85，映射为 MO(1)；当前正常矩阵包含 66 个普通/修饰键及 Fn。
Fn 表中的 0xAF 来自原厂布局元数据；独立固件不会发送它，而是处理 QMK 的 MO(1)。
实测例：W=raw34/e18、A=raw49/e11、S=raw50/e19、D=raw51/e27。
原始布局源：analysis/board_map_v118.json；完整静止/压底初值见 analysis/hall_board_profile.json。

7. 原始值、行程与键位配置

本板空闲 raw 大多约 2200..2360，按压使 raw 减小。每键使用独立静止参考；
当前压底参考初值都是 1600，并非已经逐键按到底实测出的标定值。
travel = clamp((idle - raw) * 330 / (idle - bottom), 0, 330)。
触发阈值 100，按下后释放阈值 80，带固定滞回。这些单位不是毫米。
当前没有 RT、动态触发阈值、压底自动校准或模拟手柄。
QMK 使用两层和 8 字节 6KRO 报告；Fn 优先处理按下、最后处理松开。

8. Flash、SRAM 与地址别名

按本机兼容的 DFP：Flash 512 KiB，SRAM 160 KiB；栈顶 0x20028000 已实际运行。
Flash 物理访问窗口与 User 运行时别名必须分开：

  内容              物理地址                      User 映射时的别名
  Boot 8 KiB        0x00200000..0x00201FFF        不占 User 别名；可从物理窗口读取
  User 504 KiB      0x00202000..0x0027FFFF        0x00000000..0x0007DFFF
  改键页 A          0x0027F000..0x0027F1FF        0x0007D000..0x0007D1FF
  改键页 B          0x0027F200..0x0027F3FF        0x0007D200..0x0007D3FF
  有效标记保留页    0x0027FE00..0x0027FFFF        0x0007DE00..0x0007DFFF
  有效标记字        0x0027FFFC..0x0027FFFF        0x0007DFFC..0x0007DFFF

User 映射时 Flash 页号需加 Boot 对应的 16 页；SDK HAL 的 MapAddress=0x2000 处理此偏移。
硬件页大小 512 字节。本项目传给 HAL_FLASH_Program_Page 的是 User 字节偏移；
HAL_FLASHEx_Erase 的 Page 为 User 偏移/512，HAL 再加上 Boot 占用的 16 页。
不要把 0x002xxxxx 物理访问窗口地址直接传作 HAL 的 User 偏移。
板级封装拒绝 Boot 映射，不对 Boot 区提供写入入口；只有两个改键页与最终标记页可被修改。
本板最后页擦除后实际读到 0，而非 0xFF；升级入口验证“有效签名已消失”，不假设擦除极性。

SRAM：0x20000000..0x20027FFF。
独立应用 .data/.bss：{manifest['ram_start']}..0x{int(manifest['ram_end'],0)-1:08X}；栈从 0x20028000 向下增长。
0x20011000..0x2001103F 为 16 个诊断 mailbox 字，不在 .bss 清零范围之内；
硬件软件复位可保留 SRAM，但当前 native_reset 会重新清写 mailbox；
早期桥接程序在试运行返回时才保留上一轮值。它不是当前程序的跨启动日志或非易失存储。
正式向量表位于 User 地址 0，SP=0x20028000，Reset 向量=0x000001C1（Thumb 位已置位）。
早期试运行曾链接于 0x30000，那不是当前正式程序的启动地址。

改键保存：两个独立 512 字节记录页交替写；记录含序号、两层键码、CRC32 与提交标记。
CRC 覆盖前 400 字节，CRC 位于偏移 400，提交值 0xC0DEB68A 位于偏移 404。
新记录写入非当前页并读回验证；相同键位再次保存不擦写。完整 OTA 则重写整个 User 区。

9. Bootloader 行为与实际升级流程

USB Boot 位于可独立读回的原厂 Flash 8 KiB，不是 MCU ROM 自带的 UART 下载器。
冷启动 Boot 检查应用末尾的 32 位有效值 0xAAAA5555（文件字节 55 55 AA AA）。
在 Boot 映射中，该字位于 0x0007FFFC；在 User 映射中为 0x0007DFFC。
原 Boot 还会检查 P1.3；程序显示拉低可进入 ISP，但未核对板上哪个焊盘接此脚，
也尚未做该短接入口的物理实测。不要把它当成已经验证的恢复手段。

正常应用 USB：VID/PID=0C45:8037；当前产品名 BAT68 QMK，bcdDevice=0x0118。
原 Boot USB：VID/PID=0C45:7210。[实测]
原厂 OTA 请求在 HID IF3 的 Feature Report 里携带前 8 字节：
  AA 55 A5 5A FF 00 33 CC
Windows hidapi 传输时另带 report ID 0；它不属于上述 8 字节内容。

当前应用的升级路径：
  原厂 OTA 发 Feature -> USB ISR 只置请求标志 -> 主循环等待控制传输完成
  -> 调用官方 Flash HAL 擦除 User 最末的保留页，使有效标记失效
  -> 设置 SCU PWRMODE.REMAP=Boot 并发出 REBOOT
  -> 原 Boot 在完整复位后初始化自身 RAM/时钟/USB，枚举 0C45:7210
  -> 原厂 OTA 写入完整 User 镜像、校验、恢复有效标记
  -> 重启为 BAT68 QMK。

整个过程不会改写原 Boot。Boot 缺少有效标记时保持 ISP；升级中断后可重新运行原厂工具。
本机允许修改后的应用通过更新半字累加的 16 位固件校验值进行 OTA；
有效标记、固件加和校验、Windows EXE 的 PE 校验是三件不同的事。

厂商 ISP 帮助库存在跳转地址 0x00200301；此直接跳转方式在本机两次试验均未得到
可用的 Boot USB。具体原因未确证，因此正式固件不用它，不链接厂商二进制 ISP 库。
采用上述完整复位流程后，Boot 枚举约需几百毫秒；原厂工具首次 Start 可能过早报失败。
tools/oem_native_ota.ps1 在“Update fail + 进度0 + Boot已枚举”时，
会在同一个原厂窗口中自动再点 Start 一次。该流程已完成 100% 刷写并返回独立程序。
手动双击升级 EXE 时，遇此状态应待 Boot 出现后再次点 Start。

10. USB 接口与诊断

  IF0  Boot Keyboard        IN 0x81，8 字节；锁定灯报告通过控制传输接收
  IF1  Consumer             IN 0x82，2 字节；当前未接入媒体键发送逻辑
  IF2  Vendor 0xFF68/0x61   IN 0x83、OUT 0x03，64 字节诊断
  IF3  Vendor 0xFF67        Feature 64 字节，兼容原厂进入升级请求

IF3 描述符还保留 4096 字节 Output 定义，但当前应用不在此实现烧录；真正固件写入由 Boot 执行。
诊断请求头：AA cmd count offset_lo offset_hi 42 36 38；数据从字节 8 开始。
应答头以 55 开始；count=FF 表示范围、签名、按键状态或 Flash 验证失败。
0x73 的 User ROM 偏移例外，放在字节 8..11，为 32 位小端。

  70 身份    71 原始 ADC    72 只读 Boot    73 只读 User ROM
  74 QMK状态 75 RAM改键     76 读键码      77 归一化行程
  79 保存（SAVE）           7A 软件复位（REBT）
  7D 独立程序/时钟/计数诊断 7E 原始ADC诊断
正式版本 protocol=6。早期桥接专用的快照/试运行入口不属于当前正常接口。
7B 的 CMT! 仅在首次移植的 --bringup-guard 构建中启用；正式版本未启用该保护。

11. 当前构建、源码与验证记录

当前正式构建代码大小：{manifest['bytes']} 字节。
构建 User SHA256：{manifest['application_sha256']}
代码 SHA256：{manifest['image_sha256']}
Boot SHA256：b6006ef843ef5dd4e285c9e06dc04f717326b620ce08a6dfe2b17decbd310d0e
保存改键后，两个配置页会变化；这不表示应用代码或 Boot 被改变。

实现：
  firmware/native/startup.S、main.c、clock.c、timebase.c  启动、时钟、主循环
  firmware/native/scan.c、firmware/board/bat68_scan.c    ADC、mux、槽位转换
  firmware/native/keyboard.c                          QMK 与归一化行程
  firmware/native/usb.c                               USB 描述符与 HID 粘合
  firmware/board/sn34_flash.c                         官方 Flash HAL 的地址范围封装
  firmware/board/keymap_settings.c                    双页键位配置记录

直接证据：
  analysis/board_map_v118.json、hall_board_profile.json
  build/native_app/scan_test_results.json               64 组 ISR/引脚等价性
  build/native_app/boot_test_results.json               真实 Boot 指令的有效标记分支
  analysis/native_app_v17_hardware.json                 两次完整 504 KiB 回读与构建逐字节一致
  analysis/native_standalone_persistence_hardware.json   保存、恢复与两次软件重启
  analysis/native_power_cycle_hardware.json             实际 USB 拔插、上电计数归零、配置保留
  analysis/native_standalone_manual_verification.json   用户确认断电启动、打字和 Fn
  analysis/native_app_v17_ota_hardware.json              独立程序->7210->官方OTA->独立程序
  backups/native_v17_20261030/                          应用与 Boot 实物回读

硬件资料可追踪到原厂 v1.18 函数偏移：0x760 ADC ISR、0x450C mux、
0xD0E4 指示灯、0xF528 SPI1、0x1040 DMA、0x138B4 RGB 90位置循环。
这些偏移只用于核对旧固件证据，不是当前独立程序的调用地址。
早期 v1.10 资料里的 ADC RAM 地址/管脚不能直接套到此 v1.18 板型。

12. 未完成项目与许可

三个单色灯、WS2812 的驱动和显示行为仍未适配；上述灯光 IO 是后续移植依据。
还需确认灯的物理顺序、灯珠数量/链顺序、P1.4 电路用途和未焊 UART 的脚位。
没有用示波器测量 WS2812 时序，也没有测端到端按键延迟。

QMK 有 GPL 许可、CMSIS Core 有 Apache-2.0，本项目自写代码带 GPL-2.0-or-later 标识。
官方 SDK 提供了 HAL/USB 源码，但在已核查的包、安装包和官网材料中未找到覆盖
这两部分的明确开源或再分发授权；第三方 FreeRTOS/FatFs 的许可证不能代替它。
因此当前可称“完整应用从源码构建”，不称“全套严格开源许可已确认”。
许可核查与 SDK 原始下载 URL/SHA 见 analysis/sdk_license_review.json、
analysis/sdk/source_provenance.json。
"""
    blocks=re.split(r"(?m)^(?=\d+\. )",text)
    implementation=[]
    for block in blocks[1:]:
        number=int(block.split(".",1)[0])
        if number>=4:
            implementation.append(re.sub(r"^\d+\. ",f"{len(implementation)+1}. ",block,count=1))
    text=("BAT68 固件实现与接口说明\n更新日期：2026-10-30\n\n"
          "扫描时序、数据布局、QMK、USB 协议、Bootloader 行为、构建与验证记录。\n"
          "板上器件和接线关系见同目录“硬件说明.txt”。\n\n"+"".join(implementation))
    output=ROOT/"固件说明.txt";output.write_text(text,encoding="utf-8")
    summary={"document":str(output),"keys":len(mapping),"raw_slots":len(channel_for),"matrix_rows":6,"matrix_columns":16,
             "unimplemented_lighting":["P1.6 CapsLock","P1.10 Win Lock","P1.11 Mac mode","WS2812 via SPI1 candidate P1.15"]}
    (ROOT/"analysis/firmware_document_tables.json").write_text(json.dumps({**summary,"keys":[{**k,"phase":phase_for[k["raw_slot"]],"adc_channel":channel_for[k["raw_slot"]]} for k in mapping]},indent=2),encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=True,indent=2))

if __name__=="__main__":main()
