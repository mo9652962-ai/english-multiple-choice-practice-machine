<template>
  <div class="seal-stamp-modal" v-if="visible">
    <div class="seal-backdrop" @click="handleClose"></div>
    <div class="seal-stage">
      <div class="seal-canvas-box" ref="canvasBoxRef"></div>
      
      <!-- 成绩卡纸面 -->
      <div class="scroll-card">
        <div class="scroll-inner">
          <div class="scroll-title">{{ paperTitle || '研习模拟自测卷' }}</div>
          <div class="scroll-score-row">
            <span class="score-num">{{ score }}</span>
            <span class="score-total">/ {{ maxScore }} 分</span>
          </div>
          <div class="scroll-verdict">{{ verdictText }}</div>
          <div class="scroll-date">{{ currentDateStr }} · 墨题心流阁藏</div>
        </div>
      </div>

      <div class="seal-actions">
        <button class="seal-confirm-btn" @click="handleClose">收卷归档</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import * as THREE from 'three'

const props = withDefaults(
  defineProps<{
    visible: boolean
    score: number
    maxScore: number
    paperTitle?: string
  }>(),
  {
    visible: false,
    score: 85,
    maxScore: 100,
    paperTitle: '2026年全国统考研习卷',
  }
)

const emit = defineEmits<{
  (e: 'close'): void
}>()

const canvasBoxRef = ref<HTMLDivElement | null>(null)
let scene: THREE.Scene
let camera: THREE.PerspectiveCamera
let renderer: THREE.WebGLRenderer
let stampMesh: THREE.Group
let particlesMesh: THREE.Points
let animationFrameId: number
let stampState: 'falling' | 'impact' | 'lift' | 'done' = 'falling'
let stampProgress = 0

const verdictText = computed(() => {
  const ratio = props.score / (props.maxScore || 100)
  if (ratio >= 0.9) return '拔萃甲等 · 金榜及第'
  if (ratio >= 0.8) return '炉火纯青 · 渐入佳境'
  if (ratio >= 0.6) return '日省日新 · 厚积薄发'
  return '沐墨磨砺 · 蓄力登临'
})

const currentDateStr = computed(() => {
  const d = new Date()
  return `${d.getFullYear()}年${d.getMonth() + 1}月${d.getDate()}日`
})

const initThree = () => {
  if (!canvasBoxRef.value) return

  const width = 360
  const height = 360

  scene = new THREE.Scene()
  camera = new THREE.PerspectiveCamera(40, width / height, 0.1, 100)
  camera.position.set(0, 1.2, 4.2)
  camera.lookAt(0, -0.2, 0)

  renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true })
  renderer.setSize(width, height)
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
  canvasBoxRef.value.appendChild(renderer.domElement)

  // 灯光
  const ambLight = new THREE.AmbientLight(0xfff8ee, 1.5)
  scene.add(ambLight)

  const dirLight = new THREE.DirectionalLight(0xfff5ea, 2.0)
  dirLight.position.set(2, 4, 3)
  scene.add(dirLight)

  // 1. 3D 印章组 (羊脂白玉 + 赤金顶纽)
  stampMesh = new THREE.Group()

  // 印身 (玉石质感)
  const bodyGeo = new THREE.BoxGeometry(0.9, 1.2, 0.9)
  const bodyMat = new THREE.MeshStandardMaterial({
    color: 0xedebe6,
    roughness: 0.15,
    metalness: 0.1,
  })
  const body = new THREE.Mesh(bodyGeo, bodyMat)
  body.position.y = 0.6
  stampMesh.add(body)

  // 印底 (朱砂印泥层)
  const baseGeo = new THREE.BoxGeometry(0.92, 0.08, 0.92)
  const baseMat = new THREE.MeshStandardMaterial({
    color: 0xb84a39,
    roughness: 0.3,
  })
  const base = new THREE.Mesh(baseGeo, baseMat)
  base.position.y = 0.04
  stampMesh.add(base)

  // 顶纽 (古兽印纽 - 简化金石多面体)
  const knobGeo = new THREE.DodecahedronGeometry(0.35)
  const knobMat = new THREE.MeshStandardMaterial({
    color: 0xa8842f, // 赤金
    roughness: 0.3,
    metalness: 0.8,
  })
  const knob = new THREE.Mesh(knobGeo, knobMat)
  knob.position.y = 1.35
  stampMesh.add(knob)

  stampMesh.position.set(0, 2.6, 0)
  scene.add(stampMesh)

  // 2. 朱砂微粉爆发粒子
  const particleCount = 120
  const pGeo = new THREE.BufferGeometry()
  const pPositions = new Float32Array(particleCount * 3)
  const pVelocities: THREE.Vector3[] = []

  for (let i = 0; i < particleCount; i++) {
    pPositions[i * 3] = 0
    pPositions[i * 3 + 1] = 0
    pPositions[i * 3 + 2] = 0

    const theta = Math.random() * Math.PI * 2
    const speed = 0.02 + Math.random() * 0.06
    pVelocities.push(
      new THREE.Vector3(
        Math.cos(theta) * speed,
        Math.random() * 0.04 + 0.01,
        Math.sin(theta) * speed
      )
    )
  }

  pGeo.setAttribute('position', new THREE.BufferAttribute(pPositions, 3))
  const pMat = new THREE.PointsMaterial({
    color: 0xb84a39,
    size: 0.08,
    transparent: true,
    opacity: 0,
  })
  particlesMesh = new THREE.Points(pGeo, pMat)
  particlesMesh.userData = { velocities: pVelocities, opacity: 0 }
  scene.add(particlesMesh)

  // 动画状态重置
  stampState = 'falling'
  stampProgress = 0

  animate()
}

