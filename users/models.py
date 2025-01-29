from django.db import models
from django.contrib.auth.models import User

class Feedback(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='users_feedbacks')
    feedback_text = models.TextField()
    image = models.ImageField(upload_to='feedback_images/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username}'s feedback"

class Reservation(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='users_reservations')
    date = models.DateTimeField()
    number_of_people = models.IntegerField()
    special_requests = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Reservation by {self.user.username} on {self.date}"
