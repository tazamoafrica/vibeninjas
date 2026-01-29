from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Q, Count, Sum
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.models import Group
from django.contrib.auth.views import LoginView, LogoutView
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Q
from django.utils import timezone
from datetime import timedelta
from django.core.serializers.json import DjangoJSONEncoder
from .forms import BuyerSignUpForm, SellerSignUpForm, BuyerProfileForm, SellerProfileForm
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from .models import Category, Event, Ticket, TicketCategory
from .forms import EventForm, TicketCategoryFormSet, TicketPurchaseForm
import stripe
from django.db.models import Q
from PIL import Image, ImageDraw, ImageFont
import io
from django.core.mail import EmailMessage
from django.conf import settings
import os
import json
import base64
import requests
from datetime import datetime
from twilio.rest import Client
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse
from django.contrib.auth import get_user_model

User = get_user_model()
stripe.api_key = settings.STRIPE_SECRET_KEY

def privacy_policy(request):
    """Privacy Policy page view"""
    return render(request, 'privacy_policy.html')

# Login View with Role-based access
class CustomLoginView(LoginView):
    template_name = 'registration/login.html'
    
    def get_success_url(self):
        user = self.request.user
        if user.is_staff:
            return '/admin-dashboard/'
        elif user.is_seller:
            return '/dashboard/'
        elif user.is_buyer:
            return '/'
        return '/' 

# Custom Logout View that accepts both GET and POST
def custom_logout(request):
    if request.method == 'POST' or request.method == 'GET':
        logout(request)
        messages.success(request, 'You have been successfully logged out.')
        return redirect('home')
    return redirect('home')

def home(request):
    events = Event.objects.filter(
        is_active=True, 
        date__gte=timezone.now()
    ).prefetch_related('ticket_categories').order_by('date')[:6]
    
    return render(request, 'events/home.html', {
        'events': events
    })

def event_list(request):
    events = Event.objects.filter(is_active=True, date__gte=timezone.now())
    categories = Category.objects.all()

    search_query = request.GET.get('search', '')
    category_slug = request.GET.get('category', '')
    if search_query:
        events = events.filter(
            Q(title__icontains=search_query) |
            Q(description__icontains=search_query) |
            Q(location__icontains=search_query)
        )

    if category_slug:
        events = events.filter(category__slug=category_slug)

    return render(request, 'events/event_list.html', {'events': events, 'categories': categories})

@login_required
def category_events(request, slug):
    category = get_object_or_404(Category, slug=slug)
    events = Event.objects.filter(category=category)
    return render(request, 'events/category_events.html', {'category': category, 'events': events})


def event_detail(request, pk):
    event = get_object_or_404(Event, pk=pk)
    selected_category = event.ticket_categories.filter(
        available_tickets__gt=0
    ).first()
    context = {
        'event': event,
        'now': timezone.now(),
        'selected_category': selected_category,
        'now': timezone.now(),
    }
    return render(request, 'events/event_detail.html', context)

@login_required
def dashboard(request):
    events = Event.objects.filter(organizer=request.user).prefetch_related('ticket_categories')
    total_events = events.count()
    total_tickets_sold = sum(event.tickets_sold for event in events)
    total_revenue = sum(ticket.total_amount for event in events for ticket in event.tickets.all())
    
    # Get revenue by category for each event
    events_data = []
    for event in events:
        category_revenue = {}
        for category in event.ticket_categories.all():
            tickets = category.tickets.all()
            total_amount = float(sum(ticket.total_amount for ticket in tickets))
            category_revenue[category.name] = {
                'revenue': total_amount,
                'tickets_sold': tickets.count(),
                'price': float(category.price) if category.price else 0.0
            }
        events_data.append({
            'id': event.id,
            'title': event.title,
            'category_revenue': category_revenue,
            'total_revenue': float(sum(cat['revenue'] for cat in category_revenue.values()))
        })
    
    # Get all ticket categories with their prices
    from django.db.models import Min, Max, Count
    
    ticket_categories = TicketCategory.objects.filter(
        event__organizer=request.user
    ).values(
        'name', 'price'
    ).annotate(
        min_price=Min('price'),
        max_price=Max('price'),
        event_count=Count('event', distinct=True)
    ).order_by('name')
    
    context = {
        'events': events,
        'events_json': json.dumps(events_data),  # For JavaScript
        'total_events': total_events,
        'total_tickets_sold': total_tickets_sold,
        'total_revenue': total_revenue,
        'ticket_categories': ticket_categories,
    }
    return render(request, 'events/dashboard.html', context)

