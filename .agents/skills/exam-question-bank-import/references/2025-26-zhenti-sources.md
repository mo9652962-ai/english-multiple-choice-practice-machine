# 2025-26 真题源侦察记录（2026-08 实测）

> 结论先行：2025-2026 完整真题基本被登录墙/网盘/图片挡住——网页可抓文本的极少。
> 能完整导入的路径 = 网盘 PDF/MP3（用户下载）→ 已建导入管线批量解析。

## 各源实测结论

| 源 | 实测结果 |
|:---|:---|
| en-sky.com post/1237（2026 II 卷）| 只有百度网盘链接（pwd=8888）——百度网盘命令行不可下载（需登录）|
| en-sky post/1238（2026 I 卷）| 页面含全文（已用此导入 I 卷 45 题）——**I 卷网页有全文，II 卷没有** |
| cc518.com/article.php?id=7304 | **2026 I+II 卷 PDF+答案+听力 MP3 全套**——夸克网盘 `pan.quark.cn/s/98724fa5ca85` |
| 新东方 cet4-6.xdf.cn（2025.12 四六级）| 听力页：完整材料+选项但**缺题干+答案**；阅读页："紧急整理更新中"（空）；翻译/作文有全文（非客观题）|
| 启航 jixun.iqihang.com（2026 考研）| 真题内容是图片（aged-jixun-cdn PNG 截图）——需 OCR |
| B 站真题讲解视频 | `player/v2` API 返回 subtitle 空——无字幕可提取 |
| 163.com 估分文章 | 内容是 I 卷（不是 II 卷）——网络整理的"II 卷"实为 I 卷+零散答案 |

## 夸克网盘免登录探索（失败路径记录——避免重复踩）

- 分享 token：`POST https://pan.quark.cn/1/clouddrive/share/sharepage/token` body `{"pwd_id":"...","passcode":""}` → `data.stoken`（**每次请求都要重新拿**，stoken 一次性/会失效）
- 文件列表：`GET .../sharepage/detail?pwd_id=X&stoken=Y` → data.list（顶层）
- 子文件夹：detail 带 `&fid=` 返回的还是顶层（不支持）
- 下载：`/1/clouddrive/share/sharepage/list`（GET/POST 均 404）——**夸克免登录下载不支持**（研究确认：夸克=免登录✗）
- 工具 QuarkPanTool/quarkdownloaderpro 都要登录 Cookie/扫码

## Cloudreve 云解析服务（lz.qaiu.top，netdisk-fast-download 公共实例）

- 顶层文件：`/json/parser?url=<URL编码>&pwd=` → 文件夹场景报 "没有可下载的文件（可能都是文件夹）"
- **文件夹列表：`/v2/getFileList?url=<编码>&pwd=&dirId=<fileId>` → code:200 data:[{fileName,fileId,size,...}]**（可用！）
  - 不带 dirId 返回顶层；带 dirId=顶层文件夹 fid 递归出 16 个文件（PDF/MP3/xlsx）
- 文件下载：`/v2/parser` 报 "No enum constant for type name: v2"；`/parser` 报 "Cloudreve-ce ... 500"
  → **文件夹内文件下载不支持**（Cloudreve 限制）——只能列目录

## 环球网校四六级 PDF 自动下载（2026-08 实测可行 ✅）

> 网页可抓的少数完整 PDF 源（免登录）——但内容是**考生回忆版**。

- 资料列表页：`https://m.hqwx.com/ziliao/class_cet`（web_extract 可列出全部 PDF——2026.6 四级/六级全卷、各题型、2025.12 六级完整版）
- 下载页模式：`https://m.hqwx.com/ziliao/cet/<id>.html`（如 1412565=2026.6 四级全卷 425KB / 1413121=六级全卷 462KB / 1285096=2025.12 六级完整版 541KB）
- **直链提取**：下载页 HTML 里 regex `https?://[^"]+\.pdf[^"]*` → 实际是 `https://oss-hqwx-video.hqwx.com/<文件名>_<40位hash>.pdf` → **curl 直接下载**（无需登录/cookie）
- 下载后**先查文本层**：`pip install pymupdf` → `sum(len(p.get_text()) for p in doc)`（回忆版全有文本层——非扫描）
- **内容局限（回忆版）**：
  - 听力：**材料完整 + 题干（Q1:...）+ 答案**（第一套 1-25 完整）——**但缺 3 个干扰选项**（只有正确选项文本）→ 无法构建 4 选 1 客观题
  - 阅读：有选项+答案但**无文章原文**（长段落仅 1 个=开头）→ 不可导入
  - 结论：**只能做材料/答案参考，不能直接导入做题**——正式导入仍需含完整选项的网盘完整版 PDF

## 可行路径（给用户）

1. 用户浏览器打开夸克分享链接（小文件可能免登录直接下；大文件需登录夸克——免费）→ 发路径
2. 我跑已验证的导入管线（PDF 解析 → 45 题/卷 → 3 库同步 + APK）
3. 听力 MP3 可挂到听力精听（units.audio_path + /audio 静态挂载已就绪）

## 词汇数据源补充

- KyleBing/english-vocabulary：高中/四级/六级/考研乱序 txt（`单词\t释义`），raw URL 需 URL 编码中文文件名
- exam-data/NETEMVocabulary：考研 5530 词词频排序 json（真高频——200 套真题统计）
- mahavivo/english-wordlists：多格式备选（含 NPEE_Wordlist.txt）
