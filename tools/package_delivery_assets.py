#!/usr/bin/env python3
"""将 exports/esq_bundles 中的 45 个标准 ESQ 题包按考试类别打包为独立的交付压缩包，
并附带清晰的用户导入指引说明，专为闲鱼接单/付费用户交付使用。
"""

import os
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ESQ_DIR = ROOT / "exports" / "esq_bundles"
DELIVERY_DIR = ROOT / "exports" / "delivery_zips"
DELIVERY_DIR.mkdir(parents=True, exist_ok=True)

GUIDE_TEXT = """【墨题 (Motei) · 真题扩展包导入使用说明】

感谢使用墨题英语真题题库！
本题包专为《墨题 AI 英语刷题机》打造，采用标准 ESQ 1.0 格式封装，包含官方原卷题干、标准选项及参考解析。

──────────────────────────────────────────────────────
【一分钟极速导入方法】
1. 打开《墨题》软件（桌面端 / Web 端 / 安卓 App 均可）；
2. 点击左侧导航栏的【导入题库】（或设置页面的题库管理）；
3. 将解压出来的 .esq 文件直接拖入网页窗口，或点击“选择文件”上传；
4. 确认试卷信息后，点击【开始导入】；
5. 导入完成后，返回【题库】页面即可看到对应科目的全部真题并开始刷题！

──────────────────────────────────────────────────────
【包含题包清单】
详细目录与试卷清单请查阅同目录下的题包文件名或 README。
如遇任何疑问或需补充新年份真题，请随时联系提供支持！
"""

CATEGORIES = {
    "墨题题包-考研英语一(2010-2026全套真题)": [
        "wssfk.postgraduate-english-one.2010-2026.esq",
        "cn.kaoyan1.2024.esq",
        "cn.kaoyan1.2025.esq",
        "cn.kaoyan1.2026.esq",
        "local.english-practice.postgraduate-english-one.2010-2024.esq"
    ],
    "墨题题包-考研英语二(2010-2026全套真题)": [
        "local.english-practice.postgraduate-english-two.2010-2025.esq",
        "cn.kaoyan2.2025.esq",
        "cn.kaoyan2.2026.esq"
    ],
    "墨题题包-大学英语四六级(2023-2026最新真题)": [
        "cet4-2023.esq", "cet4-2025.esq", "cet4-2026.esq",
        "cn.cet4.banked.2023.6.1.esq", "cn.cet4.banked.2023.12.1.esq",
        "cn.cet4.banked.2023.12.2.esq", "cn.cet4.banked.2023.12.3.esq",
        "cn.cet4.banked.2025.06.1.esq", "cn.cet4.banked.2025.06.2.esq",
        "cn.cet4.banked.2026.06.1.esq", "cn.cet4.banked.2026.06.2.esq", "cn.cet4.banked.2026.06.3.esq",
        "cet6-2023.esq", "cet6-2025.esq", "cet6-2026.esq",
        "cn.cet6.banked.2023.6.1.esq", "cn.cet6.banked.2023.12.1.esq",
        "cn.cet6.banked.2023.12.2.esq", "cn.cet6.banked.2025.06.1.esq",
        "cn.cet6.banked.2025.06.2.esq", "cn.cet6.banked.2025.06.3.esq",
        "cn.cet6.banked.2026.06.1.esq", "cn.cet6.banked.2026.06.2.esq", "cn.cet6.banked.2026.06.3.esq"
    ],
    "墨题题包-高考英语全国卷(2022-2026全套真题)": [
        "gaokao-english-2022-2024.esq",
        "cn.gaokao.english.7of5.esq",
        "cn.gaokao.english.cloze.esq",
        "cn.gaokao.2026.national1.esq"
    ]
}

def main():
    print("=" * 60)
    print("开始打包分类交付压缩包...")
    print("=" * 60)

    # 1. 各分类交付包
    for cat_name, file_patterns in CATEGORIES.items():
        zip_path = DELIVERY_DIR / f"{cat_name}.zip"
        count = 0
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("【必看】题包导入使用说明.txt", GUIDE_TEXT.encode("utf-8"))
            for p_name in file_patterns:
                f_path = ESQ_DIR / p_name
                if f_path.exists():
                    zf.write(f_path, arcname=p_name)
                    count += 1
                else:
                    # 尝试模糊匹配
                    for matched in ESQ_DIR.glob(p_name):
                        zf.write(matched, arcname=matched.name)
                        count += 1
        size_mb = zip_path.stat().st_size / 1024 / 1024
        print(f"✓ 已生成: {zip_path.name} (含 {count} 题包, {size_mb:.2f} MB)")

    # 2. 全量真题大合集
    all_zip_path = DELIVERY_DIR / "墨题全套真题扩展包(合集-45题包-108卷).zip"
    all_esq = list(ESQ_DIR.glob("*.esq"))
    with zipfile.ZipFile(all_zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("【必看】题包导入使用说明.txt", GUIDE_TEXT.encode("utf-8"))
        readme_path = ESQ_DIR / "README.md"
        if readme_path.exists():
            zf.write(readme_path, arcname="题包全量目录与试卷统计.md")
        for f in all_esq:
            zf.write(f, arcname=f.name)
            
    all_size_mb = all_zip_path.stat().st_size / 1024 / 1024
    print(f"\n✓ 已生成全量合集: {all_zip_path.name} (含 {len(all_esq)} 题包, {all_size_mb:.2f} MB)")
    print("\n所有交付压缩包已存放至: exports/delivery_zips/")

if __name__ == "__main__":
    main()
