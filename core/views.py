from django.shortcuts import render, redirect
from django.http import HttpResponse
from .models import MenuItem, Feedback, Reservation
from django.contrib.auth.decorators import login_required
from .models import Feedback
from .forms import ReservationForm, FeedbackForm
from core.models import Reservation
def home(request):
    feedbacks = Feedback.objects.all()
    if request.method == 'POST':
        form = FeedbackForm(request.POST, request.FILES)
        if form.is_valid():
            feedback = form.save(commit=False)
            feedback.user = request.user
            feedback.save()
            return redirect('home')
    else:
        form = FeedbackForm()
    return render(request, 'core/home.html', {'feedbacks': feedbacks, 'form': form})

def menu(request):
    items = MenuItem.objects.all()
    return render(request, 'core/menu.html', {'items': items})

def details(request):
    # You might want to return static details here or fetch from the database
    return render(request, 'core/details.html')

def feedbacks(request):
    feedbacks = Feedback.objects.all()
    return render(request, 'core/feedbacks.html', {'feedbacks': feedbacks})

@login_required
def post_feedback(request):
    if request.method == 'POST':
        form = FeedbackForm(request.POST, request.FILES)
        if form.is_valid():
            feedback = form.save(commit=False)
            feedback.user = request.user
            feedback.save()
            return redirect('feedbacks')
    else:
        form = FeedbackForm()
    return render(request, 'core/post_feedback.html', {'form': form})

@login_required
def reserve(request):
    if request.method == 'POST':
        form = ReservationForm(request.POST)
        if form.is_valid():
            reservation = form.save(commit=False)
            reservation.user = request.user
            reservation.save()
            print(f"Reservation created: {reservation}")
            return redirect('home')  # Redirect to a relevant page
        else:
            print(f"Reservation form is invalid: {form.errors}")
    else:
        form = ReservationForm()
    return render(request, 'core/reserve.html', {'form': form})

@login_required
def order(request):
    # Implement ordering logic here
    return HttpResponse("Order functionality coming soon!")
