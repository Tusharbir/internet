from datetime import datetime, timedelta

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.views import LoginView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Q, Case, Count, When
from django.db.models.deletion import ProtectedError
from django.db import transaction
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import DetailView, FormView, ListView, TemplateView
from django.views.generic.edit import CreateView, DeleteView, UpdateView

from .forms import (
    AdminItemFilterForm,
    AdminMessageFilterForm,
    AdminReportFilterForm,
    AdminUserFilterForm,
    CategoryAdminForm,
    ItemFilterForm,
    ItemForm,
    MessageForm,
    ReportForm,
    UserRegistrationForm,
    UserProfileForm,
)
from .models import Category, Favorite, Item, ItemImage, Message, Report, User

# message threads 
def build_message_threads(user, item_id=None):
    queryset = (
        Message.objects.filter(Q(sender=user) | Q(recipient=user))
        .select_related('item', 'sender', 'recipient')
        .order_by('-created_at')
    )
    if item_id is not None:
        queryset = queryset.filter(item_id=item_id)

    threads = {}
    for message in queryset:
        other_user = message.recipient if message.sender_id == user.id else message.sender
        key = (message.item_id, other_user.id)
        if key not in threads:
            thread_url = reverse('marketplace:item_messages', kwargs={'pk': message.item_id})
            if user == message.item.seller:
                thread_url = f'{thread_url}?recipient={other_user.pk}'
            threads[key] = {
                'item': message.item,
                'other_user': other_user,
                'last_message': message,
                'unread_count': 0,
                'thread_url': thread_url,
            }
        if message.recipient_id == user.id and not message.is_read:
            threads[key]['unread_count'] += 1
    return list(threads.values())


