#!/usr/bin/env python3
"""v1.0: 全端同步发布脚本 — 前后端 + Windows + APK 一次构建发布
用法: python scripts/release_all.py 2.0.0-beta.11 "发布说明标题" "详细说明"

流程（严格执行顺序）:
  1. 前端 build (frontend/dist)
  2. 后端 PyInstaller 重建 (backend/dist/backend_app) ← 关键! 后端 exe 必须每次重建
  3. electron 版本 bump + electron-builder --win
  4. Authenticode 签名
  5. gh release create (GitHub + 自动双源)
  6. APK: cap sync + gradle assembleDebug → 桌面
  7. 分发包 zip
"""
import json
import os
import shutil
import subprocess
import sys
import zipfile

ROOT = r"D:\english-multiple-choice-practice-machine"
CERT_THUMBPRINT = "227BFE4360866350CCDE133BA2A6E141F7A50E0E"
REPO = "mo9652962-ai/epm-releases"

def run(cmd, cwd=None, timeout=600):
    print(f"\n>>> {cmd[:120]}")
    r = subprocess.run(cmd, shell=True, cwd=cwd or ROOT, timeout=timeout)
    if r.returncode != 0:
        print(f"❌ 失败: {cmd[:80]} (exit {r.returncode})")
        sys.exit(1)
    return r

def main():
    if len(sys.argv) < 3:
        print("用法: python scripts/release_all.py <版本> <标题> [说明]")
        print("示例: python scripts/release_all.py 2.0.0-beta.11 \"修复XXX\" \"详细说明\"")
        sys.exit(2)
    version = sys.argv[1]
    title = sys.argv[2]
    notes = sys.argv[3] if len(sys.argv) > 3 else title

    frontend = os.path.join(ROOT, "frontend")
    backend = os.path.join(ROOT, "backend")
    electron = os.path.join(ROOT, "electron")
    dist = os.path.join(electron, "dist")

    # 0. 版本一致性
    pkg = json.load(open(os.path.join(electron, "package.json"), encoding="utf-8"))
    old = pkg["version"]
    print(f"旧版本: {old} → 新版本: {version}")
    if old == version:
        print("⚠️ 版本相同，确认继续 (Ctrl+C 取消)")
        input("回车继续...")

    # 1. 前端
    run("npm run build", cwd=frontend)

    # 2. 后端 PyInstaller (每次发布必须重建!)
    run("python -m PyInstaller backend_app.spec --noconfirm", cwd=backend)

    # 3. electron 版本 + 打包
    pkg["version"] = version
    json.dump(pkg, open(os.path.join(electron, "package.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print(f"✅ package.json → {version}")
    run("npx electron-builder --win", cwd=electron)

    # 4. 签名
    setup = os.path.join(dist, f"epm-setup-{version}.exe")
    portable = os.path.join(dist, f"epm-portable-{version}.exe")
    if os.path.exists(setup) and os.path.exists(portable):
        ps = (
            f"$cert = Get-ChildItem Cert:\\CurrentUser\\My | Where-Object {{ $_.Thumbprint -eq '{CERT_THUMBPRINT}' }}; "
            f"foreach ($f in @('{setup}', '{portable}')) {{ "
            f"$r = Set-AuthenticodeSignature -FilePath $f -Certificate $cert -HashAlgorithm SHA256; "
            f"Write-Host ($f + ': ' + $r.Status) }}"
        )
        run(f'powershell -NoProfile -Command "{ps}"', cwd=dist)

    # 5. 发布 GitHub Release
    assets = (f"{setup} {setup}.blockmap {portable} latest.yml")
    run(
        f'gh release create v{version} {assets} --repo {REPO} '
        f'--title "{title}" --notes "{notes}"',
        cwd=dist,
    )
    print(f"✅ 发布: https://github.com/{REPO}/releases/tag/v{version}")

    # 6. APK 同步（前后端同步: 前端 dist 进 APK）
    if os.path.isdir(os.path.join(frontend, "android")):
        env = os.environ.copy()
        env["JAVA_HOME"] = r"C:\Users\31954\jdk21"
        env["ANDROID_HOME"] = r"C:\Users\31954\android-sdk"
        subprocess.run("npx cap sync android", shell=True, cwd=frontend, env=env)
        ps = (
            "Set-Location 'D:\\english-multiple-choice-practice-machine\\frontend\\android'; "
            "$env:JAVA_HOME='C:\\Users\\31954\\jdk21'; "
            "& '.\\gradlew.bat' assembleDebug --no-daemon | Select-Object -Last 3"
        )
        run(f'powershell -NoProfile -Command "{ps}"')
        apk = os.path.join(frontend, "android", "app", "build", "outputs", "apk", "debug", "app-debug.apk")
        if os.path.exists(apk):
            desk = os.path.join(os.path.expanduser("~"), "Desktop", f"墨题英语刷题机-{version}.apk")
            shutil.copy2(apk, desk)
            print(f"✅ APK → {desk}")

    # 7. 分发包
    if os.path.exists(setup):
        zip_path = os.path.join(electron, f"内测分发包-v{version}.zip")
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in (setup, os.path.join(electron, "一键信任设置.bat")):
                if os.path.exists(f):
                    zf.write(f, os.path.basename(f))
        print(f"✅ 分发包 → {zip_path}")

    print("\n🎉 全端同步发布完成!")
    print(f"  版本: {version}")
    print(f"  Release: https://github.com/{REPO}/releases/tag/v{version}")
    print(f"  产物: {dist}")

if __name__ == "__main__":
    main()
