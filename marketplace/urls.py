from django.urls import path

from . import views


app_name = 'marketplace'

urlpatterns = [
    path('', views.LandingView.as_view(), name='landing'),
    path('browse/', views.BrowseListView.as_view(), name='browse'),
    path('favorites/', views.FavoritesListView.as_view(), name='favorites'),
    path('register/', views.RegisterView.as_view(), name='register'),
    path('dashboard/', views.DashboardView.as_view(), name='dashboard'),
    path('items/post/', views.ItemCreateView.as_view(), name='item_post'),
    path('items/new/', views.ItemCreateView.as_view(), name='item_create'),
    path('items/<int:pk>/', views.ItemDetailView.as_view(), name='item_detail'),
    path('items/<int:pk>/edit/', views.ItemUpdateView.as_view(), name='item_update'),
    path('items/<int:pk>/delete/', views.ItemDeleteView.as_view(), name='item_delete'),
    path('items/<int:pk>/mark-sold/', views.MarkSoldView.as_view(), name='item_mark_sold'),
    path('items/<int:pk>/favorite/', views.FavoriteToggleView.as_view(), name='item_favorite'),
    path('items/<int:pk>/report/', views.ReportItemView.as_view(), name='item_report'),
    path('items/<int:pk>/messages/', views.ItemMessageView.as_view(), name='item_messages'),
]
