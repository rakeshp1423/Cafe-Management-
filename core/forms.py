from django import forms
from .models import Feedback, Reservation

class FeedbackForm(forms.ModelForm):
    class Meta:
        model = Feedback
        fields = ['feedback_text', 'image', 'rating']

class ReservationForm(forms.ModelForm):
    class Meta:
        model = Reservation
        fields = ['date', 'number_of_people', 'special_requests']
