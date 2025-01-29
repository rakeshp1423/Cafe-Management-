from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login as auth_login
from django.contrib.auth.decorators import user_passes_test

def is_manager(user):
    return user.groups.filter(name='Managers').exists()

def manager_login(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        if user is not None and is_manager(user):
            auth_login(request, user)
            return redirect('manager_dashboard')
    return render(request, 'managers/manager_login.html')

@user_passes_test(is_manager)
def manager_dashboard(request):
    return render(request, 'managers/manager_dashboard.html')
