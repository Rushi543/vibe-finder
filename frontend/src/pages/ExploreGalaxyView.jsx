import { Stars } from '@react-three/drei'
import * as THREE from 'three'

export default function ExploreGalaxyView({ centerPoint, fallbackPoint, matches, onNodeClick, onNodeHover }) {
  const galaxyCenter = centerPoint || fallbackPoint

  if (!galaxyCenter) return null

  return (
    <>
      <GalaxyScene
        centerPoint={galaxyCenter}
        matchPoints={matches}
        onNodeClick={onNodeClick}
        onNodeHover={onNodeHover}
      />
    </>
  )
}


import { useRef } from 'react'
import { useFrame } from '@react-three/fiber'

function Planet({ point, index, totalCount, onNodeClick, onNodeHover }) {
  const groupRef = useRef()
  const orbitRadius = 0.9 + index * 0.85
  const orbitSpeed = 0.12 / (index + 1) // closer = faster
  const angleOffset = (index / totalCount) * Math.PI * 2
  const color = point.seeded ? '#55a594' : '#4DA3FF'
  const planetScale = 0.08 + Math.max(0, 0.05 * (totalCount - index))

  useFrame(({ clock }) => {
    if (!groupRef.current) return
    const angle = angleOffset + clock.getElapsedTime() * orbitSpeed
    groupRef.current.position.x = Math.cos(angle) * orbitRadius * 1.8
    groupRef.current.position.z = Math.sin(angle) * orbitRadius * 1.8
  })

  return (
    <group ref={groupRef}>
      <mesh
        scale={planetScale}
        onClick={(e) => { e.stopPropagation(); onNodeClick(point) }}
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

      {/* Sun */}
      {centerPoint && (
        <mesh position={[0, 0, 0]}>
          <sphereGeometry args={[0.16, 18, 18]} />
          <meshStandardMaterial emissive="#ffd166" color="#ffd166" roughness={0.2} metalness={0.35} />
        </mesh>
      )}

      {/* Orbit rings — static */}
      {sortedMatches.map((_, index) => {
        const orbitRadius = 0.9 + index * 0.85
        return (
          <mesh key={`ring-${index}`} rotation-x={-Math.PI / 2}>
            <ringGeometry args={[orbitRadius * 1.8 - 0.02, orbitRadius * 1.8 + 0.02, 64]} />
            <meshBasicMaterial
              color="#ffd166"
              transparent
              opacity={0.12}
              side={THREE.DoubleSide}
            />
          </mesh>
        )
      })}

      {/* Orbiting planets */}
      {sortedMatches.map((point, index) => (
        <Planet
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