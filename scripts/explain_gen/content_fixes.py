# -*- coding: utf-8 -*-
"""数据修复后的解析内容重写层。

- FULL：题面布局已修复的题，option/note 按修复后官方布局重写（字母对齐、去警示）。
- NOTE_ONLY：仅清除 note 中的警示后缀（恢复 content 文件里的原始 note）。
- 执行：清空这些题的旧补丁 → 写入新补丁 → 幂等同步 explain_collections。
"""
import json
import os
import sqlite3

BASE = r"D:\english-multiple-choice-practice-machine\scripts\explain_gen"
CONTENT_DIR = os.path.join(BASE, "content")
PATCHES_DB = os.path.join(BASE, "data", "patches.db")
MAIN_DB = r"D:\english-multiple-choice-practice-machine\backend\data\question_bank.db"
MAX_LEN = 320

ALL_QIDS = [1443, 1444, 1445, 1446, 1447, 1448, 1449, 1450,
            1523, 1524, 1528, 1529, 1530, 1531, 1533, 1534, 1535,
            1568, 1569, 1570, 1571, 1573, 1574, 2066, 2083, 2084, 2085, 2086,
            1487, 1492, 1527, 1532, 1577, 1582, 1667]

FULL = {
    1443: {
        "option": "正确项 A should be further cultivated：脏手当道、肥皂习惯缺位，Curtis 想向企业学习创造新习惯＝洗手这类习惯应被进一步培养；B are deeply rooted in history 无中生有；C are basically private concerns 无中生有，原文定性为 public health problems；D should be changed gradually 方向反了，缺的是新习惯不是改旧习惯。",
        "note": "人名观点题先找 Curtis 的立场句：问题是「没有肥皂习惯」，对策是 create new behaviors，cultivate 对应 create；D 的 change 与 can't figure out how to change 相反，是最强干扰。",
    },
    1444: {
        "option": "正确项 A reveal their impact on people's habits：列举口香糖、保湿霜等是为例证 are results of manufactured habits——展示企业制造习惯的影响力；B show the urgent need of daily necessities 无中生有；C indicate their effect on people's buying power 偷换概念；D manifest the significant role of good habits 张冠李戴，例子讲习惯被「制造」而非习惯之「好」。",
        "note": "例证题抓例子前后的观点句 manufactured habits；例证目的要回到它服务的论点，D 用 good habits 的字面做文章，与「被制造的习惯」是两回事。",
    },
    1445: {
        "option": "正确项 C Unilever.：联合利华在文中只以「公司」身份出现（被求助的三巨头之一），并非塑造习惯的具体产品；而 Tide（洗衣液）、Crest 与 Colgate（牙膏）都是文中明确出现、与习惯塑造直接挂钩的产品——NOT 题找类别异项。",
        "note": "NOT 题先分「谁生产、谁被用」两个层面：Tide、Crest、Colgate 是直接塑造刷牙、洗衣习惯的产品名，Unilever 只是幕后公司；见到企业名与产品名混列，先归类再找异项。",
    },
    1446: {
        "option": "正确项 C commercial promotions：刷牙习惯源于 shrewd advertising（精明的广告）与品牌营销，属于商业推广的产物；A perfected art of products 无中生有，文中谈的是营销不是工艺；B automatic behavior creation 张冠李戴，那是企业想掌握的能力；D scientific experiments 张冠李戴，experiments 是研究者验证习惯机制的手段。",
        "note": "因果定位抓 because of：广告加公共卫生运动即商业推广；A 的 perfected art 是企业视角的迷雾，题干问的是消费者习惯因何形成。",
    },
    1447: {
        "option": "正确项 A indifferent：作者只客观呈现「广告造习惯的威力」与「引发的争议」两面事实，未作褒贬评判，态度是不偏不倚的；B negative 否定过度，ruthless 是描述性用词非作者断语；C positive 过度，作者未替广告唱赞歌；D biased 无端偏袒更无从谈起。",
        "note": "态度题找作者的评述动词：全文用 learn、emerge、erupt 等中性动词铺陈事实，无褒贬形容词出自作者之口；ruthless 出自转述语境，勿把引语色彩算到作者头上。",
    },
    1448: {
        "option": "正确项 D judgment should consider the opinion of the public：verdicts should represent the conscience of the community＝裁决要反映公众良知，即判决应考虑民意；A both literate and illiterate 与 minimum qualifications 中 literacy 门槛相悖；B defendants are immune 与 entitled to（有权获得）正反混淆；C no age limit 与 minimum qualifications of age 矛盾。",
        "note": "原则清单逐条核对：conscience of the community＝民意，D 是它的改写；A 把 literacy 门槛抹掉，B 把 entitled 读成 immune，正反核对即可排除；真题干即原文末句的原则列举句。",
    },
    1449: {
        "option": "正确项 A the inadequacy of antidiscrimination laws：遴选 elite/blue-ribbon 陪审团是 convenient way around antidiscrimination laws 的途径——法律能被绕开正说明存在漏洞；B the prevalent discrimination against certain races 偷换概念，被禁止的是歧视行为，暴露的是法律漏洞；C the conflicting ideals 与 D the arrogance 无中生有。",
        "note": "让步转折落点在后半句：法律早已禁止歧视却被绕开——问题出在法律不严密而非歧视「普遍存在」；a way around＝loophole 是本题钥匙词。",
    },
    1450: {
        "option": "正确项 A they were supposed to perform domestic duties：women were needed at home＝女性被认定应留在家中操持家务，即承担家庭职责；B they fell far short of the required qualifications 无中生有；C they tended to evade public engagement 无中生有，是州的做法而非女性意愿；D they were automatically banned by state laws 正反混淆，是自动豁免且可申请加入，并非法律禁止。",
        "note": "because 题抓 justified by the claim：州里的理由就是 women were needed at home，A 的 domestic duties 是它的同义改写；D 利用 automatically 一词偷换 exempt 与 ban。",
    },
    1523: {
        "option": "正确项 A is receiving more criticism：particularly scorned 对应 receiving more criticism，scorn 与 criticism 同义替换；B is no longer an educational ritual 无中生有，原文仍称其为教育惯例；C is not required for advanced courses 偷换概念，是新政策豁免高级课程的作业权重；D is gaining more preferences 与 never been terribly popular 矛盾，正反混淆。",
        "note": "imply 题看首段隐含义：nowadays 对应 in recent years，锁定 but 之后 scorned，作业「一直不受欢迎、近年更糟」；正确项把 scorn 名词化为 criticism，属词性转换式同义改写。",
    },
    1528: {
        "option": "正确项 A should not be the sole representation of girlhood：粉色虽不坏但 it is such a tiny slice of the rainbow——少女气质不应被粉色这一种象征垄断；B should not be associated with girls' innocence 无中生有；C cannot explain girls' lack of imagination 是对末句的字面拼贴；D cannot influence girls' lives and interests 正反混淆，首句已说粉色 pervasive。",
        "note": "句意题抓转折与后果：not intrinsically bad 让步之后，tiny slice of the rainbow 的言外之意是「不应只有这一种色彩」；复现原词 lack of imagination 的干扰项是把结论局部字面拼进题干，正确项是对作者言外之意的概括。",
    },
    1529: {
        "option": "正确项 A Blue used to be regarded as the colour for girls：blue...symbolised femininity 直接对应；B White is preferred by babies 偷换概念，all babies wore white as a practical matter 出于实用而非偏好；C Pink used to be a neutral colour 张冠李戴，粉色曾被视为更男性化，中性的是连衣裙；D Colours are encoded in girls' DNA 正反混淆，原文说 it is not。",
        "note": "判断题逐项核对第二段时间线：20 世纪前婴儿皆穿白→童装引入色彩时粉男蓝女→80 年代营销才逆转；只有蓝色象征女性一句能原样支撑选项，注意 practical matter 与 preferred 的语义差别。",
    },
    1530: {
        "option": "正确项 A the marketing of products for children：marketing trends dictated our perception 直接对应，幼儿期概念更是 popularised as a marketing trick；B researches into children's behaviour 正反混淆，作者明说 assumed...: wrong；C studies of childhood consumption 张冠李戴，那是 Cook 的学者身份；D the observation of children's nature 无中生有，原文说的是营销支配认知。",
        "note": "题干 influenced by 对应原文 dictated，先锁定第三段；破题点是冒号后的 wrong——作者自我纠正，否定「专家研究塑造认知」的常识；researches into children's behaviour 恰是被否定项，属「用原文原词设错」。",
    },
    1533: {
        "option": "正确项 A genes to be patentable：2010 年法官裁定基因不可专利后，公司 executives were violently agitated，BIO 安抚成员称这只是 a preliminary step in a longer battle——可见公司希望基因可继续获得专利；B the BIO to issue a warning 偷换概念，BIO 是 assured（安抚）而非警告；C their executives to be active 张冠李戴，agitated 是焦躁不安；D judges to rule out gene patenting 正反混淆，这一裁定恰是挫折而非愿望。",
        "note": "would like 的愿望要靠第一段情绪词反推：agitated 加 longer battle 说明公司立场是「要继续争取专利」；题干问意愿，别选成已发生的事实——judge ruled unpatentable 是已发生的挫折而非愿望。",
    },
    1534: {
        "option": "正确项 B only man-made products are patentable：它是 a gene is a product of nature 的等价换算——自然产物不可专利，即只有人造产物才能获专利；A genetic tests are not reliable 无中生有；C patents on genes depend much on innovation 正反混淆，原文是 suppress innovation；D courts should restrict access to genetic tests 偷换主语，动作主体是专利垄断而非法院。",
        "note": "三论据与选项逐一核对：只有论据一能换算出正确项；论据二的关键是 rather than（是压制不是奖励），干扰项恰反着说；论据三的 restrict access 主语是 patents' monopolies，干扰项把动作主体换成 courts。",
    },
    1535: {
        "option": "正确项 A discovering gene interactions：connecting the dots（把点连起来）正是上文 studying how genes interact 的比喻说法，介词 for 后的宾语即专利对象；B establishing disease correlations 偷换概念，correlations 是研究成果的用途，不是专利标的本身；C drawing pictures of genes 把习语 connecting the dots 字面化；D identifying human DNA 无中生有，原文说 most are already patented，此路已基本走完。",
        "note": "人名引语是定位点，connecting the dots 必须还原为上句 how genes interact——习语回指具体动作是本题钥匙；for 后的宾语才是专利对象，别把用途当成对象。",
    },
    1568: {
        "option": "正确项 A the impact of technological advances：笑话夸张呈现纺织厂的自动化程度，机器取代人力正是技术进步的影响，与第二段 the information technology revolution...replacing labor with machines 呼应；B the alleviation of job pressure 方向相反，人被机器取代意味着就业压力加剧；C the shrinkage of textile mills 偷换概念，笑话讲用工之少而非工厂规模萎缩；D the decline of middle-class incomes 张冠李戴，那是第二段的另一论点。",
        "note": "例证题找例子的指向：笑话夸张的是「几乎不需要工人」，指向自动化与技术进步；only two employees 是理解钥匙；the decline of middle-class incomes 出自第二段，属跨段拼接。",
    },
    1569: {
        "option": "正确项 D contribute something unique：find their extra、their unique value contribution、make themselves stand out 三处与「贡献独特价值」直接对应；A work on cheap software 张冠李戴，cheap software 是雇主可廉价获取的外部资源；B ask for a moderate salary 无中生有；C adopt an average lifestyle 正反混淆，原文宣告 average is officially over。",
        "note": "第三段论证链：average is officially over→雇主能廉价获得大量资源→Therefore 每人须找 extra；正确项落在 Therefore 总结句上；average 在本文是统一的否定信号词，含 average 的选项方向必错。",
    },
    1570: {
        "option": "正确项 B job opportunities are disappearing at a high speed：shed workers so fast 与 one out of every three manufacturing jobs disappeared 都指向岗位快速消失；A gains of technology have been erased 字面拼接，erased 的宾语是就业成果而非技术成果；C factories are making much less money 无中生有；D new jobs and services offered 答非所问，那是第五段内容。",
        "note": "引语题把动词与数字分开看：so fast、erased、disappeared 是速度与消失信号，one out of every three 佐证幅度；含原词 gains 的干扰项偷换了 gains 的归属，必须核对动词宾语。",
    },
    1573: {
        "option": "正确项 A stay in a foreign country temporarily：no intention to stay、make some money and then go home 前后呼应，候鸟式移民即短暂逗留者；B leave their home countries for good 正反混淆，for good 表永久，与候鸟回乡相反；C immigrate across the Atlantic 以偏概全，那只是百年前例子的路径；D find permanent jobs overseas 偷换概念，permanent 恰是定居一类的特征。",
        "note": "习语喻义题靠首段例子定义：候鸟者赚了钱就回乡；for good（永久地）是理解钥匙，它出现在 returned to Italy for good 中，含义与暂居相反。",
    },
    2083: {
        "option": "正确项 E：E 项即 Rexford 的原话——Charles E. Smith Jewish Day School 的升学指导主任说「填 Common App 无需列满 10 项活动」，与其引语 a huge laundry list of extracurriculars（冗长清单）同源；C Undertaking too many activities hardly a plus 与「重质不重量」同旨，但那是 Harberson 段的对应项，勿因同旨串段。",
        "note": "本单元纲领句 quality matters more than the number 统领全部匹配：Rexford 的「清单无用」说与 E 的「无需列满 10 项」同源；做匹配题先给每位专家贴一句话标签再对号，E 项句首的校名是归属铁证。",
    },
    2084: {
        "option": "正确项 C Undertaking too many extracurricular activities will hardly be seen as a plus by colleges：Harberson 强调质量重于数量——热门活动竞争更激烈、要做就做到最好（be the best at it），追求数量并非加分项；A 与 B 分别是 Kelley 段与 Gwyn 段的内容，E 则是 Rexford 段的对应项。",
        "note": "匹配题用排除法收尾：各选项逐一分段后，Harberson 的「热门活动要做到最好」落在 C 的「数量多不算加分」上；区分点在「质与量」——Rexford 管清单（E），Harberson 管质量（C）。",
    },
    2085: {
        "note": "Kelley 段题眼是 hook（招生官要的 quality or hook），distinguishing yourself in one focused type 与 A 的 specific activity 对应，especially for highly selective institutions 支撑 top-tier；做匹配题先贴标签再对号，specific 对 one focused type。",
    },
    2086: {
        "note": "Levine 段首句 Extracurricular activities related to the college major...are beneficial 已把 G 说尽，引语再具体化；与 A 区分看关键词——A 找 top-tier，G 找 major，各段唯一关键词是防串段的抓手。",
    },
}

