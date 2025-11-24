from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, authenticate
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils import timezone
from .models import UserProfile, SyncLog
from .services import SyncService

# Default assignment buckets
DEFAULT_BUCKETS = ['past', 'undated', 'upcoming', 'future', 'ungraded']


def register(request):
    """User registration view."""
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            # Create associated profile
            UserProfile.objects.create(user=user)
            username = form.cleaned_data.get('username')
            messages.success(request, f'Account created for {username}!')
            login(request, user)
            return redirect('dashboard')
    else:
        form = UserCreationForm()
    
    return render(request, 'sync/register.html', {'form': form})


def user_login(request):
    """User login view."""
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                messages.success(request, f'Welcome back, {username}!')
                return redirect('dashboard')
    else:
        form = AuthenticationForm()
    
    return render(request, 'sync/login.html', {'form': form})


@login_required
def dashboard(request):
    """Main dashboard view."""
    profile = request.user.profile
    recent_logs = request.user.sync_logs.all()[:10]
    
    context = {
        'profile': profile,
        'recent_logs': recent_logs,
        'has_credentials': bool(profile.canvas_api_key and profile.notion_api_key and profile.notion_database_id),
    }
    
    return render(request, 'sync/dashboard.html', context)


@login_required
def settings(request):
    """Settings view for managing API keys and sync configuration."""
    profile = request.user.profile
    
    if request.method == 'POST':
        # Update profile with form data
        profile.canvas_api_key = request.POST.get('canvas_api_key', '').strip()
        profile.notion_api_key = request.POST.get('notion_api_key', '').strip()
        profile.notion_database_id = request.POST.get('notion_database_id', '').strip()
        
        # Canvas URL settings
        profile.use_default_canvas_url = request.POST.get('use_default_url') == 'on'
        if not profile.use_default_canvas_url:
            profile.canvas_base_url = request.POST.get('canvas_base_url', '').strip()
        
        # Sync buckets
        buckets = []
        for bucket in ['past', 'undated', 'upcoming', 'future', 'ungraded']:
            if request.POST.get(f'bucket_{bucket}') == 'on':
                buckets.append(bucket)
        profile.sync_buckets = buckets
        
        profile.save()
        messages.success(request, 'Settings saved successfully!')
        return redirect('settings')
    
    # Default buckets if none set
    if not profile.sync_buckets:
        profile.sync_buckets = DEFAULT_BUCKETS
    
    context = {
        'profile': profile,
    }
    
    return render(request, 'sync/settings.html', context)


@login_required
@require_POST
def run_sync(request):
    """Run sync operation via AJAX."""
    profile = request.user.profile
    
    # Validate credentials
    if not all([profile.canvas_api_key, profile.notion_api_key, profile.notion_database_id]):
        return JsonResponse({
            'success': False,
            'message': 'Missing required credentials. Please configure your API keys in Settings.'
        })
    
    # Determine base URL
    if profile.use_default_canvas_url:
        base_url = "https://keyinstitute.instructure.com/api/v1"
    else:
        base_url = profile.canvas_base_url
    
    # Get buckets or use defaults
    buckets = profile.sync_buckets if profile.sync_buckets else DEFAULT_BUCKETS
    
    # Create sync log
    sync_log = SyncLog.objects.create(user=request.user, status='running')
    
    # Status callback to update log
    status_messages = []
    def status_callback(msg):
        status_messages.append(msg)
    
    # Run sync
    success, message, count = SyncService.sync_assignments(
        canvas_key=profile.canvas_api_key,
        notion_key=profile.notion_api_key,
        notion_db_id=profile.notion_database_id,
        base_url=base_url,
        buckets=buckets,
        selected_course_ids=profile.selected_course_ids,
        is_first_sync=not profile.first_sync_complete,
        status_callback=status_callback
    )
    
    # Update sync log
    sync_log.completed_at = timezone.now()
    sync_log.status = 'success' if success else 'failed'
    sync_log.message = '\n'.join(status_messages) + '\n' + message
    sync_log.assignments_synced = count
    sync_log.save()
    
    # Mark first sync complete if successful
    if success and not profile.first_sync_complete:
        profile.first_sync_complete = True
        profile.save()
    
    return JsonResponse({
        'success': success,
        'message': message,
        'count': count,
        'log_id': sync_log.id
    })


@login_required
def sync_history(request):
    """View sync history."""
    logs = request.user.sync_logs.all()
    context = {
        'logs': logs,
    }
    return render(request, 'sync/history.html', context)
