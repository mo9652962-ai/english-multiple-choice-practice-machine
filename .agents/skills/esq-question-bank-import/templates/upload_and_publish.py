"""ESQ 题库包上传 + 发布 (可复用模板)
用法: 改 FILES/PROFILE_ID, python upload_and_publish.py
注意: 先启动后端 python run_app.py; 上传路径是 /imports 不是 /upload!
"""
import json, os, uuid, urllib.request

BASE = "http://127.0.0.1:8765"
PROFILE_ID = 2  # 1考研一 2高中 3四级 4六级 5考研二
FILES = [
    r"C:\path\to\cn.gaokao.english.cloze.esq",
]

def multipart(fields: dict, filepath: str):
    boundary = uuid.uuid4().hex
    parts = []
    for k, v in fields.items():
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode())
    with open(filepath, "rb") as f:
        content = f.read()
    fname = os.path.basename(filepath)
    parts.append(
        f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{fname}"\r\n'
        f'Content-Type: application/octet-stream\r\n\r\n'.encode() + content + b'\r\n')
    parts.append(f'--{boundary}--\r\n'.encode())
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"

def api(path, method="GET", body=None, ctype="application/json"):
    data = json.dumps(body, ensure_ascii=False).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method,
                                 headers={"Content-Type": ctype})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())

for fp in FILES:
    body, ctype = multipart({"profile_id": str(PROFILE_ID)}, fp)
    try:
        d = api("/api/question-banks/imports", "POST", body, ctype)  # 路径是 /imports!
        jid = d.get("id")
        print(f"✅ 上传 {os.path.basename(fp)}: job={jid} profile={d.get('profile_id')}")
        pub = api(f"/api/question-banks/imports/{jid}/publish", "POST", {})
        print(f"  发布: {pub.get('published')} paperId={pub.get('papers',[{}])[0].get('paperId')} "
              f"题数={pub.get('papers',[{}])[0].get('questionCount')}")
    except urllib.error.HTTPError as e:
        print(f"❌ {os.path.basename(fp)}: {e.code} {e.read().decode()[:200]}")
