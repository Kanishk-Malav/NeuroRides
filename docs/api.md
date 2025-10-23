# NeuroRides API Documentation

## Overview

The NeuroRides API is a RESTful API built with Django REST Framework that provides endpoints for ride booking, fleet management, payments, and analytics.

## Base URL

- **Development**: `http://localhost:8000/api/`
- **Production**: `https://api.neurorides.com/api/`

## Authentication

The API uses JWT (JSON Web Tokens) for authentication. Include the token in the Authorization header:

```
Authorization: Bearer <your-jwt-token>
```

### Obtaining a Token

```http
POST /api/accounts/login/
Content-Type: application/json

{
  "username": "your_username",
  "password": "your_password"
}
```

**Response:**
```json
{
  "token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "user": {
    "id": "123e4567-e89b-12d3-a456-426614174000",
    "username": "rider123",
    "email": "rider@example.com",
    "role": "rider",
    "first_name": "John",
    "last_name": "Doe"
  }
}
```

## Response Format

All API responses follow this standard format:

### Success Response
```json
{
  "success": true,
  "data": {
    // Response data
  },
  "message": "Operation completed successfully",
  "pagination": {
    "count": 100,
    "next": "http://api.example.com/api/endpoint/?page=2",
    "previous": null,
    "page_size": 20
  }
}
```

### Error Response
```json
{
  "success": false,
  "data": null,
  "message": "Error message",
  "errors": {
    "field_name": ["Error description"]
  }
}
```

## Status Codes

- `200 OK` - Request successful
- `201 Created` - Resource created successfully
- `204 No Content` - Request successful, no content returned
- `400 Bad Request` - Invalid request data
- `401 Unauthorized` - Authentication required
- `403 Forbidden` - Insufficient permissions
- `404 Not Found` - Resource not found
- `429 Too Many Requests` - Rate limit exceeded
- `500 Internal Server Error` - Server error

## Rate Limiting

API requests are rate limited based on user authentication:

- **Authenticated users**: 1000 requests per hour
- **Anonymous users**: 100 requests per hour

Rate limit headers are included in responses:
```
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999
X-RateLimit-Reset: 1640995200
```

## Pagination

List endpoints support pagination with the following parameters:

- `page` - Page number (default: 1)
- `page_size` - Number of items per page (default: 20, max: 100)

Example:
```
GET /api/rides/?page=2&page_size=50
```

## Filtering and Sorting

Many list endpoints support filtering and sorting:

### Filtering
```
GET /api/rides/?status=completed&created_after=2023-01-01
```

### Sorting
```
GET /api/rides/?ordering=-created_at,status
```

Use `-` prefix for descending order.

## API Endpoints

### Authentication Endpoints

#### Register User
```http
POST /api/accounts/register/
```

**Request Body:**
```json
{
  "username": "newuser",
  "email": "user@example.com",
  "password": "securepassword123",
  "first_name": "John",
  "last_name": "Doe",
  "phone_number": "+1234567890",
  "role": "rider"
}
```

**Response:** `201 Created`
```json
{
  "success": true,
  "data": {
    "id": "123e4567-e89b-12d3-a456-426614174000",
    "username": "newuser",
    "email": "user@example.com",
    "role": "rider",
    "first_name": "John",
    "last_name": "Doe",
    "phone_number": "+1234567890",
    "is_verified": false,
    "created_at": "2023-12-01T10:00:00Z"
  },
  "message": "User registered successfully"
}
```

#### Login
```http
POST /api/accounts/login/
```

**Request Body:**
```json
{
  "username": "rider123",
  "password": "securepassword123"
}
```

#### Logout
```http
POST /api/accounts/logout/
Authorization: Bearer <token>
```

#### Get User Profile
```http
GET /api/accounts/profile/
Authorization: Bearer <token>
```

#### Update User Profile
```http
PATCH /api/accounts/profile/
Authorization: Bearer <token>
```

**Request Body:**
```json
{
  "first_name": "Jane",
  "last_name": "Smith",
  "phone_number": "+1987654321"
}
```

