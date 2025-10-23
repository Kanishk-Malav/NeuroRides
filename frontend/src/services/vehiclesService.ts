import { apiService } from './api';
import { Vehicle, PaginatedResponse } from '../types';

class VehiclesService {
  async getVehicles(page = 1, pageSize = 50): Promise<Vehicle[]> {
    const response = await apiService.get<PaginatedResponse<Vehicle>>('/fleet/', {
      params: { page, page_size: pageSize }
    });
    return response.results;
  }

  async getVehicleById(vehicleId: string): Promise<Vehicle> {
    return apiService.get<Vehicle>(`/fleet/${vehicleId}/`);
  }

  async getVehiclesByStatus(status: Vehicle['status']): Promise<Vehicle[]> {
    const response = await apiService.get<PaginatedResponse<Vehicle>>('/fleet/', {
      params: { status }
    });
    return response.results;
  }

  async getNearbyVehicles(latitude: number, longitude: number, radius = 5): Promise<Vehicle[]> {
    return apiService.get<Vehicle[]>('/fleet/nearby/', {
      params: { latitude, longitude, radius }
    });
  }

  async getVehicleLocation(vehicleId: string): Promise<{ latitude: number; longitude: number }> {
    return apiService.get<{ latitude: number; longitude: number }>(`/fleet/${vehicleId}/location/`);
  }

  async getVehicleTelemetry(vehicleId: string): Promise<any> {
    return apiService.get<any>(`/fleet/${vehicleId}/telemetry/`);
  }

  async updateVehicleStatus(vehicleId: string, status: Vehicle['status']): Promise<Vehicle> {
    return apiService.patch<Vehicle>(`/fleet/${vehicleId}/`, { status });
  }

  async scheduleVehicleMaintenance(vehicleId: string, maintenanceData: any): Promise<any> {
    return apiService.post<any>(`/fleet/${vehicleId}/maintenance/`, maintenanceData);
  }

  async getVehicleMaintenanceHistory(vehicleId: string): Promise<any[]> {
    return apiService.get<any[]>(`/fleet/${vehicleId}/maintenance/`);
  }

  // Real-time vehicle tracking
  subscribeToVehicleUpdates(vehicleId: string, callback: (update: any) => void): () => void {
    // This would be implemented with WebSocket connection
    // For now, return a dummy unsubscribe function
    return () => {};
  }

  subscribeToFleetUpdates(callback: (update: any) => void): () => void {
    // This would be implemented with WebSocket connection for fleet-wide updates
    return () => {};
  }
}

export const vehiclesService = new VehiclesService();