def parse_session_datetime(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def get_recently_viewed_queryset(request):
    viewed_ids = request.session.get('recently_viewed_items', [])
    if not viewed_ids:
        return Item.objects.none()
    ordering = Case(*[When(id=pk, then=pos) for pos, pk in enumerate(viewed_ids)])
    return (
        Item.objects.filter(id__in=viewed_ids)
        .prefetch_related('images')
        .order_by(ordering)
    )


class StaffRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_staff

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            messages.error(self.request, 'You do not have access to the admin panel.')
            return redirect('marketplace:browse')
        return super().handle_no_permission()


class SellerOwnsItemMixin(LoginRequiredMixin, UserPassesTestMixin):
    raise_exception = True

    def test_func(self):
        return self.get_object().seller == self.request.user

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            raise PermissionDenied('You can only manage your own listings.')
        return super().handle_no_permission()


class AdminPanelContextMixin:
    admin_section = 'overview'
    admin_page_title = 'Admin Panel'
    admin_page_intro = 'Marketplace oversight and moderation.'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        open_statuses = [Report.STATUS_OPEN, Report.STATUS_IN_REVIEW]
        context['admin_section'] = self.admin_section
        context['admin_page_title'] = self.admin_page_title
        context['admin_page_intro'] = self.admin_page_intro
        context['admin_open_reports_count'] = Report.objects.filter(status__in=open_statuses).count()
        return context

    def get_return_url(self):
        return self.request.POST.get('next') or self.request.GET.get('next') or reverse(
            'marketplace:admin_dashboard'
        )

# register view
class RegisterView(FormView):
    template_name = 'registration/register.html'
    form_class = UserRegistrationForm
    success_url = reverse_lazy('marketplace:browse')

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect('marketplace:browse')
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        user = form.save()
        login(self.request, user)
        messages.success(self.request, 'Welcome to UniTrade!')
        return super().form_valid(form)


class UserLoginView(LoginView):
    template_name = 'registration/login.html'
    redirect_authenticated_user = True

    def get_success_url(self):
        redirect_to = self.get_redirect_url()
        if redirect_to:
            return redirect_to
        if self.request.user.is_staff:
            return reverse('marketplace:admin_dashboard')
        return reverse('marketplace:browse')

#landing view

class ProfileView(LoginRequiredMixin, TemplateView):
    template_name = 'marketplace/profile.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['profile_user'] = self.request.user
        return context


class ProfileUpdateView(LoginRequiredMixin, UpdateView):
    model = User
    form_class = UserProfileForm
    template_name = 'marketplace/profile_edit.html'
    success_url = reverse_lazy('marketplace:profile')

    def get_object(self, queryset=None):
        return self.request.user

    def form_valid(self, form):
        messages.success(self.request, 'Your profile was updated successfully.')
        return super().form_valid(form)


class HistoryView(LoginRequiredMixin, TemplateView):
    template_name = 'marketplace/history.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['visit_count'] = int(self.request.session.get('visit_count', 0))
        context['last_visit_at'] = parse_session_datetime(self.request.session.get('last_visit_at'))
        context['current_visit_at'] = parse_session_datetime(self.request.session.get('current_visit_at'))
        context['visit_history'] = self.request.session.get('visit_history', {})
        context['recently_viewed'] = get_recently_viewed_queryset(self.request)
        context['recently_viewed_count'] = context['recently_viewed'].count()
        return context


class LandingView(TemplateView):
    template_name = 'landing.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = Category.objects.all()
        context['landing_listings'] = (
            Item.objects.filter(status=Item.STATUS_PUBLISHED)
            .select_related('category', 'seller')
            .prefetch_related('images')[:6]
        )
        return context


class AboutView(TemplateView):
    template_name = 'marketplace/about.html'

#browse view with filters, sorting, and pagination
class BrowseListView(ListView):
    model = Item
    template_name = 'marketplace/home.html'
    context_object_name = 'items'
    paginate_by = 9

    def get_queryset(self):
        queryset = Item.objects.filter(
            status__in=[Item.STATUS_PUBLISHED, Item.STATUS_SOLD]
        ).select_related('category', 'seller').prefetch_related('images')
        form = self.get_filter_form()
        if form.is_valid():
            q = form.cleaned_data.get('q')
            category = form.cleaned_data.get('category')
            condition = form.cleaned_data.get('condition')
            min_price = form.cleaned_data.get('min_price')
            max_price = form.cleaned_data.get('max_price')
            sort = form.cleaned_data.get('sort') or 'newest'

            if q:
                queryset = queryset.filter(Q(title__icontains=q) | Q(description__icontains=q))
            if category:
                queryset = queryset.filter(category=category)
            if condition:
                queryset = queryset.filter(condition=condition)
            if min_price is not None:
                queryset = queryset.filter(price__gte=min_price)
            if max_price is not None:
                queryset = queryset.filter(price__lte=max_price)
            if sort == 'price_low':
                queryset = queryset.order_by('price')
            elif sort == 'price_high':
                queryset = queryset.order_by('-price')
            else:
                queryset = queryset.order_by('-created_at')
        return queryset

    def get_filter_form(self):
        return ItemFilterForm(self.request.GET or None, categories=Category.objects.all())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filter_form'] = self.get_filter_form()
        context['featured_items'] = (
            Item.objects.filter(status=Item.STATUS_PUBLISHED)
            .select_related('category')
            .order_by('-created_at')[:4]
        )
        # Preserve filter params across pagination
        params = self.request.GET.copy()
        params.pop('page', None)
        context['filter_params'] = params.urlencode()
        return context


class ItemDetailView(DetailView):
    model = Item
    template_name = 'marketplace/item_detail.html'
    context_object_name = 'item'

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        if self.object.status == Item.STATUS_DRAFT and (
            not request.user.is_authenticated or self.object.seller != request.user
        ):
            messages.error(request, 'This listing is not available.')
            return redirect('marketplace:browse')

        current_visit_at = timezone.now()
        previous_visit_at = request.session.get('current_visit_at')
        request.session['visit_count'] = int(request.session.get('visit_count', 0)) + 1
        if previous_visit_at:
            request.session['last_visit_at'] = previous_visit_at
        request.session['current_visit_at'] = current_visit_at.isoformat()

        # Track recently viewed in session
        viewed = request.session.get('recently_viewed_items', [])
        if self.object.id in viewed:
            viewed.remove(self.object.id)
        viewed.insert(0, self.object.id)
        request.session['recently_viewed_items'] = viewed[:8]

        # Track visit history for "visits per day" (session + cookie)
        today = current_visit_at.strftime('%Y-%m-%d')
        visit_history = request.session.get('visit_history', {})
        visit_history[today] = visit_history.get(today, 0) + 1
        request.session['visit_history'] = visit_history

        context = self.get_context_data(object=self.object)
        response = self.render_to_response(context)
        response.set_cookie('last_viewed_item', str(self.object.id), max_age=60 * 60 * 24 * 30)
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.user.is_authenticated:
            context['is_favorited'] = Favorite.objects.filter(
                user=self.request.user, item=self.object
            ).exists()
        else:
            context['is_favorited'] = False
        context['primary_image'] = self.object.images.first()
        context['last_viewed_cookie'] = self.request.COOKIES.get('last_viewed_item')
        return context


class ItemCreateView(LoginRequiredMixin, CreateView):
    model = Item
    form_class = ItemForm
    template_name = 'marketplace/item_post.html'

    def form_valid(self, form):
        form.instance.seller = self.request.user
        try:
            with transaction.atomic():
                response = super().form_valid(form)
                self._save_images()
        except Exception:
            form.add_error(None, 'We could not save your listing right now. Please try again.')
            return self.form_invalid(form)
        messages.success(self.request, 'Item listed successfully.')
        return response

    def _save_images(self):
        for image in self.request.FILES.getlist('images'):
            ItemImage.objects.create(item=self.object, image=image)

    def get_success_url(self):
        return reverse('marketplace:item_detail', kwargs={'pk': self.object.pk})


class ItemUpdateView(SellerOwnsItemMixin, UpdateView):
    model = Item
    form_class = ItemForm
    template_name = 'marketplace/item_edit.html'

    def form_valid(self, form):
        delete_ids = form.cleaned_data.get('delete_images', '')
        try:
            with transaction.atomic():
                if delete_ids:
                    ids_to_delete = [int(x) for x in delete_ids.split(',') if x.strip()]
                    for img in ItemImage.objects.filter(id__in=ids_to_delete, item=self.object):
                        img.image.delete(save=False)
                        img.delete()

                response = super().form_valid(form)
                self._save_images()
        except ValueError:
            form.add_error(None, 'We could not process one of the selected images.')
            return self.form_invalid(form)
        except Exception:
            form.add_error(None, 'We could not update your listing right now. Please try again.')
            return self.form_invalid(form)
        messages.success(self.request, 'Item updated successfully.')
        return response

    def _save_images(self):
        for image in self.request.FILES.getlist('images'):
            ItemImage.objects.create(item=self.object, image=image)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['existing_images'] = self.object.images.all()
        return context

    def get_success_url(self):
        return reverse('marketplace:item_detail', kwargs={'pk': self.object.pk})


class ItemDeleteView(SellerOwnsItemMixin, DeleteView):
    model = Item
    template_name = 'marketplace/item_confirm_delete.html'
    success_url = reverse_lazy('marketplace:dashboard')

    def form_valid(self, form):
        messages.success(self.request, 'Item deleted.')
        return super().form_valid(form)


class DashboardView(LoginRequiredMixin, ListView):
    template_name = 'marketplace/dashboard.html'
    context_object_name = 'items'

    def get_queryset(self):
        return Item.objects.filter(seller=self.request.user).prefetch_related('images')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['draft_items'] = Item.objects.filter(
            seller=self.request.user, status=Item.STATUS_DRAFT
        ).prefetch_related('images')
        context['published_items'] = Item.objects.filter(
            seller=self.request.user, status=Item.STATUS_PUBLISHED
        ).prefetch_related('images')
        context['sold_items'] = Item.objects.filter(
            seller=self.request.user, status=Item.STATUS_SOLD
        ).prefetch_related('images')

        # Preserve recently_viewed order using Case/When
        context['recently_viewed'] = get_recently_viewed_queryset(self.request)

        # Visit history for display (sessions + cookies)
        context['visit_history'] = self.request.session.get('visit_history', {})
        context['visit_count'] = int(self.request.session.get('visit_count', 0))
        context['last_visit_at'] = parse_session_datetime(self.request.session.get('last_visit_at'))
        context['current_visit_at'] = parse_session_datetime(self.request.session.get('current_visit_at'))
        context['recent_message_threads'] = build_message_threads(self.request.user)[:4]
        context['listing_counts'] = {
            'all': context['items'].count(),
            'draft': context['draft_items'].count(),
            'published': context['published_items'].count(),
            'sold': context['sold_items'].count(),
        }
        return context


class ItemMessageView(LoginRequiredMixin, View):
    """Message thread about an item. Handles GET (show thread) and POST (send message)."""

    def dispatch(self, request, *args, **kwargs):
        self.item = get_object_or_404(Item, pk=kwargs['pk'])
        if self.item.status == Item.STATUS_DRAFT and self.item.seller != request.user:
            messages.error(request, 'This listing is not available.')
            return redirect('marketplace:browse')
        self.thread_recipient = self._get_thread_recipient()
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        thread_messages = self._get_messages()
        thread_messages.filter(recipient=request.user, is_read=False).update(is_read=True)
        form = MessageForm()
        context = {
            'item': self.item,
            'seller': self.item.seller,
            'thread_messages': thread_messages,
            'thread_recipient': self.thread_recipient,
            'item_threads': build_message_threads(request.user, item_id=self.item.pk),
            'form': form,
        }
        return render(request, 'marketplace/message_thread.html', context)

    def post(self, request, *args, **kwargs):
        form = MessageForm(request.POST)
        if form.is_valid():
            recipient = self._get_recipient()
            if recipient is None:
                messages.error(request, 'Could not determine recipient.')
                return redirect(self._get_thread_url())
            Message.objects.create(
                item=self.item,
                sender=request.user,
                recipient=recipient,
                body=form.cleaned_data['body'],
            )
            messages.success(request, 'Message sent.')
            return redirect(self._get_thread_url())
        thread_messages = self._get_messages()
        context = {
            'item': self.item,
            'seller': self.item.seller,
            'thread_messages': thread_messages,
            'thread_recipient': self.thread_recipient,
            'item_threads': build_message_threads(request.user, item_id=self.item.pk),
            'form': form,
        }
        return render(request, 'marketplace/message_thread.html', context)

    def _get_messages(self):
        queryset = Message.objects.filter(item=self.item).filter(
            Q(sender=self.request.user) | Q(recipient=self.request.user)
        )
        if self.thread_recipient:
            queryset = queryset.filter(
                Q(sender=self.request.user, recipient=self.thread_recipient)
                | Q(sender=self.thread_recipient, recipient=self.request.user)
            )
        return queryset.select_related('sender', 'recipient')

    def _get_thread_recipient(self):
        if self.request.user != self.item.seller:
            return self.item.seller

        recipient_id = self.request.GET.get('recipient') or self.request.POST.get('recipient')
        if recipient_id:
            conversation = self.item.messages.filter(
                Q(sender_id=recipient_id, recipient=self.request.user)
                | Q(sender=self.request.user, recipient_id=recipient_id)
            ).select_related('sender', 'recipient').first()
            if conversation:
                return conversation.sender if conversation.sender_id != self.request.user.id else conversation.recipient

        latest_message = self.item.messages.filter(
            Q(sender=self.request.user) | Q(recipient=self.request.user)
        ).order_by('-created_at').select_related('sender', 'recipient').first()
        if latest_message:
            return (
                latest_message.recipient
                if latest_message.sender_id == self.request.user.id
                else latest_message.sender
            )
        return None

    def _get_recipient(self):
        return self.thread_recipient

    def _get_thread_url(self):
        url = reverse('marketplace:item_messages', kwargs={'pk': self.item.pk})
        if self.request.user == self.item.seller and self.thread_recipient:
            return f'{url}?recipient={self.thread_recipient.pk}'
        return url


class MessagesInboxView(LoginRequiredMixin, TemplateView):
    template_name = 'marketplace/messages_inbox.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        selected_item = self.request.GET.get('item')
        item_obj = None
        item_id = None
        if selected_item and selected_item.isdigit():
            item_obj = Item.objects.filter(pk=selected_item).first()
            item_id = item_obj.pk if item_obj else None

        threads = build_message_threads(self.request.user, item_id=item_id)
        context['threads'] = threads
        context['selected_item'] = item_obj
        context['unread_threads_count'] = sum(1 for thread in threads if thread['unread_count'] > 0)
        return context


class MarkSoldView(SellerOwnsItemMixin, View):
    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        self.item = get_object_or_404(Item, pk=kwargs['pk'])

    def get_object(self):
        return self.item

    def post(self, request, *args, **kwargs):
        if self.item.status == Item.STATUS_SOLD:
            messages.info(request, 'This listing is already marked as sold.')
            return redirect('marketplace:item_detail', pk=self.item.pk)
        self.item.status = Item.STATUS_SOLD
        self.item.save(update_fields=['status'])
        messages.success(request, 'Listing marked as sold.')
        return redirect('marketplace:item_detail', pk=self.item.pk)


class FavoriteToggleView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        item = get_object_or_404(Item, pk=kwargs['pk'])
        if item.status == Item.STATUS_DRAFT and item.seller != request.user:
            messages.error(request, 'This listing is not available.')
            return redirect('marketplace:browse')
        favorite, created = Favorite.objects.get_or_create(user=request.user, item=item)
        if not created:
            favorite.delete()
            messages.info(request, 'Removed from favorites.')
        else:
            messages.success(request, 'Added to favorites.')
        return redirect('marketplace:item_detail', pk=item.pk)


class FavoritesListView(LoginRequiredMixin, ListView):
    template_name = 'marketplace/favorites.html'
    context_object_name = 'items'

    def get_queryset(self):
        return Item.objects.filter(
            favorited_by__user=self.request.user,
            status__in=[Item.STATUS_PUBLISHED, Item.STATUS_SOLD],
        ).select_related('category', 'seller').prefetch_related('images')


class ReportItemView(LoginRequiredMixin, FormView):
    template_name = 'marketplace/report_item.html'
    form_class = ReportForm

    def dispatch(self, request, *args, **kwargs):
        self.item = get_object_or_404(Item, pk=kwargs['pk'])
        if self.item.seller == request.user:
            messages.error(request, 'You cannot report your own listing.')
            return redirect('marketplace:item_detail', pk=self.item.pk)
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        report, created = Report.objects.get_or_create(
            item=self.item,
            reporter=self.request.user,
            defaults={
                'reason': form.cleaned_data['reason'],
                'comment': form.cleaned_data['comment'],
            },
        )
        if not created:
            messages.error(self.request, 'You already reported this item.')
            return redirect('marketplace:item_detail', pk=self.item.pk)
        messages.success(self.request, 'Report submitted. Thank you.')
        return redirect('marketplace:item_detail', pk=self.item.pk)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['item'] = self.item
        return context


class DeleteItemImageView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        image = get_object_or_404(ItemImage, pk=kwargs['pk'])
        if image.item.seller != request.user:
            return JsonResponse({'error': 'Forbidden'}, status=403)
        image.image.delete(save=False)
        image.delete()
        return JsonResponse({'success': True})


class AdminDashboardView(StaffRequiredMixin, AdminPanelContextMixin, TemplateView):
    template_name = 'marketplace/admin/dashboard.html'
    admin_section = 'overview'
    admin_page_title = 'Admin Dashboard'
    admin_page_intro = 'Monitor activity, moderation, and marketplace health from one place.'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        open_statuses = [Report.STATUS_OPEN, Report.STATUS_IN_REVIEW]
        since = timezone.now() - timedelta(days=7)

        context['stats'] = {
            'total_users': User.objects.count(),
            'staff_users': User.objects.filter(is_staff=True).count(),
            'active_users': User.objects.filter(is_active=True).count(),
            'total_categories': Category.objects.count(),
            'total_items': Item.objects.count(),
            'published_items': Item.objects.filter(status=Item.STATUS_PUBLISHED).count(),
            'draft_items': Item.objects.filter(status=Item.STATUS_DRAFT).count(),
            'sold_items': Item.objects.filter(status=Item.STATUS_SOLD).count(),
            'open_reports': Report.objects.filter(status__in=open_statuses).count(),
            'resolved_reports': Report.objects.filter(status=Report.STATUS_RESOLVED).count(),
            'total_messages': Message.objects.count(),
            'unread_messages': Message.objects.filter(is_read=False).count(),
            'new_users_last_7_days': User.objects.filter(date_joined__gte=since).count(),
            'new_items_last_7_days': Item.objects.filter(created_at__gte=since).count(),
        }
        context['recent_reports'] = (
            Report.objects.select_related('item', 'reporter', 'reviewed_by')
            .filter(status__in=open_statuses)
            .order_by('-created_at')[:6]
        )
        context['flagged_items'] = (
            Item.objects.select_related('seller', 'category')
            .prefetch_related('images')
            .annotate(
                open_reports_count=Count(
                    'reports',
                    filter=Q(reports__status__in=open_statuses),
                    distinct=True,
                )
            )
            .filter(open_reports_count__gt=0)
            .order_by('-open_reports_count', '-created_at')[:6]
        )
        context['recent_items'] = (
            Item.objects.select_related('seller', 'category')
            .prefetch_related('images')
            .order_by('-created_at')[:6]
        )
        context['newest_users'] = User.objects.order_by('-date_joined')[:6]
        context['recent_messages'] = (
            Message.objects.select_related('item', 'sender', 'recipient')
            .order_by('-created_at')[:8]
        )
        context['report_reason_breakdown'] = Report.objects.values('reason').annotate(
            total=Count('id')
        ).order_by('-total')
        return context


class AdminItemListView(StaffRequiredMixin, AdminPanelContextMixin, ListView):
    template_name = 'marketplace/admin/items.html'
    context_object_name = 'items'
    paginate_by = 12
    admin_section = 'items'
    admin_page_title = 'Listings Moderation'
    admin_page_intro = 'Review, filter, and moderate marketplace listings.'

    def get_filter_form(self):
        return AdminItemFilterForm(self.request.GET or None, categories=Category.objects.all())

    def get_queryset(self):
        open_statuses = [Report.STATUS_OPEN, Report.STATUS_IN_REVIEW]
        queryset = (
            Item.objects.select_related('seller', 'category')
            .prefetch_related('images')
            .annotate(
                reports_count=Count('reports', distinct=True),
                open_reports_count=Count(
                    'reports',
                    filter=Q(reports__status__in=open_statuses),
                    distinct=True,
                ),
                favorites_count=Count('favorited_by', distinct=True),
            )
            .order_by('-created_at')
        )
        form = self.get_filter_form()
        if form.is_valid():
            q = form.cleaned_data.get('q')
            status = form.cleaned_data.get('status')
            category = form.cleaned_data.get('category')
            reported = form.cleaned_data.get('reported')
            if q:
                queryset = queryset.filter(
                    Q(title__icontains=q)
                    | Q(description__icontains=q)
                    | Q(seller__username__icontains=q)
                )
            if status:
                queryset = queryset.filter(status=status)
            if category:
                queryset = queryset.filter(category=category)
            if reported == 'reported':
                queryset = queryset.filter(open_reports_count__gt=0)
            elif reported == 'clean':
                queryset = queryset.filter(open_reports_count=0)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        params = self.request.GET.copy()
        params.pop('page', None)
        context['filter_form'] = self.get_filter_form()
        context['filter_params'] = params.urlencode()
        return context


class AdminItemActionView(StaffRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        item = get_object_or_404(Item, pk=kwargs['pk'])
        action = request.POST.get('action')
        if action == 'publish':
            item.status = Item.STATUS_PUBLISHED
            item.save(update_fields=['status'])
            messages.success(request, f'"{item.title}" is now published.')
        elif action == 'draft':
            item.status = Item.STATUS_DRAFT
            item.save(update_fields=['status'])
            messages.success(request, f'"{item.title}" was moved to drafts.')
        elif action == 'sold':
            item.status = Item.STATUS_SOLD
            item.save(update_fields=['status'])
            messages.success(request, f'"{item.title}" was marked as sold.')
        elif action == 'delete':
            title = item.title
            item.delete()
            messages.success(request, f'"{title}" was deleted.')
        else:
            messages.error(request, 'Unknown listing action.')
        return redirect(request.POST.get('next') or reverse('marketplace:admin_items'))


class AdminReportListView(StaffRequiredMixin, AdminPanelContextMixin, ListView):
    template_name = 'marketplace/admin/reports.html'
    context_object_name = 'reports'
    paginate_by = 12
    admin_section = 'reports'
    admin_page_title = 'Reports Queue'
    admin_page_intro = 'Process user-submitted reports and moderate flagged listings.'

    def get_filter_form(self):
        return AdminReportFilterForm(self.request.GET or None)

    def get_queryset(self):
        queryset = (
            Report.objects.select_related('item', 'item__seller', 'reporter', 'reviewed_by')
            .order_by('-created_at')
        )
        form = self.get_filter_form()
        if form.is_valid():
            q = form.cleaned_data.get('q')
            status = form.cleaned_data.get('status')
            reason = form.cleaned_data.get('reason')
            if q:
                queryset = queryset.filter(
                    Q(item__title__icontains=q)
                    | Q(reporter__username__icontains=q)
                    | Q(comment__icontains=q)
                )
            if status:
                queryset = queryset.filter(status=status)
            if reason:
                queryset = queryset.filter(reason=reason)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        params = self.request.GET.copy()
        params.pop('page', None)
        context['filter_form'] = self.get_filter_form()
        context['filter_params'] = params.urlencode()
        return context


class AdminReportActionView(StaffRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        report = get_object_or_404(Report.objects.select_related('item'), pk=kwargs['pk'])
        action = request.POST.get('action')
        now = timezone.now()

        if action == 'review':
            report.status = Report.STATUS_IN_REVIEW
            message = 'Report moved to in review.'
        elif action == 'dismiss':
            report.status = Report.STATUS_DISMISSED
            message = 'Report dismissed.'
        elif action == 'resolve':
            report.status = Report.STATUS_RESOLVED
            message = 'Report resolved.'
        elif action == 'unpublish_item':
            report.item.status = Item.STATUS_DRAFT
            report.item.save(update_fields=['status'])
            report.status = Report.STATUS_RESOLVED
            message = 'Listing was moved to drafts and the report was resolved.'
        else:
            messages.error(request, 'Unknown report action.')
            return redirect(request.POST.get('next') or reverse('marketplace:admin_reports'))

        report.reviewed_by = request.user
        report.reviewed_at = now
        report.save(update_fields=['status', 'reviewed_by', 'reviewed_at'])
        messages.success(request, message)
        return redirect(request.POST.get('next') or reverse('marketplace:admin_reports'))


class AdminUserListView(StaffRequiredMixin, AdminPanelContextMixin, ListView):
    template_name = 'marketplace/admin/users.html'
    context_object_name = 'users'
    paginate_by = 15
    admin_section = 'users'
    admin_page_title = 'User Management'
    admin_page_intro = 'Audit members, staff access, and account status.'

    def get_filter_form(self):
        return AdminUserFilterForm(self.request.GET or None)

    def get_queryset(self):
        queryset = User.objects.annotate(
            items_count=Count('items', distinct=True),
            reports_count=Count('reports', distinct=True),
            favorites_count=Count('favorites', distinct=True),
        ).order_by('-date_joined')
        form = self.get_filter_form()
        if form.is_valid():
            q = form.cleaned_data.get('q')
            role = form.cleaned_data.get('role')
            if q:
                queryset = queryset.filter(
                    Q(username__icontains=q)
                    | Q(first_name__icontains=q)
                    | Q(last_name__icontains=q)
                    | Q(email__icontains=q)
                )
            if role == 'staff':
                queryset = queryset.filter(is_staff=True)
            elif role == 'member':
                queryset = queryset.filter(is_staff=False, is_active=True)
            elif role == 'inactive':
                queryset = queryset.filter(is_active=False)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        params = self.request.GET.copy()
        params.pop('page', None)
        context['filter_form'] = self.get_filter_form()
        context['filter_params'] = params.urlencode()
        return context


class AdminUserActionView(StaffRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        target = get_object_or_404(User, pk=kwargs['pk'])
        action = request.POST.get('action')

        if action == 'activate':
            target.is_active = True
            target.save(update_fields=['is_active'])
            messages.success(request, f'{target.username} was activated.')
        elif action == 'deactivate':
            if target == request.user:
                messages.error(request, 'You cannot deactivate your own account.')
            else:
                target.is_active = False
                target.save(update_fields=['is_active'])
                messages.success(request, f'{target.username} was deactivated.')
        elif action == 'grant_staff':
            target.is_staff = True
            target.save(update_fields=['is_staff'])
            messages.success(request, f'{target.username} now has staff access.')
        elif action == 'revoke_staff':
            if target == request.user:
                messages.error(request, 'You cannot remove your own staff access.')
            else:
                target.is_staff = False
                target.save(update_fields=['is_staff'])
                messages.success(request, f'{target.username} no longer has staff access.')
        else:
            messages.error(request, 'Unknown user action.')
        return redirect(request.POST.get('next') or reverse('marketplace:admin_users'))


class AdminCategoryListView(StaffRequiredMixin, AdminPanelContextMixin, ListView):
    template_name = 'marketplace/admin/categories.html'
    context_object_name = 'categories'
    admin_section = 'categories'
    admin_page_title = 'Category Management'
    admin_page_intro = 'Create and maintain the marketplace taxonomy.'

    def get_queryset(self):
        return Category.objects.annotate(item_count=Count('items')).order_by('name')


class AdminCategoryCreateView(StaffRequiredMixin, AdminPanelContextMixin, CreateView):
    template_name = 'marketplace/admin/category_form.html'
    form_class = CategoryAdminForm
    success_url = reverse_lazy('marketplace:admin_categories')
    admin_section = 'categories'
    admin_page_title = 'Create Category'
    admin_page_intro = 'Add a new category for listings.'

    def form_valid(self, form):
        messages.success(self.request, 'Category created.')
        return super().form_valid(form)


class AdminCategoryUpdateView(StaffRequiredMixin, AdminPanelContextMixin, UpdateView):
    model = Category
    template_name = 'marketplace/admin/category_form.html'
    form_class = CategoryAdminForm
    success_url = reverse_lazy('marketplace:admin_categories')
    admin_section = 'categories'
    admin_page_title = 'Edit Category'
    admin_page_intro = 'Update category names and slugs.'

    def form_valid(self, form):
        messages.success(self.request, 'Category updated.')
        return super().form_valid(form)


class AdminCategoryDeleteView(StaffRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        category = get_object_or_404(Category, pk=kwargs['pk'])
        try:
            category.delete()
            messages.success(request, 'Category deleted.')
        except ProtectedError:
            messages.error(request, 'Category cannot be deleted while listings still use it.')
        return redirect(request.POST.get('next') or reverse('marketplace:admin_categories'))


class AdminMessageListView(StaffRequiredMixin, AdminPanelContextMixin, ListView):
    template_name = 'marketplace/admin/messages.html'
    context_object_name = 'messages_list'
    paginate_by = 20
    admin_section = 'messages'
    admin_page_title = 'Message Oversight'
    admin_page_intro = 'Review marketplace conversations and unread activity.'

    def get_filter_form(self):
        return AdminMessageFilterForm(self.request.GET or None)

    def get_queryset(self):
        queryset = Message.objects.select_related('item', 'sender', 'recipient').order_by('-created_at')
        form = self.get_filter_form()
        if form.is_valid():
            q = form.cleaned_data.get('q')
            read_state = form.cleaned_data.get('read_state')
            if q:
                queryset = queryset.filter(
                    Q(body__icontains=q)
                    | Q(item__title__icontains=q)
                    | Q(sender__username__icontains=q)
                    | Q(recipient__username__icontains=q)
                )
            if read_state == 'unread':
                queryset = queryset.filter(is_read=False)
            elif read_state == 'read':
                queryset = queryset.filter(is_read=True)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        params = self.request.GET.copy()
        params.pop('page', None)
        context['filter_form'] = self.get_filter_form()
        context['filter_params'] = params.urlencode()
        return context


class AdminMessageActionView(StaffRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        message_obj = get_object_or_404(Message, pk=kwargs['pk'])
        action = request.POST.get('action')
        if action == 'mark_read':
            message_obj.is_read = True
            message_obj.save(update_fields=['is_read'])
            messages.success(request, 'Message marked as read.')
        elif action == 'mark_unread':
            message_obj.is_read = False
            message_obj.save(update_fields=['is_read'])
            messages.success(request, 'Message marked as unread.')
        else:
            messages.error(request, 'Unknown message action.')
        return redirect(request.POST.get('next') or reverse('marketplace:admin_messages'))
