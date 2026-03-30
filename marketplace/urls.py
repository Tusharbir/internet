from django.urls import path

from . import views


app_name = 'marketplace'

urlpatterns = [
    path('', views.LandingView.as_view(), name='landing'),                                      # landing page url
    path('browse/', views.BrowseListView.as_view(), name='browse'),                             # marketplace browsing url
    path('favorites/', views.FavoritesListView.as_view(), name='favorites'),                    # user favorites url
    path('messages/', views.MessagesInboxView.as_view(), name='messages_inbox'),                # user messages inbox url
    path('register/', views.RegisterView.as_view(), name='register'),                           # user registration url
    path('dashboard/', views.DashboardView.as_view(), name='dashboard'),                        # user dashboard url
    path('admin-panel/', views.AdminDashboardView.as_view(), name='admin_dashboard'),           # admin panel url
    path('admin-panel/items/', views.AdminItemListView.as_view(), name='admin_items'),          # admin item management url
    path('admin-panel/items/<int:pk>/action/', views.AdminItemActionView.as_view(), name='admin_item_action'),  # admin item action url
    path('admin-panel/reports/', views.AdminReportListView.as_view(), name='admin_reports'),    # admin report management url   
    path('admin-panel/reports/<int:pk>/action/', views.AdminReportActionView.as_view(), name='admin_report_action'),        # admin report action url
    path('admin-panel/users/', views.AdminUserListView.as_view(), name='admin_users'),      # admin user management url
    path('admin-panel/users/<int:pk>/action/', views.AdminUserActionView.as_view(), name='admin_user_action'),  # admin user action url
    path('admin-panel/categories/', views.AdminCategoryListView.as_view(), name='admin_categories'),
    path('admin-panel/categories/new/', views.AdminCategoryCreateView.as_view(), name='admin_category_create'),
    path('admin-panel/categories/<int:pk>/edit/', views.AdminCategoryUpdateView.as_view(), name='admin_category_update'),
    path('admin-panel/categories/<int:pk>/delete/', views.AdminCategoryDeleteView.as_view(), name='admin_category_delete'),
    path('admin-panel/messages/', views.AdminMessageListView.as_view(), name='admin_messages'),
    path('admin-panel/messages/<int:pk>/action/', views.AdminMessageActionView.as_view(), name='admin_message_action'),
    path('items/post/', views.ItemCreateView.as_view(), name='item_post'),
    path('items/<int:pk>/', views.ItemDetailView.as_view(), name='item_detail'),
    path('items/<int:pk>/edit/', views.ItemUpdateView.as_view(), name='item_update'),
    path('items/<int:pk>/delete/', views.ItemDeleteView.as_view(), name='item_delete'),
    path('items/<int:pk>/mark-sold/', views.MarkSoldView.as_view(), name='item_mark_sold'),
    path('items/<int:pk>/favorite/', views.FavoriteToggleView.as_view(), name='item_favorite'),
    path('items/<int:pk>/report/', views.ReportItemView.as_view(), name='item_report'),
    path('items/<int:pk>/messages/', views.ItemMessageView.as_view(), name='item_messages'),
    path('images/<int:pk>/delete/', views.DeleteItemImageView.as_view(), name='image_delete'), 
]
