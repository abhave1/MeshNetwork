/**
 * Main App component for MeshNetwork frontend.
 */

import React, { useState, useEffect } from 'react';
import api from './services/api';
import { Post, RegionEndpoint } from './types';
import './App.css';

const REGIONS: RegionEndpoint[] = [
  { name: 'North America', url: 'http://localhost:5010', code: 'north_america' },
  { name: 'Europe', url: 'http://localhost:5011', code: 'europe' },
  { name: 'Asia-Pacific', url: 'http://localhost:5012', code: 'asia_pacific' },
];

function App() {
  const [selectedRegion, setSelectedRegion] = useState<RegionEndpoint>(REGIONS[0]);
  const [posts, setPosts] = useState<Post[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [regionHealth, setRegionHealth] = useState<any>(null);

  // All regions health status for the overview panel
  const [allRegionsHealth, setAllRegionsHealth] = useState<Record<string, any>>({});

  // New post form state
  const [showPostForm, setShowPostForm] = useState(false);
  const [newPost, setNewPost] = useState({
    user_id: '',
    post_type: 'help',
    message: '',
    longitude: -122.4194,
    latitude: 37.7749,
  });

  // Mark safe form state
  const [showMarkSafeForm, setShowMarkSafeForm] = useState(false);
  const [safeUserId, setSafeUserId] = useState('');

  // View nearby form state
  const [showNearbyForm, setShowNearbyForm] = useState(false);
  const [nearbyLocation, setNearbyLocation] = useState({
    latitude: 37.7749,
    longitude: -122.4194,
    radius: 10000,
  });
  const [nearbyPosts, setNearbyPosts] = useState<Post[]>([]);
  const [showingNearby, setShowingNearby] = useState(false);

  // Live-updating island mode timer
  const [currentTime, setCurrentTime] = useState(new Date());

  // Update current time every second for live timer
  useEffect(() => {
    const timer = setInterval(() => {
      setCurrentTime(new Date());
    }, 1000); // Update every second

    return () => clearInterval(timer);
  }, []);

  // Load posts when region changes
  useEffect(() => {
    api.setBaseUrl(selectedRegion.url);
    loadPosts();
    loadRegionHealth();
  }, [selectedRegion]);

  // Poll region health every 5 seconds for real-time island mode updates
  useEffect(() => {
    const healthInterval = setInterval(() => {
      loadRegionHealth();
    }, 5000); // Poll every 5 seconds

    return () => clearInterval(healthInterval);
  }, [selectedRegion]);

  // Load health status for all regions
  const loadAllRegionsHealth = async () => {
    const healthResults: Record<string, any> = {};
    
    await Promise.all(
      REGIONS.map(async (region) => {
        try {
          const response = await fetch(`${region.url}/status`);
          if (response.ok) {
            healthResults[region.code] = await response.json();
          } else {
            healthResults[region.code] = { error: 'Failed to fetch', status: 'unreachable' };
          }
        } catch (err) {
          healthResults[region.code] = { error: 'Connection failed', status: 'unreachable' };
        }
      })
    );
    
    setAllRegionsHealth(healthResults);
  };

  // Poll all regions health every 5 seconds
  useEffect(() => {
    loadAllRegionsHealth(); // Initial load
    const allHealthInterval = setInterval(() => {
      loadAllRegionsHealth();
    }, 5000);

    return () => clearInterval(allHealthInterval);
  }, []);

  const loadPosts = async () => {
    setLoading(true);
    setError(null);
    try {
      // Use region='all' to show posts from all regions (cross-region sync)
      const response = await api.getPosts({ limit: 50, region: 'all' });
      setPosts(response.posts || []);
    } catch (err: any) {
      setError(err.message || 'Failed to load posts');
      console.error('Error loading posts:', err);
    } finally {
      setLoading(false);
    }
  };

  const loadRegionHealth = async () => {
    try {
      const status = await api.getStatus();
      setRegionHealth(status);
    } catch (err) {
      console.error('Error loading region health:', err);
    }
  };

  const handleRegionChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const region = REGIONS.find(r => r.code === e.target.value);
    if (region) {
      setSelectedRegion(region);
    }
  };

  const handleCreatePost = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    try {
      await api.createPost({
        user_id: newPost.user_id,
        post_type: newPost.post_type as any,
        message: newPost.message,
        location: {
          type: 'Point',
          coordinates: [newPost.longitude, newPost.latitude],
        },
        region: selectedRegion.code,
      });

      // Reset form
      setNewPost({
        user_id: '',
        post_type: 'help',
        message: '',
        longitude: -122.4194,
        latitude: 37.7749,
      });
      setShowPostForm(false);

      // Reload posts
      loadPosts();
    } catch (err: any) {
      setError(err.response?.data?.error || 'Failed to create post');
      console.error('Error creating post:', err);
    }
  };

  const handleMarkSafe = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    try {
      await api.markUserSafe(safeUserId);
      setSafeUserId('');
      setShowMarkSafeForm(false);

      // Reload posts to show the new safety status
      loadPosts();
    } catch (err: any) {
      setError(err.response?.data?.error || 'Failed to mark user as safe');
      console.error('Error marking user safe:', err);
    }
  };

  const handleViewNearby = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      const response = await api.getHelpRequests({
        latitude: nearbyLocation.latitude,
        longitude: nearbyLocation.longitude,
        radius: nearbyLocation.radius,
      });

      setNearbyPosts(response.help_requests || []);
      setShowingNearby(true);
      setShowNearbyForm(false);
    } catch (err: any) {
      setError(err.response?.data?.error || 'Failed to load nearby updates');
      console.error('Error loading nearby updates:', err);
    } finally {
      setLoading(false);
    }
  };

  const getPostTypeColor = (type: string): string => {
    const colors: Record<string, string> = {
      shelter: '#2196F3',
      food: '#4CAF50',
      medical: '#F44336',
      water: '#00BCD4',
      safety: '#FFC107',
      help: '#FF5722',
    };
    return colors[type] || '#9E9E9E';
  };

  const formatTimestamp = (timestamp: string): string => {
    const date = new Date(timestamp);

    // Always display in UTC
    const utcString = date.toLocaleString('en-US', {
      timeZone: 'UTC',
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false
    });

    return `${utcString} UTC`;
  };

  const formatDuration = (seconds: number): string => {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);

    if (hours > 0) {
      return `${hours}h ${minutes}m ${secs}s`;
    } else if (minutes > 0) {
      return `${minutes}m ${secs}s`;
    } else {
      return `${secs}s`;
    }
  };

  const calculateIslandDuration = (): number | null => {
    // Use the backend-provided isolation_start and calculate elapsed time
    if (!regionHealth?.island_mode?.isolation_start) {
      return null;
    }

    // Parse the ISO timestamp from backend
    const startTime = new Date(regionHealth.island_mode.isolation_start);
    
    // Check if the date is valid
    if (isNaN(startTime.getTime())) {
      console.warn('Invalid isolation_start timestamp:', regionHealth.island_mode.isolation_start);
      // Fallback to backend-provided duration
      return regionHealth?.island_mode?.isolation_duration_seconds ?? null;
    }

    const elapsed = (currentTime.getTime() - startTime.getTime()) / 1000; // Convert to seconds
    return Math.max(0, elapsed);
  };

  // Calculate island duration for any region's health data
  const calculateRegionIslandDuration = (health: any): number | null => {
    if (!health?.island_mode?.isolation_start) {
      return null;
    }

    const startTime = new Date(health.island_mode.isolation_start);
    
    if (isNaN(startTime.getTime())) {
      return health?.island_mode?.isolation_duration_seconds ?? null;
    }

    const elapsed = (currentTime.getTime() - startTime.getTime()) / 1000;
    return Math.max(0, elapsed);
  };

  // Get region display info
  const getRegionEmoji = (code: string): string => {
    const emojis: Record<string, string> = {
      'north_america': '🌎',
      'europe': '🌍',
      'asia_pacific': '🌏'
    };
    return emojis[code] || '🌐';
  };

  return (
    <div className="App">
      {/* Header */}
      <header className="app-header">
        <h1>MeshNetwork</h1>
        <p>Disaster Resilient Social Platform</p>
      </header>

      {/* All Regions Status Panel */}
      <div className="all-regions-panel">
        <h3>🌐 Global Region Status</h3>
        <div className="regions-grid">
          {REGIONS.map((region) => {
            const health = allRegionsHealth[region.code];
            const isUnreachable = !health || health.status === 'unreachable';
            const isIsland = health?.island_mode?.active;
            const islandDuration = health ? calculateRegionIslandDuration(health) : null;
            
            return (
              <div 
                key={region.code} 
                className={`region-card ${isUnreachable ? 'unreachable' : ''} ${isIsland ? 'island' : ''} ${selectedRegion.code === region.code ? 'selected' : ''}`}
                onClick={() => setSelectedRegion(region)}
              >
                <div className="region-header">
                  <span className="region-emoji">{getRegionEmoji(region.code)}</span>
                  <span className="region-name">{region.name}</span>
                  {selectedRegion.code === region.code && <span className="current-badge">VIEWING</span>}
                </div>
                
                {isUnreachable ? (
                  <div className="region-status unreachable">
                    <span className="status-indicator">❌</span>
                    <span>Unreachable</span>
                  </div>
                ) : (
                  <>
                    <div className="region-status">
                      <span className={`status-indicator ${health?.database?.status === 'healthy' ? 'healthy' : 'degraded'}`}>
                        {health?.database?.status === 'healthy' ? '✅' : '⚠️'}
                      </span>
                      <span>DB: {health?.database?.status || 'unknown'}</span>
                    </div>
                    
                    {isIsland ? (
                      <div className="region-island-status">
                        <span className="island-indicator">🏝️</span>
                        <span className="island-label">ISLAND MODE</span>
                        <span className="island-timer">
                          {islandDuration !== null 
                            ? formatDuration(islandDuration)
                            : health?.island_mode?.isolation_duration_seconds 
                              ? formatDuration(health.island_mode.isolation_duration_seconds)
                              : '--'}
                        </span>
                      </div>
                    ) : (
                      <div className="region-connected-status">
                        <span className="connected-indicator">🔗</span>
                        <span>Connected ({health?.island_mode?.connected_regions || 0}/{health?.island_mode?.total_regions || 0} regions)</span>
                      </div>
                    )}
                  </>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Region Selector */}
      <div className="region-selector">
        <label htmlFor="region">Connected Region: </label>
        <select
          id="region"
          value={selectedRegion.code}
          onChange={handleRegionChange}
        >
          {REGIONS.map(region => (
            <option key={region.code} value={region.code}>
              {region.name}
            </option>
          ))}
        </select>

        <span style={{ marginLeft: '20px', color: '#666' }}>
          All times displayed in UTC
        </span>
      </div>

      {/* Island Mode Warning */}
      {regionHealth?.island_mode?.active && (
        <div className="island-mode-warning">
          <div className="warning-icon">⚠️</div>
          <div className="warning-content">
            <strong>ISLAND MODE ACTIVE</strong>
            <p>
              This region is isolated from other regions.
              {' '}Local operations continue normally, but cross-region sync is paused.
            </p>
            <p style={{ marginTop: '8px', fontWeight: 600, fontSize: '1.1em' }}>
              ⏱️ Isolated for:{' '}
              <span style={{ color: '#ff6b35', fontFamily: 'monospace' }}>
                {calculateIslandDuration() !== null 
                  ? formatDuration(calculateIslandDuration()!)
                  : regionHealth?.island_mode?.isolation_duration_seconds 
                    ? formatDuration(regionHealth.island_mode.isolation_duration_seconds)
                    : 'calculating...'}
              </span>
            </p>
          </div>
        </div>
      )}

      {/* System Status */}
      {regionHealth && (
        <div className="system-status">
          <h3>System Status</h3>
          <div className="status-info">
            <div className="status-item">
              <strong>Database:</strong>{' '}
              <span className={`status-badge ${regionHealth.database?.status}`}>
                {regionHealth.database?.status}
              </span>
            </div>
            <div className="status-item">
              <strong>Replica Set:</strong> {regionHealth.database?.replica_set}
            </div>
            <div className="status-item">
              <strong>Primary:</strong> {regionHealth.database?.primary}
            </div>
          </div>
        </div>
      )}

      {/* Error Display */}
      {error && (
        <div className="error-message">
          <strong>Error:</strong> {error}
          <button onClick={() => setError(null)}>✕</button>
        </div>
      )}

      {/* Action Buttons */}
      <div className="action-buttons">
        <button onClick={loadPosts} disabled={loading}>
          {loading ? 'Loading...' : 'Refresh Posts'}
        </button>
        <button onClick={() => setShowPostForm(!showPostForm)}>
          {showPostForm ? 'Hide Form' : 'Create Post'}
        </button>
        <button onClick={() => setShowMarkSafeForm(!showMarkSafeForm)}>
          {showMarkSafeForm ? 'Hide' : '✓ Mark Safe'}
        </button>
        <button onClick={() => setShowNearbyForm(!showNearbyForm)}>
          {showNearbyForm ? 'Hide' : '📍 View Nearby'}
        </button>
        {showingNearby && (
          <button onClick={() => { setShowingNearby(false); loadPosts(); }}>
            Show All Posts
          </button>
        )}
      </div>

      {/* Post Form */}
      {showPostForm && (
        <div className="post-form">
          <h3>Create New Post</h3>
          <form onSubmit={handleCreatePost}>
            <div className="form-group">
              <label>User ID:</label>
              <input
                type="text"
                value={newPost.user_id}
                onChange={(e) => setNewPost({ ...newPost, user_id: e.target.value })}
                required
                placeholder="Enter your user ID"
              />
            </div>

            <div className="form-group">
              <label>Post Type:</label>
              <select
                value={newPost.post_type}
                onChange={(e) => setNewPost({ ...newPost, post_type: e.target.value })}
              >
                <option value="help">Help Request</option>
                <option value="shelter">Shelter</option>
                <option value="food">Food</option>
                <option value="medical">Medical</option>
                <option value="water">Water</option>
                <option value="safety">Safety Status</option>
              </select>
            </div>

            <div className="form-group">
              <label>Message:</label>
              <textarea
                value={newPost.message}
                onChange={(e) => setNewPost({ ...newPost, message: e.target.value })}
                required
                rows={4}
                placeholder="Describe the situation..."
              />
            </div>

            <div className="form-group">
              <label>Location:</label>
              <div className="location-inputs">
                <input
                  type="number"
                  step="any"
                  value={newPost.latitude}
                  onChange={(e) => setNewPost({ ...newPost, latitude: parseFloat(e.target.value) })}
                  placeholder="Latitude"
                />
                <input
                  type="number"
                  step="any"
                  value={newPost.longitude}
                  onChange={(e) => setNewPost({ ...newPost, longitude: parseFloat(e.target.value) })}
                  placeholder="Longitude"
                />
              </div>
            </div>

            <button type="submit">Submit Post</button>
          </form>
        </div>
      )}

      {/* Mark Safe Form */}
      {showMarkSafeForm && (
        <div className="post-form">
          <h3>✓ Mark User as Safe</h3>
          <p style={{ color: '#666', marginBottom: '15px' }}>
            Create a safety status post to let others know you're safe
          </p>
          <form onSubmit={handleMarkSafe}>
            <div className="form-group">
              <label>Your User ID:</label>
              <input
                type="text"
                value={safeUserId}
                onChange={(e) => setSafeUserId(e.target.value)}
                required
                placeholder="Enter your user ID"
              />
            </div>
            <button type="submit">Mark as Safe</button>
          </form>
        </div>
      )}

      {/* View Nearby Form */}
      {showNearbyForm && (
        <div className="post-form">
          <h3>📍 View Nearby Help Requests</h3>
          <p style={{ color: '#666', marginBottom: '15px' }}>
            Find help requests near a specific location
          </p>
          <form onSubmit={handleViewNearby}>
            <div className="form-group">
              <label>Location:</label>
              <div className="location-inputs">
                <input
                  type="number"
                  step="any"
                  value={nearbyLocation.latitude}
                  onChange={(e) => setNearbyLocation({ ...nearbyLocation, latitude: parseFloat(e.target.value) })}
                  placeholder="Latitude"
                  required
                />
                <input
                  type="number"
                  step="any"
                  value={nearbyLocation.longitude}
                  onChange={(e) => setNearbyLocation({ ...nearbyLocation, longitude: parseFloat(e.target.value) })}
                  placeholder="Longitude"
                  required
                />
              </div>
            </div>
            <div className="form-group">
              <label>Search Radius (meters):</label>
              <input
                type="number"
                value={nearbyLocation.radius}
                onChange={(e) => setNearbyLocation({ ...nearbyLocation, radius: parseInt(e.target.value) })}
                placeholder="10000"
                min="100"
                step="1000"
              />
              <small style={{ color: '#666', display: 'block', marginTop: '5px' }}>
                Default: 10,000 meters (~6 miles)
              </small>
            </div>
            <button type="submit">Search Nearby</button>
          </form>
        </div>
      )}

      {/* Posts Feed */}
      <div className="posts-container">
        <h2>
          {showingNearby ? `Nearby Help Requests (${nearbyPosts.length})` : `Recent Posts (${posts.length})`}
        </h2>
        {showingNearby && (
          <p style={{ color: '#666', marginBottom: '15px' }}>
            Showing help requests within {nearbyLocation.radius}m of
            ({nearbyLocation.latitude.toFixed(4)}, {nearbyLocation.longitude.toFixed(4)})
          </p>
        )}

        {loading ? (
          <div className="loading">Loading posts...</div>
        ) : (showingNearby ? nearbyPosts : posts).length === 0 ? (
          <div className="no-posts">
            {showingNearby ? 'No help requests found in this area.' : 'No posts available in this region.'}
          </div>
        ) : (
          <div className="posts-grid">
            {(showingNearby ? nearbyPosts : posts).map((post) => (
              <div key={post.post_id} className="post-card">
                <div
                  className="post-type-badge"
                  style={{ backgroundColor: getPostTypeColor(post.post_type) }}
                >
                  {post.post_type.toUpperCase()}
                </div>
                <div className="post-content">
                  <div className="post-user">
                    <strong>👤 {post.user_id}</strong>
                  </div>
                  <p className="post-message">{post.message}</p>
                  <div className="post-meta">
                    <span className="post-region">📍 {post.region}</span>
                    {post.capacity && (
                      <span className="post-capacity">Capacity: {post.capacity}</span>
                    )}
                  </div>
                  <div className="post-timestamp">
                    {formatTimestamp(post.timestamp)}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export default App;