const animate = () => {
  animationFrameId = requestAnimationFrame(animate)

  if (stampMesh) {
    if (stampState === 'falling') {
      stampProgress += 0.04
      stampMesh.position.y = THREE.MathUtils.lerp(2.6, 0.0, stampProgress)
      stampMesh.rotation.y += 0.02
      if (stampProgress >= 1) {
        stampState = 'impact'
        stampProgress = 0
        // 激荡粒子
        if (particlesMesh) {
          ;(particlesMesh.material as THREE.PointsMaterial).opacity = 1
          particlesMesh.userData.opacity = 1
        }
      }
    } else if (stampState === 'impact') {
      stampProgress += 0.08
      if (stampProgress >= 1) {
        stampState = 'lift'
        stampProgress = 0
      }
    } else if (stampState === 'lift') {
      stampProgress += 0.025
      stampMesh.position.y = THREE.MathUtils.lerp(0.0, 1.4, stampProgress)
      if (stampProgress >= 1) {
        stampState = 'done'
      }
    } else {
      // 缓动漂浮
      stampMesh.rotation.y += 0.005
    }
  }

  // 粒子扩散动画
  if (particlesMesh && particlesMesh.userData.opacity > 0) {
    const pos = particlesMesh.geometry.attributes.position.array as Float32Array
    const vels = particlesMesh.userData.velocities as THREE.Vector3[]
    for (let i = 0; i < vels.length; i++) {
      pos[i * 3] += vels[i].x
      pos[i * 3 + 1] += vels[i].y
      pos[i * 3 + 2] += vels[i].z
    }
    particlesMesh.geometry.attributes.position.needsUpdate = true
    particlesMesh.userData.opacity -= 0.015
    ;(particlesMesh.material as THREE.PointsMaterial).opacity = Math.max(
      0,
      particlesMesh.userData.opacity
    )
  }

  renderer.render(scene, camera)
}

const handleClose = () => {
  emit('close')
}

watch(
  () => props.visible,
  (newVal) => {
    if (newVal) {
      setTimeout(() => {
        initThree()
      }, 50)
    } else {
      cancelAnimationFrame(animationFrameId)
      if (renderer) renderer.dispose()
    }
  }
)

onMounted(() => {
  if (props.visible) {
    initThree()
  }
})

onBeforeUnmount(() => {
  cancelAnimationFrame(animationFrameId)
  if (renderer) renderer.dispose()
})
</script>

<style scoped>
.seal-stamp-modal {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
}

.seal-backdrop {
  position: absolute;
  inset: 0;
  background: rgba(26, 24, 20, 0.7);
  backdrop-filter: blur(8px);
}

.seal-stage {
  position: relative;
  z-index: 2;
  display: flex;
  flex-direction: column;
  align-items: center;
  animation: zoomIn 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.seal-canvas-box {
  width: 360px;
  height: 360px;
  pointer-events: none;
}

.scroll-card {
  width: 320px;
  margin-top: -60px;
  background: var(--surface, #fdfaf3);
  border: 1px solid var(--line, #e4ded1);
  border-radius: var(--radius-lg, 20px);
  padding: 24px 20px;
  box-shadow: 0 16px 40px rgba(46, 42, 35, 0.15);
  text-align: center;
  position: relative;
}

.scroll-card::before {
  content: '';
  position: absolute;
  top: 6px;
  left: 6px;
  right: 6px;
  bottom: 6px;
  border: 1px dashed var(--line-strong, #cfc7b6);
  border-radius: calc(var(--radius-lg, 20px) - 4px);
  pointer-events: none;
}

.scroll-title {
  font-size: 14px;
  color: var(--muted, #6b665c);
  margin-bottom: 8px;
}

.scroll-score-row {
  display: flex;
  justify-content: center;
  align-items: baseline;
  gap: 4px;
  margin-bottom: 6px;
}

.score-num {
  font-size: 46px;
  font-weight: 800;
  color: var(--accent-vermilion, #b84a39);
  line-height: 1;
}

.score-total {
  font-size: 16px;
  color: var(--muted, #6b665c);
}

.scroll-verdict {
  font-size: 18px;
  font-weight: 700;
  color: var(--ink, #2e2a23);
  margin-bottom: 12px;
  letter-spacing: 1px;
}

.scroll-date {
  font-size: 12px;
  color: var(--muted, #6b665c);
}

.seal-actions {
  margin-top: 20px;
}

.seal-confirm-btn {
  padding: 10px 32px;
  background: var(--primary, #403c35);
  color: #f7f3ee;
  border: none;
  border-radius: 9999px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  box-shadow: 0 4px 14px rgba(46, 42, 35, 0.2);
  transition: all 0.2s ease;
}

.seal-confirm-btn:hover {
  background: var(--primary-hover, #2f2c26);
  transform: translateY(-2px);
}

@keyframes zoomIn {
  from { opacity: 0; transform: scale(0.9); }
  to { opacity: 1; transform: scale(1); }
}
</style>
