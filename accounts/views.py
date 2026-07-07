from django.shortcuts import render, redirect

# Create your views here.
from .utils import create_default_admin
from .models import User
from django.contrib.auth import authenticate, login, logout

def login_view(request):
    create_default_admin()

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)

            if user.role == 'admin':
                return redirect('admin_dashboard')
            elif user.role == 'staff':
                return redirect('staff_dashboard')

            else:
                return redirect('login-view')

        return redirect('login-view')

    return render(request, 'login.html')

def logout_view(request):
    logout(request)
    return redirect('login')