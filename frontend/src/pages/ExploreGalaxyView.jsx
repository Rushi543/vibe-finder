import { useRef } from 'react'
import { useFrame } from '@react-three/fiber'
import { Stars } from '@react-three/drei'
import * as THREE from 'three'

function OrbitingPlanet({ point, index, totalCount, onNodeClick, onNodeHover }) {
  const orbitRef = useRef(null)
  const orbitRadius = (0.9 + index * 0.85) * 1.8
  const orbitSpeed = 0.18 / (index + 1)
  const startingAngle = totalCount > 0 ? (index / totalCount) * Math.PI * 2 : 0
  const color = point.seeded ? '#55a594' : '#4DA3FF'
  const planetScale = 0.12 + Math.max(0, 0.07 * (totalCount - index))

  useFrame(({ clock }) => {
    if (!orbitRef.current) return
    orbitRef.current.rotation.y = startingAngle + clock.getElapsedTime() * orbitSpeed
  })

  return (
    <group ref={orbitRef}>
      <mesh
        position={[orbitRadius, 0, 0]}
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
    </group>
  )
}

function GalaxyScene({ centerPoint, matchPoints, onNodeClick, onNodeHover }) {
  const sortedMatches = [...matchPoints].sort((a, b) => b.similarity - a.similarity)

  return (
    <>
      <ambientLight intensity={0.35} color="#1a1a2e" />
      <pointLight position={[0, 5, 0]} intensity={2.1} color="#ffd166" />
      <Stars radius={35} depth={25} count={600} factor={2} fade />

      {centerPoint && (
        <mesh position={[0, 0, 0]}>
          <sphereGeometry args={[0.24, 22, 22]} />
          <meshStandardMaterial emissive="#ffd166" color="#ffd166" roughness={0.2} metalness={0.35} />
        </mesh>
      )}

      {sortedMatches.map((_, index) => {
        const orbitRadius = (0.9 + index * 0.85) * 1.8

        return (
          <mesh key={`ring-${index}`} rotation-x={-Math.PI / 2}>
            <ringGeometry args={[orbitRadius - 0.02, orbitRadius + 0.02, 64]} />
            <meshBasicMaterial color="#ffd166" transparent opacity={0.12} side={THREE.DoubleSide} />
          </mesh>
        )
      })}

      {sortedMatches.map((point, index) => (
        <OrbitingPlanet
          key={point.user_id}
          point={point}
          index={index}
          totalCount={sortedMatches.length}
          onNodeClick={onNodeClick}
          onNodeHover={onNodeHover}
        />
      ))}
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
