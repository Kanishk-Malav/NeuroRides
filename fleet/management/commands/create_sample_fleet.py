"""
Management command to create sample fleet vehicles for development.
"""

import random
from django.core.management.base import BaseCommand
from django.utils import timezone
from fleet.models import Vehicle, VehicleTelemetry


class Command(BaseCommand):
    """Create sample fleet vehicles for development and testing."""
    
    help = 'Create sample fleet vehicles for development'
    
    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            '--count',
            type=int,
            default=10,
            help='Number of vehicles to create (default: 10)',
        )
        parser.add_argument(
            '--with-telemetry',
            action='store_true',
            help='Create sample telemetry data for vehicles',
        )
    
    def handle(self, *args, **options):
        """Handle command execution."""
        count = options['count']
        with_telemetry = options['with_telemetry']
        
        # Sample data
        manufacturers = ['Tesla', 'BMW', 'Mercedes', 'Audi', 'Volvo']
        models = {
            'Tesla': ['Model 3', 'Model S', 'Model X', 'Model Y'],
            'BMW': ['i3', 'i4', 'iX3', 'i8'],
            'Mercedes': ['EQC', 'EQS', 'EQA', 'EQB'],
            'Audi': ['e-tron', 'e-tron GT', 'Q4 e-tron'],
            'Volvo': ['XC40 Recharge', 'C40 Recharge', 'XC90 Recharge']
        }
        vehicle_types = list(Vehicle.VehicleType.choices)
        
        # Mumbai coordinates for sample locations
        mumbai_bounds = {
            'lat_min': 18.8800,
            'lat_max': 19.2544,
            'lng_min': 72.7757,
            'lng_max': 72.9781
        }
        
        created_count = 0
        
        for i in range(count):
            # Generate license plate
            license_plate = f"MH01{random.randint(1000, 9999)}"
            
            # Check if license plate already exists
            if Vehicle.objects.filter(license_plate=license_plate).exists():
                continue
            
            # Random manufacturer and model
            manufacturer = random.choice(manufacturers)
            model = random.choice(models[manufacturer])
            
            # Random location in Mumbai
            latitude = random.uniform(mumbai_bounds['lat_min'], mumbai_bounds['lat_max'])
            longitude = random.uniform(mumbai_bounds['lng_min'], mumbai_bounds['lng_max'])
            
            # Create vehicle
            vehicle = Vehicle.objects.create(
                license_plate=license_plate,
                model=model,
                manufacturer=manufacturer,
                year=random.randint(2020, 2024),
                vehicle_type=random.choice(vehicle_types)[0],
                status=random.choice([
                    Vehicle.Status.IDLE,
                    Vehicle.Status.IDLE,  # More likely to be idle
                    Vehicle.Status.IDLE,
                    Vehicle.Status.ASSIGNED,
                    Vehicle.Status.IN_RIDE,
                ]),
                current_latitude=latitude,
                current_longitude=longitude,
                battery_level=random.randint(20, 100),
                mileage=random.uniform(1000, 50000),
                passenger_capacity=random.choice([4, 5, 6, 7]),
                has_wheelchair_access=random.choice([True, False]),
                has_child_seat=random.choice([True, False]),
                total_rides=random.randint(0, 1000),
                total_revenue=random.uniform(10000, 100000),
                last_seen=timezone.now() - timezone.timedelta(
                    minutes=random.randint(0, 60)
                )
            )
            
            created_count += 1
            
            self.stdout.write(
                f"Created vehicle: {vehicle.license_plate} - {vehicle.model}"
            )
            
            # Create sample telemetry data if requested
            if with_telemetry:
                for j in range(random.randint(5, 20)):
                    # Generate telemetry data for the last 24 hours
                    timestamp = timezone.now() - timezone.timedelta(
                        hours=random.uniform(0, 24)
                    )
                    
                    # Slight variation in location
                    tel_lat = latitude + random.uniform(-0.01, 0.01)
                    tel_lng = longitude + random.uniform(-0.01, 0.01)
                    
                    VehicleTelemetry.objects.create(
                        vehicle=vehicle,
                        latitude=tel_lat,
                        longitude=tel_lng,
                        speed=random.uniform(0, 80),
                        heading=random.uniform(0, 360),
                        battery_level=random.randint(
                            max(0, vehicle.battery_level - 20),
                            min(100, vehicle.battery_level + 10)
                        ),
                        temperature=random.uniform(18, 28),
                        engine_status=random.choice([
                            'running', 'idle', 'charging'
                        ]),
                        passenger_count=random.randint(0, vehicle.passenger_capacity),
                        timestamp=timestamp
                    )
        
        self.stdout.write(
            self.style.SUCCESS(f'Successfully created {created_count} vehicles')
        )
        
        if with_telemetry:
            telemetry_count = VehicleTelemetry.objects.count()
            self.stdout.write(
                self.style.SUCCESS(f'Created telemetry data: {telemetry_count} records')
            )
        
        # Display fleet summary
        self.stdout.write('\n' + '='*50)
        self.stdout.write(self.style.SUCCESS('FLEET SUMMARY:'))
        self.stdout.write('='*50)
        
        total_vehicles = Vehicle.objects.count()
        status_counts = {}
        for status_choice in Vehicle.Status.choices:
            status = status_choice[0]
            count = Vehicle.objects.filter(status=status).count()
            status_counts[status] = count
        
        self.stdout.write(f"Total Vehicles: {total_vehicles}")
        for status, count in status_counts.items():
            self.stdout.write(f"  {status.title()}: {count}")
        
        from django.db import models
        avg_battery = Vehicle.objects.aggregate(
            avg_battery=models.Avg('battery_level')
        )['avg_battery'] or 0
        
        self.stdout.write(f"Average Battery Level: {avg_battery:.1f}%")
        
        online_vehicles = sum(1 for v in Vehicle.objects.all() if v.is_online)
        self.stdout.write(f"Online Vehicles: {online_vehicles}")
        
        available_vehicles = sum(1 for v in Vehicle.objects.all() if v.is_available)
        self.stdout.write(f"Available Vehicles: {available_vehicles}")