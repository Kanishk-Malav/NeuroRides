import { io, Socket } from 'socket.io-client';
import { WebSocketMessage, RideUpdate, VehicleUpdate } from '../types';

class WebSocketService {
  leaveRideTracking(rideId: string) {
    throw new Error('Method not implemented.');
  }
  onRideUpdate(handleRideUpdate: (data: any) => void) {
    throw new Error('Method not implemented.');
  }
  joinRideTracking(rideId: string) {
    throw new Error('Method not implemented.');
  }
  private socket: Socket | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectDelay = 1000;
  private isConnecting = false;

  connect(token?: string): Promise<void> {
    return new Promise((resolve, reject) => {
      if (this.socket?.connected || this.isConnecting) {
        resolve();
        return;
      }

      this.isConnecting = true;
      const wsUrl = process.env.REACT_APP_WS_URL || 'ws://localhost:8000';

      this.socket = io(wsUrl, {
        auth: {
          token: token || localStorage.getItem('token')
        },
        transports: ['websocket'],
        upgrade: false,
      });

      this.socket.on('connect', () => {
        console.log('WebSocket connected');
        this.isConnecting = false;
        this.reconnectAttempts = 0;
        resolve();
      });

      this.socket.on('connect_error', (error) => {
        console.error('WebSocket connection error:', error);
        this.isConnecting = false;
        this.handleReconnect();
        reject(error);
      });

      this.socket.on('disconnect', (reason) => {
        console.log('WebSocket disconnected:', reason);
        this.isConnecting = false;
        if (reason === 'io server disconnect') {
          // Server disconnected, try to reconnect
          this.handleReconnect();
        }
      });

      this.setupEventHandlers();
    });
  }

  disconnect(): void {
    if (this.socket) {
      this.socket.disconnect();
      this.socket = null;
    }
    this.reconnectAttempts = 0;
  }

  private handleReconnect(): void {
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++;
      const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1);
      
      setTimeout(() => {
        console.log(`Attempting to reconnect (${this.reconnectAttempts}/${this.maxReconnectAttempts})`);
        this.connect();
      }, delay);
    } else {
      console.error('Max reconnection attempts reached');
    }
  }

  private setupEventHandlers(): void {
    if (!this.socket) return;

    this.socket.on('error', (error) => {
      console.error('WebSocket error:', error);
    });

    this.socket.on('message', (message: WebSocketMessage) => {
      console.log('WebSocket message received:', message);
    });
  }

  // Ride tracking
  subscribeToRideUpdates(rideId: string, callback: (update: RideUpdate) => void): () => void {
    if (!this.socket) {
      console.warn('WebSocket not connected');
      return () => {};
    }

    const eventName = `ride_update_${rideId}`;
    this.socket.on(eventName, callback);
    this.socket.emit('subscribe_ride', { ride_id: rideId });

    return () => {
      if (this.socket) {
        this.socket.off(eventName, callback);
        this.socket.emit('unsubscribe_ride', { ride_id: rideId });
      }
    };
  }

  // Vehicle tracking
  subscribeToVehicleUpdates(vehicleId: string, callback: (update: VehicleUpdate) => void): () => void {
    if (!this.socket) {
      console.warn('WebSocket not connected');
      return () => {};
    }

    const eventName = `vehicle_update_${vehicleId}`;
    this.socket.on(eventName, callback);
    this.socket.emit('subscribe_vehicle', { vehicle_id: vehicleId });

    return () => {
      if (this.socket) {
        this.socket.off(eventName, callback);
        this.socket.emit('unsubscribe_vehicle', { vehicle_id: vehicleId });
      }
    };
  }

  // Fleet monitoring (for operators)
  subscribeToFleetUpdates(callback: (update: any) => void): () => void {
    if (!this.socket) {
      console.warn('WebSocket not connected');
      return () => {};
    }

    this.socket.on('fleet_update', callback);
    this.socket.emit('subscribe_fleet');

    return () => {
      if (this.socket) {
        this.socket.off('fleet_update', callback);
        this.socket.emit('unsubscribe_fleet');
      }
    };
  }

  // Notifications
  subscribeToNotifications(callback: (notification: any) => void): () => void {
    if (!this.socket) {
      console.warn('WebSocket not connected');
      return () => {};
    }

    this.socket.on('notification', callback);

    return () => {
      if (this.socket) {
        this.socket.off('notification', callback);
      }
    };
  }

  // Analytics updates (for dashboards)
  subscribeToAnalyticsUpdates(callback: (update: any) => void): () => void {
    if (!this.socket) {
      console.warn('WebSocket not connected');
      return () => {};
    }

    this.socket.on('analytics_update', callback);
    this.socket.emit('subscribe_analytics');

    return () => {
      if (this.socket) {
        this.socket.off('analytics_update', callback);
        this.socket.emit('unsubscribe_analytics');
      }
    };
  }

  // Send messages
  sendMessage(event: string, data: any): void {
    if (this.socket?.connected) {
      this.socket.emit(event, data);
    } else {
      console.warn('WebSocket not connected, cannot send message');
    }
  }

  // Connection status
  isConnected(): boolean {
    return this.socket?.connected || false;
  }

  // Join/leave rooms (for role-based updates)
  joinRoom(room: string): void {
    if (this.socket?.connected) {
      this.socket.emit('join_room', { room });
    }
  }

  leaveRoom(room: string): void {
    if (this.socket?.connected) {
      this.socket.emit('leave_room', { room });
    }
  }
}

export const websocketService = new WebSocketService();