#### Change Password
```http
POST /api/accounts/change-password/
Authorization: Bearer <token>
```

**Request Body:**
```json
{
  "old_password": "oldpassword123",
  "new_password": "newpassword123"
}
```

### Ride Endpoints

#### List Rides
```http
GET /api/rides/
Authorization: Bearer <token>
```

**Query Parameters:**
- `status` - Filter by ride status (requested, assigned, pickup, in_progress, completed, cancelled)
- `created_after` - Filter rides created after date (YYYY-MM-DD)
- `created_before` - Filter rides created before date (YYYY-MM-DD)
- `ordering` - Sort by field (-created_at, status, fare)

**Response:** `200 OK`
```json
{
  "success": true,
  "data": {
    "count": 25,
    "next": "http://api.example.com/api/rides/?page=2",
    "previous": null,
    "results": [
      {
        "id": "123e4567-e89b-12d3-a456-426614174000",
        "status": "completed",
        "pickup_address": "123 Main St, San Francisco, CA",
        "destination_address": "456 Oak Ave, San Francisco, CA",
        "pickup_latitude": 37.7749,
        "pickup_longitude": -122.4194,
        "destination_latitude": 37.7849,
        "destination_longitude": -122.4094,
        "fare_estimate": "15.50",
        "fare": "16.25",
        "distance_km": 5.2,
        "duration_minutes": 18,
        "created_at": "2023-12-01T10:00:00Z",
        "completed_at": "2023-12-01T10:18:00Z",
        "assigned_vehicle": {
          "id": "vehicle-123",
          "license_plate": "ABC123",
          "make": "Tesla",
          "model": "Model 3"
        }
      }
    ]
  }
}
```

#### Create Ride
```http
POST /api/rides/
Authorization: Bearer <token>
```

**Request Body:**
```json
{
  "pickup_latitude": 37.7749,
  "pickup_longitude": -122.4194,
  "pickup_address": "123 Main St, San Francisco, CA",
  "destination_latitude": 37.7849,
  "destination_longitude": -122.4094,
  "destination_address": "456 Oak Ave, San Francisco, CA",
  "ride_type": "standard",
  "notes": "Please call when you arrive"
}
```

**Response:** `201 Created`
```json
{
  "success": true,
  "data": {
    "id": "123e4567-e89b-12d3-a456-426614174000",
    "status": "requested",
    "pickup_address": "123 Main St, San Francisco, CA",
    "destination_address": "456 Oak Ave, San Francisco, CA",
    "fare_estimate": "15.50",
    "estimated_duration": 18,
    "estimated_distance": 5.2,
    "created_at": "2023-12-01T10:00:00Z"
  },
  "message": "Ride requested successfully"
}
```

#### Get Ride Details
```http
GET /api/rides/{ride_id}/
Authorization: Bearer <token>
```

#### Cancel Ride
```http
POST /api/rides/{ride_id}/cancel/
Authorization: Bearer <token>
```

**Request Body:**
```json
{
  "reason": "Change of plans"
}
```

#### Estimate Fare
```http
POST /api/rides/estimate-fare/
Authorization: Bearer <token>
```

**Request Body:**
```json
{
  "pickup_latitude": 37.7749,
  "pickup_longitude": -122.4194,
  "destination_latitude": 37.7849,
  "destination_longitude": -122.4094,
  "ride_type": "standard"
}
```

**Response:** `200 OK`
```json
{
  "success": true,
  "data": {
    "estimated_fare": "15.50",
    "estimated_duration": 18,
    "estimated_distance": 5.2,
    "surge_multiplier": 1.0,
    "base_fare": "3.00",
    "distance_fare": "10.40",
    "time_fare": "2.10"
  }
}
```

### Fleet Management Endpoints (Operators Only)

#### List Vehicles
```http
GET /api/fleet/vehicles/
Authorization: Bearer <token>
```