@login_required
def create_event(request):
    if request.method == 'POST':
        form = EventForm(request.POST, request.FILES)
        ticket_formset = TicketCategoryFormSet(request.POST)
        
        if form.is_valid() and ticket_formset.is_valid():
            try:
                # Create event with initial available_tickets value
                event = form.save(commit=False)
                event.organizer = request.user
                event.available_tickets = 0  # Set initial value
                event.save()
                
                # Save ticket categories
                ticket_formset.instance = event
                categories = ticket_formset.save()
                
                if not categories:
                    messages.error(request, 'Please add at least one ticket category.')
                    event.delete()
                    return render(request, 'events/create_event.html', {
                        'form': form,
                        'ticket_formset': ticket_formset
                    })
                
                # Update available tickets from categories
                total_available = sum(tc.available_tickets for tc in categories)
                event.available_tickets = total_available
                event.total_tickets = total_available
                event.save()
                
                messages.success(request, 'Event created successfully!')
                return redirect('dashboard')
                
            except Exception as e:
                messages.error(request, f'Error creating event: {str(e)}')
                # Clean up if there was an error
                if event.pk:
                    event.delete()
        else:
            if form.errors:
                messages.error(request, 'Please correct the errors in the event form.')
            if ticket_formset.errors:
                messages.error(request, 'Please correct the errors in the ticket categories.')
            print("Form errors:", form.errors)
            print("Formset errors:", ticket_formset.errors)
    else:
        form = EventForm()
        ticket_formset = TicketCategoryFormSet()
    
    return render(request, 'events/create_event.html', {
        'form': form,
        'ticket_formset': ticket_formset
    })

@login_required
def edit_event(request, pk):
    event = get_object_or_404(Event, pk=pk, organizer=request.user)
    if request.method == 'POST':
        form = EventForm(request.POST, request.FILES, instance=event)
        ticket_formset = TicketCategoryFormSet(request.POST, instance=event)
        
        if form.is_valid() and ticket_formset.is_valid():
            try:
                # Debug: Print form data
                print(f"Form data: {form.cleaned_data}")
                print(f"Ticket formset data: {[f.cleaned_data for f in ticket_formset]}")
                
                # Save the event first
                event = form.save(commit=False)  # Don't commit yet
                
                # Save ticket categories
                categories = ticket_formset.save(commit=False)
                for category in categories:
                    if not category.max_tickets_per_purchase:
                        category.max_tickets_per_purchase = 10  # Default value
                    category.save()
                
                # Handle deletions
                for obj in ticket_formset.deleted_objects:
                    obj.delete()
                
                # Update available tickets based on ticket categories
                event.available_tickets = sum(tc.available_tickets for tc in event.ticket_categories.all())
                
                # Now save the event
                event.save()
                
                messages.success(request, 'Event updated successfully!')
                return redirect('dashboard')
            except Exception as e:
                messages.error(request, f'Error saving event: {str(e)}')
                print(f"Event edit error: {e}")  # Debug line
        else:
            # Debug: Print form errors
            print(f"Form errors: {form.errors}")
            print(f"Ticket formset errors: {[f.errors for f in ticket_formset]}")
    else:
        form = EventForm(instance=event)
        ticket_formset = TicketCategoryFormSet(instance=event)
    
    return render(request, 'events/edit_event.html', {
        'form': form,
        'ticket_formset': ticket_formset,
        'event': event
    })

@login_required
def delete_event(request, pk):
    event = get_object_or_404(Event, pk=pk, organizer=request.user)
    if request.method == 'POST':
        event.delete()
        messages.success(request, 'Event deleted successfully.')
        return redirect('dashboard')
    return render(request, 'events/delete.html', {'event': event})


