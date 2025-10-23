import { apiService } from './api';
import { Ride, RideRequest, FareEstimate, PaginatedResponse } from '../types';

class RidesService {
  async createRide(rideRequest: RideRequest): Promise<Ride> {
    return apiService.post<Ride>('/rides/', rideRequest);
  }

  async getCurrentRide(): Promise<Ride | null> {
    try {
      return await apiService.get<Ride>('/rides/current/');
    } catch (error) {
      // No current ride
      return null;
    }
  }

  async getRideById(rideId: string): Promise<Ride> {
    return apiService.get<Ride>(`/rides/${rideId}/`);
  }

  async getRideHistory(page = 1, pageSize = 20): Promise<Ride[]> {
    const response = await apiService.get<PaginatedResponse<Ride>>('/rides/', {
      params: { page, page_size: pageSize }
    });
    return response.results;
  }

  async cancelRide(rideId: string): Promise<Ride> {
    return apiService.post<Ride>(`/rides/${rideId}/cancel/`);
  }

  async rateRide(rideId: string, rating: number, comment?: string): Promise<Ride> {
    return apiService.post<Ride>(`/rides/${rideId}/rate/`, {
      rating,
      comment
    });
  }

  async getFareEstimate(
    pickupLat: number,
    pickupLng: number,
    destLat: number,
    destLng: number,
    vehicleType?: string
  ): Promise<FareEstimate> {
    return apiService.post<FareEstimate>('/payments/fare-estimate/', {
      pickup_latitude: pickupLat,
      pickup_longitude: pickupLng,
      destination_latitude: destLat,
      destination_longitude: destLng,
      vehicle_type: vehicleType
    });
  }

  async estimateFare(fareRequest: any): Promise<FareEstimate> {
    return apiService.post<FareEstimate>('/payments/fare-estimate/', fareRequest);
  }

  async getNearbyVehicles(latitude: number, longitude: number, radius = 5): Promise<any[]> {
    return apiService.get<any[]>('/fleet/nearby/', {
      params: { latitude, longitude, radius }
    });
  }

  async trackRide(rideId: string): Promise<any> {
    return apiService.get<any>(`/rides/${rideId}/track/`);
  }

  // Real-time updates would be handled via WebSocket
  subscribeToRideUpdates(rideId: string, callback: (update: any) => void): () => void {
    // This would be implemented with WebSocket connection
    // For now, return a dummy unsubscribe function
    return () => {};
  }
}

export const ridesService = new RidesService();