**Query Parameters:**
- `status` - Filter by vehicle status (idle, assigned, in_ride, maintenance, offline)
- `vehicle_type` - Filter by vehicle type (sedan, suv, luxury)
- `is_active` - Filter by active status (true, false)
- `battery_level_min` - Filter by minimum battery level
- `ordering` - Sort by field (-created_at, license_plate, battery_level)

#### Create Vehicle
```http
POST /api/fleet/vehicles/
Authorization: Bearer <token>
```

**Request Body:**
```json
{
  "license_plate": "XYZ789",
  "make": "Tesla",
  "model": "Model S",
  "year": 2023,
  "vehicle_type": "luxury",
  "color": "Black",
  "current_latitude": 37.7749,
  "current_longitude": -122.4194,
  "battery_level": 85,
  "is_active": true
}
```

#### Update Vehicle
```http
PATCH /api/fleet/vehicles/{vehicle_id}/
Authorization: Bearer <token>
```

#### Submit Vehicle Telemetry
```http
POST /api/fleet/vehicles/{vehicle_id}/telemetry/
Authorization: Bearer <token>
```

**Request Body:**
```json
{
  "latitude": 37.7750,
  "longitude": -122.4195,
  "speed": 25.5,
  "battery_level": 82,
  "engine_temperature": 75,
  "odometer_reading": 15000,
  "fuel_level": null
}
```

#### Schedule Maintenance
```http
POST /api/fleet/vehicles/{vehicle_id}/schedule-maintenance/
Authorization: Bearer <token>
```

**Request Body:**
```json
{
  "maintenance_type": "routine",
  "scheduled_date": "2023-12-15",
  "description": "Regular maintenance check",
  "estimated_duration_hours": 4
}
```

### Payment Endpoints

#### List Payments
```http
GET /api/payments/
Authorization: Bearer <token>
```

#### Process Payment
```http
POST /api/payments/
Authorization: Bearer <token>
```

**Request Body:**
```json
{
  "ride_id": "123e4567-e89b-12d3-a456-426614174000",
  "amount": "16.25",
  "payment_method": "credit_card",
  "card_token": "tok_1234567890",
  "save_payment_method": true
}
```

**Response:** `201 Created`
```json
{
  "success": true,
  "data": {
    "id": "payment-123",
    "status": "completed",
    "amount": "16.25",
    "currency": "USD",
    "payment_method": "credit_card",
    "transaction_id": "txn_1234567890",
    "receipt_url": "https://api.neurorides.com/receipts/payment-123.pdf",
    "created_at": "2023-12-01T10:20:00Z"
  },
  "message": "Payment processed successfully"
}
```

#### Get Payment Details
```http
GET /api/payments/{payment_id}/
Authorization: Bearer <token>
```

#### Process Refund
```http
POST /api/payments/{payment_id}/refund/
Authorization: Bearer <token>
```

**Request Body:**
```json
{
  "amount": "16.25",
  "reason": "customer_request",
  "notes": "Customer requested refund due to service issue"
}
```

### Analytics Endpoints (Admin/Operator Only)

#### Dashboard Data
```http
GET /api/analytics/dashboard/
Authorization: Bearer <token>
```

**Response:** `200 OK`
```json
{
  "success": true,
  "data": {
    "ride_analytics": {
      "total_rides_today": 150,
      "completed_rides_today": 142,
      "active_rides": 8,
      "completion_rate": 94.7,
      "avg_wait_time_minutes": 3.2,
      "avg_ride_duration_minutes": 15.8
    },
    "revenue_analytics": {
      "revenue_today": "2847.50",
      "revenue_this_month": "85425.00",
      "avg_fare": "18.95",
      "total_transactions_today": 150
    },
    "fleet_analytics": {
      "total_vehicles": 50,
      "active_vehicles": 45,
      "idle_vehicles": 25,
      "assigned_vehicles": 15,
      "maintenance_vehicles": 3,
      "avg_battery_level": 78.5
    }
  }
}
```

#### Generate Report
```http
POST /api/analytics/reports/
Authorization: Bearer <token>
```

