from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import DetailView, FormView, ListView, TemplateView
from django.views.generic.edit import CreateView, DeleteView, UpdateView

from .forms import ItemFilterForm, ItemForm, MessageForm, ReportForm, UserRegistrationForm
from .models import Category, Favorite, Item, ItemImage, Message, Report


class RegisterView(FormView):
    template_name = 'registration/register.html'
    form_class = UserRegistrationForm
    success_url = reverse_lazy('marketplace:browse')

    def form_valid(self, form):
        user = form.save()
        login(self.request, user)
        messages.success(self.request, 'Welcome to UniTrade!')
        return super().form_valid(form)


class LandingView(TemplateView):
    template_name = 'landing.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['category_tiles'] = [
            'Books',
            'Electronics',
            'Furniture',
            'Kitchen',
            'Clothing',
            'Sports',
            'Appliances',
            'Other',
        ]
        context['placeholder_listings'] = range(6)
        context['landing_listings'] = (
            Item.objects.filter(status__in=[Item.STATUS_PUBLISHED, Item.STATUS_SOLD])
            .select_related('category', 'seller')
            .prefetch_related('images')[:6]
        )
        return context


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
        context['featured_items'] = Item.objects.order_by('-created_at')[:4]
        return context


class ItemDetailView(DetailView):
    model = Item
    template_name = 'marketplace/item_detail.html'
    context_object_name = 'item'

    def get(self, request, *args, **kwargs):
        response = super().get(request, *args, **kwargs)
        item = self.get_object()
        if item.status == Item.STATUS_DRAFT and item.seller != request.user:
            messages.error(request, 'This listing is not available.')
            return redirect('marketplace:browse')
        viewed = request.session.get('recently_viewed_items', [])
        if item.id in viewed:
            viewed.remove(item.id)
        viewed.insert(0, item.id)
        request.session['recently_viewed_items'] = viewed[:8]
        response.set_cookie('last_viewed_item', str(item.id), max_age=60 * 60 * 24 * 30)
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.user.is_authenticated:
            context['is_favorited'] = Favorite.objects.filter(
                user=self.request.user, item=self.object
            ).exists()
        else:
            context['is_favorited'] = False
        return context


class ItemCreateView(LoginRequiredMixin, CreateView):
    model = Item
    form_class = ItemForm
    template_name = 'marketplace/item_post.html'

    def form_valid(self, form):
        form.instance.seller = self.request.user
        response = super().form_valid(form)
        self._save_images()
        messages.success(self.request, 'Item listed successfully.')
        return response

    def _save_images(self):
        for image in self.request.FILES.getlist('images'):
            ItemImage.objects.create(item=self.object, image=image)

    def get_success_url(self):
        return reverse('marketplace:item_detail', kwargs={'pk': self.object.pk})


class ItemUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Item
    form_class = ItemForm
    template_name = 'marketplace/item_edit.html'

    def test_func(self):
        return self.get_object().seller == self.request.user

    def form_valid(self, form):
        response = super().form_valid(form)
        self._save_images()
        messages.success(self.request, 'Item updated successfully.')
        return response

    def _save_images(self):
        for image in self.request.FILES.getlist('images'):
            ItemImage.objects.create(item=self.object, image=image)

    def get_success_url(self):
        return reverse('marketplace:item_detail', kwargs={'pk': self.object.pk})


class ItemDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Item
    template_name = 'marketplace/item_confirm_delete.html'
    success_url = reverse_lazy('marketplace:dashboard')

    def test_func(self):
        return self.get_object().seller == self.request.user

    def delete(self, request, *args, **kwargs):
        messages.success(self.request, 'Item deleted.')
        return super().delete(request, *args, **kwargs)


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
        viewed_ids = self.request.session.get('recently_viewed_items', [])
        context['recently_viewed'] = Item.objects.filter(id__in=viewed_ids)
        return context


class ItemMessageView(LoginRequiredMixin, ListView, FormView):
    template_name = 'marketplace/message_thread.html'
    context_object_name = 'messages'
    form_class = MessageForm

    def dispatch(self, request, *args, **kwargs):
        self.item = get_object_or_404(Item, pk=kwargs['pk'])
        if self.item.status == Item.STATUS_DRAFT and self.item.seller != request.user:
            messages.error(request, 'This listing is not available.')
            return redirect('marketplace:browse')
        if self.item.status == Item.STATUS_SOLD and self.item.seller != request.user:
            messages.error(request, 'This item is sold and cannot be messaged.')
            return redirect('marketplace:item_detail', pk=self.item.pk)
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return Message.objects.filter(item=self.item).filter(
            Q(sender=self.request.user) | Q(recipient=self.request.user)
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['item'] = self.item
        context['seller'] = self.item.seller
        return context

    def form_valid(self, form):
        recipient = self._get_recipient()
        if recipient is None:
            messages.error(self.request, 'Select a buyer to reply to.')
            return redirect('marketplace:item_messages', pk=self.item.pk)
        Message.objects.create(
            item=self.item,
            sender=self.request.user,
            recipient=recipient,
            body=form.cleaned_data['body'],
        )
        messages.success(self.request, 'Message sent.')
        return redirect('marketplace:item_messages', pk=self.item.pk)

    def _get_recipient(self):
        if self.request.user != self.item.seller:
            return self.item.seller
        recipient_id = self.request.GET.get('recipient')
        if recipient_id:
            message = self.item.messages.filter(sender_id=recipient_id).first()
            return message.sender if message else None
        latest_message = self.item.messages.exclude(sender=self.request.user).last()
        return latest_message.sender if latest_message else None


class MarkSoldView(LoginRequiredMixin, UserPassesTestMixin, View):
    def test_func(self):
        item = get_object_or_404(Item, pk=self.kwargs['pk'])
        return item.seller == self.request.user

    def post(self, request, *args, **kwargs):
        item = get_object_or_404(Item, pk=kwargs['pk'])
        item.status = Item.STATUS_SOLD
        item.save(update_fields=['status'])
        messages.success(request, 'Listing marked as sold.')
        return redirect('marketplace:item_detail', pk=item.pk)


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
