#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
极客小木数字实验室 · 劳动者离职经济补偿金法定精算器 (2026最新版)
================================================================================
依据：
  1. 《中华人民共和国劳动合同法》第46/47/87条
  2. 《中华人民共和国劳动合同法实施条例》第27条 (全口径应得工资)
  3. 《职工带薪年休假条例》第5条 (300% 工资报酬，离职补发 200%)
  4. 《最高人民法院关于审理劳动争议案件适用法律问题的解释（二）》（法释〔2025〕12号）
  5. 财政部、税务总局《关于个人所得税法修改后有关优惠政策衔接问题的通知》（财税〔2018〕164号）
================================================================================
"""

import sys
import os
import json
import argparse
from typing import Dict, Any, Optional

# 内置 30 核心城市 2026 社平工资与 3 倍封顶基准 (兜底数据)
FALLBACK_CITIES = {
    "北京": {"monthly": 11200, "cap": 33600, "annual": 134400, "tax_exempt": 403200},
    "上海": {"monthly": 12183, "cap": 36549, "annual": 146196, "tax_exempt": 438588},
    "深圳": {"monthly": 12964, "cap": 38892, "annual": 155568, "tax_exempt": 466704},
    "广州": {"monthly": 10850, "cap": 32550, "annual": 130200, "tax_exempt": 390600},
    "杭州": {"monthly": 10250, "cap": 30750, "annual": 123000, "tax_exempt": 369000},
    "南京": {"monthly": 9980,  "cap": 29940, "annual": 119760, "tax_exempt": 359280},
    "苏州": {"monthly": 9850,  "cap": 29550, "annual": 118200, "tax_exempt": 354600},
    "成都": {"monthly": 8920,  "cap": 26760, "annual": 107040, "tax_exempt": 321120},
    "武汉": {"monthly": 8650,  "cap": 25950, "annual": 103800, "tax_exempt": 311400},
    "西安": {"monthly": 8320,  "cap": 24960, "annual": 99840,  "tax_exempt": 299520},
    "天津": {"monthly": 8500,  "cap": 25500, "annual": 102000, "tax_exempt": 306000},
    "重庆": {"monthly": 8240,  "cap": 24720, "annual": 98880,  "tax_exempt": 296640},
    "长沙": {"monthly": 8420,  "cap": 25260, "annual": 101040, "tax_exempt": 303120},
    "合肥": {"monthly": 8380,  "cap": 25140, "annual": 100560, "tax_exempt": 301680},
    "青岛": {"monthly": 8290,  "cap": 24870, "annual": 99480,  "tax_exempt": 298440},
    "济南": {"monthly": 8150,  "cap": 24450, "annual": 97800,  "tax_exempt": 293400},
    "宁波": {"monthly": 9620,  "cap": 28860, "annual": 115440, "tax_exempt": 346320},
    "无锡": {"monthly": 9480,  "cap": 28440, "annual": 113760, "tax_exempt": 341280},
    "东莞": {"monthly": 8120,  "cap": 24360, "annual": 97440,  "tax_exempt": 292320},
    "佛山": {"monthly": 8190,  "cap": 24570, "annual": 98280,  "tax_exempt": 294840},
    "厦门": {"monthly": 9150,  "cap": 27450, "annual": 109800, "tax_exempt": 329400},
    "福州": {"monthly": 8450,  "cap": 25350, "annual": 101400, "tax_exempt": 304200},
    "郑州": {"monthly": 7680,  "cap": 23040, "annual": 92160,  "tax_exempt": 276480},
    "沈阳": {"monthly": 7520,  "cap": 22560, "annual": 90240,  "tax_exempt": 270720},
    "大连": {"monthly": 7850,  "cap": 23550, "annual": 94200,  "tax_exempt": 282600},
    "哈尔滨": {"monthly": 7120, "cap": 21360, "annual": 85440,  "tax_exempt": 256320},
    "长春": {"monthly": 7240,  "cap": 21720, "annual": 86880,  "tax_exempt": 260640},
    "昆明": {"monthly": 7650,  "cap": 22950, "annual": 91800,  "tax_exempt": 275400},
    "贵阳": {"monthly": 7420,  "cap": 22260, "annual": 89040,  "tax_exempt": 267120},
    "南昌": {"monthly": 7580,  "cap": 22740, "annual": 90960,  "tax_exempt": 272880},
}


def load_city_database() -> Dict[str, Dict[str, Any]]:
    """优先从 national_30_cities_2026.json (同级或 data 目录) 加载数据，失败则降级到内置数据"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(current_dir, "national_30_cities_2026.json"),
        os.path.join(current_dir, "data", "national_30_cities_2026.json"),
    ]
    for json_path in candidates:
        if os.path.exists(json_path):
            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    result = {}
                    for item in data:
                        c = item["city"]
                        result[c] = {
                            "monthly": float(item["monthly_avg_salary"]),
                            "cap": float(item["salary_cap_3x"]),
                            "annual": float(item.get("annual_avg_salary", item["monthly_avg_salary"] * 12)),
                            "tax_exempt": float(item.get("tax_exempt_threshold", item["monthly_avg_salary"] * 12 * 3)),
                        }
                    return result
            except Exception:
                pass
    return FALLBACK_CITIES


