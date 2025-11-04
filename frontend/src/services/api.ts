/**
 * API service for communicating with MeshNetwork backend.
 */

import axios, { AxiosInstance } from 'axios';
import { Post, User, RegionHealth } from '../types';

class ApiService {
  private client: AxiosInstance;
  private baseUrl: string;

  constructor(baseUrl: string = 'http://localhost:5000') {
    this.baseUrl = baseUrl;
    this.client = axios.create({
      baseURL: this.baseUrl,
      timeout: 5000,
      headers: {
        'Content-Type': 'application/json',
      },
    });
  }

  /**
   * Set the base URL for API requests (e.g., when switching regions)
   */
  setBaseUrl(url: string) {
    this.baseUrl = url;
    this.client = axios.create({
      baseURL: this.baseUrl,
      timeout: 5000,
      headers: {
        'Content-Type': 'application/json',
      },
    });
  }

  /**
   * Health check
   */
  async getHealth() {
    const response = await this.client.get('/health');
    return response.data;
  }

  /**
   * Get detailed status
   */
  async getStatus(): Promise<RegionHealth> {
    const response = await this.client.get<RegionHealth>('/status');
    return response.data;
  }

  /**
   * Get posts with optional filters
   */
  async getPosts(params?: {
    post_type?: string;
    region?: string;
    limit?: number;
  }) {
    const response = await this.client.get('/api/posts', { params });
    return response.data;
  }

  /**
   * Get a specific post by ID
   */
  async getPost(postId: string): Promise<Post> {
    const response = await this.client.get<Post>(`/api/posts/${postId}`);
    return response.data;
  }

  /**
   * Create a new post
   */
  async createPost(postData: Partial<Post>) {
    const response = await this.client.post('/api/posts', postData);
    return response.data;
  }

  /**
   * Update a post
   */
  async updatePost(postId: string, postData: Partial<Post>) {
    const response = await this.client.put(`/api/posts/${postId}`, postData);
    return response.data;
  }

  /**
   * Delete a post
   */
  async deletePost(postId: string) {
    const response = await this.client.delete(`/api/posts/${postId}`);
    return response.data;
  }

  /**
   * Get help requests near a location
   */
  async getHelpRequests(params: {
    longitude: number;
    latitude: number;
    radius?: number;
  }) {
    const response = await this.client.get('/api/help-requests', { params });
    return response.data;
  }

  /**
   * Get a user by ID
   */
  async getUser(userId: string): Promise<User> {
    const response = await this.client.get<User>(`/api/users/${userId}`);
    return response.data;
  }

  /**
   * Create a new user
   */
  async createUser(userData: Partial<User>) {
    const response = await this.client.post('/api/users', userData);
    return response.data;
  }

  /**
   * Update a user
   */
  async updateUser(userId: string, userData: Partial<User>) {
    const response = await this.client.put(`/api/users/${userId}`, userData);
    return response.data;
  }

  /**
   * Mark a user as safe
   */
  async markUserSafe(userId: string) {
    const response = await this.client.post('/api/mark-safe', { user_id: userId });
    return response.data;
  }
}

// Create a singleton instance
const api = new ApiService();

export default api;
