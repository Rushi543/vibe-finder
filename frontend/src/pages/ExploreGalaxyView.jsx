import { Stars } from '@react-three/drei'
import * as THREE from 'three'
import styles from './Explore.module.css'

function GalaxyScene({ centerPoint, matchPoints, onNodeClick, onNodeHover }) {
  const sortedMatches = [...matchPoints].sort((a, b) => b.similarity - a.similarity)

  return (
    <>
      <ambientLight intensity={0.35} color="#1a1a2e" />
      <pointLight position={[0, 5, 0]} intensity={2.1} color="#ffd166" />
      <Stars radius={35} depth={25} count={600} factor={2} fade />

      {centerPoint && (
        <mesh position={[0, 0, 0]}>
          <sphereGeometry args={[0.16, 18, 18]} />
          <meshStandardMaterial emissive="#ffd166" color="#ffd166" roughness={0.2} metalness={0.35} />
        </mesh>
      )}

      {sortedMatches.map((point, index) => {
        const orbitRadius = 0.9 + index * 0.85
        const angle = (index / sortedMatches.length) * Math.PI * 2
        const x = Math.cos(angle) * orbitRadius * 1.8
        const z = Math.sin(angle) * orbitRadius * 1.8
        const planetScale = 0.08 + Math.max(0, 0.05 * (sortedMatches.length - index))
        const color = point.seeded ? '#55a594' : '#4DA3FF'

        return (
          <group key={point.user_id}>
            <mesh rotation-x={-Math.PI / 2}>
              <ringGeometry args={[orbitRadius - 0.02, orbitRadius + 0.02, 64]} />
              <meshBasicMaterial color="rgba(255, 209, 102, 0.14)" transparent opacity={0.25} side={THREE.DoubleSide} />
            </mesh>
            <mesh
              position={[x, 0, z]}
              scale={planetScale}
              onClick={(event) => {
                event.stopPropagation()
                onNodeClick(point)
              }}
              onPointerOver={() => onNodeHover(point)}
              onPointerOut={() => onNodeHover(null)}
            >
              <sphereGeometry args={[0.05, 12, 12]} />
              <meshStandardMaterial color={color} emissive={color} emissiveIntensity={0.7} roughness={0.3} metalness={0.4} />
            </mesh>
          </group>
        )
      })}
    </>
  )
}

export default function ExploreGalaxyView({ centerPoint, fallbackPoint, matches, onNodeClick, onNodeHover }) {
  const galaxyCenter = centerPoint || fallbackPoint

  if (!galaxyCenter) {
    return <div className={styles.emptyGalaxy}>Select a profile to view the galaxy system.</div>
  }

  return (
    <>
      <GalaxyScene
        centerPoint={galaxyCenter}
        matchPoints={matches}
        onNodeClick={onNodeClick}
        onNodeHover={onNodeHover}
      />
      {matches.length === 0 && (
        <div className={styles.emptyGalaxy}>No similar profiles yet. Select a profile or reconnect a source to fill the orbit.</div>
      )}
    </>
  )
}