def calculate_tenure_n(years: float) -> float:
    """
    依照《劳动合同法》第47条第1款折算年限 N：
    - 满 1 年算 1
    - 6 个月以上不满 1 年算 1
    - 不满 6 个月算 0.5
    """
    full_years = int(years)
    remaining_fraction = years - full_years
    if remaining_fraction == 0:
        return float(full_years)
    elif remaining_fraction >= 0.5:
        return float(full_years + 1)
    else:
        return float(full_years + 0.5)


def run_calculation(
    city: str,
    base_salary: float,
    years: float,
    annual_bonus: float = 0.0,
    unused_leave_days: float = 0.0,
    notice_salary: Optional[float] = None
) -> Dict[str, Any]:
    cities = load_city_database()
    if city not in cities:
        # 模糊匹配
        matched = [k for k in cities.keys() if city in k or k in city]
        if matched:
            city = matched[0]
        else:
            raise ValueError(f"未收录城市: {city}，支持全国 30 核心城市。可使用 --list-cities 查看。")

    city_data = cities[city]
    monthly_avg = city_data["monthly"]
    cap_3x = city_data["cap"]
    tax_exempt_limit = city_data["tax_exempt"]

    # 1. 全口径平均月薪 (含年终奖月均摊入)
    bonus_monthly = annual_bonus / 12.0
    full_monthly_salary = base_salary + bonus_monthly

    # 2. 司龄折算 N
    n_factor = calculate_tenure_n(years)

    # 3. 封顶法则判定 (劳动合同法第47条第2款)
    is_capped = full_monthly_salary > cap_3x
    if is_capped:
        effective_monthly = cap_3x
        applied_tenure = min(n_factor, 12.0)
        tenure_was_limited = n_factor > 12.0
    else:
        effective_monthly = full_monthly_salary
        applied_tenure = n_factor
        tenure_was_limited = False

    # 4. 补偿金金额精算
    compensation_n = effective_monthly * applied_tenure

    # 代通知金 (+1)
    if notice_salary is None or notice_salary <= 0:
        actual_notice = full_monthly_salary
    else:
        actual_notice = notice_salary

    compensation_n_plus_1 = compensation_n + actual_notice
    compensation_2n = (effective_monthly * applied_tenure) * 2.0

    # 5. 未休年休假工资报酬 (带薪年休假条例第5条: 300% 报酬，扣除已发100%，额外补发200%)
    # 日工资 = 月工资收入 ÷ 21.75
    daily_wage = full_monthly_salary / 21.75
    unused_leave_comp = unused_leave_days * daily_wage * 2.0

    # 6. 财税〔2018〕164号 个税免征红线测算
    # 离职补偿金总额 (以 N+1 加上年休假补偿为例)
    total_package = compensation_n_plus_1 + unused_leave_comp
    is_tax_free = total_package <= tax_exempt_limit
    taxable_amount = max(0.0, total_package - tax_exempt_limit)

    return {
        "city": city,
        "monthly_avg": monthly_avg,
        "cap_3x": cap_3x,
        "tax_exempt_limit": tax_exempt_limit,
        "base_salary": base_salary,
        "annual_bonus": annual_bonus,
        "bonus_monthly": bonus_monthly,
        "full_monthly_salary": full_monthly_salary,
        "years": years,
        "n_factor": n_factor,
        "applied_tenure": applied_tenure,
        "is_capped": is_capped,
        "tenure_was_limited": tenure_was_limited,
        "effective_monthly": effective_monthly,
        "compensation_n": compensation_n,
        "actual_notice": actual_notice,
        "compensation_n_plus_1": compensation_n_plus_1,
        "compensation_2n": compensation_2n,
        "unused_leave_days": unused_leave_days,
        "unused_leave_comp": unused_leave_comp,
        "total_package": total_package,
        "is_tax_free": is_tax_free,
        "taxable_amount": taxable_amount,
    }