def checkout(request, pk):
    event = get_object_or_404(Event, pk=pk)
    category_id = request.GET.get('category')
    
    if not category_id:
        messages.error(request, 'Please select a ticket category.')
        return redirect('event_detail', pk=event.pk)
    
    try:
        selected_category = TicketCategory.objects.get(
            id=category_id,
            event=event,
            available_tickets__gt=0
        )
    except TicketCategory.DoesNotExist:
        messages.error(request, 'Selected ticket category is not available.')
        return redirect('event_detail', pk=event.pk)
    
    initial_data = {
        'ticket_category': selected_category,
        'quantity': 1
    }
    
    if request.user.is_authenticated:
        initial_data.update({
            'buyer_name': request.user.get_full_name(),
            'buyer_email': request.user.email
        })
    
    form = TicketPurchaseForm(
        event, 
        initial=initial_data
    )
    
    context = {
        'event': event,
        'selected_category': selected_category,
        'form': form,
        'stripe_publishable_key': settings.STRIPE_PUBLISHABLE_KEY,
    }
    
    return render(request, 'events/checkout.html', context)

@csrf_exempt
@require_POST
def payment_success(request):
    try:
        payload = json.loads(request.body)
        payment_intent_id = payload.get('payment_intent_id')
        intent = stripe.PaymentIntent.retrieve(payment_intent_id)
        
        if intent.status == 'succeeded':
            event_id = intent.metadata.get('event_id')
            ticket_category_id = intent.metadata.get('ticket_category_id')
            buyer_name = intent.metadata.get('buyer_name')
            buyer_email = intent.metadata.get('buyer_email')
            quantity = int(intent.metadata.get('quantity'))
            
            event = Event.objects.get(id=event_id)
            ticket_category = TicketCategory.objects.get(id=ticket_category_id)
            
            ticket = Ticket.objects.create(
                event=event,
                ticket_category=ticket_category,
                buyer_name=buyer_name,
                buyer_email=buyer_email,
                quantity=quantity,
                unit_price=ticket_category.price,
                total_amount=intent.amount / 100,
                stripe_payment_intent_id=payment_intent_id
            )
            
            # Update available tickets
            ticket_category.available_tickets -= quantity
            ticket_category.save()
            
            event.available_tickets -= quantity
            event.save()
            
            send_ticket_email(ticket)
            
            if hasattr(ticket, 'buyer_phone') and ticket.buyer_phone:
                send_ticket_sms(ticket)
            
            return JsonResponse({'success': True, 'ticket_id': ticket.id})
    
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
def generate_ticket_image(ticket):
    """Generate a ticket image with event and buyer details"""
    # Create a new image with white background
    width = 1000
    height = 500
    image = Image.new('RGB', (width, height), 'white')
    draw = ImageDraw.Draw(image)
    
    # Try to load a font, fallback to default if not found
    try:
        font_large = ImageFont.truetype("arial.ttf", 40)
        font_medium = ImageFont.truetype("arial.ttf", 30)
        font_small = ImageFont.truetype("arial.ttf", 25)
    except:
        font_large = ImageFont.load_default()
        font_medium = ImageFont.load_default()
        font_small = ImageFont.load_default()

    # Draw ticket content
    draw.text((50, 50), ticket.event.title, fill='black', font=font_large)
    draw.text((50, 100), f"Category: {ticket.ticket_category.name}", fill='black', font=font_medium)
    draw.text((50, 150), f"Date: {ticket.event.date.strftime('%B %d, %Y at %I:%M %p')}", fill='black', font=font_medium)
    draw.text((50, 200), f"Location: {ticket.event.location}", fill='black', font=font_medium)
    draw.text((50, 250), f"Attendee: {ticket.buyer_name}", fill='black', font=font_medium)
    draw.text((50, 300), f"Quantity: {ticket.quantity}", fill='black', font=font_medium)
    draw.text((50, 350), f"Price per ticket: ${ticket.unit_price}", fill='black', font=font_medium)
    draw.text((50, 400), f"Ticket Code: {ticket.ticket_code}", fill='black', font=font_large)
    
    # Save image to bytes buffer
    image_buffer = io.BytesIO()
    image.save(image_buffer, format='JPEG', quality=90)
    image_buffer.seek(0)
    
    return image_buffer

