import axios, { AxiosInstance } from 'axios';
import { Post, User, RegionHealth } from '../types';

class ApiService {
  private client: AxiosInstance;
  private baseUrl: string;

  constructor(baseUrl: string = 'http://localhost:5010') {
    this.baseUrl = baseUrl;
    this.client = axios.create({
      baseURL: this.baseUrl,
      timeout: 5000,
      headers: {
        'Content-Type': 'application/json',
      },
    });
  }

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

  async getHealth() {
    const response = await this.client.get('/health');
    return response.data;
  }

  async getStatus(): Promise<RegionHealth> {
    const response = await this.client.get<RegionHealth>('/status');
    return response.data;
  }

  async getPosts(params?: {
    post_type?: string;
    region?: string;
    limit?: number;
    skip?: number;
  }): Promise<{
    posts: Post[];
    count: number;
    total_count: number;
    skip: number;
    limit: number;
    region: string;
  }> {
    const response = await this.client.get('/api/posts', { params });
    return response.data;
  }

  async getPost(postId: string): Promise<Post> {
    const response = await this.client.get<Post>(`/api/posts/${postId}`);
    return response.data;
  }

  async createPost(postData: Partial<Post>) {
    const response = await this.client.post('/api/posts', postData);
    return response.data;
  }

  async updatePost(postId: string, postData: Partial<Post>) {
    const response = await this.client.put(`/api/posts/${postId}`, postData);
    return response.data;
  }

  async deletePost(postId: string) {
    const response = await this.client.delete(`/api/posts/${postId}`);
    return response.data;
  }

  async getHelpRequests(params: {
    longitude: number;
    latitude: number;
    radius?: number;
  }) {
    const response = await this.client.get('/api/help-requests', { params });
    return response.data;
  }

  async getUser(userId: string): Promise<User> {
    const response = await this.client.get<User>(`/api/users/${userId}`);
    return response.data;
  }

  async createUser(userData: Partial<User>) {
    const response = await this.client.post('/api/users', userData);
    return response.data;
  }

  async updateUser(userId: string, userData: Partial<User>) {
    const response = await this.client.put(`/api/users/${userId}`, userData);
    return response.data;
  }

  async markUserSafe(userId: string) {
    const response = await this.client.post('/api/mark-safe', { user_id: userId });
    return response.data;
  }
}

const api = new ApiService();

export default api;
