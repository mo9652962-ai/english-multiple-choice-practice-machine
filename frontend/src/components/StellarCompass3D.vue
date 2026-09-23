<template>
  <div class="stellar-compass-container" ref="containerRef">
    <div class="stellar-canvas-wrapper" ref="canvasWrapperRef"></div>
    
    <!-- 顶部状态浮层 -->
    <div class="compass-hud-header">
      <div class="hud-badge">
        <span class="hud-dot"></span>
        <span class="hud-title">3D 水墨浑天学情仪</span>
      </div>
      <div class="hud-metrics" v-if="compassData">
        <div class="metric-item">
          <span class="label">综合掌握度</span>
          <span class="val highlight">{{ compassData.overall_accuracy }}%</span>
        </div>
        <div class="metric-item">
          <span class="label">薄弱星位</span>
          <span class="val warn">{{ compassData.weak_points }} 处</span>
        </div>
      </div>
    </div>

    <!-- 交互提示 -->
    <div class="compass-hint" v-if="!selectedStar">
      <span>✦ 拖拽旋转星轨 · 滚轮缩放 · 悬停考点星辰</span>
    </div>

    <!-- 选中星辰考点详情浮卡 -->
    <transition name="pop">
      <div v-if="selectedStar" class="star-card" :class="selectedStar.status">
        <div class="star-card-header">
          <span class="star-tag" :style="{ backgroundColor: selectedStar.color }">
            {{ selectedStar.status === 'weak' ? '薄弱考点' : '已掌握' }}
          </span>
          <button class="close-btn" @click="selectedStar = null">✕</button>
        </div>
        <div class="star-title">{{ selectedStar.title }}</div>
        <div class="star-meta">来源：{{ selectedStar.paper }}</div>
        <div class="star-action">
          <button class="redo-btn" @click="handleReviewStar(selectedStar)">
            研习此考点真题
          </button>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue'
import * as THREE from 'three'

interface Dimension {
  axis: string
  score: number
  max: number
  weight: number
}

interface StarNode {
  id: string
  title: string
  paper: string
  status: 'weak' | 'mastered'
  color: string
  x: number
  y: number
  z: number
  size: number
}

interface CompassData {
  overall_accuracy: number
  total_practiced: number
  mastered_points: number
  weak_points: number
  dimensions: Dimension[]
  stars: StarNode[]
}

const emit = defineEmits<{
  (e: 'select-star', star: StarNode): void
}>()

const containerRef = ref<HTMLDivElement | null>(null)
const canvasWrapperRef = ref<HTMLDivElement | null>(null)
const compassData = ref<CompassData | null>(null)
const selectedStar = ref<StarNode | null>(null)

let scene: THREE.Scene
let camera: THREE.PerspectiveCamera
let renderer: THREE.WebGLRenderer
let animationFrameId: number
let ringsGroup: THREE.Group
let starsGroup: THREE.Group
let coreMesh: THREE.Mesh
let raycaster: THREE.Raycaster
let mouse: THREE.Vector2

// 旋转交互变量
let isDragging = false
let previousMousePosition = { x: 0, y: 0 }
let targetRotationX = 0.2
let targetRotationY = 0.4
let currentRotationX = 0.2
let currentRotationY = 0.4

const fetchCompassData = async () => {
  try {
    const res = await fetch('/api/diagnostic/stellar-compass')
    if (res.ok) {
      const data = await res.json()
      compassData.value = data
      rebuildStars(data.stars)
    }
  } catch (err) {
    console.warn('获取学情天球仪数据失败，使用降级数据', err)
  }
}