def send_ticket_email(ticket):
    """Send email with ticket details and attached ticket image"""
    subject = f'Your Ticket for {ticket.event.title}'
    message = f"""
    Dear {ticket.buyer_name},
    
    Thank you for purchasing tickets for {ticket.event.title}!
    
    Event Details:
    - Event: {ticket.event.title}
    - Category: {ticket.ticket_category.name}
    - Date: {ticket.event.date.strftime('%B %d, %Y at %I:%M %p')}
    - Location: {ticket.event.location}
    - Quantity: {ticket.quantity}
    - Price per ticket: ${ticket.unit_price}
    - Total Paid: ${ticket.total_amount}
    - Ticket Code: {ticket.ticket_code}
    
    
    Please find your ticket attached to this email.
    Present this ticket (either digital or printed) at the event entrance.
    
    Best regards,
    Event Team
    """
    
    # Create EmailMessage object
    email = EmailMessage(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [ticket.buyer_email]
    )
    
    ticket_image = generate_ticket_image(ticket)
    email.attach(
        f'ticket_{ticket.ticket_code}.jpg',
        ticket_image.getvalue(),
        'image/jpeg'
    )
    
    email.send(fail_silently=False)

def send_ticket_sms(ticket):
    try:
        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        
        message = client.messages.create(
            body=f'Ticket confirmed for {ticket.event.title} on {ticket.event.date.strftime("%m/%d/%Y")}. Code: {ticket.ticket_code}',
            from_=settings.TWILIO_PHONE_NUMBER,
            to=ticket.buyer_phone
        )
    except Exception as e:
        print(f"SMS sending failed: {e}")

def ticket_confirmation(request, ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)
    return render(request, 'events/ticket_confirmation.html', {'ticket': ticket})


SUBSCRIPTION_PLANS = {
    'daily': {
        'name': 'Daily Plan',
        'price_id': 'price_XXXXX', 
        'amount': 500,  # $5.00
    },
    'monthly': {
        'name': 'Monthly Plan',
        'price_id': 'price_XXXXX',  
        'amount': 4900,  # $49.00
    },
    'yearly': {
        'name': 'Yearly Plan',
        'price_id': 'price_XXXXX',  
        'amount': 39900,  # $399.00
    }
}

@login_required
def subscription(request, plan):
    if plan not in SUBSCRIPTION_PLANS:
        messages.error(request, 'Invalid subscription plan')
        return redirect('dashboard')
    
    plan_data = SUBSCRIPTION_PLANS[plan]
    
    try:
        # Create Stripe checkout session
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price': plan_data['price_id'],
                'quantity': 1,
            }],
            mode='subscription',
            success_url=request.build_absolute_uri('/subscription/success/'),
            cancel_url=request.build_absolute_uri('/subscription/cancel/'),
            client_reference_id=request.user.id,
        )
        return redirect(checkout_session.url)
    except Exception as e:
        messages.error(request, f'Error creating subscription: {str(e)}')
        return redirect('dashboard')

@login_required
def subscription_success(request):
    messages.success(request, 'Successfully subscribed to TazamoXM Pro!')
    return redirect('dashboard')

@login_required
def subscription_cancel(request):
    messages.info(request, 'Subscription cancelled')
    return redirect('dashboard')

@login_required
def pro_features(request):
    return render(request, 'subscription/pro_features.html')

@login_required
def subscription_settings(request):
    return render(request, 'subscription/settings.html')

