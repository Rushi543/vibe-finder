import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Canvas, useFrame } from '@react-three/fiber'
import { OrbitControls, Stars } from '@react-three/drei'
import * as THREE from 'three'
import { useAuth } from '../App'
import { getMatches, getUmap, getWeightedMatches } from '../lib/api'
import styles from './Explore.module.css'

const PROFILE_COLORS = {
  profile: '#7c6aff',
  seeded: '#55a594',
  match: '#f4d35e',
  currentUser: '#4DA3FF',
  selected: '#ff5f87',
}

function displayNameFor(point) {
  return point.label || point.github_username || point.user_id
}

function dominantColor(point, { isCurrentUser, isSelected, isMatch }) {
  if (isSelected) return PROFILE_COLORS.selected
  if (isCurrentUser) return PROFILE_COLORS.currentUser
  if (isMatch) return PROFILE_COLORS.match
  return point.seeded ? PROFILE_COLORS.seeded : PROFILE_COLORS.profile
}

function Node({ point, isCurrentUser, isSelected, isMatch, onClick, onHover }) {
  const meshRef = useRef()
  const pulseRef = useRef(Math.random() * Math.PI * 2)
  const color = dominantColor(point, { isCurrentUser, isSelected, isMatch })
  const isReal = !point.seeded
  const hasCompleteProfile = isReal && (point.sources || []).length > 1
  const sourceScale = hasCompleteProfile ? 1.18 : 1
  const baseScale = (isSelected ? 1.8 : isMatch ? 1.35 : 1) * sourceScale

  useFrame((_, delta) => {
    if (!meshRef.current || !isReal) return
    pulseRef.current += delta
    const pulse = baseScale + 0.08 * Math.sin(pulseRef.current * 2)
    meshRef.current.scale.setScalar(pulse)
    meshRef.current.material.emissiveIntensity = 0.55 + 0.28 * Math.sin(pulseRef.current * 2)
  })

  return (
    <group position={[point.x * 2.8, point.y * 2.8, point.z * 2.8]}> 
      {isCurrentUser && (
        <mesh scale={baseScale * 1.4}>
          <sphereGeometry args={[isReal ? 0.05 : 0.04, 12, 12]} />
          <meshBasicMaterial
            color={color}
            transparent
            opacity={0.18}
            blending={THREE.AdditiveBlending}
            depthWrite={false}
          />
        </mesh>
      )}

      <mesh
        ref={meshRef}
        scale={baseScale}
        onClick={(event) => {
          event.stopPropagation()
          onClick(point)
        }}
        onPointerOver={() => onHover(point)}
        onPointerOut={() => onHover(null)}
      >
        <sphereGeometry args={[isReal ? 0.05 : 0.04, 12, 12]} />
        <meshStandardMaterial
          color={color}
          emissive={color}
          emissiveIntensity={isSelected ? 0.95 : isCurrentUser ? 1.1 : point.seeded ? 0.42 : hasCompleteProfile ? 0.75 : 0.55}
          roughness={0.32}
          metalness={0.52}
        />
      </mesh>
    </group>
  )
}

function MatchLines({ selectedPoint, matchPoints }) {
  if (!selectedPoint || matchPoints.length === 0) return null

  const from = new THREE.Vector3(selectedPoint.x * 2.8, selectedPoint.y * 2.8, selectedPoint.z * 2.8)

  return (
    <>
      {matchPoints.map((point) => {
        const to = new THREE.Vector3(point.x * 2.8, point.y * 2.8, point.z * 2.8)
        const geometry = new THREE.BufferGeometry().setFromPoints([from, to])
        return (
          <line key={point.user_id} geometry={geometry}>
            <lineBasicMaterial color={PROFILE_COLORS.match} transparent opacity={0.3} />
          </line>
        )
      })}
    </>
  )
}

