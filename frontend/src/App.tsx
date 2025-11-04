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

  // New post form state
  const [showPostForm, setShowPostForm] = useState(false);
  const [newPost, setNewPost] = useState({
    user_id: '',
    post_type: 'help',
    message: '',
    longitude: -122.4194,
    latitude: 37.7749,
  });

  // Load posts when region changes
  useEffect(() => {
    api.setBaseUrl(selectedRegion.url);
    loadPosts();
    loadRegionHealth();
  }, [selectedRegion]);

  const loadPosts = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await api.getPosts({ limit: 50 });
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
    return date.toLocaleString();
  };

  return (
    <div className="App">
      {/* Header */}
      <header className="app-header">
        <h1>MeshNetwork</h1>
        <p>Disaster Resilient Social Platform</p>
      </header>

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
      </div>

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

      {/* Posts Feed */}
      <div className="posts-container">
        <h2>Recent Posts ({posts.length})</h2>

        {loading ? (
          <div className="loading">Loading posts...</div>
        ) : posts.length === 0 ? (
          <div className="no-posts">No posts available in this region.</div>
        ) : (
          <div className="posts-grid">
            {posts.map((post) => (
              <div key={post.post_id} className="post-card">
                <div
                  className="post-type-badge"
                  style={{ backgroundColor: getPostTypeColor(post.post_type) }}
                >
                  {post.post_type.toUpperCase()}
                </div>
                <div className="post-content">
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
