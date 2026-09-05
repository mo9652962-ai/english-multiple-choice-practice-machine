# -*- coding: utf-8 -*-
"""q1443-1450（题库选项错位）与 q1487/q1492（答案键存疑）的解析修正补丁。

补丁硬编码于本脚本，写入 data/patches.db；apply_content.py 与 validate_content.py
读取该表对内容做字段级覆盖。数据层问题本身（错位/答案键）不在本任务范围内修改，
已在 note 中如实标注并上报。
"""
import os
import sqlite3

BASE = r"D:\english-multiple-choice-practice-machine\scripts\explain_gen"
PATCHES_DB = os.path.join(BASE, "data", "patches.db")

PATCHES = {
    1443: {
        "long_sentence": "定位句 There are fundamental public health problems, like dirty hands instead of a soap habit, that remain killers only because we can't figure out how to change people's habits。that remain killers 为定语从句；instead of 对比脏手与肥皂习惯。译：一些根本公共卫生问题——如脏手代替肥皂习惯——仍是杀手，只因我们不知如何改变人们的习惯；柯蒂斯想向企业学习创造自动发生的新行为。",
        "option": "题库本题选项错位：正确表述「should be further cultivated（应被进一步培养）」被存入题干栏。柯蒂斯博士想向企业学习创造新习惯，即洗手这类习惯应被「培养」；题库标记的 A 项 should be changed gradually 与 can't figure out how to change people's habits 方向相反；deeply rooted in history 与 basically private concerns 均无中生有。",
        "keyword": "soap habit 用肥皂的习惯；cultivate 培养＝foster；public health 公共卫生；create new behaviors 创造新行为。",
        "note": "注：本题题库数据错位——真题干是「According to Dr. Curtis, habits like hand washing with soap ______」，正确文本被存进题干栏，标记的 A 项实为干扰文本。记结论：柯蒂斯主张「培养」新习惯（create/cultivate），不是「逐渐改变」旧习惯。",
    },
    1444: {
        "long_sentence": "定位句 If you look hard enough, you'll find that many of the products we use every day – chewing gums, skin moisturizers, disinfecting wipes, air fresheners... – are results of manufactured habits。破折号内为产品列举；manufactured habits 被制造出的习惯。译：仔细观察就会发现，我们每天使用的许多产品——口香糖、保湿霜、消毒湿巾、空气清新剂等——都是被制造出来的习惯的产物。",
        "option": "题库选项错位：正确表述「reveal their impact on people's habits（揭示它们对人们习惯的影响）」被存入题干栏。列举口香糖、保湿霜等是为例证 are results of manufactured habits——展示企业制造习惯的影响力；题库标记的 A 项 show the urgent need of daily necessities 无中生有，B 项 buying power 偷换概念，C 项 good habits 张冠李戴。",
        "keyword": "manufactured habit 被制造的习惯；moisturizer 保湿霜；disinfecting wipe 消毒湿巾；ritual 仪式、惯例。",
        "note": "注：题库数据错位——真题干「Bottled water, chewing gum and skin moisturizers are mentioned in Paragraph 5 so as to ______」被存于上一题选项 D。例证题抓例子前后的观点句 manufactured habits；urgent need、buying power 都偏离例证目的。",
    },
    1445: {
        "long_sentence": "定位句 The companies that Dr. Curtis turned to – Procter & Gamble, Colgate-Palmolive and Unilever – had invested hundreds of millions of dollars finding the subtle cues...；文中 Colgate, Crest 是牙膏品牌，Tide 是宝洁旗下洗衣产品。译：柯蒂斯博士求助的公司——宝洁、高露洁棕榄与联合利华——已投入数亿美元寻找生活中可用于培养新惯常行为的细微线索。",
        "option": "题库选项错位：真题干「Which of the following does NOT belong to products that help create people's habits?」被存于上一题选项 D，本题标记的 D 项实为该题干文本。正确答案文本 Unilever 存于本题 C 项——它是被求助的「公司」而非塑造习惯的产品；Tide（洗衣液）、Crest 与 Colgate（牙膏）都是文中直接塑造习惯的产品。",
        "keyword": "NOT 题找类别异项；product 产品；company 公司＝corporation；Unilever 联合利华（公司而非产品）。",
        "note": "注：题库数据错位，按「找出非产品项」作答：Tide、Crest、Colgate 是产品，Unilever 是公司——类别异项即答案；标记的 D 项是一句题干文本，勿按其作答。",
    },
    1446: {
        "long_sentence": "定位句 Today, because of shrewd advertising and public health campaigns, many Americans habitually give their pearly whites a cavity-preventing scrub twice a day, often with Colgate, Crest or one of the other brands。because of 引出习惯成因；shrewd 精明的。译：如今，由于精明的广告与公共卫生运动，许多美国人习惯性地每天两次用高露洁、佳洁士等品牌的牙膏洁齿防蛀。",
        "option": "题库选项错位：真题干「From the text we know that some of consumers' habits are developed due to ______」存于本题 D 项。正确文本「commercial promotions（商业推广）」存于本题 B 项——刷牙习惯源于 shrewd advertising；题库标记的 C 项 scientific experiments 张冠李戴，experiments 是研究手段而非成因；automatic behavior creation 是企业想掌握的能力；perfected art of products（存于题干栏）无中生有。",
        "keyword": "shrewd advertising 精明的广告；campaign 运动、宣传；cavity-preventing 防蛀的；scrub 刷洗。",
        "note": "注：题库数据错位，真题干在本题 D 项。因果定位抓 because of：广告加公共卫生运动即商业推广，commercial promotions 对应；「科学实验」只是验证习惯机制的工具，不是消费者习惯的成因。",
    },
    1447: {
        "note": "态度题找作者的评述动词：全文用 learn、emerge、erupt 等中性动词铺陈事实，无褒贬形容词出自作者之口；ruthless 出自转述语境，勿把引语色彩算到作者头上。注：本题题干被错存于上一题选项 D（The author's attitude toward the influence of advertisement on people's habits is），题库题干栏为空占位。",
    },
    1448: {
        "long_sentence": "定位句 that verdicts should represent the conscience of the community and not just the letter of the law。that 引导同位语从句解释 principles 之一；conscience 良知；letter of the law 法律字面。译：陪审团的裁决应当体现共同体的良知，而不仅是法律的字面条文。",
        "option": "题库选项错位：正确文本「judgment should consider the opinion of the public（判决应考虑民意）」存于本题 C 项，对应 verdicts should represent the conscience of the community；题库标记的 D 项实为下一题题干文本。immune（A 项）与 entitled to 相反，no age limit（B 项）与 minimum age 矛盾，「both literate and illiterate…」（存于题干栏）与 literacy 门槛相悖。",
        "keyword": "verdict 裁决；conscience 良知＝moral sense；the letter of the law 法律条文；be entitled to 有权享有。",
        "note": "注：题库数据错位，真题干「From the principles of the US jury system, we learn that ______」即原文末句。原则清单逐条核对：conscience of the community＝民意，judgment considering public opinion 是它的改写；immune 与 entitled、no age limit 与 minimum age 是两组正反混淆。",
    },
    1449: {
        "long_sentence": "定位句 Although the Supreme Court had prohibited intentional racial discrimination as early as 1880, the practice of selecting so-called elite or blue-ribbon juries provided a convenient way around... antidiscrimination laws。way around 绕开…的途径。译：尽管最高法院早在 1880 年就禁止陪审团遴选中的蓄意种族歧视，但遴选所谓精英「蓝绶带」陪审团的做法，为绕开反歧视法提供了便利。",
        "option": "题库选项错位：正确文本「the inadequacy of antidiscrimination laws（反歧视法的不足）」被存入题干栏。遴选 elite/blue-ribbon 陪审团是 convenient way around antidiscrimination laws 的途径——法律能被绕开正说明存在漏洞；题库标记的 A 项 the prevalent discrimination against certain races 偷换概念，被禁止的是歧视行为，暴露的是法律漏洞；conflicting ideals 与 arrogance 无中生有。",
        "keyword": "prohibit 禁止＝ban；blue-ribbon jury 精英陪审团；a way around 绕开…的捷径＝loophole；antidiscrimination 反歧视的。",
        "note": "注：题库数据错位，真题干「The practice of selecting so-called elite jurors prior to 1968 showed ______」存于上一题选项 D。让步转折落点在后半句：法律早已禁止歧视却被绕开——问题在法律不严密，而非歧视「普遍存在」。",
    },
    1450: {
        "note": "because 题抓 justified by the claim：州里的理由就是 women were needed at home，C 的 domestic duties 是 its 同义改写；A 利用 automatically 一词偷换 exempt 与 ban。注：本题题干被错存于上一题选项 D（Even in the 1960s, women were seldom on the jury list in some states because），题库题干栏为空占位；本题答案 C 与存储选项文本一致，可放心按 C 作答。",
    },
    1487: {
        "note": "标题题抓全文态度拐点：首段渲染死亡预言，But the discussions now seem out of date 一转，正确标题必须同时容纳困境与生路两面；只写惨（Hopeless）或只写好（Thriving）都以偏概全。注：题库答案键标为 D（A Hopeless Story），但原文 survived 与 returned to profit 同「无望」直接矛盾，正确项应为 A（Struggling for Survival），建议核对题库答案键。",
    },
    1492: {
        "note": "设计特征题抓效果来源句：come from 后的三项并列就是设计清单，与选项逐一对号；B 是 landscape 的同义展开，C 把 forthright detailing 读反是本题最强陷阱。注：题库答案键标为 C（Details were sacrificed for the overall effect），但 forthright detailing 明说细部被坦率呈现，正确项应为 B（Natural scenes were taken into consideration），建议核对题库答案键。",
    },
}