@staff_member_required
def admin_dashboard(request):
    if not request.user.is_staff:
        return redirect('home')
    
    # User statistics
    total_users = User.objects.count()
    new_users_week = User.objects.filter(date_joined__gte=timezone.now()-timedelta(days=7)).count()
    active_users = User.objects.filter(is_active=True).count()
    
    # Ticket statistics
    total_tickets = Ticket.objects.count()
    tickets_today = Ticket.objects.filter(purchased_at__date=timezone.now().date()).count()
    total_revenue = Ticket.objects.aggregate(total=Sum('total_amount'))['total'] or 0
    
    # Event statistics
    total_events = Event.objects.count()
    upcoming_events = Event.objects.filter(date__gte=timezone.now()).count()
    
    # User statistics
    today = timezone.now().date()
    user_signups = {
        'today': User.objects.filter(date_joined__date=today).count(),
        'this_week': User.objects.filter(date_joined__gte=today - timedelta(days=7)).count(),
        'this_month': User.objects.filter(date_joined__year=today.year, date_joined__month=today.month).count(),
        'total': User.objects.count()
    }
    
    # Recent activity
    recent_tickets = Ticket.objects.select_related('event', 'ticket_category', 'buyer').order_by('-purchased_at')[:10]
    recent_users = User.objects.order_by('-date_joined')[:10]
    
    # User activity (last login times)
    active_users_list = User.objects.filter(is_active=True).order_by('-last_login')[:10]
    
    # Visitor analytics
    visitor_stats = {}
    recent_visits = []
    
    try:
        from .models_analytics import Visitor
        # Get visitor statistics for the last 30 days
        visitor_stats = Visitor.get_visitor_stats(days=30)
        # Get recent visits with user info
        recent_visits = Visitor.get_recent_visits(limit=10)
    except Exception as e:
        print(f"Error loading visitor analytics: {str(e)}")
    
    # Sales data for charts (last 30 days)
    thirty_days_ago = timezone.now() - timedelta(days=30)
    daily_sales = list(Ticket.objects.filter(
        purchased_at__gte=thirty_days_ago
    ).values('purchased_at__date').annotate(
        total_sales=Sum('total_amount'),
        count=Count('id')
    ).order_by('purchased_at__date'))
    
    # User signup trend (last 30 days)
    user_signup_trend = list(User.objects.filter(
        date_joined__gte=thirty_days_ago
    ).extra({
        'signup_date': "date(date_joined)"
    }).values('signup_date').annotate(
        count=Count('id')
    ).order_by('signup_date'))
    
    # Convert date objects to strings for JSON serialization
    for sale in daily_sales:
        if sale['purchased_at__date']:
            sale['purchased_at__date'] = sale['purchased_at__date'].isoformat()
    
    # Debug logging
    print("Daily sales data:", daily_sales)
    print("Recent tickets:", list(recent_tickets.values('id', 'purchased_at', 'total_amount')))
    print("Recent users:", list(recent_users.values('id', 'username', 'date_joined')))
    
    context = {
        'total_users': total_users,
        'new_users_week': new_users_week,
        'active_users_count': active_users,
        'total_tickets': total_tickets,
        'tickets_today': tickets_today,
        'total_revenue': total_revenue,
        'total_events': total_events,
        'upcoming_events': upcoming_events,
        'recent_tickets': recent_tickets,
        'recent_users': recent_users,
        'active_users': active_users_list,
        'user_signups': user_signups,
        'user_signup_trend': json.dumps(user_signup_trend, cls=DjangoJSONEncoder),
        'daily_sales': json.dumps(daily_sales, cls=DjangoJSONEncoder),
        'visitor_stats': json.dumps(visitor_stats, cls=DjangoJSONEncoder),
        'recent_visits': recent_visits,
        'total_visits': visitor_stats.get('total_visits', 0),
        'unique_visitors': visitor_stats.get('unique_visitors', 0),
    }
    
    return render(request, 'admin/dashboard.html', context)

@login_required
def subscription_settings(request):
    context = {
        'billing_history': [],  # Fetch from Stripe
    }
    if request.user.subscription:
        # Fetch recent invoices from Stripe
        invoices = stripe.Invoice.list(
            customer=request.user.subscription.stripe_customer_id,
            limit=5
        )
        context['billing_history'] = invoices.data
    
    return render(request, 'subscription/settings.html', context)

