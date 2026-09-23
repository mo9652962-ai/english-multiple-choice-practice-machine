<template>
  <div class="ink-timer-container">
    <div class="ink-canvas-box" ref="canvasBoxRef"></div>
    <div class="timer-controls">
      <div class="ink-level-tag">
        <span class="ink-dot"></span>
        <span>砚池蓄墨：{{ Math.round(progress * 100) }}%</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, watch } from 'vue'
import * as THREE from 'three'

const props = withDefaults(
  defineProps<{
    progress: number // 0.0 ~ 1.0
    isRunning: boolean
  }>(),
  {
    progress: 0,
    isRunning: false,
  }
)

const canvasBoxRef = ref<HTMLDivElement | null>(null)
let scene: THREE.Scene
let camera: THREE.PerspectiveCamera
let renderer: THREE.WebGLRenderer
let animationFrameId: number
let inkPoolMesh: THREE.Mesh
let dropMesh: THREE.Mesh
let dropGroup: THREE.Group
let rippleRings: THREE.Mesh[] = []

const initThree = () => {
  if (!canvasBoxRef.value) return

  const width = canvasBoxRef.value.clientWidth || 320
  const height = canvasBoxRef.value.clientHeight || 280

  scene = new THREE.Scene()
  camera = new THREE.PerspectiveCamera(40, width / height, 0.1, 100)
  camera.position.set(0, 3.2, 4.0)
  camera.lookAt(0, 0, 0)

  renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true })
  renderer.setSize(width, height)
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
  canvasBoxRef.value.appendChild(renderer.domElement)

  // 1. 灯光
  const ambLight = new THREE.AmbientLight(0xfcf7ed, 1.6)
  scene.add(ambLight)

  const dirLight = new THREE.DirectionalLight(0xffeedd, 2.2)
  dirLight.position.set(3, 6, 4)
  scene.add(dirLight)

  // 2. 3D 端石云纹砚台底座 (深紫褐砚石色)
  const inkstoneGeo = new THREE.CylinderGeometry(1.6, 1.7, 0.35, 32)
  const inkstoneMat = new THREE.MeshStandardMaterial({
    color: 0x221e1a, // 墨黑泛紫
    roughness: 0.6,
    metalness: 0.2,
  })
  const inkstone = new THREE.Mesh(inkstoneGeo, inkstoneMat)
  inkstone.position.y = -0.18
  scene.add(inkstone)

  // 3. 砚池内部凹陷 (微弧面)
  const poolBaseGeo = new THREE.CylinderGeometry(1.3, 1.25, 0.15, 32)
  const poolBaseMat = new THREE.MeshStandardMaterial({
    color: 0x141210,
    roughness: 0.8,
  })
  const poolBase = new THREE.Mesh(poolBaseGeo, poolBaseMat)
  poolBase.position.y = -0.05
  scene.add(poolBase)

  // 4. 蓄墨液面 (高光深浓墨汁，随 progress 升起)
  const inkGeo = new THREE.CylinderGeometry(1.28, 1.28, 0.05, 32)
  const inkMat = new THREE.MeshStandardMaterial({
    color: 0x0a0908,
    roughness: 0.1, // 镜面墨液反光
    metalness: 0.8,
  })
  inkPoolMesh = new THREE.Mesh(inkGeo, inkMat)
  inkPoolMesh.position.y = -0.08 + props.progress * 0.1
  scene.add(inkPoolMesh)

  // 5. 水滴组
  dropGroup = new THREE.Group()
  const dropGeo = new THREE.SphereGeometry(0.06, 16, 16)
  const dropMat = new THREE.MeshStandardMaterial({
    color: 0x3a352e,
    roughness: 0.2,
    metalness: 0.5,
  })
  dropMesh = new THREE.Mesh(dropGeo, dropMat)
  dropMesh.position.set(0, 2.2, 0)
  dropGroup.add(dropMesh)
  scene.add(dropGroup)

  // 6. 涟漪光环
  rippleRings = []
  for (let i = 0; i < 3; i++) {
    const ringGeo = new THREE.RingGeometry(0.1, 0.14, 32)
    const ringMat = new THREE.MeshBasicMaterial({
      color: 0x4a443b,
      transparent: true,
      opacity: 0,
      side: THREE.DoubleSide,
    })
    const ring = new THREE.Mesh(ringGeo, ringMat)
    ring.rotation.x = -Math.PI / 2
    ring.position.y = -0.02
    ring.userData = { scale: 1, maxScale: 8 + i * 2, opacity: 0 }
    scene.add(ring)
    rippleRings.push(ring)
  }

  animate()
}

let dropY = 2.2
const animate = () => {
  animationFrameId = requestAnimationFrame(animate)

  // 液面高度渐变
  if (inkPoolMesh) {
    const targetY = -0.08 + props.progress * 0.12
    inkPoolMesh.position.y += (targetY - inkPoolMesh.position.y) * 0.05
  }

  // 运行中的水滴下落动画
  if (props.isRunning && dropMesh) {
    dropY -= 0.035
    dropMesh.position.y = dropY

    if (dropY <= -0.04) {
      dropY = 2.2
      // 触发一圈涟漪
      const ring = rippleRings.find((r) => r.userData.opacity <= 0)
      if (ring) {
        ring.scale.set(1, 1, 1)
        ring.userData.scale = 1
        ring.userData.opacity = 0.8
        ;(ring.material as THREE.MeshBasicMaterial).opacity = 0.8
      }
    }
  }

  // 涟漪扩散
  rippleRings.forEach((ring) => {
    if (ring.userData.opacity > 0) {
      ring.userData.scale += 0.12
      ring.scale.set(ring.userData.scale, ring.userData.scale, 1)
      ring.userData.opacity -= 0.015
      ;(ring.material as THREE.MeshBasicMaterial).opacity = Math.max(
        0,
        ring.userData.opacity
      )
    }
  })

  // 镜头极微小自旋呼吸感
  if (scene) {
    scene.rotation.y = Math.sin(Date.now() * 0.0008) * 0.08
  }

  renderer.render(scene, camera)
}

watch(
  () => props.progress,
  (val) => {
    if (inkPoolMesh) {
      const targetY = -0.08 + val * 0.12
      inkPoolMesh.position.y = targetY
    }
  }
)

onMounted(() => {
  initThree()
})

onBeforeUnmount(() => {
  cancelAnimationFrame(animationFrameId)
  if (renderer) renderer.dispose()
})
</script>

<style scoped>
.ink-timer-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  position: relative;
  width: 100%;
}

.ink-canvas-box {
  width: 100%;
  max-width: 340px;
  height: 260px;
}

.timer-controls {
  margin-top: -12px;
}

.ink-level-tag {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: rgba(253, 250, 243, 0.85);
  backdrop-filter: blur(8px);
  padding: 4px 12px;
  border-radius: 9999px;
  border: 1px solid var(--line, #e4ded1);
  font-size: 12px;
  color: var(--ink, #2e2a23);
  font-weight: 500;
}

.ink-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background-color: var(--ink, #2e2a23);
}
</style>