def print_report(res: Dict[str, Any]):
    print("\n" + "=" * 78)
    print("🛡️  极客小木数字实验室 · 劳动者离职补偿法定精算报告 (2026)")
    print("=" * 78)
    
    print(f"【基础档案】")
    print(f"  • 工作城市   : {res['city']}")
    print(f"  • 司龄年限   : {res['years']:.2f} 年  ➔  法定折算系数 N = {res['n_factor']:.1f} 个月")
    print(f"  • 基础月薪   : ¥{res['base_salary']:,.2f}")
    if res['annual_bonus'] > 0:
        print(f"  • 全年年终奖 : ¥{res['annual_bonus']:,.2f}  (分摊至每月 ¥{res['bonus_monthly']:,.2f})")
    print(f"  • 全口径月薪 : ¥{res['full_monthly_salary']:,.2f}  (劳动合同法实施条例§27 应发标准)")
    
    print("-" * 78)
    print(f"【30城司法基准与封顶判定】")
    print(f"  • 当地社平月薪 : ¥{res['monthly_avg']:,.2f}")
    print(f"  • 社平3倍封顶线: ¥{res['cap_3x']:,.2f}")
    if res['is_capped']:
        print(f"  ⚠️  [触发高薪封顶] 全口径月薪 (¥{res['full_monthly_salary']:,.2f}) > 3倍社平 (¥{res['cap_3x']:,.2f})")
        print(f"      • 补偿计算基数强制按封顶上限: ¥{res['effective_monthly']:,.2f}")
        if res['tenure_was_limited']:
            print(f"      • 依据劳动合同法§47，高薪受 12 年上限约束，计算年限由 {res['n_factor']:.1f} 年压减为 12.0 年！")
    else:
        print(f"  ✅  [未触发封顶] 全口径月薪低于当地 3 倍社平，无 12 年补偿年限限制！")
    
    print("-" * 78)
    print(f"【法定补偿方案对比 (税前)】")
    print(f"  ┌──────────────────────────────┬──────────────────┬────────────────────────┐")
    print(f"  │ 补偿方案类别                 │ 法定金额 (RMB)   │ 核心适用场景与法条     │")
    print(f"  ├──────────────────────────────┼──────────────────┼────────────────────────┤")
    print(f"  │ 1. 协商解除补偿 (N)          │ ¥{res['compensation_n']:>14,.2f} │ 劳动合同法§46 协商一致 │")
    print(f"  │ 2. 辞退代通知补偿 (N+1)      │ ¥{res['compensation_n_plus_1']:>14,.2f} │ 劳动合同法§40 未提30天 │")
    print(f"  │ 3. 违法解除赔偿金 (2N)       │ ¥{res['compensation_2n']:>14,.2f} │ 劳动合同法§87 逼退/开除│")
    print(f"  └──────────────────────────────┴──────────────────┴────────────────────────┘")

    if res['unused_leave_days'] > 0:
        print(f"\n【应休未休年假 200% 补发差额】")
        print(f"  • 剩余年休假 : {res['unused_leave_days']} 天")
        print(f"  • 额外补发差额: ¥{res['unused_leave_comp']:,.2f}  (除正常已发工资外补发，带薪年休假条例§5)")
    
    print("-" * 78)
    print(f"【💰 财税〔2018〕164号 个税免征红线自查】")
    print(f"  • 当地年社平工资 3 倍免税额度 : ¥{res['tax_exempt_limit']:,.2f}")
    print(f"  • 离职结算总计 (N+1 + 年假)   : ¥{res['total_package']:,.2f}")
    if res['is_tax_free']:
        print(f"  🎉  [完全免税] 补偿总额低于当地 3 倍年社平，依据国家政策 100% 免征个人所得税！公司不得扣税！")
    else:
        print(f"  ⚠️  [部分超额] 超过免税线部分 ¥{res['taxable_amount']:,.2f}，依法按单独适用综合所得税率计税。")

    print("=" * 78)
    print("📱 现场谈判无法掏出电脑？")
    print("👉 在线免登录工作台体验: https://feishu.cn/base/ZeSSb4ioAae1EXsyyBXcnaPvnDf")
    print("👉 关注微信公众号【极客小木】，回复【工作台】获取个人独立加密多维母版与 24 类证据链！")
    print("=" * 78 + "\n")