# 仅恢复原始 note（去除警示后缀）的题
NOTE_ONLY = [1524, 1531, 1571, 1574, 2066, 1487, 1492, 1527, 1532, 1577, 1582, 1667]


def content_file(qid: int) -> str:
    chunk_no = qid // 25 + 1
    batch_no = (chunk_no - 1) // 20 + 1
    return os.path.join(CONTENT_DIR, "batch%d" % batch_no, "chunk_%03d.json" % chunk_no)


def file_item(qid: int) -> dict:
    with open(content_file(qid), encoding="utf-8") as f:
        data = json.load(f)
    for it in data["items"]:
        if it["question_id"] == qid:
            return it
    raise KeyError(qid)


def main() -> None:
    conn = sqlite3.connect(PATCHES_DB)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS patches ("
        "question_id INTEGER NOT NULL, field TEXT NOT NULL, value TEXT NOT NULL, "
        "PRIMARY KEY (question_id, field))"
    )
    conn.execute(
        "DELETE FROM patches WHERE question_id IN (%s)"
        % ",".join(str(q) for q in ALL_QIDS)
    )
    rows = []
    problems = []
    for qid, fields in FULL.items():
        for field, value in fields.items():
            if len(value) > MAX_LEN:
                problems.append("q%d %s 超长(%d)" % (qid, field, len(value)))
            rows.append((qid, field, value))
    for qid in NOTE_ONLY:
        note = str(file_item(qid).get("note") or "")
        if len(note) > MAX_LEN:
            problems.append("q%d note 超长(%d)" % (qid, len(note)))
        rows.append((qid, "note", note))
    if problems:
        conn.close()
        print("ABORT: %s" % "; ".join(problems))
        raise SystemExit(1)
    conn.executemany("INSERT OR REPLACE INTO patches (question_id, field, value) VALUES (?, ?, ?)", rows)
    conn.commit()
    main_conn = sqlite3.connect(MAIN_DB)
    synced = 0
    for qid, field, value in rows:
        cur = main_conn.execute(
            "UPDATE explain_collections SET content=? WHERE question_id=? AND fragment_type=?",
            (value, qid, field),
        )
        synced += cur.rowcount
    main_conn.commit()
    main_conn.close()
    conn.close()
    print("patch rows=%d (FULL %d 题, NOTE_ONLY %d 题), explain_collections synced=%d" % (
        len(rows), len(FULL), len(NOTE_ONLY), synced))
    print("CONTENT FIXES DONE")


if __name__ == "__main__":
    main()
