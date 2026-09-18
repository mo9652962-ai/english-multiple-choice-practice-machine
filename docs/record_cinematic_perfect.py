import asyncio, os, shutil, subprocess, wave, math, struct
from playwright.async_api import async_playwright

async def run_cinematic_perfect():
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

        print("1. 加载官网...")
        await page.goto(url)
        await page.wait_for_load_state('networkidle')
        await page.wait_for_timeout(1000)

        # 注入高阶动态虚拟光标与底部 HUD
        await page.evaluate('''() => {
            const cur = document.createElement('div');
            cur.id = 'demo-cursor';
            cur.style.cssText = `
                position: fixed;
                width: 22px;
                height: 22px;
                border-radius: 50%;
                background: rgba(199, 62, 58, 0.85);
                border: 2px solid #ffffff;
                box-shadow: 0 0 16px rgba(199, 62, 58, 0.9), 0 4px 10px rgba(0,0,0,0.3);
                pointer-events: none;
                z-index: 999999;
                transform: translate(-50%, -50%);
                transition: transform 0.15s ease, background 0.2s ease;
                left: 640px;
                top: 360px;
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
                cur.style.background = 'rgba(199, 62, 58, 0.85)';
            });

            const hud = document.createElement('div');
            hud.id = 'demo-hud';
            hud.style.cssText = `
                position: fixed;
                bottom: 24px;
                left: 50%;
                transform: translateX(-50%);
                background: rgba(36, 34, 29, 0.92);
                backdrop-filter: blur(16px);
                border: 1px solid rgba(255, 255, 255, 0.2);
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

        async def smooth_scroll(target_y, duration=1.2, steps=30):
            current_y = await page.evaluate('window.scrollY')
            delta = target_y - current_y
            for i in range(1, steps + 1):
                progress = i / steps
                ease = 4 * progress * progress * progress if progress < 0.5 else 1 - pow(-2 * progress + 2, 3) / 2
                y = current_y + delta * ease
                await page.evaluate(f'window.scrollTo(0, {y})')
                await asyncio.sleep(duration / steps)

        async def move_mouse(x, y, steps=15):
            await page.mouse.move(x, y, steps=steps)

        # ===== 场景 1: 首屏 3D 生词力场排斥与水墨互动 (0s ~ 4.5s) =====
        print("2. [Scene 1] 首屏 3D 生词力场排斥...")
        await page.evaluate('updateHUD("Act I · 3D 生词力场与水墨微粒磁斥避让", "#c73e3a")')
        await move_mouse(340, 280)
        await page.wait_for_timeout(350)
        await move_mouse(640, 360)
        await page.wait_for_timeout(350)
        await move_mouse(860, 260)
        await page.wait_for_timeout(350)
        await move_mouse(500, 460)
        await page.wait_for_timeout(350)
        await page.mouse.click(640, 380)
        await page.wait_for_timeout(800)

        # ===== 场景 2: 3D 古卷三维爆炸拆解 (定位至 920px 居中) =====
        print("3. [Scene 2] 3D 古卷三维爆炸拆解 (定位至 920px)...")
        await page.evaluate('updateHUD("Act II · GSAP 滚动驱动 · 3D 试卷古卷爆炸解构", "#a8842f")')
        await smooth_scroll(920, duration=1.2)
        await page.wait_for_timeout(700)

        # 鼠标拖拽 3D 画布
        await move_mouse(950, 380)
        await page.mouse.down()
        await move_mouse(820, 280, steps=15)
        await page.mouse.up()
        await page.wait_for_timeout(600)

        # 点击 Layer 01 / 02 / 03
        layer1 = page.locator('.layer-card').nth(2)
        if await layer1.count():
            lbox = await layer1.bounding_box()
            if lbox:
                await move_mouse(lbox['x'] + 100, lbox['y'] + 30)
                await layer1.click()
                await page.wait_for_timeout(600)

        layer2 = page.locator('.layer-card').nth(1)
        if await layer2.count():
            lbox = await layer2.bounding_box()
            if lbox:
                await move_mouse(lbox['x'] + 100, lbox['y'] + 30)
                await layer2.click()
                await page.wait_for_timeout(600)

        layer3 = page.locator('.layer-card').nth(0)
        if await layer3.count():
            lbox = await layer3.bounding_box()
            if lbox:
                await move_mouse(lbox['x'] + 100, lbox['y'] + 30)
                await layer3.click()
                await page.wait_for_timeout(700)

        # ===== 场景 3: 长难句语法透视演示窗 (定位至 1350px 居中) =====
        print("4. [Scene 3] 长难句语法透视与词汇解析 (定位至 1350px)...")
        await page.evaluate('updateHUD("Act II.2 · 考研长难句水墨语法骨架透视", "#5c7a52")')
        await smooth_scroll(1350, duration=1.0)
        await page.wait_for_timeout(600)

        btn_syntax = page.locator('#btn-toggle-syntax')
        if await btn_syntax.count():
            sbox = await btn_syntax.bounding_box()
            if sbox:
                await move_mouse(sbox['x'] + sbox['width']/2, sbox['y'] + sbox['height']/2)
                await btn_syntax.click()
                await page.wait_for_timeout(600)
                await btn_syntax.click()
                await page.wait_for_timeout(600)

        token = page.locator('.word-token:has-text("paradigm")')
        if await token.count():
            tbox = await token.bounding_box()
            if tbox:
                await move_mouse(tbox['x'] + tbox['width']/2, tbox['y'] + tbox['height']/2)
                await token.click()
                await page.wait_for_timeout(800)

        token_scrutiny = page.locator('.word-token:has-text("scrutiny")')
        if await token_scrutiny.count():
            scbox = await token_scrutiny.bounding_box()
            if scbox:
                await move_mouse(scbox['x'] + scbox['width']/2, scbox['y'] + scbox['height']/2)
                await token_scrutiny.click()
                await page.wait_for_timeout(800)

        # ===== 场景 4: 键盘极速做题工坊与五维雷达 (定位至 2150px 居中) =====
        print("5. [Scene 4] 键盘极速流做题与五维水墨雷达 (定位至 2150px)...")
        await page.evaluate('updateHUD("Act II.5 · 键盘极速刷题 [C] 正解 · 五维能力雷达", "#c73e3a")')
        await smooth_scroll(2150, duration=1.1)
        await page.wait_for_timeout(700)

        # 鼠标移动到选项 C 区域，并敲击键盘 C 键秒选
        opt_c = page.locator('.option-item[data-key="C"]')
        if await opt_c.count():
            cbox = await opt_c.bounding_box()
            if cbox:
                await move_mouse(cbox['x'] + 150, cbox['y'] + cbox['height']/2)
        
        await page.keyboard.press('c')
        await page.wait_for_timeout(1100)

        # 敲击 Space 折叠与展开 AI 破题手记抽屉
        await page.keyboard.press('Space')
        await page.wait_for_timeout(500)
        await page.keyboard.press('Space')
        await page.wait_for_timeout(800)

        # 鼠标移至右侧雷达图，点击切换“传统刷题”与“墨题三周强化”对比
        btn_before = page.locator('#btn-radar-before')
        if await btn_before.count():
            bbox = await btn_before.bounding_box()
            if bbox:
                await move_mouse(bbox['x'] + bbox['width']/2, bbox['y'] + bbox['height']/2)
                await btn_before.click()
                await page.wait_for_timeout(600)
        
        btn_after = page.locator('#btn-radar-after')
        if await btn_after.count():
            abox = await btn_after.bounding_box()
            if abox:
                await move_mouse(abox['x'] + abox['width']/2, abox['y'] + abox['height']/2)
                await btn_after.click()
                await page.wait_for_timeout(700)

        # ===== 场景 5: 朱墨对勘主观题重塑 (定位至 3040px 居中) =====
        print("6. [Scene 5] 朱墨对勘主观题重塑 (定位至 3040px)...")
        await page.evaluate('updateHUD("Act II.8 · 朱墨对勘 · 主观题双向高亮重塑", "#c73e3a")')
        await smooth_scroll(3040, duration=1.1)
        await page.wait_for_timeout(700)

        phrase = page.locator('.phrase-match.polished').first
        if await phrase.count():
            pbox = await phrase.bounding_box()
            if pbox:
                await move_mouse(pbox['x'] + pbox['width']/2, pbox['y'] + pbox['height']/2)
                await page.wait_for_timeout(1000)

        tab_trans = page.locator('#tab-trans')
        if await tab_trans.count():
            tbox = await tab_trans.bounding_box()
            if tbox:
                await move_mouse(tbox['x'] + tbox['width']/2, tbox['y'] + tbox['height']/2)
                await tab_trans.click()
                await page.wait_for_timeout(1000)

        # ===== 场景 6: 3D 真题星系罗盘与打卡热力图 (定位至 3920px 居中) =====
        print("7. [Scene 6] 3D 真题星系与打卡热力图 (定位至 3920px)...")
        await page.evaluate('updateHUD("Act III · 3D 斐波那契球面罗盘 · 考研打卡矩阵", "#5c7a52")')
        await smooth_scroll(3920, duration=1.1)
        await page.wait_for_timeout(700)

        swrap = page.locator('#sphere-wrap')
        sbox = await swrap.bounding_box()
        if sbox:
            cx = sbox['x'] + sbox['width'] * 0.5
            cy = sbox['y'] + sbox['height'] * 0.5
            await move_mouse(cx, cy)
            await page.mouse.down()
            await move_mouse(cx - 180, cy - 40, steps=15)
            await page.mouse.up()
            await page.wait_for_timeout(1000)

        heat_cell = page.locator('.heat-cell.heat-l4').first
        if await heat_cell.count():
            hbox = await heat_cell.bounding_box()
            if hbox:
                await move_mouse(hbox['x'] + hbox['width']/2, hbox['y'] + hbox['height']/2)
                await page.wait_for_timeout(600)

        # ===== 场景 7: 玄色夜读模式切换与下载收官 (定位至 5250px 居中) =====
        print("8. [Scene 7] 玄色夜读黑金模式切换与尾屏下载 (定位至 5250px)...")
        await page.evaluate('updateHUD("Act IV · 一键切换「玄色夜读」黑金水墨模式", "#d4554a")')
        theme_btn = page.locator('#theme-btn')
        if await theme_btn.count():
            thbox = await theme_btn.bounding_box()
            if thbox:
                await move_mouse(thbox['x'] + thbox['width']/2, thbox['y'] + thbox['height']/2)
                await theme_btn.click()
                await page.wait_for_timeout(1200)

        await page.evaluate('updateHUD("入书院，登金榜 · Windows / Android / Web 开源交付", "#ffffff")')
        await smooth_scroll(5250, duration=1.2)
        await page.wait_for_timeout(1800)

        print("9. 录制完成，关闭浏览器封包视频...")
        await context.close()
        await browser.close()

    webms = [f for f in os.listdir(rec_dir) if f.endswith('.webm')]
    if webms:
        src_webm = os.path.join(rec_dir, webms[0])
        print("Source WebM recorded:", src_webm, "Size:", os.path.getsize(src_webm))
        return src_webm

if __name__ == '__main__':
    asyncio.run(run_cinematic_perfect())
