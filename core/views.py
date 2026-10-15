import logging

from django.contrib.auth.decorators import login_required
from django.db import DatabaseError, connection
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET

from .forms import FeedbackForm, ReservationForm
from .models import Feedback, MenuItem, Reservation

logger = logging.getLogger(__name__)


@require_GET
def health_check(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
    except DatabaseError:
        logger.exception('Health check could not reach the database.')
        return JsonResponse({'status': 'unavailable'}, status=503)
    return JsonResponse({'status': 'ok'})


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