function Scene({ points, currentUserId, selectedUserId, matchUserIds, onNodeClick, onNodeHover }) {
  const selectedPoint = points.find((point) => point.user_id === selectedUserId)
  const matchPoints = points.filter((point) => matchUserIds.includes(point.user_id))

  return (
    <>
      <ambientLight intensity={0.45} color="#1a1a2e" />
      <pointLight position={[3, 3, 3]} intensity={3} color="#7c6aff" />
      <pointLight position={[-3, -2, -2]} intensity={2} color="#6affd4" />
      <Stars radius={30} depth={20} count={900} factor={2} fade />

      {points.map((point) => (
        <Node
          key={point.user_id}
          point={point}
          isCurrentUser={point.user_id === currentUserId}
          isSelected={point.user_id === selectedUserId}
          isMatch={matchUserIds.includes(point.user_id)}
          onClick={onNodeClick}
          onHover={onNodeHover}
        />
      ))}

      <MatchLines selectedPoint={selectedPoint} matchPoints={matchPoints} />
    </>
  )
}

export default function Explore() {
  const { session } = useAuth()
  const navigate = useNavigate()
  const currentUserId = session?.user?.id || ''

  const [points, setPoints] = useState([])
  const [loading, setLoading] = useState(true)
  const [hoveredUser, setHoveredUser] = useState(null)
  const [selectedUser, setSelectedUser] = useState(null)
  const [matches, setMatches] = useState([])
  const [activeMatchUserIds, setActiveMatchUserIds] = useState([])
  const [activeGraphUserId, setActiveGraphUserId] = useState(null)
  const [matchLoading, setMatchLoading] = useState(false)
  const [panelOpen, setPanelOpen] = useState(false)
  const [tooltipPos, setTooltipPos] = useState({ x: 0, y: 0 })
  const [weights, setWeights] = useState({ github: 1, steam: 1 })
  const [userSources, setUserSources] = useState([])
  const [showSeeded, setShowSeeded] = useState(true)
  const debounceRef = useRef(null)

  useEffect(() => {
    loadPoints()
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
    }
  }, [])

  async function loadPoints() {
    setLoading(true)
    try {
      const data = await getUmap()
      const nextPoints = data.points || []
      setPoints(nextPoints)

      const me = nextPoints.find((point) => point.user_id === currentUserId)
      if (me?.sources?.length) {
        setUserSources(me.sources)
        setWeights(Object.fromEntries(me.sources.map((source) => [source, 1])))
      }
    } catch (error) {
      console.error(error)
    } finally {
      setLoading(false)
    }
  }

  async function fetchMatchesForUser(userId, nextWeights = null) {
    setMatchLoading(true)
    try {
      const data = nextWeights
        ? await getWeightedMatches(userId, nextWeights, 5)
        : await getMatches(userId, 5)
      const nextMatches = data.matches || []
      setMatches(nextMatches)
      setActiveGraphUserId(userId)
      setActiveMatchUserIds(nextMatches.map((match) => match.user_id))
    } catch (error) {
      console.error(error)
      setMatches([])
      setActiveGraphUserId(userId)
      setActiveMatchUserIds([])
    } finally {
      setMatchLoading(false)
    }
  }

  async function handleNodeClick(point) {
    setSelectedUser(point)
    setPanelOpen(true)
    setActiveGraphUserId(point.user_id)
    await fetchMatchesForUser(point.user_id)
  }

  function clearSelection() {
    setPanelOpen(false)
    setSelectedUser(null)
    setMatches([])
    setActiveGraphUserId(null)
    setActiveMatchUserIds([])
  }

  function handleWeightChange(source, value) {
    const nextWeights = { ...weights, [source]: Number.parseFloat(value) }
    setWeights(nextWeights)

    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      if (selectedUser) fetchMatchesForUser(selectedUser.user_id, nextWeights)
    }, 350)
  }

  const myPoint = points.find((point) => point.user_id === currentUserId)
  const activeGraphPoint = points.find((point) => point.user_id === activeGraphUserId) || selectedUser
  const visiblePoints = showSeeded ? points : points.filter((point) => !point.seeded)
  const visibleMatchUserIds = activeMatchUserIds.filter((userId) => visiblePoints.some((point) => point.user_id === userId))
  const seededCount = points.filter((point) => point.seeded).length

  return (
    <div className={styles.root} onMouseMove={(event) => setTooltipPos({ x: event.clientX, y: event.clientY })}>
      <div className={styles.backdrop} />

      <header className={styles.header}>
        <button className={styles.back} onClick={() => navigate('/dashboard')}>
          Back to dashboard
        </button>
        <span className={styles.logo}>Vibe<span>Finder</span></span>
        <span className={styles.count}>{visiblePoints.length} profiles</span>
      </header>

      {loading ? (
        <div className={styles.loader}>
          <div className={styles.spinner} />
          <p>Mapping the space...</p>
        </div>
      ) : (
        <Canvas className={styles.canvas} camera={{ position: [0, 0, 5], fov: 60 }}>
          <Scene
            points={visiblePoints}
            currentUserId={currentUserId}
            selectedUserId={activeGraphUserId}
            matchUserIds={visibleMatchUserIds}
            onNodeClick={handleNodeClick}
            onNodeHover={setHoveredUser}
          />
          <OrbitControls enableDamping dampingFactor={0.06} autoRotate={!panelOpen} autoRotateSpeed={0.35} />
        </Canvas>
      )}

      {hoveredUser && (
        <div className={styles.tooltip} style={{ left: tooltipPos.x + 14, top: tooltipPos.y - 10 }}>
          <strong>{displayNameFor(hoveredUser)}</strong>
          {hoveredUser.sources?.length > 0 && (
            <span className={styles.tooltipSources}> | {hoveredUser.sources.join(' + ')}</span>
          )}
        </div>
      )}

      <div className={styles.legend}>
        <label className={styles.toggle}>
          <input
            type="checkbox"
            checked={showSeeded}
            onChange={(event) => setShowSeeded(event.target.checked)}
          />
          <span>Show seeded</span>
          <strong>{seededCount}</strong>
        </label>
        <div className={styles.legendItem}>
          <div className={styles.legendDot} style={{ background: PROFILE_COLORS.profile }} />
          Profile
        </div>
        <div className={styles.legendItem}>
          <div className={styles.legendDot} style={{ background: PROFILE_COLORS.currentUser }} />
          You
        </div>
        <div className={styles.legendItem}>
          <div className={styles.legendDot} style={{ background: PROFILE_COLORS.seeded }} />
          Seeded profile
        </div>
        <div className={styles.legendItem}>
          <div className={styles.legendDot} style={{ background: PROFILE_COLORS.selected }} />
          Selected
        </div>
      </div>

      <aside className={`${styles.panel} ${panelOpen ? styles.open : ''}`}>
        <div className={styles.panelActions}>
          <button className={styles.panelClose} onClick={() => setPanelOpen(false)}>Hide details</button>
          {activeGraphUserId && (
            <button className={styles.panelClear} onClick={clearSelection}>Clear graph</button>
          )}
        </div>

        {selectedUser && (
          <>
            {selectedUser.github_username ? (
              <a
                className={styles.panelUsername}
                href={`https://github.com/${selectedUser.github_username}`}
                target="_blank"
                rel="noreferrer"
              >
                {displayNameFor(selectedUser)}
              </a>
            ) : (
              <div className={styles.panelUsername}>{displayNameFor(selectedUser)}</div>
            )}

            <div className={styles.userMeta}>{selectedUser.seeded ? 'Seeded comparison profile' : selectedUser.user_id}</div>

            <div className={styles.tagSection}>
              {selectedUser.top_languages?.length > 0 && (
                <>
                  <div className={styles.tagLabel}>Languages</div>
                  <div className={styles.tagRow}>
                    {selectedUser.top_languages.map((language) => (
                      <span key={language} className={`${styles.tag} ${styles.tagLang}`}>{language}</span>
                    ))}
                  </div>
                </>
              )}

              {selectedUser.top_topics?.length > 0 && (
                <>
                  <div className={styles.tagLabel}>Topics</div>
                  <div className={styles.tagRow}>
                    {selectedUser.top_topics.map((topic) => (
                      <span key={topic} className={`${styles.tag} ${styles.tagTopic}`}>{topic}</span>
                    ))}
                  </div>
                </>
              )}

              {((selectedUser.top_favorites && selectedUser.top_favorites.length) || (selectedUser.top_anime || []).length > 0) && (
                <>
                  <div className={styles.tagLabel}>ANIME</div>
                  <div className={styles.tagRow}>
                    {(selectedUser.top_favorites?.length ? selectedUser.top_favorites : selectedUser.top_anime || []).slice(0, 5).map((anime) => (
                      <span key={anime} className={`${styles.tag} ${styles.tagAnime}`}>{anime}</span>
                    ))}
                  </div>
                </>
              )}

              {selectedUser.top_games?.length > 0 && (
                <>
                  <div className={styles.tagLabel}>Top games</div>
                  <div className={styles.tagRow}>
                    {selectedUser.top_games.map((game) => (
                      <span key={game} className={`${styles.tag} ${styles.tagGame}`}>{game}</span>
                    ))}
                  </div>
                </>
              )}

            </div>

            {selectedUser.user_id === currentUserId && userSources.length > 1 && (
              <div className={styles.sliders}>
                <div className={styles.sliderLabel}>Reweight your vibe</div>
                <p className={styles.sliderHint}>Shift emphasis between the sources you connected.</p>
                {userSources.map((source) => (
                  <div key={source} className={styles.sliderRow}>
                    <div className={styles.sliderSource}>
                      {source}
                    </div>
                    <input
                      type="range"
                      min="0"
                      max="1"
                      step="0.05"
                      value={weights[source] ?? 1}
                      onChange={(event) => handleWeightChange(source, event.target.value)}
                      className={styles.slider}
                    />
                    <span className={styles.sliderValue}>{Math.round((weights[source] ?? 1) * 100)}%</span>
                  </div>
                ))}
              </div>
            )}

            <div className={styles.matchesSection}>
              <div className={styles.tagLabel}>Closest profiles</div>
              {matchLoading ? (
                <div className={styles.matchLoading}>Querying vectors...</div>
              ) : (
                matches.length === 0 ? (
                  <div className={styles.emptyState}>No closest profiles returned yet. Try selecting a seeded profile or reconnecting a source.</div>
                ) : (
                  <div className={styles.matchList}>
                    {matches.map((match) => (
                      <button
                        key={match.user_id}
                        className={styles.matchCard}
                        onClick={() => handleNodeClick(points.find((point) => point.user_id === match.user_id) || match)}
                      >
                        <div className={styles.matchName}>{displayNameFor(match)}</div>
                        <div className={styles.matchSim}>{(match.similarity * 100).toFixed(1)}% similarity</div>
                        {match.explanation && (
                          <div className={styles.matchExplanation}>{match.explanation}</div>
                        )}
                        <div className={styles.simBar}>
                          <div className={styles.simFill} style={{ width: `${match.similarity * 100}%` }} />
                        </div>
                        {(match.top_languages || []).length > 0 && (
                          <div className={styles.tagRow}>
                            <span className={`${styles.tag} ${styles.tagRowLabel}`}>LANG</span>
                            {match.top_languages.slice(0, 3).map((language) => (
                              <span key={language} className={`${styles.tag} ${styles.tagLang}`}>{language}</span>
                            ))}
                          </div>
                        )}
                        {((match.top_favorites && match.top_favorites.length) || (match.top_anime || []).length > 0) && (
                          <div className={styles.tagRow}>
                            <span className={`${styles.tag} ${styles.tagRowLabel}`}>ANIME</span>
                            {(match.top_favorites?.length ? match.top_favorites : match.top_anime || []).slice(0, 3).map((anime) => (
                              <span key={anime} className={`${styles.tag} ${styles.tagAnime}`}>{anime}</span>
                            ))}
                          </div>
                        )}
                        {(match.top_games || []).length > 0 && (
                          <div className={styles.tagRow}>
                            <span className={`${styles.tag} ${styles.tagRowLabel}`}>GAME</span>
                            {match.top_games.slice(0, 3).map((game) => (
                              <span key={game} className={`${styles.tag} ${styles.tagGame}`}>{game}</span>
                            ))}
                          </div>
                        )}
                      </button>
                    ))}
                  </div>
                )
              )}
            </div>
          </>
        )}
      </aside>

      {activeGraphPoint && !panelOpen && (
        <div className={styles.graphStatus}>
          <span>Connections pinned for {displayNameFor(activeGraphPoint)}</span>
          <button className={styles.graphStatusButton} onClick={() => setPanelOpen(true)}>Open details</button>
          <button className={styles.graphStatusButton} onClick={clearSelection}>Clear</button>
        </div>
      )}

      {myPoint && !panelOpen && (
        <button className={styles.findMe} onClick={() => handleNodeClick(myPoint)}>
          Find me in the space
        </button>
      )}
    </div>
  )
}
