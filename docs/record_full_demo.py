import asyncio, os, shutil, subprocess
from playwright.async_api import async_playwright

async def record_demo():
    rec_dir = os.path.abspath('D:/english-multiple-choice-practice-machine/docs/video_record')
    # 清理旧视频
    if os.path.exists(rec_dir):
        shutil.rmtree(rec_dir)
    os.makedirs(rec_dir, exist_ok=True)

    url = 'file:///D:/english-multiple-choice-practice-machine/docs/index.html'

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=['--enable-gpu', '--use-gl=angle', '--enable-webgl']
        )
        context = await browser.new_context(
            viewport={'width': 1280, 'height': 720},
            record_video_dir=rec_dir,
            record_video_size={'width': 1280, 'height': 720}
        )
        page = await context.new_page()

        print("1. 加载墨题官网...")
        await page.goto(url, wait_until='networkidle')
        await page.wait_for_timeout(1500)

        # ===== 场景 1: 首屏 3D 生词磁吸排斥与水墨点击 =====
        print("2. 演示首屏 3D 生词力场磁斥与水墨涟漪...")
        # 鼠标在虚空中轻盈滑过，激起力场避让
        for x, y in [(350, 280), (600, 380), (880, 260), (500, 450)]:
            await page.mouse.move(x, y, steps=8)
            await page.wait_for_timeout(300)
        # 点击生成水墨扩散
        await page.mouse.click(640, 360)
        await page.wait_for_timeout(1000)

        # ===== 场景 2: 滚动驱动 3D 卷轴三维爆炸拆解 =====
        print("3. 滚动进入 3D 古卷解构...")
        narrative = page.locator('#narrative')
        await narrative.scroll_into_view_if_needed()
        await page.wait_for_timeout(1200)

        # 稍微推进滚轮，让 GSAP ScrollTrigger 展开分层
        await page.mouse.wheel(0, 250)
        await page.wait_for_timeout(1000)

        # 交互点击左侧层级卡片 Layer 01 / 02 / 03
        layer1 = page.locator('.layer-card').nth(2)
        if await layer1.count():
            await layer1.click()
            await page.wait_for_timeout(800)
        
        layer2 = page.locator('.layer-card').nth(1)
        if await layer2.count():
            await layer2.click()
            await page.wait_for_timeout(800)

        layer3 = page.locator('.layer-card').nth(0)
        if await layer3.count():
            await layer3.click()
            await page.wait_for_timeout(1000)

        # ===== 场景 3: 长难句语法透视与生词解析 =====
        print("4. 演示长难句语法透视与词汇解析...")
        sim = page.locator('#simulator')
        await sim.scroll_into_view_if_needed()
        await page.wait_for_timeout(800)

        # 点击切换语法骨架透视
        toggle_btn = page.locator('#btn-toggle-syntax')
        if await toggle_btn.count():
            await toggle_btn.click()
            await page.wait_for_timeout(600)
            await toggle_btn.click()
            await page.wait_for_timeout(600)

        # 点击生词 token (paradigm)
        token = page.locator('.word-token:has-text("paradigm")')
        if await token.count():
            await token.click()
            await page.wait_for_timeout(800)

        token2 = page.locator('.word-token:has-text("vulnerability")')
        if await token2.count():
            await token2.click()
            await page.wait_for_timeout(1000)

        # ===== 场景 4: 键盘极速做题工坊与五维雷达 =====
        print("5. 演示纯键盘做题手感与水墨能力雷达...")
        bench = page.locator('#practice-bench')
        await bench.scroll_into_view_if_needed()
        await page.wait_for_timeout(800)

        # 模拟键盘敲击 C 键秒选正解
        await page.keyboard.press('c')
        await page.wait_for_timeout(1200)

        # 模拟敲击空格键折叠/展开 AI 破题手记
        await page.keyboard.press('Space')
        await page.wait_for_timeout(600)
        await page.keyboard.press('Space')
        await page.wait_for_timeout(800)

        # 切换雷达图对比状态
        btn_before = page.locator('#btn-radar-before')
        if await btn_before.count():
            await btn_before.click()
            await page.wait_for_timeout(900)

        btn_after = page.locator('#btn-radar-after')
        if await btn_after.count():
            await btn_after.click()
            await page.wait_for_timeout(1000)

        # ===== 场景 5: 朱墨对勘主观题重塑对比 =====
        print("6. 演示朱墨对勘主观题重塑对比...")
        comp = page.locator('#comparison')
        await comp.scroll_into_view_if_needed()
        await page.wait_for_timeout(800)

        # 悬停在学术词组上触发双向高亮
        phrase = page.locator('.phrase-match.polished').first
        if await phrase.count():
            await phrase.hover()
            await page.wait_for_timeout(1200)

        # 切换到英译汉 Tab
        tab_trans = page.locator('#tab-trans')
        if await tab_trans.count():
            await tab_trans.click()
            await page.wait_for_timeout(1200)

        # ===== 场景 6: 3D 真题星系罗盘旋转与热力图 =====
        print("7. 演示 3D 真题星系罗盘与打卡热力图...")
        sphere = page.locator('#sphere')
        await sphere.scroll_into_view_if_needed()
        await page.wait_for_timeout(800)

        # 在 3D 球体上拖拽自转
        swrap = page.locator('#sphere-wrap')
        sbox = await swrap.bounding_box()
        if sbox:
            cx = sbox['x'] + sbox['width'] * 0.5
            cy = sbox['y'] + sbox['height'] * 0.5
            await page.mouse.move(cx, cy)
            await page.mouse.down()
            await page.mouse.move(cx - 160, cy - 40, steps=15)
            await page.mouse.up()
            await page.wait_for_timeout(1200)

        # 悬停打卡热力图单元格
        heat_cell = page.locator('.heat-cell.heat-l4').first
        if await heat_cell.count():
            await heat_cell.hover()
            await page.wait_for_timeout(600)

        # ===== 场景 7: 夜读模式切换与下载收官 =====
        print("8. 演示玄色夜读黑金模式切换与尾屏下载...")
        # 点击右上角主题切换按钮
        theme_btn = page.locator('#theme-btn')
        if await theme_btn.count():
            await theme_btn.click()
            await page.wait_for_timeout(1500)

        # 滚动到底部查看 Windows / Android / Web 开源卡片
        dl = page.locator('#download')
        await dl.scroll_into_view_if_needed()
        await page.wait_for_timeout(1800)

        # 稍稍回滚定格
        await page.mouse.wheel(0, -300)
        await page.wait_for_timeout(1200)

        print("9. 录制完成，关闭浏览器封包视频...")
        await context.close()
        await browser.close()

    # 寻找生成的 webm
    webms = [f for f in os.listdir(rec_dir) if f.endswith('.webm')]
    if webms:
        src_webm = os.path.join(rec_dir, webms[0])
        print("Source WebM recorded:", src_webm, "Size:", os.path.getsize(src_webm))
        return src_webm
    else:
        print("No WebM generated!")
        return None

if __name__ == '__main__':
    asyncio.run(record_demo())
