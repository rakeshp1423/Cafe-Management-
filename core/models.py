from django.db import models
from django.contrib.auth.models import User

class MenuItem(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField()
    price = models.DecimalField(max_digits=6, decimal_places=2)
    image = models.ImageField(upload_to='menu_images/', blank=True, null=True)

    def __str__(self):
        return self.name

class Feedback(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='core_feedbacks')
    feedback_text = models.TextField()
    image = models.ImageField(upload_to='feedback_images/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    rating = models.IntegerField(default=0)
    def __str__(self):
        return f"{self.user.username}'s feedback"

from django.db import models
from django.contrib.auth.models import User

class Reservation(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reservations')
    date = models.DateTimeField()
    number_of_people = models.IntegerField(null=True)
    special_requests = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    token = models.CharField(max_length=10, unique=True)

    def __str__(self):
        return f"Reservation by {self.user.username} on {self.date}"

    def save(self, *args, **kwargs):
        if not self.token:
            self.token = self.generate_token()
        super().save(*args, **kwargs)

    def generate_token(self):
        import random
        import string
        return ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))
