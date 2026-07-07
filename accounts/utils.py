from django.contrib.auth import get_user_model

User = get_user_model()

def create_default_admin():
    if not User.objects.filter(username='admin').exists():
        User.objects.create_user(
            username='admin',
            password='admin123',
            role='admin',
            is_active=True,
        )