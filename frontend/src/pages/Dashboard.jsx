import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../App'
import { buildGithubConnectUrl, connectSteam, connectAnilist, getUser } from '../lib/api'
import { supabase } from '../lib/supabase'
import styles from './Dashboard.module.css'

export default function Dashboard() {
  const { session } = useAuth()
  const navigate = useNavigate()

  const userId = session?.user?.id || ''
  const displayName =
    session?.user?.user_metadata?.full_name ||
    session?.user?.email ||
    'Anonymous explorer'

  const [connectedSources, setConnectedSources] = useState([])
  const [githubMeta, setGithubMeta] = useState({ top_languages: [], top_topics: [] })
  const [anilistMeta, setAnilistMeta] = useState({ top_anime: [], top_genres: [] })
  const [steamInput, setSteamInput] = useState('')
  const [steamLoading, setSteamLoading] = useState(false)
  const [steamError, setSteamError] = useState('')
  const [steamSuccess, setSteamSuccess] = useState('')
  const [anilistInput, setAnilistInput] = useState('')
  const [anilistLoading, setAnilistLoading] = useState(false)
  const [anilistError, setAnilistError] = useState('')
  const [anilistSuccess, setAnilistSuccess] = useState('')
  const [loadingUser, setLoadingUser] = useState(true)
  const [githubSuccess, setGithubSuccess] = useState(false)

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    if (params.get('github') === 'success') {
      setGithubSuccess(true)
      window.history.replaceState({}, '', '/dashboard')
      if (userId) loadUserData()
    }
  }, [])

  useEffect(() => {
    if (!userId) return
    loadUserData()
  }, [userId])

  useEffect(() => {
    if (githubSuccess && userId) {
      loadUserData()
    }
  }, [githubSuccess, userId])

  async function loadUserData() {
    setLoadingUser(true)
    try {
      const user = await getUser(userId)
      setConnectedSources(user.sources || [])
      setGithubMeta({
        top_languages: user.top_languages || [],
        top_topics: user.top_topics || [],
      })
      setAnilistMeta({
        top_anime: user.top_anime || [],
        top_genres: user.top_genres || [],
      })
      // If steam metadata exists, show a summary message
      if (user.top_games && user.top_games.length) {
        setSteamSuccess(`Top picks: ${user.top_games.slice(0, 3).join(', ')}`)
      }
    } catch (error) {
      setConnectedSources([])
    } finally {
      setLoadingUser(false)
    }
  }

  function handleGithubConnect() {
    window.location.href = buildGithubConnectUrl(userId, displayName)
  }

  async function handleAnilistConnect() {
    if (!anilistInput.trim()) return

    setAnilistLoading(true)
    setAnilistError('')
    setAnilistSuccess('')

    try {
      const result = await connectAnilist(userId, anilistInput.trim(), displayName)
      setAnilistSuccess(`Connected ${result.anime_count} anime. Top picks: ${(result.top_anime || []).slice(0, 3).join(', ')}`)
      setConnectedSources((current) => [...new Set([...current, 'anilist'])])
      setAnilistInput('')
    } catch (error) {
      setAnilistError(error.message || 'Failed to connect AniList')
    } finally {
      setAnilistLoading(false)
    }
  }

  async function handleSteamConnect() {
    if (!steamInput.trim()) return

    setSteamLoading(true)
    setSteamError('')
    setSteamSuccess('')

    try {
      const result = await connectSteam(userId, steamInput.trim(), displayName)
      setSteamSuccess(`Connected ${result.total_games} games. Top picks: ${(result.top_games || []).slice(0, 3).join(', ')}`)
      setConnectedSources((current) => [...new Set([...current, 'steam'])])
      setSteamInput('')
    } catch (error) {
      setSteamError(error.message || 'Failed to connect Steam')
    } finally {
      setSteamLoading(false)
    }
  }

  async function handleSignOut() {
    await supabase.auth.signOut()
  }

  const isConnected = (source) => connectedSources.includes(source)
  const canExplore = connectedSources.length > 0

  return (
    <div className={styles.root}>
      <div className={styles.glowA} />
      <div className={styles.glowB} />

      <header className={styles.header}>
        <div>
          <span className={styles.logo}>Vibe<span>Finder</span></span>
          <p className={styles.headerCopy}>Link sources, build your vector, then step into the map.</p>
        </div>
        <div className={styles.headerRight}>
          <span className={styles.userEmail}>{displayName}</span>
          <button className={styles.signOut} onClick={handleSignOut}>Sign out</button>
        </div>
      </header>

      <main className={styles.main}>
        <section className={styles.intro}>
          <div className={styles.kicker}>Authenticated via Google</div>
          <h1 className={styles.heading}>Connect your data sources</h1>
          <p className={styles.sub}>
            GitHub captures what you build. Steam captures what you gravitate toward.
          </p>
          <div className={styles.identityCard}>
            <span className={styles.identityLabel}>User ID</span>
            <code className={styles.identityValue}>{userId}</code>
          </div>
          {githubSuccess && <div className={styles.successBanner}>GitHub connected. Your graph is ready to refresh.</div>}
        </section>

        <section className={styles.cards}>
          <article className={`${styles.card} ${isConnected('github') ? styles.connected : ''}`}>
            <div className={styles.cardHeader}>
              <div className={styles.sourceIcon} style={{ '--c': '#7c6aff' }}>
                <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                  <path d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z" />
                </svg>
              </div>
              <div>
                <div className={styles.sourceName}>GitHub</div>
                <div className={styles.sourceDesc}>Repos, stars, languages, topics</div>
              </div>
              {isConnected('github') && <span className={styles.connectedBadge}>Connected</span>}
            </div>
              <div style={{display: 'flex', flexDirection: 'column', gap: '8px'}}>
                <button className={styles.connectBtn} style={{ '--c': '#7c6aff' }} onClick={handleGithubConnect}>
                  {isConnected('github') ? 'Reconnect GitHub' : 'Connect GitHub'}
                </button>
                {isConnected('github') && (
                  <div className={styles.sourceMeta}>
                    <div><strong>Top languages:</strong> {(githubMeta.top_languages || []).slice(0,3).join(', ') || '—'}</div>
                    <div><strong>Top topics:</strong> {(githubMeta.top_topics || []).slice(0,3).join(', ') || '—'}</div>
                  </div>
                )}
              </div>
          </article>

          <article className={`${styles.card} ${isConnected('steam') ? styles.connected : ''}`}>
            <div className={styles.cardHeader}>
              <div className={styles.sourceIcon} style={{ '--c': '#6affd4' }}>
                <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                  <path d="M11.979 0C5.678 0 .511 4.86.022 11.037l6.432 2.658c.545-.371 1.203-.59 1.912-.59.063 0 .125.004.188.006l2.861-4.142V8.91c0-2.495 2.028-4.524 4.524-4.524 2.494 0 4.524 2.031 4.524 4.527s-2.03 4.525-4.524 4.525h-.105l-4.076 2.911c0 .052.004.105.004.159 0 1.875-1.515 3.396-3.39 3.396-1.635 0-3.016-1.173-3.331-2.727L.436 15.27C1.862 20.307 6.486 24 11.979 24c6.627 0 11.999-5.373 11.999-12S18.605 0 11.979 0z" />
                </svg>
              </div>
              <div>
                <div className={styles.sourceName}>Steam</div>
                <div className={styles.sourceDesc}>Library, playtime, genres</div>
              </div>
              {isConnected('steam') && <span className={styles.connectedBadge}>Connected</span>}
            </div>

            <div className={styles.steamForm}>
              <input
                className={styles.input}
                placeholder="Steam vanity name or profile URL"
                value={steamInput}
                onChange={(event) => setSteamInput(event.target.value)}
                onKeyDown={(event) => event.key === 'Enter' && handleSteamConnect()}
              />
              <button
                className={styles.connectBtn}
                style={{ '--c': '#6affd4' }}
                onClick={handleSteamConnect}
                disabled={steamLoading || !steamInput.trim()}
              >
                {steamLoading ? 'Fetching...' : isConnected('steam') ? 'Update Steam' : 'Connect Steam'}
              </button>
            </div>

            {steamError && <div className={styles.error}>{steamError}</div>}
            {steamSuccess && <div className={styles.success}>{steamSuccess}</div>}
          </article>

          <article className={`${styles.card} ${isConnected('anilist') ? styles.connected : ''}`}>
            <div className={styles.cardHeader}>
              <div className={styles.sourceIcon} style={{ '--c': '#f47fff' }}>
                <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                  <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8zm-5-9h10v2H7z" />
                </svg>
              </div>
              <div>
                <div className={styles.sourceName}>AniList</div>
                <div className={styles.sourceDesc}>Anime, manga, genres, studios</div>
              </div>
              {isConnected('anilist') && <span className={styles.connectedBadge}>Connected</span>}
            </div>

            <div className={styles.steamForm}>
              <input
                className={styles.input}
                placeholder="AniList username"
                value={anilistInput}
                onChange={(event) => setAnilistInput(event.target.value)}
                onKeyDown={(event) => event.key === 'Enter' && handleAnilistConnect()}
              />
              <button
                className={styles.connectBtn}
                style={{ '--c': '#f47fff' }}
                onClick={handleAnilistConnect}
                disabled={anilistLoading || !anilistInput.trim()}
              >
                {anilistLoading ? 'Fetching...' : isConnected('anilist') ? 'Update AniList' : 'Connect AniList'}
              </button>
            </div>

            {anilistError && <div className={styles.error}>{anilistError}</div>}
            {anilistSuccess && <div className={styles.success}>{anilistSuccess}</div>}
            {isConnected('anilist') && !anilistSuccess && (
              <div className={styles.sourceMeta}>
                <div><strong>Top anime:</strong> {(anilistMeta.top_anime || []).slice(0,2).join(', ') || '—'}</div>
                <div><strong>Top genres:</strong> {(anilistMeta.top_genres || []).slice(0,3).join(', ') || '—'}</div>
              </div>
            )}
          </article>
        </section>

        <section className={styles.enterSection}>
          {loadingUser ? (
            <div className={styles.loadingText}>Checking your profile...</div>
          ) : canExplore ? (
            <button className={styles.exploreBtn} onClick={() => navigate('/explore')}>
              Enter the space
            </button>
          ) : (
            <p className={styles.connectHint}>Connect at least one source to generate your position in the map.</p>
          )}
        </section>
      </main>
    </div>
  )
}