const initThree = () => {
  if (!canvasWrapperRef.value) return

  const width = canvasWrapperRef.value.clientWidth || 600
  const height = canvasWrapperRef.value.clientHeight || 420

  // 1. 场景
  scene = new THREE.Scene()
  scene.fog = new THREE.FogExp2(0x1a1814, 0.05)

  // 2. 相机
  camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 1000)
  camera.position.set(0, 1.8, 6.5)
  camera.lookAt(0, 0, 0)

  // 3. 渲染器
  renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true })
  renderer.setSize(width, height)
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
  canvasWrapperRef.value.appendChild(renderer.domElement)

  // 4. 灯光 (古雅暖光 + 月白冷光)
  const ambientLight = new THREE.AmbientLight(0xf2eee5, 1.2)
  scene.add(ambientLight)

  const pointLight1 = new THREE.PointLight(0xc73e3a, 2.5, 20) // 朱砂光
  pointLight1.position.set(3, 4, 3)
  scene.add(pointLight1)

  const pointLight2 = new THREE.PointLight(0x8fa89b, 2.0, 20) // 松绿冷光
  pointLight2.position.set(-4, -2, -3)
  scene.add(pointLight2)

  // 5. 浑天仪环结构
  ringsGroup = new THREE.Group()
  scene.add(ringsGroup)

  // 六合环 (外环 - 青铜水墨)
  const ring1Geo = new THREE.TorusGeometry(3.0, 0.035, 16, 100)
  const ring1Mat = new THREE.MeshStandardMaterial({
    color: 0x4a443b,
    metalness: 0.6,
    roughness: 0.4,
  })
  const ring1 = new THREE.Mesh(ring1Geo, ring1Mat)
  ringsGroup.add(ring1)

  // 三辰环 (赤道倾斜环)
  const ring2Geo = new THREE.TorusGeometry(2.6, 0.025, 16, 100)
  const ring2Mat = new THREE.MeshStandardMaterial({
    color: 0x8a7f70,
    metalness: 0.7,
    roughness: 0.3,
  })
  const ring2 = new THREE.Mesh(ring2Geo, ring2Mat)
  ring2.rotation.x = Math.PI / 4
  ringsGroup.add(ring2)

  // 四游环 (内层经度环)
  const ring3Geo = new THREE.TorusGeometry(2.2, 0.02, 16, 100)
  const ring3Mat = new THREE.MeshStandardMaterial({
    color: 0xb5a895,
    metalness: 0.8,
    roughness: 0.2,
  })
  const ring3 = new THREE.Mesh(ring3Geo, ring3Mat)
  ring3.rotation.y = Math.PI / 3
  ringsGroup.add(ring3)

  // 6. 核心水墨多面体星核
  const coreGeo = new THREE.IcosahedronGeometry(0.85, 1)
  const coreMat = new THREE.MeshStandardMaterial({
    color: 0x2e2a23,
    roughness: 0.2,
    metalness: 0.8,
    wireframe: true,
  })
  coreMesh = new THREE.Mesh(coreGeo, coreMat)
  scene.add(coreMesh)

  // 7. 星辰考点组
  starsGroup = new THREE.Group()
  scene.add(starsGroup)

  // 8. 射线检测器
  raycaster = new THREE.Raycaster()
  mouse = new THREE.Vector2()

  // 监听事件
  bindEvents()

  // 开始循环
  animate()
}

const rebuildStars = (stars: StarNode[]) => {
  if (!starsGroup) return

  // 清除旧星辰
  while (starsGroup.children.length > 0) {
    const obj = starsGroup.children[0]
    starsGroup.remove(obj)
  }

  stars.forEach((star) => {
    const starGeo = new THREE.SphereGeometry(star.size || 0.18, 16, 16)
    const starColor = star.status === 'weak' ? 0xb23a2e : 0x2f6b5e
    const starMat = new THREE.MeshStandardMaterial({
      color: starColor,
      emissive: starColor,
      emissiveIntensity: star.status === 'weak' ? 0.8 : 0.4,
      roughness: 0.3,
    })
    const starMesh = new THREE.Mesh(starGeo, starMat)
    starMesh.position.set(star.x, star.y, star.z)
    starMesh.userData = star
    starsGroup.add(starMesh)
  })
}

const bindEvents = () => {
  const el = canvasWrapperRef.value
  if (!el) return

  el.addEventListener('mousedown', onMouseDown)
  window.addEventListener('mousemove', onMouseMove)
  window.addEventListener('mouseup', onMouseUp)

  el.addEventListener('touchstart', onTouchStart, { passive: false })
  window.addEventListener('touchmove', onTouchMove, { passive: false })
  window.addEventListener('touchend', onTouchEnd)

  el.addEventListener('click', onClick)
}