def interactive_mode():
    print("\n" + "=" * 60)
    print("🎯 欢迎使用劳动者离职经济补偿法定精算器 (交互引导模式)")
    print("=" * 60)
    cities = load_city_database()
    
    city = input("1. 请输入工作所在城市 (如: 北京/上海/杭州/深圳): ").strip()
    while city not in cities and not any(city in k for k in cities):
        print(f"暂未收录 '{city}'。支持的城市包括：北京, 上海, 深圳, 广州, 杭州, 成都, 武汉等。")
        city = input("请重新输入城市: ").strip()
    
    while True:
        try:
            salary_str = input("2. 请输入税前全口径月薪 (不含年终奖，单位: 元): ").strip()
            salary = float(salary_str)
            break
        except ValueError:
            print("请输入有效数字。")
            
    while True:
        try:
            years_str = input("3. 请输入在职司龄年限 (如 3.2 或 5.6 年): ").strip()
            years = float(years_str)
            break
        except ValueError:
            print("请输入有效数字。")

    bonus_str = input("4. 请输入全年年终奖总额 (元，没有请直接按回车): ").strip()
    bonus = float(bonus_str) if bonus_str else 0.0

    leave_str = input("5. 请输入当年剩余未休年休假天数 (天，没有请直接按回车): ").strip()
    leave_days = float(leave_str) if leave_str else 0.0

    res = run_calculation(city, salary, years, bonus, leave_days)
    print_report(res)


def main():
    parser = argparse.ArgumentParser(
        description="2026 劳动者离职经济补偿法定精算器 (极客小木数字实验室)"
    )
    parser.add_argument("--city", "-c", type=str, help="工作所在城市 (如: 北京, 上海, 杭州)")
    parser.add_argument("--salary", "-s", type=float, help="税前全口径基础月薪 (元)")
    parser.add_argument("--years", "-y", type=float, help="在职司龄年限 (如: 3.5)")
    parser.add_argument("--annual-bonus", "-b", type=float, default=0.0, help="全年年终奖总额 (元)")
    parser.add_argument("--unused-leave", "-l", type=float, default=0.0, help="当年未休年假天数")
    parser.add_argument("--list-cities", action="store_true", help="打印已收录的全国30核心城市名单")

    args = parser.parse_args()

    if args.list_cities:
        cities = load_city_database()
        print("\n🏛️  已收录的全国 30 核心城市及社平工资/3倍封顶基数 (2026):")
        print("-" * 65)
        print(f"{'城市':<8} {'社平月工资':<12} {'3倍封顶上限':<14} {'免个税红线(年3倍)':<18}")
        print("-" * 65)
        for c, d in cities.items():
            print(f"{c:<8} ¥{d['monthly']:<11,.0f} ¥{d['cap']:<13,.0f} ¥{d['tax_exempt']:<17,.0f}")
        print("-" * 65 + "\n")
        sys.exit(0)

    if not args.city or args.salary is None or args.years is None:
        interactive_mode()
    else:
        res = run_calculation(
            args.city,
            args.salary,
            args.years,
            args.annual_bonus,
            args.unused_leave
        )
        print_report(res)


if __name__ == "__main__":
    main()
