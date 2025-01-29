from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login as auth_login, logout
from django.contrib.auth.models import User
from django_otp.plugins.otp_totp.models import TOTPDevice
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from .forms import SignupForm, OTPForm
import random
import string
from django.shortcuts import render, redirect
from django.contrib.auth.forms import UserCreationForm
from core.models import Reservation
from core.forms import ReservationForm
from django.shortcuts import get_object_or_404
from django.contrib import messages
from core.models import Feedback 

def register(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('login')  # Redirect to login or any other page
    else:
        form = UserCreationForm()
    return render(request, 'register.html', {'form': form})
# def signup(request):
#     if request.method == 'POST':
#         form = SignupForm(request.POST)
#         if form.is_valid():
#             device = TOTPDevice.objects.create(user=request.user)
#             user = form.save(commit=False)
#             user.is_active = False  # Deactivate account until it is verified
#             user.set_password(form.cleaned_data['password'])  # Set hashed password
#             user.save()
            
#             # Create a TOTP device for the user
#             device = TOTPDevice.objects.create(user=user, name='default')
#             device.save()
            
#             # Generate OTP and send it to the user
#             otp = device.generate_token()
#             send_mail(
#                 'Your OTP Code',
#                 f'Your OTP code is {otp}',
#                 'from@example.com',
#                 [user.email],
#                 fail_silently=False,
#             )
            
#             request.session['user_id'] = user.id
#             return redirect('otp_verification')
#     else:
#         form = SignupForm()
#     return render(request, 'users/signup.html', {'form': form})

def signup(request):
    if request.method == 'POST':
        username = request.POST['username']
        email = request.POST['email']
        password = request.POST['password']

        # Check if user already exists
        if User.objects.filter(username=username).exists():
            messages.error(request, 'Username already exists.')
            return redirect('signup')

        # Create a new user
        user = User.objects.create_user(username=username, email=email, password=password)
        user.save()

        # Redirect to login page after signup
        return redirect('login')

    return render(request, 'users/signup.html')
def otp_verification(request):
    if request.method == 'POST':
        form = OTPForm(request.POST)
        if form.is_valid():
            otp = form.cleaned_data['otp']
            user_id = request.session.get('user_id')
            try:
                user = User.objects.get(id=user_id)
                device = TOTPDevice.objects.get(user=user, name='default')
                if device.verify_token(otp):
                    user.is_active = True
                    user.save()
                    auth_login(request, user)
                    return redirect('home')
            except (User.DoesNotExist, TOTPDevice.DoesNotExist):
                form.add_error(None, "Invalid OTP. Please try again.")
    else:
        form = OTPForm()
    return render(request, 'users/otp_verification.html', {'form': form})

@login_required
def profile(request):
    reservations = Reservation.objects.filter(user=request.user).order_by('-date')
    return render(request, 'users/profile.html', {'reservations': reservations})

def logout_view(request):
    logout(request)
    return redirect('login')


# users/views.py

@login_required
def reserve(request):
    if request.method == 'POST':
        form = ReservationForm(request.POST)
        if form.is_valid():
            reservation = form.save(commit=False)
            reservation.user = request.user
            reservation.save()
            return redirect('profile')  # Redirect to the profile page
        else:
            print(f"Reservation form is invalid: {form.errors}")
    else:
        form = ReservationForm()
    return render(request, 'core/reserve.html', {'form': form})


@login_required
def cancel_reservation(request, reservation_id):
    reservation = get_object_or_404(Reservation, id=reservation_id, user=request.user)
    if reservation.status != 'cancelled':
        reservation.status = 'cancelled'
        reservation.save()
        messages.success(request, "Your reservation has been cancelled.")
    else:
        messages.warning(request, "This reservation is already cancelled.")
    return redirect('profile')

@login_required
def delete_feedback(request, feedback_id):
    feedback = get_object_or_404(Feedback, id=feedback_id, user=request.user)
    feedback.delete()
    messages.success(request, "Your feedback has been deleted.")
    return redirect('home')