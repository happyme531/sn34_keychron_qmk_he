"""Generate board components, pins and fixed analog routing only."""
from collections import Counter
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def main():
    keys=json.loads((ROOT/"analysis/board_map_v118.json").read_text(encoding="utf-8"))["keys"]
    assert len(keys)==67
    counts=Counter(k["name"] for k in keys);labels={}
    for key in keys:
        peers=sorted((k for k in keys if k["name"]==key["name"]),key=lambda k:k["rect"][0])
        label=key["name"]
        if counts[label]>1:label=("左" if key is peers[0] else "右")+label
        labels[key["raw_slot"]]=label
    rows=[]
    for y in sorted({k["rect"][1] for k in keys}):
        row=sorted((k for k in keys if k["rect"][1]==y),key=lambda k:k["rect"][0])
        rows.append("  "+"  ".join(labels[k["raw_slot"]] for k in row))
    channels=(1,2,3,4,5,6,7,10,11,12,13,14);route={}
    for select in range(8):
        for cluster,group in enumerate(((10,11,12,13),(1,2,3,4),(5,6,7,14))):
            for lane in range(4):
                upper=select>>2
                slot=cluster*32+upper*16+(lane>>1)*8+(select&3)*2+(lane&1)
                route[select,group[lane^upper]]=labels.get(slot,"--")
    table="  S2S1S0 "+" ".join(f"P2.{c:<2}".ljust(10) for c in channels)+"\n"
    table+="\n".join(f"  {s:03b}    "+" ".join(route[s,c].ljust(10) for c in channels) for s in range(8))
    text=f"""BAT68 板级硬件与连接说明
更新日期：2026-10-30

适用板：本机 HFD8KCG200 主控、带 6 颗 HFD24MH001 的 BAT68。
用于追线、核对 IO、理解按键与主控的固定连接，以及识别调试和 BOOT 引脚。

1. 板上器件

  主控             HFD8KCG200
  兼容芯片族       SONiX SN34F280，Cortex-M4F；具体 SN34F28x 尾号未确认
  主控存储容量     按兼容目标为 512 KiB Flash、160 KiB SRAM
  外围小芯片       6 颗 HFD24MH001
  单色指示灯       3 个；物理左右顺序、颜色和丝印对应待逐灯核对
  RGB 灯           一套 WS2812；实物灯数和链路顺序待确认
  调试连接         SWD 焊盘，另有未焊串口座

HFD24MH001 的公开引脚资料和内部框图尚未取得。
外部连接等效为 12 路模拟输出、3 根选择线，可选择 8 组按键信号。
这与“6 颗双路 8 选 1”结构相容，但不能据此断定每颗内部是纯模拟 mux，
也不能排除缓冲、开关或其他模拟前端功能。六颗芯片的具体脚位待通断测量。

2. 主控 IO 与用途

Pn.m 表示 MCU 端口，不是封装脚号或 PCB 焊盘排列顺序。
“反推”表示来自原厂 IO 配置及按键响应，不代表已对该条走线做过通断测量。

  端口/信号         对应连接或功能                     依据
  P2.9              模拟前端选择线 S0                 按键响应与 IO 配置
  P0.0              模拟前端选择线 S1                 按键响应与 IO 配置
  P0.1              模拟前端选择线 S2                 按键响应与 IO 配置
  P1.12             模拟前端门控/使能线                反推，具体电路名称待确认
  P2.1..P2.7        ADC0 AIN1..AIN7                   模拟按键信号输入
  P2.10..P2.14      ADC0 AIN10..AIN14                 模拟按键信号输入
  P3.12             外部高速晶振 XIN                  芯片复用定义与原厂配置
  P3.13             外部高速晶振 XOUT                 芯片复用定义与原厂配置
  USB_DP/USB_DM     USB 数据线                         封装脚号和 PCB 走线待核对
  P1.6              CapsLock 指示灯控制                反推
  P1.10             Win Lock 指示灯控制                反推
  P1.11             Mac 模式指示灯控制                 反推
  P1.15             SPI1 MO1；WS2812 DIN 候选          反推，待通断/波形确认
  P1.13             SPI1 SCK1                          已知复用；板上去向待确认
  P1.4              RGB 相关控制脚候选                 疑似使能/供电控制，待确认
  P3.5              SWDIO                              芯片定义；焊盘对应待逐根核对
  P3.6              SWCLK                              芯片定义；焊盘对应待逐根核对
  P1.3              原厂 BOOT 检测输入候选             低电平入口未在板上短接实测

P2.9 虽然也有 ADC 复用能力，但在此板上用作选择线，不列入模拟输入。
P1.12 与 P1.4 的晶体管/供电网络没有追清，不能把它们视为可互换的电源使能。
晶振的实物丝印、外部灯珠供电和板上各电压轨尚未记录。

3. 选择线与按键模拟输入的固定对应

选择线：S2=P0.1、S1=P0.0、S0=P2.9。
下表表示给定选择线电平时，各 ADC 输入对应哪个按键，用于追线与更换主控。
-- 表示目前没有已识别按键对应，不等于已确认该引脚或通道完全悬空。

{table}

这是模拟前端的电气对应关系。按键不构成普通开关式键盘的交叉行列网络。
已建立 67 个按键的对应关系，包含 Fn；其余组合没有已识别的按键。
每颗 HFD24MH001 分别承载哪些输入/输出，仍需沿 PCB 走线或测通断确认。

4. 实际键位排列

按本板布局数据整理，键名与上面的电气对应表相同：
{chr(10).join(rows)}

5. 灯与调试连接

三个单色灯的控制端口为 P1.6、P1.10、P1.11，功能对应 CapsLock、Win Lock、
Mac 模式。实物左右顺序、颜色、串联电阻和驱动级还未逐一核对。

WS2812 数据线最有力的候选是 P1.15。P1.13 为同一 SPI 外设的时钟脚，
但 WS2812 本身是单线器件，不能据此假定灯链需要或连接了这根时钟线。
P1.4 疑似与灯链使能/供电有关；实际灯数、第一颗位置、串接顺序和额外侧灯待确认。

SWD 的芯片端信号：P3.5=SWDIO、P3.6=SWCLK，另需共地。
CH347T 使用 TMS 对应 SWDIO、TCK 对应 SWCLK。此前以键盘 USB 供电，
没有接调试器电源输出；手按接触尚未取得稳定 SWD 读数。
焊盘到这些端口的逐根对应、VTref 电压和 NRST 焊盘位置仍待确认。

未焊串口座的 TX、RX、GND、电源及对应 UART 实例均未追线，不能预设接法。
P1.3 是原厂 BOOT 检测的低电平输入候选；板上哪个焊盘连到此脚、
短接后能否稳定进入下载状态，尚无实物验证。

6. 待补充的板级信息

  HFD24MH001 的封装、逐脚连接和内部功能资料
  USB 专用脚的封装编号及走线
  晶振丝印、主控/模拟前端/WS2812 的实际供电电压
  三个单色灯的物理顺序、颜色、电阻和驱动级
  WS2812 数量、链路顺序、P1.15 连通性及 P1.4 电路用途
  SWD 焊盘标号、VTref/NRST 与未焊串口座的脚位
  BOOT 焊盘与 P1.3 的实际连接

引脚名称依据官方 SN34F280 AFIO 定义；按键对应源数据为
analysis/board_map_v118.json 和 analysis/hardware_document_tables.json。
固件实现另见“固件说明.txt”；日常操作见“QMK使用说明.txt”。
"""
    output=ROOT/"硬件说明.txt";output.write_text(text,encoding="utf-8")
    data={"document":str(output),"kind":"board_connectivity_only","keys":len(keys),
          "select_pins":{"S0":"P2.9","S1":"P0.0","S2":"P0.1"},
          "routing":[{"select":f"{s:03b}","adc_channel":c,"port":f"P2.{c}","key":route[s,c]} for s in range(8) for c in channels]}
    (ROOT/"analysis/hardware_document_tables.json").write_text(json.dumps(data,ensure_ascii=True,indent=2))
    print(json.dumps({"document":str(output),"lines":len(text.splitlines()),"keys":len(keys)},ensure_ascii=True))

if __name__=="__main__":main()