**Request Body:**
```json
{
  "report_type": "daily_summary",
  "date_from": "2023-12-01",
  "date_to": "2023-12-01",
  "format": "pdf",
  "email_to": "admin@neurorides.com"
}
```

#### List Reports
```http
GET /api/analytics/reports/
Authorization: Bearer <token>
```

### Dispatch Endpoints (Operators Only)

#### List Dispatch Requests
```http
GET /api/dispatch/
Authorization: Bearer <token>
```

#### Create Dispatch Request
```http
POST /api/dispatch/
Authorization: Bearer <token>
```

**Request Body:**
```json
{
  "ride_id": "123e4567-e89b-12d3-a456-426614174000",
  "priority": "normal",
  "max_wait_time_minutes": 10,
  "preferred_vehicle_type": "sedan"
}
```

#### Process Dispatch Request
```http
POST /api/dispatch/{dispatch_id}/process/
Authorization: Bearer <token>
```

### Health Check Endpoints

#### Basic Health Check
```http
GET /health/
```

**Response:** `200 OK`
```json
{
  "status": "healthy",
  "timestamp": "2023-12-01T10:00:00Z",
  "version": "1.0.0"
}
```

#### Detailed Health Check
```http
GET /health/detailed/
```

**Response:** `200 OK`
```json
{
  "status": "healthy",
  "timestamp": "2023-12-01T10:00:00Z",
  "services": {
    "database": {
      "status": "healthy",
      "response_time_ms": 5
    },
    "redis": {
      "status": "healthy",
      "response_time_ms": 2
    },
    "celery": {
      "status": "healthy",
      "active_workers": 4,
      "pending_tasks": 0
    }
  }
}
```

## WebSocket API

### Connection

Connect to WebSocket endpoints for real-time updates:

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/rides/123e4567-e89b-12d3-a456-426614174000/');
```

### Authentication

Send authentication token after connection:

```javascript
ws.onopen = function() {
    ws.send(JSON.stringify({
        'type': 'authenticate',
        'token': 'your-jwt-token'
    }));
};
```

### Ride Tracking

Subscribe to ride updates:

```javascript
ws.send(JSON.stringify({
    'type': 'subscribe_ride_updates',
    'ride_id': '123e4567-e89b-12d3-a456-426614174000'
}));
```

**Received Messages:**
```json
{
  "type": "ride_status_update",
  "ride_id": "123e4567-e89b-12d3-a456-426614174000",
  "status": "assigned",
  "assigned_vehicle": {
    "id": "vehicle-123",
    "license_plate": "ABC123",
    "current_latitude": 37.7749,
    "current_longitude": -122.4194,
    "eta_minutes": 5
  }
}
```

### Vehicle Location Updates

```json
{
  "type": "vehicle_location_update",
  "vehicle_id": "vehicle-123",
  "latitude": 37.7750,
  "longitude": -122.4195,
  "speed": 25.5,
  "heading": 45,
  "timestamp": "2023-12-01T10:05:00Z"
}
```

## Error Handling

### Common Error Responses

#### Validation Error (400)
```json
{
  "success": false,
  "message": "Validation failed",
  "errors": {
    "pickup_latitude": ["This field is required."],
    "destination_address": ["This field may not be blank."]
  }
}
```

#### Authentication Error (401)
```json
{
  "success": false,
  "message": "Authentication credentials were not provided.",
  "errors": null
}
```

#### Permission Error (403)
```json
{
  "success": false,
  "message": "You do not have permission to perform this action.",
  "errors": null
}
```

#### Not Found Error (404)
```json
{
  "success": false,
  "message": "Ride not found.",
  "errors": null
}
```

#### Rate Limit Error (429)
```json
{
  "success": false,
  "message": "Request was throttled. Expected available in 3600 seconds.",
  "errors": null
}
```

## SDK Examples

### Python SDK Example

```python
import requests
from datetime import datetime

