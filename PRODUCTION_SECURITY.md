# Production Deployment Security Checklist

## Critical Security Steps for Production

### 1. Secret Key
```python
# In settings.py, replace with:
import os
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY')

# Generate a new key:
python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'
```

### 2. Debug Mode
```python
# In settings.py:
DEBUG = False
ALLOWED_HOSTS = ['yourdomain.com', 'www.yourdomain.com']
```

### 3. Database Encryption
For production, encrypt API keys stored in the database:

```bash
pip install django-fernet-fields
```

```python
# In sync/models.py:
from fernet_fields import EncryptedCharField

class UserProfile(models.Model):
    canvas_api_key = EncryptedCharField(max_length=255, blank=True)
    notion_api_key = EncryptedCharField(max_length=255, blank=True)
```

Set encryption key in environment:
```bash
export DJANGO_FERNET_KEY=$(python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')
```

### 4. HTTPS Only
```python
# In settings.py:
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
```

### 5. Database Configuration
Use PostgreSQL instead of SQLite:

```python
# In settings.py:
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('DB_NAME'),
        'USER': os.environ.get('DB_USER'),
        'PASSWORD': os.environ.get('DB_PASSWORD'),
        'HOST': os.environ.get('DB_HOST'),
        'PORT': os.environ.get('DB_PORT', '5432'),
    }
}
```

### 6. Static Files
```bash
python manage.py collectstatic
```

Configure web server (nginx/Apache) to serve static files.

### 7. WSGI Server
Use Gunicorn instead of development server:

```bash
pip install gunicorn
gunicorn notionsync_web.wsgi:application --bind 0.0.0.0:8000
```

### 8. Environment Variables
Create `.env` file (add to .gitignore):

```
DJANGO_SECRET_KEY=your-secret-key-here
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
DB_NAME=notionsync
DB_USER=notionsync_user
DB_PASSWORD=strong-password-here
DB_HOST=localhost
DB_PORT=5432
DJANGO_FERNET_KEY=your-fernet-key-here
```

Use python-decouple to load:
```bash
pip install python-decouple
```

```python
# In settings.py:
from decouple import config

SECRET_KEY = config('DJANGO_SECRET_KEY')
DEBUG = config('DJANGO_DEBUG', default=False, cast=bool)
```

### 9. CORS and CSRF
If using API from different domains:
```bash
pip install django-cors-headers
```

### 10. Backup Strategy
- Regular database backups
- Secure backup of encryption keys
- Document recovery procedures

## Deployment Checklist

- [ ] SECRET_KEY moved to environment variable
- [ ] DEBUG = False
- [ ] ALLOWED_HOSTS configured
- [ ] API keys encrypted in database
- [ ] HTTPS/SSL certificate installed
- [ ] PostgreSQL database configured
- [ ] Gunicorn or uWSGI configured
- [ ] Nginx/Apache reverse proxy set up
- [ ] Static files collected and served
- [ ] Database migrations applied
- [ ] Backup system in place
- [ ] Monitoring/logging configured
- [ ] Rate limiting enabled
- [ ] Security headers configured

## Additional Security Measures

### Rate Limiting
```bash
pip install django-ratelimit
```

### Two-Factor Authentication
```bash
pip install django-otp
```

### Audit Logging
Track all API key access and sync operations in logs.

### Regular Security Updates
```bash
pip list --outdated
pip install --upgrade django
```

### Security Scanning
```bash
pip install bandit
bandit -r .
```

## References
- [Django Deployment Checklist](https://docs.djangoproject.com/en/stable/howto/deployment/checklist/)
- [Django Security](https://docs.djangoproject.com/en/stable/topics/security/)
- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