const unbindEvents = () => {
  const el = canvasWrapperRef.value
  if (!el) return

  el.removeEventListener('mousedown', onMouseDown)
  window.removeEventListener('mousemove', onMouseMove)
  window.removeEventListener('mouseup', onMouseUp)

  el.removeEventListener('touchstart', onTouchStart)
  window.removeEventListener('touchmove', onTouchMove)
  window.removeEventListener('touchend', onTouchEnd)

  el.removeEventListener('click', onClick)
}

const onMouseDown = (e: MouseEvent) => {
  isDragging = true
  previousMousePosition = { x: e.clientX, y: e.clientY }
}

const onMouseMove = (e: MouseEvent) => {
  if (isDragging) {
    const deltaX = e.clientX - previousMousePosition.x
    const deltaY = e.clientY - previousMousePosition.y

    targetRotationY += deltaX * 0.006
    targetRotationX += deltaY * 0.006

    previousMousePosition = { x: e.clientX, y: e.clientY }
  }

  // 射线碰撞判定
  if (canvasWrapperRef.value) {
    const rect = canvasWrapperRef.value.getBoundingClientRect()
    mouse.x = ((e.clientX - rect.left) / rect.width) * 2 - 1
    mouse.y = -((e.clientY - rect.top) / rect.height) * 2 + 1
  }
}

const onMouseUp = () => {
  isDragging = false
}

const onTouchStart = (e: TouchEvent) => {
  if (e.touches.length === 1) {
    isDragging = true
    previousMousePosition = { x: e.touches[0].clientX, y: e.touches[0].clientY }
  }
}

const onTouchMove = (e: TouchEvent) => {
  if (isDragging && e.touches.length === 1) {
    const deltaX = e.touches[0].clientX - previousMousePosition.x
    const deltaY = e.touches[0].clientY - previousMousePosition.y

    targetRotationY += deltaX * 0.008
    targetRotationX += deltaY * 0.008

    previousMousePosition = { x: e.touches[0].clientX, y: e.touches[0].clientY }
  }
}

const onTouchEnd = () => {
  isDragging = false
}

const onClick = () => {
  if (!starsGroup || !camera) return

  raycaster.setFromCamera(mouse, camera)
  const intersects = raycaster.intersectObjects(starsGroup.children)

  if (intersects.length > 0) {
    const hitStar = intersects[0].object.userData as StarNode
    selectedStar.value = hitStar
    emit('select-star', hitStar)
  }
}

const handleReviewStar = (star: StarNode) => {
  emit('select-star', star)
}

const animate = () => {
  animationFrameId = requestAnimationFrame(animate)

  // 平滑缓动旋转
  currentRotationX += (targetRotationX - currentRotationX) * 0.08
  currentRotationY += (targetRotationY - currentRotationY) * 0.08

  if (ringsGroup) {
    ringsGroup.rotation.x = currentRotationX
    ringsGroup.rotation.y = currentRotationY
    // 自身微动
    ringsGroup.children[0].rotation.z += 0.001
    ringsGroup.children[1].rotation.x += 0.0015
    ringsGroup.children[2].rotation.y -= 0.002
  }

  if (starsGroup) {
    starsGroup.rotation.x = currentRotationX
    starsGroup.rotation.y = currentRotationY
  }

  if (coreMesh) {
    coreMesh.rotation.x += 0.005
    coreMesh.rotation.y += 0.008
  }

  // 悬停光晕呼吸效果
  if (raycaster && camera && starsGroup && !isDragging) {
    raycaster.setFromCamera(mouse, camera)
    const intersects = raycaster.intersectObjects(starsGroup.children)
    if (canvasWrapperRef.value) {
      canvasWrapperRef.value.style.cursor = intersects.length > 0 ? 'pointer' : 'grab'
    }
  }

  renderer.render(scene, camera)
}

const handleResize = () => {
  if (!canvasWrapperRef.value || !renderer || !camera) return
  const width = canvasWrapperRef.value.clientWidth
  const height = canvasWrapperRef.value.clientHeight
  camera.aspect = width / height
  camera.updateProjectionMatrix()
  renderer.setSize(width, height)
}

