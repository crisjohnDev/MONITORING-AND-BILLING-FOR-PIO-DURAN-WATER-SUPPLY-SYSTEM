from django.contrib.auth import get_user_model

User = get_user_model()

def create_default_admin():
    if not User.objects.filter(username='pwssadmin').exists():
        User.objects.create_user(
            username='pwssadmin',
            password='pwss321',
            role='admin',
            is_active=True,
        )