def main() -> None:
    os.makedirs(os.path.dirname(PATCHES_DB), exist_ok=True)
    conn = sqlite3.connect(PATCHES_DB)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS patches ("
        "question_id INTEGER NOT NULL, field TEXT NOT NULL, value TEXT NOT NULL, "
        "PRIMARY KEY (question_id, field))"
    )
    rows = []
    for qid, fields in PATCHES.items():
        for field, value in fields.items():
            rows.append((qid, field, value))
    conn.executemany("INSERT OR REPLACE INTO patches (question_id, field, value) VALUES (?, ?, ?)", rows)
    conn.commit()
    # 同步已入库的 explain_collections 行（幂等纠偏：补丁更新后直接覆盖已写内容）
    field_to_ft = {"long_sentence": "long_sentence", "option": "option", "keyword": "keyword", "note": "note"}
    main_conn = sqlite3.connect(r"D:\english-multiple-choice-practice-machine\backend\data\question_bank.db")
    synced = 0
    for qid, field, value in rows:
        cur = main_conn.execute(
            "UPDATE explain_collections SET content=? WHERE question_id=? AND fragment_type=?",
            (value, qid, field_to_ft[field]),
        )
        synced += cur.rowcount
    main_conn.commit()
    main_conn.close()
    n = conn.execute("SELECT COUNT(*) FROM patches").fetchone()[0]
    qids = [r[0] for r in conn.execute("SELECT DISTINCT question_id FROM patches ORDER BY question_id")]
    conn.close()
    print("patches.db: %d fields for qids %s" % (n, qids))
    print("explain_collections rows synced by patch: %d" % synced)
    print("SAVE PATCHES DONE")


if __name__ == "__main__":
    main()