onMounted(() => {
  initThree()
  fetchCompassData()
  window.addEventListener('resize', handleResize)
})

onBeforeUnmount(() => {
  cancelAnimationFrame(animationFrameId)
  unbindEvents()
  window.removeEventListener('resize', handleResize)
  if (renderer && renderer.domElement) {
    renderer.dispose()
  }
})
</script>

<style scoped>
.stellar-compass-container {
  position: relative;
  width: 100%;
  height: 480px;
  background: radial-gradient(circle at center, rgba(46, 42, 35, 0.04) 0%, rgba(26, 24, 20, 0.12) 100%);
  border-radius: var(--radius-lg, 20px);
  border: 1px solid var(--line, #e4ded1);
  overflow: hidden;
  user-select: none;
}

.stellar-canvas-wrapper {
  width: 100%;
  height: 100%;
  cursor: grab;
}

.stellar-canvas-wrapper:active {
  cursor: grabbing;
}

.compass-hud-header {
  position: absolute;
  top: 16px;
  left: 20px;
  right: 20px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  pointer-events: none;
}

.hud-badge {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  background: rgba(253, 250, 243, 0.85);
  backdrop-filter: blur(8px);
  padding: 6px 14px;
  border-radius: 9999px;
  border: 1px solid var(--line, #e4ded1);
  box-shadow: 0 4px 12px rgba(46, 42, 35, 0.06);
}

.hud-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background-color: var(--accent-vermilion, #b84a39);
  box-shadow: 0 0 8px var(--accent-vermilion, #b84a39);
  animation: pulse 2s infinite;
}

.hud-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--ink, #2e2a23);
  letter-spacing: 0.5px;
}

.hud-metrics {
  display: flex;
  gap: 12px;
}

.metric-item {
  background: rgba(253, 250, 243, 0.85);
  backdrop-filter: blur(8px);
  padding: 4px 12px;
  border-radius: 8px;
  border: 1px solid var(--line, #e4ded1);
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
}

.metric-item .label {
  color: var(--muted, #6b665c);
}

.metric-item .val.highlight {
  color: var(--accent-bamboo, #4a5f4e);
  font-weight: 700;
}

.metric-item .val.warn {
  color: var(--accent-vermilion, #b84a39);
  font-weight: 700;
}

.compass-hint {
  position: absolute;
  bottom: 16px;
  left: 50%;
  transform: translateX(-50%);
  font-size: 12px;
  color: var(--muted, #6b665c);
  background: rgba(253, 250, 243, 0.75);
  backdrop-filter: blur(6px);
  padding: 4px 14px;
  border-radius: 9999px;
  border: 1px solid var(--line, #e4ded1);
  pointer-events: none;
}

.star-card {
  position: absolute;
  bottom: 24px;
  right: 24px;
  width: 280px;
  background: var(--surface, #fdfaf3);
  border: 1px solid var(--line, #e4ded1);
  border-radius: var(--radius-md, 14px);
  padding: 16px;
  box-shadow: 0 12px 32px rgba(46, 42, 35, 0.12);
  z-index: 10;
}

.star-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.star-tag {
  color: #fff;
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 4px;
  font-weight: 600;
}

.close-btn {
  background: none;
  border: none;
  color: var(--muted, #6b665c);
  cursor: pointer;
  font-size: 14px;
}

.star-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--ink, #2e2a23);
  line-height: 1.4;
  margin-bottom: 6px;
}

.star-meta {
  font-size: 12px;
  color: var(--muted, #6b665c);
  margin-bottom: 12px;
}

.redo-btn {
  width: 100%;
  padding: 8px 12px;
  background: var(--primary, #403c35);
  color: #f7f3ee;
  border: none;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.2s ease;
}

.redo-btn:hover {
  background: var(--primary-hover, #2f2c26);
}

@keyframes pulse {
  0% { transform: scale(0.95); opacity: 0.8; }
  50% { transform: scale(1.15); opacity: 1; }
  100% { transform: scale(0.95); opacity: 0.8; }
}

.pop-enter-active,
.pop-leave-active {
  transition: all 0.25s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.pop-enter-from,
.pop-leave-to {
  opacity: 0;
  transform: translateY(12px) scale(0.95);
}
</style>