@require_POST
@login_required
def create_payment_intent(request, pk):
    try:
        event = get_object_or_404(Event, pk=pk)
        category_id = request.POST.get('category_id')
        quantity = int(request.POST.get('quantity', 1))
        
        category = get_object_or_404(TicketCategory, 
            id=category_id,
            event=event,
            available_tickets__gt=0
        )
        
        # Calculate amount in cents
        amount = int(category.price * quantity * 100)
        
        # Create payment intent
        intent = stripe.PaymentIntent.create(
            amount=amount,
            currency='kes',
            metadata={
                'event_id': event.id,
                'category_id': category.id,
                'quantity': quantity,
                'buyer_name': request.POST.get('buyer_name'),
                'buyer_email': request.POST.get('buyer_email'),
                'buyer_phone': request.POST.get('buyer_phone', ''),
            }
        )
        
        return JsonResponse({
            'client_secret': intent.client_secret
        })
        
    except Exception as e:
        return JsonResponse({
            'error': str(e)
        }, status=400)
    
def ticket_confirmation(request, payment_intent):
    try:
        # Retrieve the payment intent from Stripe
        intent = stripe.PaymentIntent.retrieve(payment_intent)
        
        # Get or create the ticket
        ticket = get_object_or_404(Ticket, stripe_payment_intent_id=payment_intent)
        
        return render(request, 'events/ticket_confirmation.html', {
            'ticket': ticket,
            'payment': intent
        })
    except Exception as e:
        messages.error(request, 'Error retrieving ticket information.')
        return redirect('dashboard')
    
def signup_buyer(request):
    if request.method == 'POST':
        form = BuyerSignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('home')
    else:
        form = BuyerSignUpForm()
    return render(request, 'registration/buyer-signup.html', {'form': form})

def signup_seller(request):
    if request.method == 'POST':
        form = SellerSignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('dashboard')
    else:
        form = SellerSignUpForm()
    return render(request, 'registration/seller-signup.html', {'form': form})

@login_required
# M-Pesa callback view
@csrf_exempt
def mpesa_callback(request):
    """
    Handle M-Pesa API callbacks for payment notifications
    """
    if request.method == 'POST':
        try:
            # Log the raw request data for debugging
            print("M-Pesa Callback Received:", request.body)
            
            # Parse the JSON data
            data = json.loads(request.body)
            
            # Extract important information
            result_code = data.get('Body', {}).get('stkCallback', {}).get('ResultCode')
            result_desc = data.get('Body', {}).get('stkCallback', {}).get('ResultDesc')
            
            # Check if payment was successful
            if result_code == 0:
                # Payment was successful
                checkout_request_id = data.get('Body', {}).get('stkCallback', {}).get('CheckoutRequestID')
                amount = None
                mpesa_receipt_number = None
                
                # Extract amount and receipt number from callback metadata
                for item in data.get('Body', {}).get('stkCallback', {}).get('CallbackMetadata', {}).get('Item', []):
                    if item.get('Name') == 'Amount':
                        amount = item.get('Value')
                    if item.get('Name') == 'MpesaReceiptNumber':
                        mpesa_receipt_number = item.get('Value')
                
                #update database with the payment details
                order = Order.objects.get(checkout_request_id=checkout_request_id)
                order.payment_status = 'completed'
                order.mpesa_receipt = mpesa_receipt_number
                order.save()
                
                print(f"Payment successful. Receipt: {mpesa_receipt_number}, Amount: {amount}")
                
            else:
                # Payment failed
                print(f"Payment failed. Reason: {result_desc}")
            
            # Always return success to M-Pesa
            return JsonResponse({"ResultCode": 0, "ResultDesc": "Success"})
            
        except Exception as e:
            print(f"Error processing M-Pesa callback: {str(e)}")
            return JsonResponse({"ResultCode": 1, "ResultDesc": "Failed"}, status=500)
    
    return JsonResponse({"ResultCode": 1, "ResultDesc": "Method not allowed"}, status=405)

