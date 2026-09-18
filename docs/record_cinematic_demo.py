import asyncio, os, shutil, subprocess
from playwright.async_api import async_playwright

async def record_cinematic_demo():
    rec_dir = os.path.abspath('D:/english-multiple-choice-practice-machine/docs/video_record')
    if os.path.exists(rec_dir):
        shutil.rmtree(rec_dir)
    os.makedirs(rec_dir, exist_ok=True)

    url = 'file:///D:/english-multiple-choice-practice-machine/docs/index.html'

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                '--enable-gpu',
                '--use-gl=angle',
                '--enable-webgl',
                '--font-render-hinting=none',
                '--disable-font-subpixel-positioning'
            ]
        )
        context = await browser.new_context(
            viewport={'width': 1280, 'height': 720},
            record_video_dir=rec_dir,
            record_video_size={'width': 1280, 'height': 720}
        )
        page = await context.new_page()

        print("1. 加载墨题官网并注入电影级演示增强组件...")
        await page.goto(url, wait_until='networkidle')

        # 注入虚拟发光光标与底部功能讲解 HUD 浮窗
        await page.evaluate('''() => {
            // 1. 虚拟光标
            const cur = document.createElement('div');
            cur.id = 'virtual-cursor';
            cur.style.cssText = `
                position: fixed;
                width: 22px;
                height: 22px;
                border-radius: 50%;
                background: rgba(199, 62, 58, 0.75);
                border: 2px solid #ffffff;
                box-shadow: 0 2px 10px rgba(0,0,0,0.3);
                pointer-events: none;
                z-index: 999999;
                transform: translate(-50%, -50%);
                transition: transform 0.08s ease, width 0.15s ease, height 0.15s ease, background 0.15s ease;
            `;
            document.body.appendChild(cur);

            window.addEventListener('mousemove', (e) => {
                cur.style.left = e.clientX + 'px';
                cur.style.top = e.clientY + 'px';
            });
            window.addEventListener('mousedown', () => {
                cur.style.transform = 'translate(-50%, -50%) scale(0.75)';
                cur.style.background = '#c73e3a';
            });
            window.addEventListener('mouseup', () => {
                cur.style.transform = 'translate(-50%, -50%) scale(1)';
                cur.style.background = 'rgba(199, 62, 58, 0.75)';
            });

            // 2. 底部功能讲解 HUD 标签
            const hud = document.createElement('div');
            hud.id = 'demo-hud';
            hud.style.cssText = `
                position: fixed;
                bottom: 24px;
                left: 50%;
                transform: translateX(-50%);
                background: rgba(36, 34, 29, 0.88);
                backdrop-filter: blur(16px);
                border: 1px solid rgba(255, 255, 255, 0.18);
                color: #ffffff;
                padding: 10px 24px;
                border-radius: 30px;
                font-size: 14px;
                font-weight: 600;
                letter-spacing: 0.5px;
                box-shadow: 0 8px 32px rgba(0,0,0,0.35);
                pointer-events: none;
                z-index: 999998;
                display: flex;
                align-items: center;
                gap: 10px;
                transition: all 0.35s cubic-bezier(0.22, 1, 0.36, 1);
            `;
            const dot = document.createElement('span');
            dot.style.cssText = 'width:8px;height:8px;border-radius:50%;background:#c73e3a;';
            const label = document.createElement('span');
            label.id = 'hud-text';
            label.textContent = '墨题 MOTI · 东方水墨 3D 沉浸式官网';
            hud.appendChild(dot);
            hud.appendChild(label);
            document.body.appendChild(hud);

            window.updateHUD = function(text, color = '#c73e3a') {
                const el = document.getElementById('hud-text');
                const dot = hud.querySelector('span:first-child');
                if (el) el.textContent = text;
                if (dot) dot.style.background = color;
                hud.style.transform = 'translateX(-50%) scale(1.05)';
                setTimeout(() => { hud.style.transform = 'translateX(-50%) scale(1)'; }, 200);
            };
        }''')

        # 辅助函数：平滑滚动（电影级阻尼插值，彻底告别突兀瞬移）
        async def smooth_scroll(target_y, duration=1.0, steps=25):
            current_y = await page.evaluate('window.scrollY')
            delta = target_y - current_y
            for i in range(1, steps + 1):
                progress = i / steps
                # easeInOutCubic 缓动
                ease = 4 * progress * progress * progress if progress < 0.5 else 1 - pow(-2 * progress + 2, 3) / 2
                y = current_y + delta * ease
                await page.evaluate(f'window.scrollTo(0, {y})')
                await asyncio.sleep(duration / steps)

        # 辅助移动鼠标函数
        async def move_mouse(x, y, steps=15):
            await page.mouse.move(x, y, steps=steps)

        await page.wait_for_timeout(1000)

        # ===== 场景 1: 首屏 3D 生词力场排斥与水墨互动 =====
        print("2. [Scene 1] 首屏 3D 生词力场排斥...")
        await page.evaluate('updateHUD("Act I · 3D 生词力场与水墨微粒磁斥避让", "#c73e3a")')
        
        # 光标优雅拂过生词，触发 3D 避让
        await move_mouse(320, 260)
        await page.wait_for_timeout(350)
        await move_mouse(640, 360)
        await page.wait_for_timeout(350)
        await move_mouse(880, 240)
        await page.wait_for_timeout(350)
        await move_mouse(520, 480)
        await page.wait_for_timeout(350)
        
        # 居中水墨点击，激发水墨涟漪
        await page.mouse.click(640, 380)
        await page.wait_for_timeout(900)

        # ===== 场景 2: 滚动驱动 3D 卷轴三维爆炸拆解 =====
        print("3. [Scene 2] 3D 古卷三维爆炸拆解...")
        await page.evaluate('updateHUD("Act II · GSAP 滚动驱动 · 3D 试卷古卷爆炸解构", "#a8842f")')
        await smooth_scroll(750, duration=1.4)
        await page.wait_for_timeout(800)

        # 鼠标移动到 3D 爆炸画布上，微幅拖拽环视
        await move_mouse(820, 400)
        await page.mouse.down()
        await move_mouse(720, 340, steps=18)
        await page.mouse.up()
        await page.wait_for_timeout(700)

        # 依次点击左侧 Layer 01 / 02 / 03 联动
        layer1 = page.locator('.layer-card').nth(2)
        if await layer1.count():
            await move_mouse(300, 460)
            await layer1.click()
            await page.wait_for_timeout(700)

        layer2 = page.locator('.layer-card').nth(1)
        if await layer2.count():
            await move_mouse(300, 360)
            await layer2.click()
            await page.wait_for_timeout(700)

        layer3 = page.locator('.layer-card').nth(0)
        if await layer3.count():
            await move_mouse(300, 260)
            await layer3.click()
            await page.wait_for_timeout(800)

        # ===== 场景 3: 长难句水墨语法透视模拟器 =====
        print("4. [Scene 3] 长难句语法透视与词汇解析...")
        await page.evaluate('updateHUD("Act II.2 · 考研长难句水墨语法骨架透视", "#5c7a52")')
        await smooth_scroll(1200, duration=1.1)
        await page.wait_for_timeout(700)

        # 点击切换语法骨架
        btn_syntax = page.locator('#btn-toggle-syntax')
        if await btn_syntax.count():
            box = await btn_syntax.bounding_box()
            if box:
                await move_mouse(box['x'] + box['width']/2, box['y'] + box['height']/2)
                await btn_syntax.click()
                await page.wait_for_timeout(600)
                await btn_syntax.click()
                await page.wait_for_timeout(600)

        # 点击单词 paradigm
        token = page.locator('.word-token:has-text("paradigm")')
        if await token.count():
            tbox = await token.bounding_box()
            if tbox:
                await move_mouse(tbox['x'] + tbox['width']/2, tbox['y'] + tbox['height']/2)
                await token.click()
                await page.wait_for_timeout(800)

        # 点击单词 scrutiny
        token_scrutiny = page.locator('.word-token:has-text("scrutiny")')
        if await token_scrutiny.count():
            sbox = await token_scrutiny.bounding_box()
            if sbox:
                await move_mouse(sbox['x'] + sbox['width']/2, sbox['y'] + sbox['height']/2)
                await token_scrutiny.click()
                await page.wait_for_timeout(900)

        # ===== 场景 4: 键盘极速做题工坊与五维雷达 =====
        print("5. [Scene 4] 键盘极速流做题与五维水墨雷达...")
        await page.evaluate('updateHUD("Act II.5 · 键盘极速刷题 [C] 正解 · 五维能力雷达", "#c73e3a")')
        await smooth_scroll(1720, duration=1.1)
        await page.wait_for_timeout(800)

        # 敲击键盘 C 键秒选正解并展开 AI 破题手记
        await move_mouse(400, 360)
        await page.keyboard.press('c')
        await page.wait_for_timeout(1200)

        # 敲击 Space 演示 AI 抽屉折叠与再展开
        await page.keyboard.press('Space')
        await page.wait_for_timeout(500)
        await page.keyboard.press('Space')
        await page.wait_for_timeout(700)

        # 右侧五维雷达切换
        btn_before = page.locator('#btn-radar-before')
        if await btn_before.count():
            bbox = await btn_before.bounding_box()
            if bbox:
                await move_mouse(bbox['x'] + bbox['width']/2, bbox['y'] + bbox['height']/2)
                await btn_before.click()
                await page.wait_for_timeout(800)

        btn_after = page.locator('#btn-radar-after')
        if await btn_after.count():
            abox = await btn_after.bounding_box()
            if abox:
                await move_mouse(abox['x'] + abox['width']/2, abox['y'] + abox['height']/2)
                await btn_after.click()
                await page.wait_for_timeout(900)

        # ===== 场景 5: 朱墨对勘主观题重塑对比 =====
        print("6. [Scene 5] 朱墨对勘主观题重塑...")
        await page.evaluate('updateHUD("Act II.8 · 朱墨对勘 · 主观题双向高亮重塑", "#c73e3a")')
        await smooth_scroll(2300, duration=1.2)
        await page.wait_for_timeout(800)

        # 鼠标悬停在右侧学术词组上触发双向高亮
        phrase = page.locator('.phrase-match.polished').first
        if await phrase.count():
            pbox = await phrase.bounding_box()
            if pbox:
                await move_mouse(pbox['x'] + pbox['width']/2, pbox['y'] + pbox['height']/2)
                await page.wait_for_timeout(1100)

        # 切换到英译汉 Tab
        tab_trans = page.locator('#tab-trans')
        if await tab_trans.count():
            tbox = await tab_trans.bounding_box()
            if tbox:
                await move_mouse(tbox['x'] + tbox['width']/2, tbox['y'] + tbox['height']/2)
                await tab_trans.click()
                await page.wait_for_timeout(1100)

        # ===== 场景 6: 3D 真题星系罗盘与打卡热力图 =====
        print("7. [Scene 6] 3D 真题星系与打卡热力图...")
        await page.evaluate('updateHUD("Act III · 3D 斐波那契球面罗盘 · 考研打卡矩阵", "#5c7a52")')
        await smooth_scroll(2850, duration=1.2)
        await page.wait_for_timeout(800)

        # 拖拽 3D 旋转球体
        swrap = page.locator('#sphere-wrap')
        sbox = await swrap.bounding_box()
        if sbox:
            cx = sbox['x'] + sbox['width'] * 0.5
            cy = sbox['y'] + sbox['height'] * 0.5
            await move_mouse(cx, cy)
            await page.mouse.down()
            await move_mouse(cx - 200, cy - 50, steps=20)
            await page.mouse.up()
            await page.wait_for_timeout(1100)

        # 悬停打卡热力图
        heat_cell = page.locator('.heat-cell.heat-l4').first
        if await heat_cell.count():
            hbox = await heat_cell.bounding_box()
            if hbox:
                await move_mouse(hbox['x'] + hbox['width']/2, hbox['y'] + hbox['height']/2)
                await page.wait_for_timeout(600)

        # ===== 场景 7: 玄色夜读模式切换与下载收官 =====
        print("8. [Scene 7] 玄色夜读黑金模式切换与尾屏下载...")
        await page.evaluate('updateHUD("Act IV · 一键切换「玄色夜读」黑金水墨模式", "#d4554a")')
        
        # 鼠标优雅移至右上角切换主题
        theme_btn = page.locator('#theme-btn')
        if await theme_btn.count():
            thbox = await theme_btn.bounding_box()
            if thbox:
                await move_mouse(thbox['x'] + thbox['width']/2, thbox['y'] + thbox['height']/2)
                await theme_btn.click()
                await page.wait_for_timeout(1400)

        # 滚动到底部查看下载卡片
        await page.evaluate('updateHUD("入书院，登金榜 · Windows / Android / Web 开源交付", "#ffffff")')
        await smooth_scroll(3380, duration=1.2)
        await page.wait_for_timeout(1800)

        # 缓缓上滑定格优雅收官
        await smooth_scroll(3050, duration=0.8)
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
    asyncio.run(record_cinematic_demo())