class NeuroRidesAPI:
    def __init__(self, base_url, token=None):
        self.base_url = base_url
        self.token = token
        self.session = requests.Session()
        if token:
            self.session.headers.update({'Authorization': f'Bearer {token}'})
    
    def login(self, username, password):
        response = self.session.post(f'{self.base_url}/accounts/login/', {
            'username': username,
            'password': password
        })
        data = response.json()
        if data['success']:
            self.token = data['data']['token']
            self.session.headers.update({'Authorization': f'Bearer {self.token}'})
        return data
    
    def create_ride(self, pickup_lat, pickup_lng, dest_lat, dest_lng, pickup_addr, dest_addr):
        return self.session.post(f'{self.base_url}/rides/', {
            'pickup_latitude': pickup_lat,
            'pickup_longitude': pickup_lng,
            'destination_latitude': dest_lat,
            'destination_longitude': dest_lng,
            'pickup_address': pickup_addr,
            'destination_address': dest_addr,
            'ride_type': 'standard'
        }).json()
    
    def get_rides(self, status=None):
        params = {}
        if status:
            params['status'] = status
        return self.session.get(f'{self.base_url}/rides/', params=params).json()

# Usage
api = NeuroRidesAPI('http://localhost:8000/api')
api.login('rider123', 'password')
ride = api.create_ride(37.7749, -122.4194, 37.7849, -122.4094, 
                      '123 Main St', '456 Oak Ave')
```

### JavaScript SDK Example

```javascript
class NeuroRidesAPI {
    constructor(baseUrl, token = null) {
        this.baseUrl = baseUrl;
        this.token = token;
    }
    
    async request(endpoint, options = {}) {
        const url = `${this.baseUrl}${endpoint}`;
        const config = {
            headers: {
                'Content-Type': 'application/json',
                ...(this.token && { 'Authorization': `Bearer ${this.token}` })
            },
            ...options
        };
        
        if (config.body && typeof config.body === 'object') {
            config.body = JSON.stringify(config.body);
        }
        
        const response = await fetch(url, config);
        return response.json();
    }
    
    async login(username, password) {
        const data = await this.request('/accounts/login/', {
            method: 'POST',
            body: { username, password }
        });
        
        if (data.success) {
            this.token = data.data.token;
        }
        return data;
    }
    
    async createRide(rideData) {
        return this.request('/rides/', {
            method: 'POST',
            body: rideData
        });
    }
    
    async getRides(filters = {}) {
        const params = new URLSearchParams(filters);
        return this.request(`/rides/?${params}`);
    }
}

// Usage
const api = new NeuroRidesAPI('http://localhost:8000/api');
await api.login('rider123', 'password');
const ride = await api.createRide({
    pickup_latitude: 37.7749,
    pickup_longitude: -122.4194,
    destination_latitude: 37.7849,
    destination_longitude: -122.4094,
    pickup_address: '123 Main St',
    destination_address: '456 Oak Ave',
    ride_type: 'standard'
});
```

## Testing

### Using cURL

```bash
# Login
curl -X POST http://localhost:8000/api/accounts/login/ \
  -H "Content-Type: application/json" \
  -d '{"username": "rider123", "password": "password"}'

# Create ride (replace TOKEN with actual token)
curl -X POST http://localhost:8000/api/rides/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer TOKEN" \
  -d '{
    "pickup_latitude": 37.7749,
    "pickup_longitude": -122.4194,
    "pickup_address": "123 Main St, San Francisco, CA",
    "destination_latitude": 37.7849,
    "destination_longitude": -122.4094,
    "destination_address": "456 Oak Ave, San Francisco, CA",
    "ride_type": "standard"
  }'
```

### Using Postman

1. Import the API collection from `/docs/postman_collection.json`
2. Set up environment variables:
   - `base_url`: `http://localhost:8000/api`
   - `token`: Your JWT token
3. Run the authentication request first to get a token
4. Use the token for subsequent requests

## Changelog

### Version 1.0.0 (2023-12-01)
- Initial API release
- Authentication endpoints
- Ride booking and management
- Fleet management
- Payment processing
- Analytics and reporting
- Real-time WebSocket support

---

For more information or support, please contact the development team or check the GitHub repository.