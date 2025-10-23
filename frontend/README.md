# NeuroRides Frontend

A modern React TypeScript application for the NeuroRides autonomous vehicle ride-sharing platform.

## Features Completed

### ✅ Task 9.1 - Project Setup
- React 18 with TypeScript
- TailwindCSS for styling
- React Router for navigation
- Redux Toolkit for state management
- Comprehensive API service layer

### ✅ Task 9.2 - Authentication Components
- **LoginForm**: Email/password login with validation
- **RegisterForm**: User registration with role selection
- **ProtectedRoute**: Role-based route protection
- **ForgotPasswordForm**: Password reset functionality
- JWT token management and automatic refresh

### ✅ Task 9.3 - Ride Booking Interface
- **RideBookingForm**: Complete ride request form
- **LocationPicker**: Address search and current location
- Fare estimation with real-time updates
- Ride type selection (Standard/Premium)
- Scheduled ride booking

### ✅ Task 9.4 - Real-time Tracking
- **RideTracker**: Live ride tracking with maps
- WebSocket integration for real-time updates
- Interactive Leaflet maps with custom markers
- Vehicle location tracking
- ETA and route display

### ✅ Task 9.5 - Payment Interface
- **PaymentForm**: Secure payment processing
- **PaymentHistory**: Transaction history and receipts
- Credit card validation and formatting
- Payment method management
- Receipt generation and download

### ✅ Task 9.6 - Dashboard Components
- **RiderDashboard**: Personal ride history and quick actions
- **OperatorDashboard**: Fleet monitoring and management
- **AdminDashboard**: Analytics and system overview
- Responsive design for all screen sizes
- Real-time KPI displays with Recharts

### ✅ Task 9.7 - Layout and Navigation
- **Layout**: Main application layout with sidebar
- **Navbar**: Top navigation with user menu
- **Sidebar**: Role-based navigation menu
- Responsive design patterns
- Theme and UI state management

## Technology Stack

- **React 18** - Modern React with hooks
- **TypeScript** - Type-safe development
- **Redux Toolkit** - State management
- **React Router** - Client-side routing
- **TailwindCSS** - Utility-first CSS framework
- **Leaflet** - Interactive maps
- **Recharts** - Data visualization
- **Lucide React** - Modern icon library
- **Socket.io Client** - Real-time communication

## Project Structure

```
frontend/src/
├── components/
│   ├── auth/           # Authentication components
│   ├── dashboard/      # Role-specific dashboards
│   ├── layout/         # Layout components
│   ├── payments/       # Payment processing
│   └── rides/          # Ride booking and tracking
├── services/           # API service layer
├── store/              # Redux store and slices
├── types/              # TypeScript type definitions
├── App.tsx             # Main application component
└── index.tsx           # Application entry point
```

## Key Features

### Authentication & Authorization
- JWT-based authentication
- Role-based access control (Rider, Operator, Admin)
- Secure route protection
- Password reset flow

### Ride Management
- Interactive map-based location selection
- Real-time fare estimation
- Live ride tracking with WebSocket updates
- Comprehensive ride history

### Payment Processing
- Secure payment form with validation
- Multiple payment method support
- Transaction history and receipts
- PCI-compliant data handling

### Real-time Features
- WebSocket integration for live updates
- Real-time vehicle tracking
- Live ride status updates
- Fleet monitoring for operators

### Analytics & Reporting
- Interactive charts and graphs
- KPI dashboards for different roles
- Data export functionality
- Real-time metrics

## Getting Started

1. Install dependencies:
```bash
npm install
```

2. Start the development server:
```bash
npm start
```

3. Build for production:
```bash
npm run build
```

## API Integration

The frontend integrates with the Django REST API backend:
- Authentication endpoints
- Ride management APIs
- Payment processing
- Real-time WebSocket connections
- Analytics data

## Responsive Design

All components are built with mobile-first responsive design:
- Tailwind CSS breakpoints
- Flexible grid layouts
- Touch-friendly interfaces
- Optimized for all screen sizes

## State Management

Redux Toolkit slices for:
- Authentication state
- Ride management
- Vehicle tracking
- Payment processing
- Analytics data
- UI state management

## Next Steps

The frontend is now complete and ready for:
- Integration testing with backend
- End-to-end testing
- Performance optimization
- Production deployment