"""
Management command to create sample rides for development.
"""

import random
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal

from rides.models import Ride, ServiceArea, RideFareCalculator
from fleet.models import Vehicle

User = get_user_model()


class Command(BaseCommand):
    """Create sample rides for development and testing."""
    
    help = 'Create sample rides for development'
    
    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            '--count',
            type=int,
            default=20,
            help='Number of rides to create (default: 20)',
        )
        parser.add_argument(
            '--with-history',
            action='store_true',
            help='Create rides with historical data (completed/cancelled)',
        )
    
    def handle(self, *args, **options):
        """Handle command execution."""
        count = options['count']
        with_history = options['with_history']
        
        # Get riders
        riders = list(User.objects.filter(role=User.Role.RIDER))
        if not riders:
            self.stdout.write(
                self.style.ERROR('No riders found. Please create some riders first.')
            )
            return
        
        # Get vehicles
        vehicles = list(Vehicle.objects.all())
        if not vehicles:
            self.stdout.write(
                self.style.ERROR('No vehicles found. Please create some vehicles first.')
            )
            return
        
        # Create Mumbai service area if it doesn't exist
        service_area, created = ServiceArea.objects.get_or_create(
            name='Mumbai',
            defaults={
                'description': 'Mumbai metropolitan area',
                'north_lat': 19.2544,
                'south_lat': 18.8800,
                'east_lng': 72.9781,
                'west_lng': 72.7757,
                'is_active': True,
                'surge_multiplier': Decimal('1.0')
            }
        )
        
        if created:
            self.stdout.write(f"Created service area: {service_area.name}")
        
        # Sample locations in Mumbai
        mumbai_locations = [
            (19.0760, 72.8777, "CST Station"),
            (19.0544, 72.8311, "Gateway of India"),
            (19.1136, 72.8697, "Bandra West"),
            (19.0896, 72.8656, "Dadar"),
            (19.1075, 72.8263, "Juhu Beach"),
            (19.0330, 72.8697, "Colaba"),
            (19.0176, 72.8562, "Nariman Point"),
            (19.0728, 72.8826, "Lower Parel"),
            (19.1197, 72.9073, "Powai"),
            (19.0825, 72.8428, "Worli"),
        ]
        
        created_count = 0
        
        for i in range(count):
            # Random rider
            rider = random.choice(riders)
            
            # Random pickup and destination
            pickup_location = random.choice(mumbai_locations)
            destination_location = random.choice(mumbai_locations)
            
            # Ensure pickup and destination are different
            while destination_location == pickup_location:
                destination_location = random.choice(mumbai_locations)
            
            # Create ride
            ride = Ride.objects.create(
                rider=rider,
                pickup_latitude=pickup_location[0],
                pickup_longitude=pickup_location[1],
                pickup_address=pickup_location[2],
                destination_latitude=destination_location[0],
                destination_longitude=destination_location[1],
                destination_address=destination_location[2],
                passenger_count=random.randint(1, 4),
                requires_wheelchair_access=random.choice([True, False]) if random.random() < 0.1 else False,
                requires_child_seat=random.choice([True, False]) if random.random() < 0.2 else False,
                pickup_notes=random.choice([
                    '', 'Near the main entrance', 'Building A, 2nd floor',
                    'Call when you arrive', 'Blue building'
                ]),
                ride_notes=random.choice([
                    '', 'Please keep AC on', 'Prefer highway route',
                    'No music please', 'In a hurry'
                ])
            )
            
            created_count += 1
            
            # If creating historical data, simulate ride progression
            if with_history and random.random() < 0.8:  # 80% chance for historical rides
                self._simulate_ride_progression(ride, vehicles)
            
            self.stdout.write(
                f"Created ride: {ride.id} - {rider.username} "
                f"({pickup_location[2]} → {destination_location[2]})"
            )
        
        self.stdout.write(
            self.style.SUCCESS(f'Successfully created {created_count} rides')
        )
        
        # Display ride statistics
        self._display_ride_statistics()
    
    def _simulate_ride_progression(self, ride, vehicles):
        """Simulate ride progression for historical data."""
        
        # 70% chance to assign a vehicle
        if random.random() < 0.7:
            vehicle = random.choice(vehicles)
            ride.assign_vehicle(vehicle)
            
            # Add some time delay
            ride.assigned_at = ride.requested_at + timedelta(minutes=random.randint(1, 5))
            
            # 90% chance to start pickup
            if random.random() < 0.9:
                ride.start_pickup()
                ride.pickup_started_at = ride.assigned_at + timedelta(minutes=random.randint(2, 8))
                
                # 85% chance to confirm pickup
                if random.random() < 0.85:
                    ride.confirm_pickup()
                    ride.picked_up_at = ride.pickup_started_at + timedelta(minutes=random.randint(3, 10))
                    
                    # 95% chance to complete ride
                    if random.random() < 0.95:
                        # Calculate actual distance (add some variance)
                        estimated_distance = ride.estimated_distance_km or ride.calculate_distance()
                        actual_distance = estimated_distance * random.uniform(0.9, 1.2)
                        
                        # Calculate ride duration
                        ride_duration = timedelta(minutes=int(actual_distance / 25 * 60))  # 25 km/h avg
                        
                        ride.complete_ride(
                            actual_distance_km=actual_distance,
                            final_fare=RideFareCalculator.calculate_final_fare(
                                ride, 
                                actual_distance_km=actual_distance,
                                actual_duration_minutes=int(ride_duration.total_seconds() / 60)
                            )
                        )
                        ride.completed_at = ride.picked_up_at + ride_duration
                        
                        # Add rating
                        ride.rider_rating = random.randint(3, 5)
                        if ride.rider_rating <= 3:
                            ride.rider_feedback = random.choice([
                                'Vehicle was not clean',
                                'Driver was late',
                                'Rough driving',
                                'AC was not working'
                            ])
                        elif ride.rider_rating >= 4:
                            ride.rider_feedback = random.choice([
                                'Great ride!',
                                'Very smooth',
                                'Clean vehicle',
                                'On time pickup',
                                ''
                            ])
                    
                    else:
                        # Cancel during ride
                        ride.cancel_ride(
                            reason=random.choice([
                                Ride.CancellationReason.USER_CANCELLED,
                                Ride.CancellationReason.SYSTEM_ERROR
                            ]),
                            notes='Cancelled during ride'
                        )
                
                else:
                    # Cancel during pickup
                    ride.cancel_ride(
                        reason=Ride.CancellationReason.USER_CANCELLED,
                        notes='Cancelled during pickup'
                    )
            
            else:
                # Cancel after assignment
                ride.cancel_ride(
                    reason=Ride.CancellationReason.DRIVER_CANCELLED,
                    notes='Driver cancelled'
                )
        
        else:
            # No vehicle available
            ride.cancel_ride(
                reason=Ride.CancellationReason.NO_DRIVER,
                notes='No driver available'
            )
        
        # Adjust timestamps to be in the past
        time_offset = timedelta(days=random.randint(1, 30))
        ride.requested_at = timezone.now() - time_offset
        
        if ride.assigned_at:
            ride.assigned_at = ride.requested_at + timedelta(minutes=random.randint(1, 5))
        if ride.pickup_started_at:
            ride.pickup_started_at = ride.assigned_at + timedelta(minutes=random.randint(2, 8))
        if ride.picked_up_at:
            ride.picked_up_at = ride.pickup_started_at + timedelta(minutes=random.randint(3, 10))
        if ride.completed_at:
            ride.completed_at = ride.picked_up_at + timedelta(minutes=random.randint(10, 60))
        if ride.cancelled_at:
            ride.cancelled_at = ride.assigned_at or ride.requested_at + timedelta(minutes=random.randint(1, 15))
        
        ride.save()
    
    def _display_ride_statistics(self):
        """Display ride statistics."""
        self.stdout.write('\n' + '='*50)
        self.stdout.write(self.style.SUCCESS('RIDE STATISTICS:'))
        self.stdout.write('='*50)
        
        total_rides = Ride.objects.count()
        
        # Status distribution
        status_counts = {}
        for status_choice in Ride.Status.choices:
            status = status_choice[0]
            count = Ride.objects.filter(status=status).count()
            status_counts[status] = count
        
        self.stdout.write(f"Total Rides: {total_rides}")
        for status, count in status_counts.items():
            percentage = (count / total_rides * 100) if total_rides > 0 else 0
            self.stdout.write(f"  {status.title()}: {count} ({percentage:.1f}%)")
        
        # Completed rides statistics
        completed_rides = Ride.objects.filter(status=Ride.Status.COMPLETED)
        if completed_rides.exists():
            from django.db.models import Avg, Sum
            
            avg_fare = completed_rides.aggregate(avg=Avg('final_fare'))['avg'] or 0
            total_revenue = completed_rides.aggregate(total=Sum('final_fare'))['total'] or 0
            avg_distance = completed_rides.aggregate(avg=Avg('actual_distance_km'))['avg'] or 0
            avg_rating = completed_rides.filter(rider_rating__isnull=False).aggregate(
                avg=Avg('rider_rating')
            )['avg'] or 0
            
            self.stdout.write(f"\nCompleted Rides Analysis:")
            self.stdout.write(f"  Average Fare: ₹{avg_fare:.2f}")
            self.stdout.write(f"  Total Revenue: ₹{total_revenue:.2f}")
            self.stdout.write(f"  Average Distance: {avg_distance:.2f} km")
            self.stdout.write(f"  Average Rating: {avg_rating:.1f}/5")
        
        # Recent rides
        recent_rides = Ride.objects.order_by('-requested_at')[:5]
        if recent_rides:
            self.stdout.write(f"\nRecent Rides:")
            for ride in recent_rides:
                self.stdout.write(
                    f"  {ride.requested_at.strftime('%Y-%m-%d %H:%M')} - "
                    f"{ride.rider.username} - {ride.get_status_display()}"
                )