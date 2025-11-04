/**
 * Type definitions for MeshNetwork frontend.
 */

export interface Location {
  type: 'Point';
  coordinates: [number, number]; // [longitude, latitude]
}

export interface Post {
  _id?: string;
  post_id: string;
  user_id: string;
  post_type: 'shelter' | 'food' | 'medical' | 'water' | 'safety' | 'help';
  message: string;
  location: Location;
  region: string;
  capacity?: number;
  timestamp: string;
  last_modified: string;
}

export interface User {
  _id?: string;
  user_id: string;
  name: string;
  email: string;
  region: string;
  location: Location;
  verified: boolean;
  reputation: number;
  created_at: string;
}

export interface RegionHealth {
  status: string;
  region: {
    name: string;
    display_name: string;
  };
  database: {
    status: string;
    replica_set: string;
    primary: string;
    members: Array<{
      name: string;
      state: string;
      health: number;
    }>;
  };
  remote_regions: Record<string, string>;
}

export type Region = 'north_america' | 'europe' | 'asia_pacific';

export interface RegionEndpoint {
  name: string;
  url: string;
  code: Region;
}