# Profile Management Views
@login_required
def profile_view(request):
    """View user profile based on their role"""
    user = request.user
    context = {'user': user}
    
    if user.is_seller:
        # Add seller-specific context
        active_events_count = user.events.filter(is_active=True).count()
        context.update({
            'active_events_count': active_events_count,
            'total_events': user.events.count(),
            'tickets_sold': 0,
            'total_revenue': 0
        })
        return render(request, 'profile/seller_profile.html', context)
    elif user.is_buyer:
        # Add buyer-specific context
        context.update({
            'total_tickets': user.purchased_tickets.count(),
            'confirmed_tickets': user.purchased_tickets.filter(status='confirmed').count(),
            'used_tickets': user.purchased_tickets.filter(status='used').count()
        })
        return render(request, 'profile/buyer_profile.html', context)
    else:
        return render(request, 'profile/default_profile.html', context)

@login_required
def profile_edit(request):
    """Edit user profile based on their role"""
    if request.user.is_seller:
        form_class = SellerProfileForm
        template_name = 'profile/seller_profile_edit.html'
        success_message = 'Seller profile updated successfully!'
    elif request.user.is_buyer:
        form_class = BuyerProfileForm
        template_name = 'profile/buyer_profile_edit.html'
        success_message = 'Buyer profile updated successfully!'
    else:
        form_class = BuyerProfileForm
        template_name = 'profile/buyer_profile_edit.html'
        success_message = 'Profile updated successfully!'
    
    if request.method == 'POST':
        form = form_class(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, success_message)
            return redirect('profile_view')
    else:
        form = form_class(instance=request.user)
    
    return render(request, template_name, {'form': form})

@login_required
def profile_delete(request):
    """Delete user profile with confirmation"""
    if request.method == 'POST':
        request.user.delete()
        messages.success(request, 'Your account has been deleted successfully.')
        return redirect('home')
    return render(request, 'profile/confirm_delete.html')

@login_required
def my_tickets(request):
    """View all tickets purchased by the logged-in buyer"""
    if not request.user.is_buyer:
        messages.warning(request, 'This page is only available to buyers.')
        return redirect('profile')
    
    # Get all tickets for the current buyer, ordered by event date (upcoming first)
    tickets = request.user.purchased_tickets.select_related('event', 'ticket_category')\
        .filter(event__date__gte=timezone.now())\
        .order_by('event__date')
    
    # Get past tickets (for a separate section)
    past_tickets = request.user.purchased_tickets.select_related('event', 'ticket_category')\
        .filter(event__date__lt=timezone.now())\
        .order_by('-event__date')
    
    context = {
        'upcoming_tickets': tickets,
        'past_tickets': past_tickets,
    }
    return render(request, 'profile/my_tickets.html', context)

@login_required
def buyer_merchandise_order_list(request):
    """View all merchandise orders for the logged-in buyer"""
    if not request.user.is_buyer:
        messages.warning(request, 'This page is only available to buyers.')
        return redirect('profile')
    
    # Get all merchandise orders for the current buyer, ordered by creation date (newest first)
    from seller_merchandise.models import SellerMerchandiseOrder
    
    orders = SellerMerchandiseOrder.objects.filter(buyer=request.user)\
        .prefetch_related('sellerorderitem_set__merchandise')\
        .order_by('-created_at')
    
    # Calculate status counts
    pending_orders_count = orders.filter(status='pending').count()
    shipped_orders_count = orders.filter(status='shipped').count()
    delivered_orders_count = orders.filter(status='delivered').count()
    
    context = {
        'orders': orders,
        'pending_orders_count': pending_orders_count,
        'shipped_orders_count': shipped_orders_count,
        'delivered_orders_count': delivered_orders_count,
    }
    return render(request, 'merchandise/buyer_order_list.html', context)

@login_required
def buyer_merchandise_order_detail(request, pk):
    """View details of a specific merchandise order"""
    if not request.user.is_buyer:
        messages.warning(request, 'This page is only available to buyers.')
        return redirect('profile')
    
    from seller_merchandise.models import SellerMerchandiseOrder
    
    order = get_object_or_404(SellerMerchandiseOrder, pk=pk, buyer=request.user)
    order_items = order.sellerorderitem_set.select_related('merchandise').all()
    
    context = {
        'order': order,
        'order_items': order_items,
    }
    return render(request, 'merchandise/buyer_order_detail.html', context)