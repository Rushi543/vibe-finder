import { useRef } from 'react'
import { useFrame } from '@react-three/fiber'
import { Stars } from '@react-three/drei'
import { Bloom, EffectComposer } from '@react-three/postprocessing'
import * as THREE from 'three'

const SOURCE_COLORS = {
  github: '#4DA3FF',
  steam: '#4ADE80',
  anilist: '#C084FC',
  mixed: '#FFD166',
  seeded: '#55a594',
}

function colorForPoint(point) {
  if (point.seeded) return SOURCE_COLORS.seeded

  const sources = point.sources || []
  if (sources.length > 1) return SOURCE_COLORS.mixed
  if (sources.includes('github')) return SOURCE_COLORS.github
  if (sources.includes('steam')) return SOURCE_COLORS.steam
  if (sources.includes('anilist')) return SOURCE_COLORS.anilist

  return SOURCE_COLORS.github
}

const INNER_ORBIT_RADIUS = 2.4
const MIN_ORBIT_GAP = 1.35
const SIMILARITY_SPREAD = 8

function buildOrbitLayout(points) {
  if (points.length === 0) return []

  const topSimilarity = points[0]?.similarity ?? 1
  let previousRadius = INNER_ORBIT_RADIUS

  return points.map((point, index) => {
    if (index === 0) {
      return { point, orbitRadius: INNER_ORBIT_RADIUS }
    }

    const similarity = point.similarity ?? 0.5
    const similarityRadius = INNER_ORBIT_RADIUS + Math.max(0, topSimilarity - similarity) * SIMILARITY_SPREAD
    const orbitRadius = Math.max(previousRadius + MIN_ORBIT_GAP, similarityRadius)
    previousRadius = orbitRadius

    return { point, orbitRadius }
  })
}

function OrbitingPlanet({ point, index, totalCount, orbitRadius, onNodeClick, onNodeHover }) {
  const orbitRef = useRef(null)
  const verticalOffset = ((index % 5) - 2) * 0.3
  const orbitSpeed = 0.18 / (index + 1)
  const startingAngle = totalCount > 0 ? (index / totalCount) * Math.PI * 2 : 0
  const color = colorForPoint(point)
  const similarityFactor = point.similarity ?? 0.5
  const planetScale = (0.4 + similarityFactor * 0.8) * 3
  const hasPlanetRing = index < 3

  useFrame(({ clock }) => {
    if (!orbitRef.current) return
    orbitRef.current.rotation.y = startingAngle + clock.getElapsedTime() * orbitSpeed
  })

  return (
    <group ref={orbitRef}>
      <mesh
        position={[orbitRadius, verticalOffset, 0]}
        scale={planetScale}
        onClick={(event) => {
          event.stopPropagation()
          onNodeClick(point)
        }}
        onPointerOver={() => onNodeHover(point)}
        onPointerOut={() => onNodeHover(null)}
        >
        <sphereGeometry args={[0.05, 12, 12]} />
        <meshStandardMaterial
          color={color}
          emissive={color}
          emissiveIntensity={0.7}
          roughness={0.3}
          metalness={0.4}
        />
      </mesh>
      {hasPlanetRing && (
        <mesh position={[orbitRadius, verticalOffset, 0]} rotation-x={-Math.PI / 2} scale={planetScale}>
          <ringGeometry args={[0.08, 0.13, 48]} />
          <meshBasicMaterial color={color} transparent opacity={0.28} side={THREE.DoubleSide} />
        </mesh>
      )}
    </group>
  )
}

function GalaxyScene({ centerPoint, matchPoints, onNodeClick, onNodeHover }) {
  const sortedMatches = [...matchPoints].sort((a, b) => b.similarity - a.similarity)
  const orbitLayout = buildOrbitLayout(sortedMatches)
  const sunRef = useRef(null)

  useFrame(({ clock }) => {
    if (!sunRef.current) return
    const pulse = 1 + Math.sin(clock.elapsedTime * 2) * 0.05
    sunRef.current.scale.setScalar(pulse)
  })

  return (
    <>
      <ambientLight intensity={0.35} color="#1a1a2e" />
      <pointLight position={[0, 5, 0]} intensity={2.1} color="#ffd166" />
      <Stars radius={100} depth={50} count={5000} factor={5} saturation={0} fade />

      {centerPoint && (
        <mesh ref={sunRef} position={[0, 0, 0]}>
          <sphereGeometry args={[0.8, 48, 48]} />
          <meshStandardMaterial emissive="#ffd166" emissiveIntensity={3} color="#ffd166" roughness={0.2} metalness={0.35} />
        </mesh>
      )}

      {orbitLayout.map(({ point, orbitRadius }) => {
        return (
          <mesh key={`ring-${point.user_id}`} rotation-x={-Math.PI / 2}>
            <ringGeometry args={[orbitRadius - 0.02, orbitRadius + 0.02, 64]} />
            <meshBasicMaterial color="#ffd166" transparent opacity={0.05} side={THREE.DoubleSide} />
          </mesh>
        )
      })}

      {orbitLayout.map(({ point, orbitRadius }, index) => (
        <OrbitingPlanet
          key={point.user_id}
          point={point}
          index={index}
          totalCount={sortedMatches.length}
          orbitRadius={orbitRadius}
          onNodeClick={onNodeClick}
          onNodeHover={onNodeHover}
        />
      ))}

      <EffectComposer>
        <Bloom intensity={1.6} luminanceThreshold={0.08} luminanceSmoothing={0.85} mipmapBlur />
      </EffectComposer>
    </>
  )
}

export default function ExploreGalaxyView({ centerPoint, fallbackPoint, matches, onNodeClick, onNodeHover }) {
  const galaxyCenter = centerPoint || fallbackPoint

  if (!galaxyCenter) return null

  return (
    <GalaxyScene
      centerPoint={galaxyCenter}
      matchPoints={matches}
      onNodeClick={onNodeClick}
      onNodeHover={onNodeHover}
    />
  )
}
